"""Transcript ophalen via de Supadata-API.

Supadata is een kant-en-klare dienst die de YouTube-transcriptie ophaalt en
YouTube's datacenter-IP-blokkade aan hún kant oplost (eigen proxy's). Zo werkt
de app ook gehost (bijv. op Railway) zonder eigen proxy of cookies. De gratis
tier volstaat voor een kerk met enkele diensten per week.

We vragen de transcriptie mét tijdcodes (segmenten) op, zodat de bestaande
preekdetectie (op basis van [muziek]-markeringen) blijft werken.

Instellingen (omgevingsvariabelen):
- SUPADATA_API_KEY      : verplicht om deze bron te gebruiken.
- SUPADATA_BASE         : API-basis, standaard https://api.supadata.ai/v1
- SUPADATA_OFFSET_DELER : deler om tijdcodes naar seconden te brengen
                          (standaard 1000, want Supadata geeft milliseconden).
"""

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request

_log = logging.getLogger("aftersermon.supadata")

BASE = os.environ.get("SUPADATA_BASE", "https://api.supadata.ai/v1")
OFFSET_DELER = float(os.environ.get("SUPADATA_OFFSET_DELER", "1000"))
# Video's > 20 min verwerkt Supadata asynchroon (HTTP 202 + jobId); we pollen tot
# de transcriptie klaar is. Een lange preek kan minuten duren — ruim budget nemen.
JOB_TIMEOUT = float(os.environ.get("SUPADATA_JOB_TIMEOUT", "900"))  # seconden
POLL_INTERVAL = float(os.environ.get("SUPADATA_POLL_INTERVAL", "5"))  # seconden
# native = alleen bestaande ondertitels, auto = ondertitels of anders AI-genereren,
# generate = altijd AI-transcriptie uit de audio.
MODE = os.environ.get("SUPADATA_MODE", "auto")
# Aantal recente video's dat de fallback-kanaallijst ophaalt. Elke video kost
# één API-call (de batch-endpoint zit niet in de gratis tier), dus beperkt.
KANAAL_MAX = int(os.environ.get("SUPADATA_KANAAL_MAX", "20"))


def beschikbaar():
    return bool(os.environ.get("SUPADATA_API_KEY"))


def diagnose():
    if not beschikbaar():
        return "SUPADATA_API_KEY niet ingesteld — Supadata wordt niet gebruikt."
    return f"Supadata ingesteld (API-basis {BASE})."


_laatste_quota_alert = [0.0]


def _meld_quota_op():
    """Stuur (hoogstens 1x per 12 uur) een mail dat de Supadata-quota op is."""
    nu = time.time()
    if nu - _laatste_quota_alert[0] < 12 * 3600:
        return
    _laatste_quota_alert[0] = nu
    try:
        import brevo

        naar = os.environ.get("ALERT_EMAIL", "ruard.stolper@gmail.com")
        brevo.verzend(
            naar,
            "AfterSermon: Supadata-quota is op",
            "<p>De Supadata-quota is bereikt (429, limit-exceeded).</p>"
            "<p>YouTube-verwerking op de server werkt niet tot de quota reset "
            "(maandelijks) of je het plan verhoogt. Kerkomroep, Kerkdienstgemist "
            "en het uploaden van een preek (document of audio) werken gewoon door.</p>",
            tekst="Supadata-quota is op (429). YouTube-verwerking gehost werkt niet "
            "tot reset/upgrade; andere bronnen werken door.",
        )
    except Exception:  # noqa: BLE001 — melden mag nooit iets breken
        pass


def _get(pad, params, _herkansing=True):
    url = f"{BASE.rstrip('/')}/{pad.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "x-api-key": os.environ.get("SUPADATA_API_KEY", ""),
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        if e.code == 429:
            if "limit-exceeded" in body or "usage limit" in body.lower():
                _meld_quota_op()  # maandquota op: melden en direct stoppen
                raise RuntimeError(f"Supadata-quota op (429): {body}") from None
            if _herkansing:  # tijdelijke rate limit: even wachten en 1x opnieuw
                time.sleep(5)
                return _get(pad, params, _herkansing=False)
        raise RuntimeError(f"Supadata-API gaf status {e.code}: {body}") from None


def video_datum(video_id):
    """Uploaddatum (YYYY-MM-DD) van één video via Supadata, of None."""
    if not video_id:
        return None
    try:
        v = _get("youtube/video", {"id": video_id})
    except RuntimeError:
        return None
    return (v.get("uploadDate") or "")[:10] or None


def lijst_kanaal(kanaal_url, maximum=None, voortgang=None):
    """Fallback-dienstenlijst via Supadata (als yt-dlp geblokkeerd wordt).

    Haalt de recentste video-id's van het kanaal op en per video de metadata
    (titel, uploaddatum). Beperkt tot KANAAL_MAX video's, want elke video kost
    één API-call. Geeft dezelfde dict-structuur terug als transcript.lijst_diensten.
    """
    from datetime import date

    import transcript as ts  # hergebruik de titel-parsers; geen kringverwijzing

    def meld(s):
        if voortgang:
            voortgang(s)

    maximum = maximum or KANAAL_MAX
    meld("Kanaallijst ophalen via Supadata...")
    data = _get("youtube/channel/videos", {"id": kanaal_url, "limit": maximum})
    ids = (data.get("videoIds") or []) + (data.get("liveIds") or [])
    ids = ids[:maximum]

    vandaag = date.today().isoformat()
    diensten = []
    for i, vid in enumerate(ids):
        meld(f"Dienst {i + 1}/{len(ids)} ophalen (Supadata)...")
        try:
            v = _get("youtube/video", {"id": vid})
        except RuntimeError:
            continue  # één mislukte video mag de hele lijst niet breken
        titel = v.get("title") or ""
        datum = ts._datum_uit_titel(titel) or (v.get("uploadDate") or "")[:10] or None
        diensten.append(
            {
                "id": vid,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "titel": titel,
                "label": ts._label_uit_titel(titel),
                "datum": datum,
                "tijd": ts._tijd_uit_titel(titel),
                # Toekomstige datum of live-aankondiging = nog niet gestreamd.
                "gepland": bool(datum and datum > vandaag) or bool(v.get("isLive")),
            }
        )
        if i + 1 < len(ids):
            time.sleep(1.2)  # de gratis tier heeft een strakke rate limit
    return diensten


def _transcript_eenmalig(url, taal, meld, mode):
    """Eén transcript-verzoek (met async-polling). Geeft (entries, lang, data).

    `mode`: native | auto | generate (zie Supadata-docs). Bij lege inhoud geeft
    dit ([], lang, data) terug — de aanroeper beslist over een herkansing.
    """
    meld(f"Transcript opvragen bij Supadata (mode={mode})...")
    params = {"url": url, "text": "false", "mode": mode}
    if taal:
        params["lang"] = taal
    data = _get("transcript", params)

    # Video's > 20 min: Supadata antwoordt met HTTP 202 + {"jobId": ...}. We pollen
    # /transcript/{jobId} tot status "completed" (dan zit "content" erbij). Zolang de
    # job "queued"/"active" is komt er alléén een status-veld terug; dat is normaal.
    job = data.get("jobId") or data.get("id")
    if job and "content" not in data and "transcript" not in data:
        verstreken = 0.0
        status = ""
        while verstreken < JOB_TIMEOUT:
            time.sleep(POLL_INTERVAL)
            verstreken += POLL_INTERVAL
            data = _get(f"transcript/{job}", None)
            status = str(data.get("status", "")).lower()
            if "content" in data or "transcript" in data or status in (
                "completed", "complete", "done", "success", "succeeded",
            ):
                break
            if status in ("failed", "error", "errored"):
                fout = data.get("error") or "onbekende fout"
                if not isinstance(fout, str):
                    fout = json.dumps(fout, ensure_ascii=False)
                raise RuntimeError("Supadata kon de transcriptie niet maken: " + fout)
            meld(f"Transcriberen bij Supadata... (±{int(verstreken)}s, status: {status or 'bezig'})")
        else:
            raise RuntimeError(
                f"Supadata is na {int(JOB_TIMEOUT)}s nog bezig met transcriberen "
                f"(status: {status or 'onbekend'}). Probeer het later opnieuw, of "
                "verwerk deze preek via een upload (document/audio)."
            )

    inhoud = data.get("content")
    if inhoud is None:
        inhoud = data.get("transcript")
    entries = _naar_entries(inhoud) if inhoud is not None else []
    lang = (data.get("lang") or taal or "").split("-")[0].lower() or None
    return entries, lang, data


def haal_transcript(url, taal=None, voortgang=None):
    """Haal de transcriptie op.

    Geeft (entries, taal) terug, waarbij entries = [(seconden, tekst), ...] en
    taal de ISO-code is die Supadata detecteerde. Wordt `taal` niet opgegeven,
    dan levert Supadata de oorspronkelijke taal van de video.

    Standaard `auto`: eerst de bestaande YouTube-ondertitels, anders zelf uit de
    audio genereren. Levert dat tóch niets op (bijv. een lege captions-track bij
    livestreams), dan forceren we één herkansing met `generate` (AI-transcriptie).
    """

    def meld(s):
        if voortgang:
            voortgang(s)

    modi = [MODE]
    if MODE != "generate":
        modi.append("generate")  # herkansing als 'auto/native' leeg blijft

    laatste = None
    for i, mode in enumerate(modi):
        if i > 0:
            meld("Geen bruikbare ondertitels; transcript uit de audio genereren...")
        entries, lang, data = _transcript_eenmalig(url, taal, meld, mode)
        laatste = (data, mode)
        if entries:
            return entries, lang

    data, mode = laatste
    _log.warning(
        "Supadata lege transcriptie (modi=%s): response-velden=%s, snippet=%s",
        modi, list(data)[:8], repr(data.get("content") or data.get("transcript"))[:400],
    )
    raise RuntimeError(
        "Supadata gaf een lege transcriptie terug. Deze dienst heeft (nog) geen "
        "bruikbare ondertitels én kon niet uit de audio worden getranscribeerd. "
        "Probeer een andere dienst, of upload de preek als document of audio."
    )


def _naar_entries(inhoud):
    """Zet Supadata-content om naar [(seconden, tekst)]. Tolerant voor vormvarianten."""
    # Soms zit de eigenlijke lijst/tekst genest onder een sleutel.
    if isinstance(inhoud, dict):
        for sleutel in ("content", "segments", "chunks", "transcript", "data", "items"):
            deel = inhoud.get(sleutel)
            if isinstance(deel, (list, str)):
                return _naar_entries(deel)
        return []
    if isinstance(inhoud, str):
        # Geen tijdcodes: alles als één regel (preekdetectie valt dan terug op
        # 'alles is preek', wat het taalmodel verder afhandelt).
        tekst = inhoud.strip()
        return [(0, tekst)] if tekst else []

    entries = []
    losse_tekst = []
    for seg in inhoud:
        if isinstance(seg, str):  # lijst van kale regels zonder tijdcodes
            s = seg.strip()
            if s:
                losse_tekst.append(s)
            continue
        if not isinstance(seg, dict):
            continue
        tekst = (seg.get("text") or seg.get("content") or seg.get("snippet") or "").strip()
        if not tekst:
            continue
        rauw = seg.get("offset")
        for k in ("start", "startTime", "begin", "from", "startMs", "start_ms"):
            if rauw is None:
                rauw = seg.get(k)
        try:
            sec = int(float(rauw) / OFFSET_DELER) if rauw is not None else 0
        except (TypeError, ValueError):
            sec = 0
        entries.append((sec, tekst))
    if not entries and losse_tekst:  # lijst van kale regels: alles als één blok
        return [(0, "\n".join(losse_tekst))]
    return entries
