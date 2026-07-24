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


def beschikbaar():
    return bool(os.environ.get("SUPADATA_API_KEY"))


def diagnose():
    if not beschikbaar():
        return "SUPADATA_API_KEY niet ingesteld — Supadata wordt niet gebruikt."
    return f"Supadata ingesteld (API-basis {BASE})."


def _get(pad, params):
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
        raise RuntimeError(f"Supadata-API gaf status {e.code}: {body}") from None


def haal_transcript(url, taal="nl", voortgang=None):
    """Geeft de transcriptie als lijst [(seconden, tekst), ...] terug."""

    def meld(s):
        if voortgang:
            voortgang(s)

    meld("Transcript opvragen bij Supadata...")
    data = _get("transcript", {"url": url, "lang": taal, "text": "false"})

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
    return entries


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
