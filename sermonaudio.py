"""Preken ophalen van SermonAudio.com via de publieke v2-API.

SermonAudio's site (React-SPA) en RSS zijn bot-beschermd, maar de gedocumenteerde
API werkt server-side met een API-sleutel (`X-API-Key`). Een gratis sleutel is aan
te vragen op sermonaudio.com; zet die als omgevingsvariabele SERMONAUDIO_API_KEY.

Er is geen preek-markering in de audio, dus de hele preek-mp3 wordt
getranscribeerd (SermonAudio-preken zijn doorgaans al alleen de preek).
"""

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.sermonaudio.com/v2"
BROADCASTER_RE = re.compile(r"sermonaudio\.com/broadcasters/([A-Za-z0-9_.-]+)", re.I)
SERMON_RE = re.compile(r"sermonaudio\.com/(?:sermons|sermoninfo)[/?=]+(\d+)", re.I)
SID_RE = re.compile(r"[?&](?:SID|sermonID)=(\d+)", re.I)


def is_sermonaudio(url):
    return "sermonaudio.com" in (url or "").lower()


def _sermon_id(url):
    for rx in (SERMON_RE, SID_RE):
        m = rx.search(url or "")
        if m:
            return m.group(1)
    return None


def is_kanaal(url):
    return is_sermonaudio(url) and _sermon_id(url) is None and "/broadcasters/" in (url or "").lower()


def _broadcaster_id(url):
    m = BROADCASTER_RE.search(url or "")
    if not m:
        raise RuntimeError("Kon geen SermonAudio-broadcaster uit de link halen.")
    return m.group(1)


def video_id(url):
    sid = _sermon_id(url)
    if sid:
        return f"sa_{sid}"
    return f"sa_{_broadcaster_id(url)}"


def _key():
    k = os.environ.get("SERMONAUDIO_API_KEY")
    if not k:
        raise RuntimeError(
            "SERMONAUDIO_API_KEY is niet ingesteld. Vraag een gratis API-sleutel aan "
            "op sermonaudio.com en zet die als omgevingsvariabele."
        )
    return k


def _get(pad, params=None):
    url = f"{API}/{pad}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "X-API-Key": _key(),
            "Accept": "application/json",
            "User-Agent": "AfterSermon/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:200]
        raise RuntimeError(f"SermonAudio-API gaf status {e.code}: {body}") from None


def _mp3_en_duur(sermon):
    media = (sermon.get("media") or {}).get("audio") or []
    for m in media:
        url = m.get("downloadURL") or m.get("streamURL") or m.get("url")
        if url:
            return url, int(m.get("duration") or sermon.get("durationSeconds") or 0)
    return None, int(sermon.get("durationSeconds") or 0)


def _dienst(sermon, broadcaster):
    sid = str(sermon.get("sermonID") or "")
    datum = (sermon.get("preachDate") or "")[:10] or None
    titel = sermon.get("displayTitle") or sermon.get("fullTitle") or "Preek"
    spreker = ((sermon.get("speaker") or {}).get("displayName")) or None
    return {
        "id": f"sa_{sid}",
        "url": f"https://www.sermonaudio.com/sermons/{sid}/",
        "titel": titel,
        "label": titel + (f" — {spreker}" if spreker else ""),
        "datum": datum,
        "tijd": None,
        "gepland": False,
    }


def lijst_diensten(kanaal_url, maximum=25):
    broadcaster = _broadcaster_id(kanaal_url)
    data = _get("node/sermons", {
        "broadcasterID": broadcaster, "sortBy": "newest", "pageSize": maximum,
    })
    resultaten = data.get("results") or data.get("nodes") or []
    return [_dienst(s, broadcaster) for s in resultaten if s.get("sermonID")]


def haal_opname(url):
    sid = _sermon_id(url)
    if not sid:
        raise RuntimeError("Geen preek-id in de SermonAudio-link.")
    sermon = _get(f"node/sermons/{sid}")
    if "sermonID" not in sermon and sermon.get("results"):
        sermon = sermon["results"][0]
    mp3, duur = _mp3_en_duur(sermon)
    if not mp3:
        raise RuntimeError("Voor deze preek is geen audio-download beschikbaar.")
    spreker = ((sermon.get("speaker") or {}).get("displayName")) or None
    return {
        "video_id": f"sa_{sid}",
        "titel": sermon.get("displayTitle") or sermon.get("fullTitle") or "Preek",
        "mp3_url": mp3,
        "duur": duur,
        "datum": (sermon.get("preachDate") or "")[:10] or None,
        "voorganger": spreker,
        "bijbelgedeelte": sermon.get("bibleText") or None,
        "liturgie": "",
    }
