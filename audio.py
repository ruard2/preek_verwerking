"""Audio van het preekgedeelte downloaden en via OpenAI transcriberen.

Werkwijze:
1. De volledige audiostream downloaden (yt-dlp, met dezelfde provider-/proxy-/
   cookie-opties als de rest). De audiostream is PO-token-beveiligd, dus dit
   werkt alleen als de PO-token-provider bereikbaar is.
2. Per preekdeel het juiste tijdvak uitknippen met ffmpeg en comprimeren naar
   16 kHz mono mp3 (klein genoeg voor de OpenAI-transcriptie, ruim onder 25 MB).
3. Elk deel transcriberen met een OpenAI-transcriptiemodel en de tekst
   samenvoegen met de preekdeel-markering.
"""

import glob
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time

import imageio_ffmpeg
import yt_dlp
from openai import OpenAI

import transcript as ts

TRANSCRIBE_MODEL = os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
# Veiligheidsmarge onder de 25 MB-limiet van de OpenAI-transcriptie-API.
MAX_DEEL_SECONDEN = 20 * 60
DEEL_MARKERING = "\n\n[VOLGEND PREEKDEEL — hiervoor werd gezongen]\n\n"

# ---- Audio-cache ----------------------------------------------------------
# Gedownloade audiobestanden bewaren zodat dezelfde preek niet herhaaldelijk
# via de (dure) residentiële proxy gedownload hoeft te worden.
# Standaard onder DATA_DIR/audio_cache; stel AUDIO_CACHE_DIR in om te overschrijven.
_DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
AUDIO_CACHE_DIR = os.environ.get("AUDIO_CACHE_DIR", os.path.join(_DATA_DIR, "audio_cache"))
AUDIO_CACHE_TTL = int(os.environ.get("AUDIO_CACHE_TTL", str(7 * 24 * 3600)))  # 7 dagen


def _video_sleutel(url):
    """Stabiele cache-sleutel voor een video-URL (YouTube-ID of MD5-hash)."""
    m = re.search(r"(?:v=|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})", url)
    return m.group(1) if m else hashlib.md5(url.encode()).hexdigest()[:16]


def _cache_ophalen(sleutel):
    """Geef het gecachede audiopad als het bestaat en nog vers is, anders None."""
    if not os.path.isdir(AUDIO_CACHE_DIR):
        return None
    grens = time.time() - AUDIO_CACHE_TTL
    for naam in os.listdir(AUDIO_CACHE_DIR):
        if naam.startswith(sleutel + "."):
            pad = os.path.join(AUDIO_CACHE_DIR, naam)
            try:
                if os.path.isfile(pad) and os.path.getmtime(pad) >= grens:
                    return pad
            except OSError:
                pass
    return None


def _cache_opslaan(sleutel, bron):
    """Kopieer het audiobestand naar de cache; geeft het cachedpad terug."""
    os.makedirs(AUDIO_CACHE_DIR, exist_ok=True)
    ext = os.path.splitext(bron)[1] or ".m4a"
    doel = os.path.join(AUDIO_CACHE_DIR, sleutel + ext)
    shutil.copy2(bron, doel)
    return doel


def _cache_opruimen():
    """Verwijder gecachede audiobestanden ouder dan AUDIO_CACHE_TTL seconden."""
    if not os.path.isdir(AUDIO_CACHE_DIR):
        return
    grens = time.time() - AUDIO_CACHE_TTL
    for naam in os.listdir(AUDIO_CACHE_DIR):
        pad = os.path.join(AUDIO_CACHE_DIR, naam)
        try:
            if os.path.isfile(pad) and os.path.getmtime(pad) < grens:
                os.remove(pad)
        except OSError:
            pass


def _ffmpeg():
    """Pad naar een ffmpeg-binary die 'ffmpeg(.exe)' heet (yt-dlp/ffmpeg-vriendelijk).

    Voorkeur: een echte, door het systeem geïnstalleerde ffmpeg (op Railway via
    nixpacks.toml). De gebundelde imageio-ffmpeg-binary crasht op Railway bij het
    lezen van HLS-streams (SIGSEGV), dus die gebruiken we alleen als terugval
    (typisch lokaal op Windows).
    """
    systeem = shutil.which("ffmpeg")
    if systeem:
        return systeem
    src = imageio_ffmpeg.get_ffmpeg_exe()
    naam = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    doelmap = os.path.join(tempfile.gettempdir(), "preek_ffmpeg")
    os.makedirs(doelmap, exist_ok=True)
    doel = os.path.join(doelmap, naam)
    if not os.path.exists(doel):
        shutil.copy(src, doel)
    return doel


def ffmpeg_diagnose():
    """Korte beschrijving van de ffmpeg die gebruikt wordt (voor /api/diagnose)."""
    systeem = shutil.which("ffmpeg")
    try:
        pad = _ffmpeg()
        uit = subprocess.run([pad, "-version"], capture_output=True, text=True)
        regels = (uit.stdout or uit.stderr or "").splitlines()
        versie = regels[0] if regels else "?"
        soort = "systeem" if systeem else "gebundeld (imageio-ffmpeg)"
        return f"{soort}: {pad} — {versie}"
    except Exception as fout:  # noqa: BLE001
        return f"ffmpeg niet bruikbaar: {fout}"


def _download_audio(url, map_):
    opties = ts.basis_opties()
    opties.update(
        {
            "skip_download": False,
            # Alleen audio, zo klein mogelijk — ffmpeg converteert toch naar 16kHz
            # mono 32kbps, dus hogere kwaliteit is pure verspilling van proxy-bandbreedte.
            # Voorkeur: ≤64 kbps audio-only (itag 139 = 48k m4a, itag 249/250 = 50-70k opus).
            # Valt terug op m4a (~128k), dan elke audio-only stream, dan best als laatste redmiddel.
            "format": "bestaudio[abr<=64]/bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(map_, "audio.%(ext)s"),
            # Residentiële proxy's zijn traag en haperen: ruime timeout + veel
            # herpogingen, zodat een korte stilval de download niet laat mislukken.
            "socket_timeout": int(os.environ.get("YTDLP_SOCKET_TIMEOUT", "120")),
            "retries": int(os.environ.get("YTDLP_RETRIES", "20")),
            "fragment_retries": int(os.environ.get("YTDLP_RETRIES", "20")),
            "file_access_retries": 10,
            "continuedl": True,
            # ffmpeg-locatie: zorgt dat yt-dlp de juiste ffmpeg-binary vindt voor
            # audio-conversie na de download (niet als externe downloader).
            "ffmpeg_location": os.path.dirname(_ffmpeg()),
        }
    )
    with yt_dlp.YoutubeDL(opties) as ydl:
        ydl.download([url])
    bestanden = [f for f in glob.glob(os.path.join(map_, "audio.*"))]
    if not bestanden:
        raise RuntimeError("De audio kon niet worden gedownload.")
    return bestanden[0]


def _download_audio_gecached(url, map_):
    """Download audio met cache: als hetzelfde bestand binnen 7 dagen al gedownload
    is, kopieer het uit de cache in plaats van opnieuw te downloaden via de proxy.
    """
    sleutel = _video_sleutel(url)
    gecached = _cache_ophalen(sleutel)
    if gecached:
        ext = os.path.splitext(gecached)[1]
        doel = os.path.join(map_, "audio" + ext)
        shutil.copy2(gecached, doel)
        return doel
    # Niet in cache: downloaden en daarna opslaan.
    bron = _download_audio(url, map_)
    try:
        _cache_opruimen()  # verwijder verlopen bestanden opportunistisch
        _cache_opslaan(sleutel, bron)
    except Exception:  # noqa: BLE001
        pass  # cache-fout blokkeert de verwerking niet
    return bron


def _knip(ffmpeg, bron, start, eind, doel):
    subprocess.run(
        [
            ffmpeg, "-y", "-ss", str(start), "-to", str(eind), "-i", bron,
            "-ac", "1", "-ar", "16000", "-b:a", "32k", doel,
        ],
        capture_output=True,
        check=True,
    )


def _filter_muziek(antwoord):
    """Filter muziek/zang uit verbose_json segmenten; geeft gefilterde tekst terug.

    Gebruikt no_speech_prob en avg_logprob als score-filter (whisper-1 en
    sommige nieuwere modellen). Zonder scores: tekstgebaseerde filter op
    muziekannotaties (♪, [muziek], [zingt] e.d.). Terugval op antwoord.text
    als filtering niets oplevert.
    """
    segmenten = getattr(antwoord, "segments", None) or []
    if not segmenten:
        return (getattr(antwoord, "text", "") or "").strip()
    tekst_delen = []
    for s in segmenten:
        if isinstance(s, dict):
            tekst = s.get("text", "") or ""
            no_speech = s.get("no_speech_prob")
            avg_logprob = s.get("avg_logprob")
        else:
            tekst = getattr(s, "text", "") or ""
            no_speech = getattr(s, "no_speech_prob", None)
            avg_logprob = getattr(s, "avg_logprob", None)
        # Score-gebaseerde filter (whisper-1 / modellen die deze scores teruggeven)
        if no_speech is not None and no_speech > 0.5:
            continue  # waarschijnlijk geen spraak
        if avg_logprob is not None and avg_logprob < -1.2:
            continue  # Whisper erg onzeker → waarschijnlijk zang/muziek
        # Tekstgebaseerde filter: typische muziekmarkeringen
        if re.search(r"[♪♫]|\[muziek\]|\[music\]|\[zingen?\]|\[sing", tekst, re.I):
            continue
        tekst_delen.append(tekst)
    resultaat = " ".join(tekst_delen).strip()
    # Terugval: als filtering alles weggooit geef dan de originele tekst terug
    return resultaat or (getattr(antwoord, "text", "") or "").strip()


def _transcribeer_bestand(client, pad, taal=None):
    """Transcribeer één audiobestand.

    Vraagt verbose_json aan voor segmentinfo zodat muziek/zang gefilterd kan
    worden op basis van confidence-scores (no_speech_prob, avg_logprob). Als
    verbose_json niet ondersteund wordt, valt het terug op gewone transcriptie.
    Zonder taal auto-detectie, zodat ook Afrikaanse/Engelse preken werken.
    """
    basisargs = {"model": TRANSCRIBE_MODEL}
    if taal and len(taal) == 2:
        basisargs["language"] = taal
    try:
        with open(pad, "rb") as f:
            antwoord = client.audio.transcriptions.create(
                file=f, **basisargs, response_format="verbose_json"
            )
        return _filter_muziek(antwoord)
    except Exception:  # noqa: BLE001 — verbose_json niet ondersteund of andere fout
        with open(pad, "rb") as f:
            antwoord = client.audio.transcriptions.create(file=f, **basisargs)
        return antwoord.text.strip()


def _knip_stream(ffmpeg, url, start, lengte, doel):
    """Haal met ffmpeg alleen [start, start+lengte] audio uit een stream (HLS/mp4)."""
    subprocess.run(
        [
            ffmpeg, "-y", "-ss", str(start), "-i", url, "-t", str(lengte),
            "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k", doel,
        ],
        capture_output=True,
        check=True,
    )


def _duur_van(ffmpeg, bron):
    """Duur (seconden) van een audiobron via ffmpeg, of 0 als onbekend."""
    uit = subprocess.run([ffmpeg, "-i", bron], capture_output=True, text=True)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+)", uit.stderr or "")
    if not m:
        return 0
    u, mi, s = (int(x) for x in m.groups())
    return u * 3600 + mi * 60 + s


def transcribeer_audio(bron, duur=None, voortgang=None):
    """Transcribeer een volledige audiobron (mp3-URL of lokaal pad).

    Voor Kerkomroep/uploads: er is geen preek-markering, dus de hele opname wordt
    getranscribeerd en het model haalt de preek eruit.
    """
    if not duur or duur <= 0:
        duur = _duur_van(_ffmpeg(), bron)
    if duur <= 0:
        raise RuntimeError("Kon de duur van de audio niet bepalen.")
    return transcribeer_hls(bron, 0, duur, voortgang)


def transcribeer_upload(inhoud: bytes, bestandsnaam, voortgang=None):
    """Transcribeer een geüpload audiobestand (mp3/m4a/wav/ogg)."""
    achtervoegsel = os.path.splitext(bestandsnaam or "audio.mp3")[1] or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=achtervoegsel, delete=False) as f:
        f.write(inhoud)
        pad = f.name
    try:
        return transcribeer_audio(pad, voortgang=voortgang)
    finally:
        try:
            os.remove(pad)
        except OSError:
            pass


def is_audio(bestandsnaam):
    return (bestandsnaam or "").lower().endswith(
        (".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac", ".mp4", ".webm")
    )


def transcribeer_hls(url, start, eind, voortgang=None):
    """Transcribeer alleen het gedeelte [start, eind] (seconden) uit een stream.

    Voor Kerkdienstgemist: alleen de preek (vanaf de markering tot het einde)
    wordt opgehaald en getranscribeerd — niet de hele dienst.
    """

    def meld(stap):
        if voortgang:
            voortgang(stap)

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")
    if eind <= start:
        raise RuntimeError("Ongeldig preekgedeelte (einde vóór begin).")

    client = OpenAI()
    ffmpeg = _ffmpeg()
    with tempfile.TemporaryDirectory() as tmp:
        stukken = []
        begin, idx = start, 0
        while begin < eind:
            stop = min(begin + MAX_DEEL_SECONDEN, eind)
            pad = os.path.join(tmp, f"deel_{idx}.mp3")
            meld(f"Preekaudio ophalen (deel {idx + 1})...")
            _knip_stream(ffmpeg, url, begin, stop - begin, pad)
            stukken.append(pad)
            begin, idx = stop, idx + 1

        teksten = []
        for i, pad in enumerate(stukken):
            meld(f"Audio transcriberen ({i + 1}/{len(stukken)})...")
            teksten.append(_transcribeer_bestand(client, pad))
    return " ".join(t for t in teksten if t).strip()


def transcribeer_preek(url, tijden, voortgang=None):
    """Download de preekaudio en geef de getranscribeerde tekst terug.

    `tijden` is een lijst [(start_sec, eind_sec), ...] per preekdeel.
    Werpt een fout als de provider niet bereikbaar is of de audio niet lukt;
    de aanroeper valt dan terug op de ondertiteltekst.
    """

    def meld(stap):
        if voortgang:
            voortgang(stap)

    if not ts.download_mogelijk():
        raise RuntimeError(
            "Geen residentiële proxy (YTDLP_PROXY) of PO-token-provider; "
            "audio-transcriptie niet mogelijk."
        )
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")

    client = OpenAI()
    ffmpeg = _ffmpeg()
    with tempfile.TemporaryDirectory() as tmp:
        meld("Audio van de dienst downloaden...")
        bron = _download_audio_gecached(url, tmp)

        # Knip elk preekdeel; splits een te lang deel op in stukken onder de
        # API-limiet. Onthoud per stuk bij welk preekdeel het hoort.
        stukken = []  # (deel_index, pad)
        for deel_index, (start, eind) in enumerate(tijden):
            begin = start
            while begin < eind:
                stop = min(begin + MAX_DEEL_SECONDEN, eind)
                pad = os.path.join(tmp, f"deel{deel_index}_{begin}.mp3")
                _knip(ffmpeg, bron, begin, stop, pad)
                stukken.append((deel_index, pad))
                begin = stop

        teksten = {i: [] for i in range(len(tijden))}
        for i, (deel_index, pad) in enumerate(stukken):
            meld(f"Audio transcriberen ({i + 1}/{len(stukken)})...")
            teksten[deel_index].append(_transcribeer_bestand(client, pad))

    resultaat_delen = [
        " ".join(teksten[i]).strip() for i in range(len(tijden))
    ]
    return DEEL_MARKERING.join(d for d in resultaat_delen if d)


def transcribeer_hele_video(url, voortgang=None):
    """Download de hele video-audio (via yt-dlp/proxy) en transcribeer die volledig.

    Voor YouTube zonder bruikbare ondertitels (bijv. livestreams). Het taalmodel
    haalt daarna zelf het preekgedeelte eruit (volledige_dienst=True). Geeft de
    volledige transcripttekst terug.
    """

    def meld(stap):
        if voortgang:
            voortgang(stap)

    if not ts.download_mogelijk():
        raise RuntimeError(
            "Geen residentiële proxy (YTDLP_PROXY) of PO-token-provider; "
            "audio-transcriptie niet mogelijk."
        )
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")

    client = OpenAI()
    ffmpeg = _ffmpeg()
    with tempfile.TemporaryDirectory() as tmp:
        meld("Audio van de dienst downloaden...")
        bron = _download_audio_gecached(url, tmp)
        duur = _duur_van(ffmpeg, bron)
        stukken = []
        if duur:
            begin = 0
            while begin < duur:
                stop = min(begin + MAX_DEEL_SECONDEN, duur)
                pad = os.path.join(tmp, f"deel_{begin}.mp3")
                _knip(ffmpeg, bron, begin, stop, pad)
                stukken.append(pad)
                begin = stop
        else:  # onbekende duur: alles in één keer (mono 32k blijft ruim onder de limiet)
            pad = os.path.join(tmp, "deel_0.mp3")
            _knip(ffmpeg, bron, 0, 24 * 3600, pad)
            stukken.append(pad)

        teksten = []
        for i, pad in enumerate(stukken):
            meld(f"Audio transcriberen ({i + 1}/{len(stukken)})...")
            teksten.append(_transcribeer_bestand(client, pad))
    return " ".join(t for t in teksten if t).strip()
