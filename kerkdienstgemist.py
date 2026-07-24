"""Opname-informatie ophalen van Kerkdienstgemist.nl.

Kerkdienstgemist levert via zijn publieke API precies wat we nodig hebben,
netjes gestructureerd:
- de preek-starttijd in seconden (`sermon_start_time`) en de totale duur;
- een HLS-stream waaruit ffmpeg alleen het preekgedeelte kan halen;
- de voorganger (`artist`) en de volledige liturgie (`description`), waaruit we
  het Bijbelgedeelte afleiden.

In tegenstelling tot YouTube is dit een gewone mediasite: geen botblokkade op
datacenter-IP's, dus dit werkt ook gehost zonder proxy.

De API vereist een (anonieme, publieke) Bearer-token die de website zelf
gebruikt; die zit al jaren vast en staat hieronder. Te overschrijven met
KDG_TOKEN als hij ooit verandert.
"""

import json
import os
import re
import urllib.error
import urllib.request

# Anonieme, publieke token uit de frontend (aud: kdgm:anonymous, geen vervaldatum).
STANDAARD_TOKEN = (
    "eyJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJrZGdtIiwiYXVkIjoia2RnbTphbm9ueW1vdXMiLCJpYXQ"
    "iOjE1OTcyMzY5NTcsImp0aSI6ImIzYzIzZWY0OGIxZDc4ZTg3ZWFkNTMyZjg1MWI2MmY1In0."
    "K0eQrCdMN3HDr-ytHECPs3jHDpgfz5IPM2bhJrgbezQ"
)
API = "https://api.kerkdienstgemist.nl/api/v2"

URL_RE = re.compile(r"kerkdienstgemist\.nl/stations/(\d+)/events/recording/(\d+)", re.I)
# Terugval: losse station- en opname-id's ergens in de URL.
STATION_RE = re.compile(r"/stations/(\d+)")
RECORDING_RE = re.compile(r"/recording/(\d+)")

# Liturgie-labels waaruit we het preek-Bijbelgedeelte afleiden (in volgorde
# van voorkeur).
PREEK_LABELS = (
    "verkondiging", "preek", "prediking", "tekst voor de prediking",
    "preektekst", "tekst", "schriftlezing", "bijbellezing", "lezing",
)


def is_kerkdienstgemist(url):
    return "kerkdienstgemist.nl" in (url or "").lower()


def video_id(url):
    """Cache-sleutel zonder API-call (parseert alleen de URL)."""
    station, opname = _ids(url)
    return f"kdg_{station}_{opname}"


def is_kanaal(url):
    """Een station-/kanaal-URL (lijst) i.p.v. een enkele opname."""
    u = (url or "").lower()
    return is_kerkdienstgemist(url) and "/recording/" not in u and "/stations/" in u


def _station_id(url):
    m = STATION_RE.search(url)
    if not m:
        raise RuntimeError("Kon geen station-id uit de Kerkdienstgemist-link halen.")
    return m.group(1)


def lijst_diensten(station_url, maximum=120):
    """Alle (recente) opnames van een station, als klikbare dienst-items."""
    station = _station_id(station_url)
    diensten, page = [], 1
    while len(diensten) < maximum:
        data = _api(f"stations/{station}/recordings?page={page}&size=50")
        recs = data.get("data") or []
        if not recs:
            break
        for r in recs:
            rid = r.get("id")
            a = r.get("attributes") or {}
            if not rid:
                continue
            start = a.get("start_at") or ""
            diensten.append({
                "id": f"kdg_{station}_{rid}",
                "url": f"https://kerkdienstgemist.nl/stations/{station}/events/recording/{rid}",
                "titel": a.get("title") or "Dienst",
                "label": _label(a.get("title")),
                "datum": start[:10] if len(start) >= 10 else None,
                "tijd": start[11:16] if len(start) >= 16 else None,
                "gepland": False,
            })
        if not ((data.get("meta") or {}).get("pagination") or {}).get("next"):
            break
        page += 1
    return diensten[:maximum]


def _label(titel):
    """'Avonddienst | Ds. Willem Jan de Hek | Utrecht' -> 'Avonddienst — Ds. Willem Jan de Hek'."""
    if not titel:
        return "Dienst"
    delen = [d.strip() for d in titel.split("|") if d.strip()]
    if len(delen) >= 2:
        return f"{delen[0]} — {delen[1]}"
    return delen[0] if delen else titel


def _ids(url):
    m = URL_RE.search(url)
    if m:
        return m.group(1), m.group(2)
    ms, mr = STATION_RE.search(url), RECORDING_RE.search(url)
    if ms and mr:
        return ms.group(1), mr.group(1)
    raise RuntimeError(
        "Kon geen station- en opname-id uit de Kerkdienstgemist-link halen."
    )


def _api(pad):
    token = os.environ.get("KDG_TOKEN", STANDAARD_TOKEN)
    req = urllib.request.Request(
        f"{API}/{pad}",
        headers={
            "User-Agent": "Mozilla/5.0 Chrome/126 Safari/537.36",
            "Accept": "application/json",
            "Authorization": "Bearer " + token,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        raise RuntimeError(f"Kerkdienstgemist-API gaf status {e.code}: {body}") from None


def haal_opname(url):
    """Geef alle benodigde opname-informatie terug als dict."""
    station, opname = _ids(url)
    data = _api(f"stations/{station}/recordings/{opname}?include=media")

    attr = (data.get("data") or {}).get("attributes") or {}
    media = None
    for inc in data.get("included") or []:
        if inc.get("type") in ("video_files", "audio_files") and inc.get("attributes"):
            media = inc["attributes"]
            break
    if not media:
        raise RuntimeError("Geen media gevonden voor deze opname.")

    hls = _kies_hls(media.get("sources") or [])
    duur = int(media.get("duration") or 0)
    preek_start = int(media.get("sermon_start_time") or 0)
    if not hls:
        raise RuntimeError("Geen bruikbare (HLS-)stream gevonden voor deze opname.")
    if duur <= 0:
        raise RuntimeError("Onbekende duur voor deze opname.")

    liturgie = _liturgie_tekst(attr.get("description") or "")
    return {
        "video_id": f"kdg_{station}_{opname}",
        "titel": attr.get("title") or "Kerkdienst",
        "start_at": attr.get("start_at"),
        "voorganger": _voorganger(attr.get("artist")),
        "liturgie": liturgie,
        "bijbelgedeelte": _bijbelgedeelte(liturgie),
        "hls_url": hls,
        "download_url": media.get("download_url"),
        "sermon_start": preek_start,
        "duur": duur,
    }


def _kies_hls(sources):
    for s in sources:
        if isinstance(s, dict) and s.get("type") == "hls" and s.get("file"):
            return s["file"]
    # Terugval: een directe mp4-bron.
    for s in sources:
        if isinstance(s, dict) and s.get("type") == "mp4" and s.get("file"):
            return s["file"]
    return None


def _voorganger(artist):
    if not artist:
        return None
    # "Ds. Willem Jan de Hek | Utrecht - Jacobikerk" -> "Ds. Willem Jan de Hek"
    naam = artist.split("|")[0].strip()
    return naam or None


def _liturgie_tekst(beschrijving_html):
    """De liturgie-HTML omzetten naar nette platte tekst (regels behouden)."""
    tekst = re.sub(r"(?i)<br\s*/?>", "\n", beschrijving_html)
    tekst = re.sub(r"(?i)</p>", "\n", tekst)
    tekst = re.sub(r"<[^>]+>", "", tekst)
    tekst = (
        tekst.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        .replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
    )
    regels = [r.strip(" \t-–•").strip() for r in tekst.splitlines()]
    return "\n".join(r for r in regels if r).strip()


def _bijbelgedeelte(liturgie):
    """Leid het preek-Bijbelgedeelte af uit de liturgie."""
    if not liturgie:
        return None
    regels = liturgie.splitlines()
    for label in PREEK_LABELS:
        for regel in regels:
            if regel.lower().startswith(label) or re.match(
                rf"\s*{re.escape(label)}\s*[:\-]", regel, re.I
            ):
                deel = re.split(r"[:\-]", regel, maxsplit=1)
                if len(deel) == 2 and deel[1].strip():
                    return _normaliseer_verwijzing(deel[1])
    return None


def _normaliseer_verwijzing(tekst):
    tekst = tekst.strip().strip(".")
    tekst = tekst.replace("–", "-").replace("—", "-")
    tekst = re.sub(r"\s*:\s*", ":", tekst)
    tekst = re.sub(r"\s*-\s*", "-", tekst)
    tekst = re.sub(r"\s+", " ", tekst)
    return tekst[:120]
