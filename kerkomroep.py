"""Uitzendingen ophalen van Kerkomroep.nl.

De site is een SPA met een eenvoudige publieke API: één POST naar
`/v1/getstreams/` met {"id": "<kerk-id>"} geeft alle uitzendingen, elk met datum,
tijd, tijdsduur en een directe mp3-download-URL. Er is geen preek-startmarkering,
dus we transcriberen de hele dienst en laten het model de preek eruit halen.
"""

import json
import re
import urllib.request

BASE = "https://kerkomroep.nl/v1"
KERK_RE = re.compile(r"kerkomroep\.nl/kerken/(\d+)", re.I)
AUDIO_RE = re.compile(r"/audio/(\d+)")


def is_kerkomroep(url):
    return "kerkomroep.nl" in (url or "").lower()


def is_kanaal(url):
    u = (url or "").lower()
    return is_kerkomroep(url) and "/kerken/" in u and "/audio/" not in u


def _kerk_id(url):
    m = KERK_RE.search(url or "")
    if not m:
        raise RuntimeError("Kon geen kerk-id uit de Kerkomroep-link halen.")
    return m.group(1)


def video_id(url):
    kerk = _kerk_id(url)
    m = AUDIO_RE.search(url or "")
    return f"ko_{kerk}_{m.group(1)}" if m else f"ko_{kerk}"


def _post(pad, body):
    req = urllib.request.Request(
        f"{BASE}/{pad}",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 Chrome/126 Safari/537.36",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _streams(kerk_id):
    data = _post("getstreams/", {"id": str(kerk_id)})
    return data if isinstance(data, list) else (data.get("streams") or data.get("data") or [])


def lijst_diensten(kanaal_url, maximum=120):
    kerk = _kerk_id(kanaal_url)
    diensten = []
    for s in _streams(kerk)[:maximum]:
        sid = str(s.get("stream_id") or "")
        if not sid:
            continue
        datum = s.get("datum") or None
        diensten.append({
            "id": f"ko_{kerk}_{sid}",
            "url": f"https://kerkomroep.nl/kerken/{kerk}/audio/{sid}",
            "titel": f"Uitzending {datum or ''} {(s.get('tijd') or '')[:5]}".strip(),
            "label": f"Uitzending {(s.get('tijd') or '')[:5]}".strip(),
            "datum": datum,
            "tijd": (s.get("tijd") or "")[:5] or None,
            "gepland": bool(s.get("is_live")),
        })
    return diensten


def haal_opname(url):
    """Geef de mp3-URL en duur van één uitzending terug (voor de audio-pijplijn)."""
    kerk = _kerk_id(url)
    m = AUDIO_RE.search(url or "")
    if not m:
        raise RuntimeError("Geen uitzending-id in de Kerkomroep-link.")
    sid = m.group(1)
    stream = next((s for s in _streams(kerk) if str(s.get("stream_id")) == sid), None)
    if not stream:
        raise RuntimeError("Deze uitzending is niet (meer) gevonden bij Kerkomroep.")
    mp3 = stream.get("audio_download_url") or stream.get("audio_url")
    if not mp3 or not stream.get("audio_openbaar", True):
        raise RuntimeError("Voor deze uitzending is geen openbare audio beschikbaar.")
    datum = stream.get("datum")
    return {
        "video_id": f"ko_{kerk}_{sid}",
        "titel": f"Uitzending {datum or ''} {(stream.get('tijd') or '')[:5]}".strip(),
        "mp3_url": mp3,
        "duur": int(stream.get("tijdsduur") or 0),
        "datum": datum,
        "voorganger": None,
        "liturgie": "",
        "bijbelgedeelte": None,
    }
