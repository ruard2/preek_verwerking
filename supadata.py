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
import os
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("SUPADATA_BASE", "https://api.supadata.ai/v1")
OFFSET_DELER = float(os.environ.get("SUPADATA_OFFSET_DELER", "1000"))
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


def haal_transcript(url, taal=None, voortgang=None):
    """Haal de transcriptie op.

    Geeft (entries, taal) terug, waarbij entries = [(seconden, tekst), ...] en
    taal de ISO-code is die Supadata detecteerde. Wordt `taal` niet opgegeven,
    dan levert Supadata de oorspronkelijke taal van de video — zo krijgen we
    een Afrikaanse preek in het Afrikaans, een Engelse in het Engels, enz.
    """

    def meld(s):
        if voortgang:
            voortgang(s)

    meld("Transcript opvragen bij Supadata...")
    params = {"url": url, "text": "false"}
    if taal:
        params["lang"] = taal
    data = _get("transcript", params)

    # Langere video's kunnen asynchroon verwerkt worden: dan komt er een jobId
    # terug die we pollen tot de transcriptie klaar is.
    job = data.get("jobId") or data.get("id")
    if job and "content" not in data and "transcript" not in data:
        for _ in range(60):
            time.sleep(3)
            meld("Wachten op de transcriptie (Supadata)...")
            data = _get(f"transcript/{job}", None)
            status = str(data.get("status", "")).lower()
            if "content" in data or "transcript" in data or status in (
                "completed", "complete", "done", "success", "succeeded",
            ):
                break
            if status in ("failed", "error", "errored"):
                raise RuntimeError(
                    "Supadata kon de transcriptie niet maken: "
                    + str(data.get("error", "onbekende fout"))
                )

    inhoud = data.get("content")
    if inhoud is None:
        inhoud = data.get("transcript")
    if inhoud is None:
        raise RuntimeError(
            "Onverwacht antwoord van Supadata (geen transcriptie): "
            + ", ".join(list(data)[:8])
        )

    entries = _naar_entries(inhoud)
    if not entries:
        raise RuntimeError("Supadata gaf een lege transcriptie terug.")
    gedetecteerd = (data.get("lang") or taal or "").split("-")[0].lower() or None
    return entries, gedetecteerd


def _naar_entries(inhoud):
    """Zet Supadata-content om naar [(seconden, tekst)]."""
    if isinstance(inhoud, str):
        # Geen tijdcodes: alles als één regel (preekdetectie valt dan terug op
        # 'alles is preek', wat het taalmodel verder afhandelt).
        tekst = inhoud.strip()
        return [(0, tekst)] if tekst else []

    entries = []
    for seg in inhoud:
        if not isinstance(seg, dict):
            continue
        tekst = (seg.get("text") or seg.get("content") or "").strip()
        if not tekst:
            continue
        rauw = seg.get("offset")
        if rauw is None:
            rauw = seg.get("start")
        try:
            sec = int(float(rauw) / OFFSET_DELER) if rauw is not None else 0
        except (TypeError, ValueError):
            sec = 0
        entries.append((sec, tekst))
    return entries
