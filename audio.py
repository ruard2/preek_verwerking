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
import os
import re
import shutil
import subprocess
import tempfile

import imageio_ffmpeg
import yt_dlp
from openai import OpenAI

import transcript as ts

TRANSCRIBE_MODEL = os.environ.get("OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
# Veiligheidsmarge onder de 25 MB-limiet van de OpenAI-transcriptie-API.
MAX_DEEL_SECONDEN = 20 * 60
DEEL_MARKERING = "\n\n[VOLGEND PREEKDEEL — hiervoor werd gezongen]\n\n"


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
            "format": "bestaudio/best",
            "outtmpl": os.path.join(map_, "audio.%(ext)s"),
        }
    )
    with yt_dlp.YoutubeDL(opties) as ydl:
        ydl.download([url])
    bestanden = [f for f in glob.glob(os.path.join(map_, "audio.*"))]
    if not bestanden:
        raise RuntimeError("De audio kon niet worden gedownload.")
    return bestanden[0]


def _knip(ffmpeg, bron, start, eind, doel):
    subprocess.run(
        [
            ffmpeg, "-y", "-ss", str(start), "-to", str(eind), "-i", bron,
            "-ac", "1", "-ar", "16000", "-b:a", "32k", doel,
        ],
        capture_output=True,
        check=True,
    )


def _transcribeer_bestand(client, pad, taal=None):
    # Zonder taal laten we het model automatisch detecteren, zodat ook
    # Afrikaanse/Engelse preken goed getranscribeerd worden. Alleen een
    # betrouwbaar bekende taalcode meegeven als hint.
    argumenten = {"model": TRANSCRIBE_MODEL}
    if taal and len(taal) == 2:
        argumenten["language"] = taal
    with open(pad, "rb") as f:
        antwoord = client.audio.transcriptions.create(file=f, **argumenten)
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

    if not ts.provider_bereikbaar():
        raise RuntimeError(
            "PO-token-provider niet bereikbaar; audio-transcriptie niet mogelijk."
        )
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")

    client = OpenAI()
    ffmpeg = _ffmpeg()
    with tempfile.TemporaryDirectory() as tmp:
        meld("Audio van de dienst downloaden...")
        bron = _download_audio(url, tmp)

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
