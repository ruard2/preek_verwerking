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
import json
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

# ---- Transcript-cache -----------------------------------------------------
# Getranscribeerde preekteksten bewaren (30 dagen). Zelfde video + zelfde
# preektijden → transcript direct uit cache, download + transcriptie overgeslagen.
_TRANSCRIPT_CACHE_DIR = os.environ.get(
    "TRANSCRIPT_CACHE_DIR", os.path.join(_DATA_DIR, "transcript_cache")
)
_TRANSCRIPT_CACHE_TTL = int(os.environ.get("TRANSCRIPT_CACHE_TTL", str(30 * 24 * 3600)))


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


def _transcript_ophalen(url, tijden):
    """Geef het gecachede transcript als het bestaat en nog vers is, anders None."""
    alle_start = min(t[0] for t in tijden)
    alle_eind = max(t[1] for t in tijden)
    sleutel = f"{_video_sleutel(url)}_{int(alle_start)}_{int(alle_eind)}_{TRANSCRIBE_MODEL}"
    pad = os.path.join(_TRANSCRIPT_CACHE_DIR, sleutel + ".json")
    if not os.path.isfile(pad):
        return None
    grens = time.time() - _TRANSCRIPT_CACHE_TTL
    try:
        if os.path.getmtime(pad) < grens:
            return None
        with open(pad, encoding="utf-8") as f:
            return json.load(f)["tekst"]
    except Exception:  # noqa: BLE001
        return None


def _transcript_opslaan(url, tijden, tekst):
    """Sla het getranscribeerde preektekst op in de cache."""
    alle_start = min(t[0] for t in tijden)
    alle_eind = max(t[1] for t in tijden)
    sleutel = f"{_video_sleutel(url)}_{int(alle_start)}_{int(alle_eind)}_{TRANSCRIBE_MODEL}"
    os.makedirs(_TRANSCRIPT_CACHE_DIR, exist_ok=True)
    pad = os.path.join(_TRANSCRIPT_CACHE_DIR, sleutel + ".json")
    try:
        with open(pad, "w", encoding="utf-8") as f:
            json.dump({"tekst": tekst}, f, ensure_ascii=False)
    except Exception:  # noqa: BLE001
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


def _download_audio_chunked(url, map_, start_sec=None, eind_sec=None, proxy=None):
    """Snel: native yt-dlp downloader met kleine HTTP-chunks + optioneel tijdsegment.

    YouTube throttlet aaneengesloten HTTP-requests van > ~10 MB tot net boven de
    audiobitrate (~11 KiB/s). Door in chunks van 1 MB te downloaden wordt per chunk
    een nieuwe HTTP-range request gedaan — die vallen onder de throttle-drempel en
    worden niet gelimiteerd. Vereist een sticky-session proxy (vaste IP per download)
    zodat het YouTube-CDN elke chunk accepteert met dezelfde gesigneerde URL.

    Met start_sec/eind_sec wordt via download_ranges alleen het preeksegment opgehaald;
    het resulterende bestand begint op t=0 (tijden zijn relatief aan start_sec).
    """
    opties = ts.basis_opties(proxy_override=proxy)
    opties.update(
        {
            "skip_download": False,
            "format": "bestaudio[abr<=64]/bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(map_, "audio.%(ext)s"),
            "socket_timeout": int(os.environ.get("YTDLP_SOCKET_TIMEOUT", "120")),
            "retries": int(os.environ.get("YTDLP_RETRIES", "20")),
            "fragment_retries": int(os.environ.get("YTDLP_RETRIES", "20")),
            "file_access_retries": 10,
            "continuedl": True,
            # 1 MB per chunk — onder de YouTube throttle-drempel van ~10 MB.
            "http_chunk_size": 1024 * 1024,
        }
    )
    if start_sec is not None and eind_sec is not None:
        opties["download_ranges"] = lambda _info, _ydl: [
            {"start_time": start_sec, "end_time": eind_sec}
        ]
        # force_keyframes_at_cuts NIET gebruiken: dat roept ffmpeg aan voor
        # post-processing en geeft "ffmpeg exited with code 8" als de download
        # mislukt (bijv. geblokkeerd datacenter-IP). Zonder deze vlag knipt
        # yt-dlp op de dichtstbijzijnde keyframe — nauwkeurig genoeg voor audio.
    with yt_dlp.YoutubeDL(opties) as ydl:
        ydl.download([url])
    bestanden = glob.glob(os.path.join(map_, "audio.*"))
    if not bestanden:
        raise RuntimeError("De audio kon niet worden gedownload.")
    # Leeg bestand = geblokkeerd of mislukte download (yt-dlp maakt bestand aan voor inhoud)
    if os.path.getsize(bestanden[0]) < 10_000:
        raise RuntimeError(
            f"Audiobestand te klein ({os.path.getsize(bestanden[0])} bytes) — "
            "download waarschijnlijk geblokkeerd door YouTube."
        )
    return bestanden[0]


def _download_audio(url, map_, start_sec=None, eind_sec=None, zonder_proxy=False, ios_mweb=False):
    """Download (deel van) audio via yt-dlp + ffmpeg.

    Met start_sec/eind_sec vraagt ffmpeg via HTTP-range only dat tijdvak op,
    wat de downloadgrootte flink beperkt bij lange dienstvideo's.
    Met zonder_proxy=True / ios_mweb=True: directe snelle download proberen.
    """
    ffmpeg_bin = _ffmpeg()
    opties = ts.basis_opties(zonder_proxy=zonder_proxy, ios_mweb=ios_mweb)

    ffmpeg_input_args = [
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "30",
    ]
    if start_sec is not None and eind_sec is not None:
        # Beperk de download tot het preeksegment. -ss seek + -t duration:
        # -t (duur) werkt betrouwbaarder als input-optie dan -to (eindtijd) voor
        # HTTP-streams; -to als input geeft soms "ffmpeg exited with code 8".
        duur = int(eind_sec) - int(start_sec)
        ffmpeg_input_args += ["-ss", str(int(start_sec)), "-t", str(duur)]

    opties.update(
        {
            "skip_download": False,
            # Alleen audio, zo klein mogelijk — ffmpeg converteert toch naar 16kHz
            # mono 32kbps, dus hogere kwaliteit is pure verspilling van proxy-bandbreedte.
            # Voorkeur: ≤64 kbps audio-only (itag 139 = 48k m4a, itag 249/250 = 50-70k opus).
            # Valt terug op m4a (~128k), dan elke audio-only stream, dan best als laatste redmiddel.
            "format": "bestaudio[abr<=64]/bestaudio[ext=m4a]/bestaudio/best",
            "outtmpl": os.path.join(map_, "audio.%(ext)s"),
            # Ruime timeout + veel herpogingen: residentiële proxy's zijn traag en haperen.
            "socket_timeout": int(os.environ.get("YTDLP_SOCKET_TIMEOUT", "120")),
            "retries": int(os.environ.get("YTDLP_RETRIES", "20")),
            "fragment_retries": int(os.environ.get("YTDLP_RETRIES", "20")),
            "file_access_retries": 10,
            "continuedl": True,
            # ffmpeg als externe downloader: één persistente HTTP-verbinding voor
            # het hele bestand. Voorkomt dat de roterende proxy halverwege van IP
            # wisselt, waarna het YouTube-CDN de gesigneerde URL afwijst (403).
            "external_downloader": "ffmpeg",
            "external_downloader_args": {"ffmpeg_i": ffmpeg_input_args},
            "ffmpeg_location": os.path.dirname(ffmpeg_bin),
        }
    )
    with yt_dlp.YoutubeDL(opties) as ydl:
        ydl.download([url])
    bestanden = [f for f in glob.glob(os.path.join(map_, "audio.*"))]
    if not bestanden:
        raise RuntimeError("De audio kon niet worden gedownload.")
    return bestanden[0]


def _segment_sleutel(url, start_sec, eind_sec):
    """Cache-sleutel voor een specifiek preeksegment (video-ID + tijdstempels)."""
    basis = _video_sleutel(url)
    if start_sec is not None and eind_sec is not None:
        return f"{basis}_{int(start_sec)}_{int(eind_sec)}"
    return basis


def _download_audio_cdn_direct(url, map_, start_sec=None, eind_sec=None, proxy=None):
    """Hybride: CDN-URL ophalen via proxy (web+POT), daarna direct downloaden zonder proxy.

    Als YouTube de CDN-URL niet strikt aan het proxy-IP bindt → download op
    datacenter-snelheid (seconden i.p.v. minuten). Gooit RuntimeError als het
    bestand te klein is (= CDN weigerde de directe verbinding, IP-gebonden).
    """
    opties = ts.basis_opties(proxy_override=proxy)
    opties.update({
        "skip_download": True,
        "format": "bestaudio[abr<=64]/bestaudio[ext=m4a]/bestaudio/best",
    })
    with yt_dlp.YoutubeDL(opties) as ydl:
        info = ydl.extract_info(url, download=False)

    # CDN-URL en extensie uit de geselecteerde format halen.
    # Bij audio-only is dit een directe HTTPS-URL (geen HLS-manifest).
    import logging
    log = logging.getLogger("aftersermon")
    log.info("[audio] Stap 4: CDN-URL ophalen via residentieel proxy...")

    cdn_url = None
    ext = "m4a"
    for fmt in (info.get("requested_formats") or []):
        if fmt.get("vcodec") in ("none", None) and fmt.get("url"):
            cdn_url = fmt["url"]
            ext = fmt.get("ext", "m4a")
            break
    if not cdn_url:
        cdn_url = info.get("url")
        ext = info.get("ext", "m4a") or "m4a"
    if not cdn_url:
        raise RuntimeError("Geen CDN-URL gevonden in de video-info.")

    log.info("[audio] Stap 4: CDN-URL verkregen, direct downloaden (geen proxy)...")
    doel = os.path.join(map_, f"audio.{ext}")
    ffmpeg_bin = _ffmpeg()
    ffmpeg_args = [
        ffmpeg_bin, "-y",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",  # kort: snel opgeven bij IP-blokkade
    ]
    if start_sec is not None and eind_sec is not None:
        duur = int(eind_sec) - int(start_sec)
        ffmpeg_args += ["-ss", str(int(start_sec)), "-t", str(duur)]
    ffmpeg_args += ["-i", cdn_url, "-vn", "-acodec", "copy", doel]
    try:
        # Timeout van 60 s: als CDN direct werkt klaar het in seconden;
        # bij IP-blokkade/throttling niet eindeloos wachten.
        subprocess.run(ffmpeg_args, capture_output=True, check=True, timeout=60)
    except subprocess.TimeoutExpired:
        raise RuntimeError("CDN-directe download te traag (timeout 60 s) — IP-gebonden of geblokkeerd.")

    if not os.path.isfile(doel) or os.path.getsize(doel) < 10_000:
        raise RuntimeError(
            f"Directe CDN-download mislukt ({os.path.getsize(doel) if os.path.isfile(doel) else 0} bytes)"
            " — CDN-URL waarschijnlijk IP-gebonden."
        )
    return doel


def _is_live(url, proxy=None):
    """Snelle metadata-check: is deze video een actieve YouTube-livestream?"""
    import logging
    log = logging.getLogger("aftersermon")
    opties = ts.basis_opties(proxy_override=proxy)
    opties.update({"skip_download": True, "quiet": True})
    try:
        with yt_dlp.YoutubeDL(opties) as ydl:
            info = ydl.extract_info(url, download=False)
        status = info.get("live_status") or ""
        return bool(info.get("is_live") or status == "is_live")
    except Exception as fout:
        log.info(f"[audio] live-check mislukt ({fout}), ga uit van VOD.")
        return False


def _download_audio_live(url, map_, start_sec=None, eind_sec=None, proxy=None):
    """Download een segment van een actieve YouTube-livestream via HLS + ffmpeg.

    Werkwijze:
    1. yt-dlp haalt (met residentiële proxy + live_from_start) de HLS-manifest-URL
       op — dit geeft de DVR-variant waarmee je terug kunt in de stream.
    2. ffmpeg leest de HLS-manifest en pakt met -ss/-t alleen het gevraagde
       tijdvak; download_ranges van yt-dlp werkt niet op live-HLS-formats.

    Timeout: segmentduur + 3 min marge (HLS heeft meer latency dan directe HTTPS).
    """
    import logging
    log = logging.getLogger("aftersermon")

    # Stap 1: HLS-manifest-URL ophalen
    opties = ts.basis_opties(proxy_override=proxy)
    opties.update({
        "skip_download": True,
        "live_from_start": True,
        "format": "bestaudio[ext=m4a]/bestaudio/best",
    })
    with yt_dlp.YoutubeDL(opties) as ydl:
        info = ydl.extract_info(url, download=False)

    stream_url = None
    ext = "m4a"
    for fmt in (info.get("requested_formats") or []):
        if fmt.get("vcodec") in ("none", None) and fmt.get("url"):
            stream_url = fmt["url"]
            ext = fmt.get("ext", "m4a")
            break
    if not stream_url:
        stream_url = info.get("url")
        ext = info.get("ext", "m4a") or "m4a"
    if not stream_url:
        raise RuntimeError("Geen HLS-stream-URL gevonden voor de live stream.")
    log.info(f"[audio] Live: HLS-URL verkregen (ext={ext}), ffmpeg haalt segment op...")

    # Stap 2: ffmpeg knipt het tijdvak uit de HLS-stream
    doel = os.path.join(map_, f"audio.{ext}")
    ffmpeg_bin = _ffmpeg()
    ffmpeg_args = [
        ffmpeg_bin, "-y",
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "10",
    ]
    if start_sec is not None and eind_sec is not None:
        duur = int(eind_sec) - int(start_sec)
        ffmpeg_args += ["-ss", str(int(start_sec)), "-t", str(duur)]
    ffmpeg_args += ["-i", stream_url, "-vn", "-acodec", "copy", doel]

    timeout = 180  # basistimeout
    if start_sec is not None and eind_sec is not None:
        timeout = int(eind_sec - start_sec) + 180
    try:
        subprocess.run(ffmpeg_args, capture_output=True, check=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Live-HLS download timeout ({timeout}s) — DVR niet bereikbaar.")

    if not os.path.isfile(doel) or os.path.getsize(doel) < 10_000:
        raise RuntimeError(
            f"Live-audiobestand te klein "
            f"({os.path.getsize(doel) if os.path.isfile(doel) else 0} bytes)"
        )
    return doel


def _download_audio_met_fallback(url, map_, start_sec=None, eind_sec=None):
    """Probeer snelle download, val stap voor stap terug op langzamere opties.

    Bij een actieve livestream wordt automatisch de live-DVR-codepath gebruikt
    (live_from_start + download_ranges via residentiële proxy).

    Volgorde voor VODs (snelst → langzaamst):
    1. ios/mweb zonder proxy — niet-IP-gebonden CDN, werkt voor gewone video's.
    2. Chunked via datacenter sticky proxy (YTDLP_PROXY_DC) — 1 MB chunks omzeilen
       YouTube throttling; datacenter = server-bandbreedte. Betrouwbaar voor VODs.
    3. ios/mweb via residentiële proxy — voor reguliere video's als DC blokkeert.
    4. web+POT via residentiële proxy — traag (~17 min) maar bewezen voor VODs.
       Stap 4 checkt de cache eerst: als een eerdere run al downloadde, wordt het
       gecachede bestand hergebruikt. Stappen 1-3 proberen altijd vers.
    """
    import logging
    log = logging.getLogger("aftersermon")

    def _opruimen():
        for pad in glob.glob(os.path.join(map_, "audio.*")):
            try:
                os.remove(pad)
            except OSError:
                pass

    def _bewaar_in_cache(bron):
        sleutel = _segment_sleutel(url, start_sec, eind_sec)
        try:
            _cache_opruimen()
            _cache_opslaan(sleutel, bron)
        except Exception:  # noqa: BLE001
            pass

    proxy_res = os.environ.get("YTDLP_PROXY")
    proxy_dc = os.environ.get("YTDLP_PROXY_DC")

    # ── Live-detectie: actieve livestream krijgt eigen codepath ──────────────
    log.info("[audio] Live-check (metadata)...")
    if _is_live(url):
        log.info("[audio] Actieve livestream gedetecteerd — live-DVR-download via residentiële proxy.")
        if proxy_res:
            bron = _download_audio_live(url, map_, start_sec, eind_sec, proxy=proxy_res)
            log.info("[audio] Live-download gelukt.")
            _bewaar_in_cache(bron)
            return bron
        log.warning("[audio] Geen residentiële proxy beschikbaar voor live-download; val terug op normale stappen.")

    # Stap 1: ios/mweb zonder proxy (gratis, snel voor gewone video's)
    try:
        log.info("[audio] Stap 1: ios/mweb direct (geen proxy)...")
        bron = _download_audio(url, map_, start_sec, eind_sec, zonder_proxy=True, ios_mweb=True)
        log.info("[audio] Stap 1 gelukt.")
        _bewaar_in_cache(bron)
        return bron
    except Exception as fout:  # noqa: BLE001
        log.info(f"[audio] Stap 1 mislukt ({fout}).")
        _opruimen()

    # Stap 2: chunked via datacenter sticky proxy (snel voor VODs, omzeilt throttling)
    if proxy_dc:
        try:
            log.info("[audio] Stap 2: chunked via datacenter proxy...")
            bron = _download_audio_chunked(url, map_, start_sec, eind_sec, proxy=proxy_dc)
            log.info("[audio] Stap 2 gelukt.")
            _bewaar_in_cache(bron)
            return bron
        except Exception as fout:  # noqa: BLE001
            log.info(f"[audio] Stap 2 mislukt ({fout}).")
            _opruimen()

    # Stap 3: ios/mweb via residentiële proxy (voor gewone video's als DC blokkeert)
    if proxy_res:
        try:
            log.info("[audio] Stap 3: ios/mweb via residentiële proxy...")
            bron = _download_audio(url, map_, start_sec, eind_sec, zonder_proxy=False, ios_mweb=True)
            log.info("[audio] Stap 3 gelukt.")
            _bewaar_in_cache(bron)
            return bron
        except Exception as fout:  # noqa: BLE001
            log.info(f"[audio] Stap 3 mislukt ({fout}).")
            _opruimen()

    # Cache check voor stap 4+5: als een eerdere run dit segment al downloadde, hergebruiken.
    sleutel = _segment_sleutel(url, start_sec, eind_sec)
    gecached = _cache_ophalen(sleutel)
    if gecached:
        log.info("[audio] Cache: gecached segment gevonden, download overgeslagen.")
        ext = os.path.splitext(gecached)[1]
        doel = os.path.join(map_, "audio" + ext)
        shutil.copy2(gecached, doel)
        return doel

    # Stap 4: hybride CDN-direct — info via residentieel proxy, download zonder proxy.
    # Als de CDN-URL niet IP-gebonden is: download op datacenter-snelheid (seconden).
    if proxy_res:
        try:
            log.info("[audio] Stap 4: CDN-direct (info via residentieel, download direct)...")
            bron = _download_audio_cdn_direct(url, map_, start_sec, eind_sec, proxy=proxy_res)
            log.info("[audio] Stap 4 gelukt (CDN direct, geen proxy voor download).")
            _bewaar_in_cache(bron)
            return bron
        except Exception as fout:  # noqa: BLE001
            log.info(f"[audio] Stap 4 mislukt ({fout}).")
            _opruimen()

    # Stap 5: chunked web+POT via residentiële sticky-proxy (traag maar bewezen voor VODs).
    log.info("[audio] Stap 5: chunked web+POT via residentiële sticky-proxy...")
    bron = _download_audio_chunked(url, map_, start_sec, eind_sec, proxy=proxy_res)
    log.info("[audio] Stap 5 gelukt.")
    _bewaar_in_cache(bron)
    return bron


def _download_audio_gecached(url, map_):
    """Download volledige audio met cache (7 dagen TTL).

    Gebruikt alleen voor transcribeer_hele_video waarbij de volledige opname
    nodig is. Voor preek-segmenten: gebruik _download_audio_met_fallback direct.
    """
    sleutel = _video_sleutel(url)
    gecached = _cache_ophalen(sleutel)
    if gecached:
        ext = os.path.splitext(gecached)[1]
        doel = os.path.join(map_, "audio" + ext)
        shutil.copy2(gecached, doel)
        return doel
    # Niet in cache: downloaden en daarna opslaan.
    bron = _download_audio_met_fallback(url, map_)
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
    Bij herhaling van dezelfde preek: transcript uit cache (30 dagen TTL),
    download + transcriptie worden dan overgeslagen.
    """
    import logging
    log = logging.getLogger("aftersermon")

    def meld(stap):
        if voortgang:
            voortgang(stap)

    # Transcript-cache: download + transcriptie overslaan als al gedaan.
    gecacheed = _transcript_ophalen(url, tijden)
    if gecacheed:
        log.info("[audio] Transcript uit cache geladen.")
        meld("Transcript uit cache geladen.")
        return gecacheed

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
        # Download alleen het preeksegment (niet de hele video).
        # Dit spaart ~60% downloadtijd bij diensten van 1-2 uur.
        alle_start = min(t[0] for t in tijden)
        alle_eind = max(t[1] for t in tijden)
        meld("Audio van de dienst downloaden...")
        bron = _download_audio_met_fallback(url, tmp, alle_start, alle_eind)

        # Knip elk preekdeel; pas tijden aan voor de offset van het segment.
        # Het gedownloade bestand begint bij t=0 (= originele tijd alle_start).
        stukken = []  # (deel_index, pad)
        for deel_index, (start, eind) in enumerate(tijden):
            begin = start - alle_start
            eind_rel = eind - alle_start
            while begin < eind_rel:
                stop = min(begin + MAX_DEEL_SECONDEN, eind_rel)
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
    resultaat = DEEL_MARKERING.join(d for d in resultaat_delen if d)
    _transcript_opslaan(url, tijden, resultaat)
    return resultaat


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
