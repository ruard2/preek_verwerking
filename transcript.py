"""Ondertitels van YouTube ophalen en daaruit het preekgedeelte halen.

Werkwijze:
1. Met yt-dlp de (automatische) ondertitels downloaden, bij voorkeur in de
   oorspronkelijke taal van de video ("<taal>-orig").
2. De VTT-ondertitels omzetten naar een lijst (seconden, tekstregel).
3. Het preekblok zoeken: het langste aaneengesloten blok spraak dat niet
   door langere stukken muziek/zang wordt onderbroken.
"""

import base64
import json
import os
import re
import glob
import tempfile
import urllib.request

import yt_dlp

# Markeringen die op zang/muziek wijzen (niet [snuift]/[schraapt keel] e.d.,
# want die komen ook midden in de preek voor).
MUZIEK_TAG_RE = re.compile(
    r"\[\s*(muziek|musiek|music|zingt|zingen|sing(?:ing)?|applaus|applause)"
    r"[^\]]*\]",
    re.I,
)
# Alle [annotaties] die uit de uitvoertekst gestript worden.
ANNOTATIE_RE = re.compile(r"\[[^\]]+\]")
TAG_RE = re.compile(r"<[^>]+>")
TIJD_RE = re.compile(r"(\d+):(\d\d):(\d\d)\.\d+\s*-->")

# Een blok korter dan dit beschouwen we niet als preek.
MIN_PREEK_SECONDEN = 8 * 60
# Extra preekdelen (bij een preek in twee of drie delen, met bijvoorbeeld een
# lied ertussen): een blok telt mee als het minstens zo lang is als dit én
# minstens dit aandeel van het langste blok.
MIN_DEEL_SECONDEN = 5 * 60
MIN_DEEL_AANDEEL = 0.45
# Maximale lengte van het meegegeven welkomstfragment (voor de voorganger).
MAX_WELKOM_TEKENS = 1500
# Een regel geldt als muziek wanneer er binnen ± dit venster (seconden)
# minstens MIN_TAGS_IN_VENSTER muziekmarkeringen voorkomen.
MUZIEK_VENSTER = 30
MIN_TAGS_IN_VENSTER = 3


def haal_preek_segmentatie(url, voortgang=None):
    """Bepaal via de ondertitels waar de preek zit.

    Geeft een dict terug met:
      - meta: titel, taal, start/einde, aantal delen, duur
      - welkom: welkomstfragment (voor de naam van de voorganger), of None
      - tijden: [(start_sec, eind_sec), ...] per preekdeel — om audio te knippen
      - ondertitel_tekst: de preektekst uit de ondertitels (terugval als er
        geen audio-transcriptie beschikbaar is)
    """

    def meld(stap):
        if voortgang:
            voortgang(stap)

    meld("Video-informatie ophalen...")
    info = _haal_info(url)
    titel = info.get("title") or "Onbekende video"

    taal = _kies_taal(info)
    if taal is None:
        raise RuntimeError(
            "Deze video heeft geen (automatische) ondertitels; het "
            "preekgedeelte kan dan niet worden bepaald."
        )

    meld(f"Ondertitels ophalen ({taal})...")
    entries = _download_ondertitels(url, taal)
    if not entries:
        raise RuntimeError("De ondertitels konden niet worden gelezen.")

    meld("Preekgedeelte zoeken...")
    return segmenteer(entries, titel=titel, taal=taal)


def segmenteer(entries, titel="Onbekende dienst", taal="nl"):
    """Bepaal de preekdelen + het welkomstblok uit (seconden, tekst)-entries.

    Gedeeld door de yt-dlp- en de Supadata-bron: beide leveren entries in
    hetzelfde formaat aan, zodat de preekdetectie identiek werkt.
    """
    if not entries:
        raise RuntimeError("Lege transcriptie ontvangen.")

    delen, welkom = _vind_preekdelen(entries)
    ondertitel_tekst = "\n\n[VOLGEND PREEKDEEL — hiervoor werd gezongen]\n\n".join(
        "\n".join(t for _, t in deel if t) for deel in delen
    )
    welkomtekst = None
    if welkom:
        welkomtekst = "\n".join(t for _, t in welkom if t)[:MAX_WELKOM_TEKENS]

    tijden = [(deel[0][0], deel[-1][0]) for deel in delen]
    meta = {
        "titel": titel,
        "taal": taal,
        "preek_start": _fmt(delen[0][0][0]),
        "preek_einde": _fmt(delen[-1][-1][0]),
        "delen": len(delen),
        "duur_minuten": round(
            sum(deel[-1][0] - deel[0][0] for deel in delen) / 60
        ),
    }
    return {
        "meta": meta,
        "welkom": welkomtekst,
        "tijden": tijden,
        "ondertitel_tekst": ondertitel_tekst,
    }


def _plugin_geladen():
    """Is de bgutil-yt-dlp-plugin geïnstalleerd? (passief, zonder te importeren
    — importeren zou de provider dubbel registreren.)"""
    import importlib.util

    for naam in (
        "yt_dlp_plugins.extractor.getpot_bgutil_http",
        "bgutil_ytdlp_pot_provider",
    ):
        try:
            if importlib.util.find_spec(naam) is not None:
                return True
        except Exception:  # noqa: BLE001
            continue
    return False


def pot_provider_diagnose():
    """Controleer of de PO-token-provider geconfigureerd en bereikbaar is."""
    plugin = (
        "yt-dlp-plugin geladen"
        if _plugin_geladen()
        else "LET OP: yt-dlp-plugin niet gevonden"
    )
    extra = []
    if os.environ.get("YTDLP_PROXY"):
        extra.append("proxy actief")
    if os.environ.get("YTDLP_COOKIES") or os.environ.get("YTDLP_COOKIES_B64"):
        extra.append("cookies actief")
    staart = f", {plugin}" + ("".join(f", {e}" for e in extra))

    url = os.environ.get("POT_PROVIDER_URL")
    if not url:
        return (
            "POT_PROVIDER_URL is niet ingesteld — de PO-token-provider wordt "
            f"niet gebruikt. Zie de README voor de installatiestappen.{staart}"
        )
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/ping", timeout=5) as r:
            data = json.loads(r.read().decode())
        return (
            f"PO-token-provider op {url} is bereikbaar "
            f"(versie {data.get('version', '?')}{staart})."
        )
    except Exception as fout:  # noqa: BLE001
        return f"PO-token-provider op {url} is NIET bereikbaar: {fout}{staart}"


def _basis_opties():
    opties = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # We hebben alleen metadata en ondertitels nodig, geen video-/audio-
        # formaten. Zonder dit breekt "geen formaten beschikbaar" (bij de
        # web-client met cookies) onnodig de ondertitel-extractie af.
        "ignore_no_formats_error": True,
    }
    # PO-token-provider (bgutil) tegen YouTube's botdetectie op server-IP's.
    # Wijst naar een draaiende bgutil-ytdlp-pot-provider-service.
    #
    # Belangrijk: het token wordt alleen daadwerkelijk opgehaald en meegestuurd
    # als (a) de PO-token-fetch geforceerd wordt ("fetch_pot": always) én (b) de
    # web-client wordt gebruikt, die PO-tokens ondersteunt. Zonder deze twee
    # laat yt-dlp op een geblokkeerd datacenter-IP het token liggen en volgt de
    # "Sign in to confirm you're not a bot"-fout.
    pot_url = os.environ.get("POT_PROVIDER_URL")
    if pot_url:
        opties["extractor_args"] = {
            "youtubepot-bgutilhttp": {"base_url": [pot_url.rstrip("/")]},
            "youtube": {
                "fetch_pot": ["always"],
                "player_client": ["web", "default"],
            },
        }
    # Optioneel: al het YouTube-verkeer via een (residentiële) proxy leiden.
    # Meest betrouwbare oplossing als het datacenter-IP geblokkeerd blijft.
    proxy = os.environ.get("YTDLP_PROXY")
    if proxy:
        opties["proxy"] = proxy

    # Optioneel alternatief: cookies meegeven als YouTube het IP toch blokkeert.
    # Voorkeur: YTDLP_COOKIES_B64 (base64 van het cookies.txt-bestand) — dat is
    # één regel zonder tabs/regeleinden en overleeft het plakken in Railway.
    # YTDLP_COOKIES (platte inhoud) blijft als alternatief ondersteund.
    cookies = None
    cookies_b64 = os.environ.get("YTDLP_COOKIES_B64")
    if cookies_b64:
        try:
            cookies = base64.b64decode(cookies_b64).decode("utf-8")
        except Exception:  # noqa: BLE001
            cookies = None
    if cookies is None:
        cookies = os.environ.get("YTDLP_COOKIES")
    if cookies:
        pad = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
        with open(pad, "w", encoding="utf-8", newline="\n") as f:
            f.write(cookies)
        opties["cookiefile"] = pad
    return opties


def basis_opties():
    """Publieke toegang tot de yt-dlp-opties (provider/proxy/cookies) voor hergebruik."""
    return _basis_opties()


def provider_bereikbaar():
    """Is de PO-token-provider ingesteld én bereikbaar? (nodig voor audiodownload)"""
    url = os.environ.get("POT_PROVIDER_URL")
    if not url:
        return False
    try:
        urllib.request.urlopen(url.rstrip("/") + "/ping", timeout=5).read()
        return True
    except Exception:  # noqa: BLE001
        return False


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


def _vind_spraakblokken(entries):
    """Splits het transcript in spraakblokken, gescheiden door muziek/zang.

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
    return blokken


def _vind_preekdelen(entries):
    """Kies de preekdelen en het welkomstblok (waarin de voorganger genoemd wordt).

    De preek is het langste spraakblok. Wordt de preek onderbroken door een
    lied, dan bestaat hij uit meerdere blokken; andere lange blokken die qua
    duur in de buurt van het langste komen tellen daarom mee als preekdeel.
    Korte blokken (gebed, schriftlezing, mededelingen) vallen daarbuiten.
    """
    blokken = _vind_spraakblokken(entries)
    if not blokken:
        raise RuntimeError("Geen bruikbare spraak gevonden in de ondertitels.")

    def duur(blok):
        return blok[-1][0] - blok[0][0]

    langste = max(blokken, key=duur)
    if duur(langste) < MIN_PREEK_SECONDEN:
        # Geen duidelijk preekblok gevonden: geef alles terug en laat het
        # taalmodel de liturgie eromheen negeren.
        alles = [
            (t, s)
            for t, x in entries
            if (s := ANNOTATIE_RE.sub(" ", x).strip())
        ]
        return [alles], None

    grens = max(MIN_DEEL_SECONDEN, MIN_DEEL_AANDEEL * duur(langste))
    delen = [b for b in blokken if duur(b) >= grens]

    # Welkomstblok: het eerste blok van betekenis vóór de preek, waarin de
    # ouderling doorgaans meldt wie er voorgaat. Vereis echte inhoud, zodat
    # flarden uit de intromuziek niet meetellen.
    def woorden(blok):
        return sum(len(t.split()) for _, t in blok)

    welkom = next(
        (
            b
            for b in blokken
            if b[0][0] < delen[0][0][0]
            and duur(b) >= 30
            and woorden(b) >= 40
            and b not in delen
        ),
        None,
    )
    return delen, welkom


MAANDEN = {
    "jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}
DATUM_RE = re.compile(
    r"(\d{1,2})\s+(jan|feb|mrt|apr|mei|jun|jul|aug|sep|okt|nov|dec)\w*\.?\s+(\d{4})",
    re.I,
)
KLOKTIJD_RE = re.compile(r"\b(\d{1,2}:\d{2})\b")


def lijst_diensten(kanaal_url, maximum=120):
    """Alle streams (gepland en al gestreamd) van het kanaal, met datum/tijd uit de titel."""
    opties = _basis_opties()
    opties.update({"extract_flat": "in_playlist", "playlistend": maximum})
    with yt_dlp.YoutubeDL(opties) as ydl:
        info = ydl.extract_info(kanaal_url, download=False)

    diensten = []
    for e in info.get("entries") or []:
        video_id = e.get("id")
        titel = e.get("title") or ""
        if not video_id:
            continue
        diensten.append(
            {
                "id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "titel": titel,
                "label": _label_uit_titel(titel),
                "datum": _datum_uit_titel(titel),
                "tijd": _tijd_uit_titel(titel),
                "gepland": e.get("live_status") == "is_upcoming",
            }
        )
    return diensten


def _datum_uit_titel(titel):
    m = DATUM_RE.search(titel)
    if not m:
        return None
    dag, maand, jaar = int(m.group(1)), MAANDEN[m.group(2).lower()], int(m.group(3))
    return f"{jaar:04d}-{maand:02d}-{dag:02d}"


def _tijd_uit_titel(titel):
    m = KLOKTIJD_RE.search(titel)
    return m.group(1) if m else None


def _label_uit_titel(titel):
    """'NGK Middelharnis - Kerstviering | Ochtenddienst 25 dec 2026 - 10:00' -> 'Kerstviering | Ochtenddienst'."""
    kaal = titel.split(" - ", 1)[-1]
    kaal = DATUM_RE.sub("", kaal)
    kaal = KLOKTIJD_RE.sub("", kaal)
    return kaal.strip(" -|–") or titel


def _fmt(seconden):
    u, rest = divmod(int(seconden), 3600)
    m, s = divmod(rest, 60)
    return f"{u:02d}:{m:02d}:{s:02d}"
