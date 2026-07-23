"""Ondertitels van YouTube ophalen en daaruit het preekgedeelte halen.

Werkwijze:
1. Met yt-dlp de (automatische) ondertitels downloaden, bij voorkeur in de
   oorspronkelijke taal van de video ("<taal>-orig").
2. De VTT-ondertitels omzetten naar een lijst (seconden, tekstregel).
3. Het preekblok zoeken: het langste aaneengesloten blok spraak dat niet
   door langere stukken muziek/zang wordt onderbroken.
"""

import os
import re
import glob
import tempfile

import yt_dlp

# Markeringen die op zang/muziek wijzen (niet [snuift]/[schraapt keel] e.d.,
# want die komen ook midden in de preek voor).
MUZIEK_TAG_RE = re.compile(r"\[\s*(muziek|zingt|applaus)\s*\]", re.I)
# Alle [annotaties] die uit de uitvoertekst gestript worden.
ANNOTATIE_RE = re.compile(r"\[[^\]]+\]")
TAG_RE = re.compile(r"<[^>]+>")
TIJD_RE = re.compile(r"(\d+):(\d\d):(\d\d)\.\d+\s*-->")

# Een blok korter dan dit beschouwen we niet als preek.
MIN_PREEK_SECONDEN = 8 * 60
# Een regel geldt als muziek wanneer er binnen ± dit venster (seconden)
# minstens MIN_TAGS_IN_VENSTER muziekmarkeringen voorkomen.
MUZIEK_VENSTER = 30
MIN_TAGS_IN_VENSTER = 3


def haal_preek_transcript(url, voortgang=None):
    """Geeft (preektekst, meta) terug voor een YouTube-url."""

    def meld(stap):
        if voortgang:
            voortgang(stap)

    meld("Video-informatie ophalen...")
    info = _haal_info(url)
    titel = info.get("title") or "Onbekende video"

    taal = _kies_taal(info)
    if taal is None:
        raise RuntimeError(
            "Deze video heeft geen (automatische) ondertitels; "
            "transcriptie is dan niet mogelijk."
        )

    meld(f"Ondertitels downloaden ({taal})...")
    entries = _download_ondertitels(url, taal)
    if not entries:
        raise RuntimeError("De ondertitels konden niet worden gelezen.")

    meld("Preekgedeelte zoeken...")
    blok = _vind_preekblok(entries)
    tekst = "\n".join(t for _, t in blok if t)

    meta = {
        "titel": titel,
        "taal": taal,
        "preek_start": _fmt(blok[0][0]),
        "preek_einde": _fmt(blok[-1][0]),
        "duur_minuten": round((blok[-1][0] - blok[0][0]) / 60),
    }
    return tekst, meta


def _basis_opties():
    opties = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }
    # Optioneel: cookies meegeven als YouTube het server-IP blokkeert.
    cookies = os.environ.get("YTDLP_COOKIES")
    if cookies:
        pad = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
        with open(pad, "w", encoding="utf-8") as f:
            f.write(cookies)
        opties["cookiefile"] = pad
    return opties


def _haal_info(url):
    with yt_dlp.YoutubeDL(_basis_opties()) as ydl:
        return ydl.extract_info(url, download=False)


def _kies_taal(info):
    """Voorkeur: handmatige ondertitels, dan automatische in de oorspronkelijke taal."""
    # "live_chat" is geen ondertiteling maar de chatgeschiedenis van een livestream.
    handmatig = {
        t: v for t, v in (info.get("subtitles") or {}).items() if t != "live_chat"
    }
    automatisch = info.get("automatic_captions") or {}

    for taal in ("nl", "af", "en"):
        if taal in handmatig:
            return taal
    if handmatig:
        return next(iter(handmatig))

    for taal in automatisch:
        if taal.endswith("-orig"):
            return taal
    for taal in ("nl", "af", "en"):
        if taal in automatisch:
            return taal
    return None


def _download_ondertitels(url, taal):
    with tempfile.TemporaryDirectory() as tmp:
        opties = _basis_opties()
        opties.update(
            {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": [taal],
                "subtitlesformat": "vtt",
                "outtmpl": os.path.join(tmp, "video.%(ext)s"),
            }
        )
        with yt_dlp.YoutubeDL(opties) as ydl:
            ydl.download([url])

        bestanden = glob.glob(os.path.join(tmp, "*.vtt"))
        if not bestanden:
            return []
        with open(bestanden[0], encoding="utf-8") as f:
            return _parse_vtt(f.read())


def _parse_vtt(inhoud):
    entries = []
    tijd = None
    for regel in inhoud.splitlines():
        m = TIJD_RE.match(regel)
        if m:
            u, mi, s = (int(x) for x in m.groups())
            tijd = u * 3600 + mi * 60 + s
            continue
        if tijd is None or regel.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        tekst = TAG_RE.sub("", regel).strip()
        if not tekst:
            continue
        # Automatische ondertitels herhalen regels (rollend venster): dedupliceren.
        if entries and entries[-1][1] == tekst:
            continue
        entries.append((tijd, tekst))
    return entries


def _vind_preekblok(entries):
    """Kies het langste spraakblok tussen de muziek-/zangstukken.

    Een regel telt als muziek wanneer er rondom die regel (schuivend venster)
    voldoende muziekmarkeringen staan. Zo breken losse zangflarden zonder
    markering de detectie niet, en splitsen incidentele markeringen midden in
    de preek het blok niet.
    """
    tag_tijden = []
    for t, tekst in entries:
        tag_tijden.extend([t] * len(MUZIEK_TAG_RE.findall(tekst)))

    def is_muziek(t):
        aantal = sum(1 for x in tag_tijden if abs(x - t) <= MUZIEK_VENSTER)
        return aantal >= MIN_TAGS_IN_VENSTER

    blokken = []
    huidig = []
    for t, tekst in entries:
        schoon = ANNOTATIE_RE.sub(" ", tekst).strip()
        if is_muziek(t):
            if huidig:
                blokken.append(huidig)
                huidig = []
        elif schoon:
            huidig.append((t, schoon))
    if huidig:
        blokken.append(huidig)

    if not blokken:
        raise RuntimeError("Geen bruikbare spraak gevonden in de ondertitels.")

    beste = max(blokken, key=lambda b: b[-1][0] - b[0][0])
    if beste[-1][0] - beste[0][0] < MIN_PREEK_SECONDEN:
        # Geen duidelijk preekblok gevonden: geef alles terug en laat het
        # taalmodel de liturgie eromheen negeren.
        return [
            (t, s)
            for t, x in entries
            if (s := ANNOTATIE_RE.sub(" ", x).strip())
        ]
    return beste


def _fmt(seconden):
    u, rest = divmod(int(seconden), 3600)
    m, s = divmod(rest, 60)
    return f"{u:02d}:{m:02d}:{s:02d}"
