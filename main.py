"""Preekverwerker: YouTube-link in, preekverwerking (weekboekje) uit.

De verwerking duurt enkele minuten, daarom loopt die als achtergrondtaak
en pollt de frontend op /api/status/<id>.
"""

import os
import re
import threading
import time
import uuid

from dotenv import load_dotenv

load_dotenv()  # leest een .env-bestand in de projectmap (lokaal gebruik)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import yt_dlp

import supadata
import transcript as ts
from audio import transcribeer_preek
from llm import verwerk_preek
from transcript import (
    haal_preek_segmentatie,
    lijst_diensten,
    pot_provider_diagnose,
    provider_bereikbaar,
)

VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/live/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")


def _video_id(url):
    m = VIDEO_ID_RE.search(url)
    return m.group(1) if m else None


def _titel_uit_cache(url):
    """Zoek de titel van de dienst in de (op Railway wél werkende) dienstenlijst,
    zodat we geen geblokkeerde yt-dlp-info-call nodig hebben."""
    vid = _video_id(url)
    data = _diensten_cache.get("data")
    if not vid or not data:
        return None
    for d in data:
        if d.get("id") == vid:
            return d.get("titel")
    return None

app = FastAPI(title="Preekverwerker")

KANAAL_URL = os.environ.get(
    "KANAAL_URL", "https://www.youtube.com/@GKvMiddelharnis_HetBaken/streams"
)
DIENSTEN_CACHE_SECONDEN = 600

# Eenvoudige takenlijst in het geheugen; volstaat voor één Railway-instantie.
taken = {}
_diensten_cache = {"tijd": 0.0, "data": None}


class VerwerkVerzoek(BaseModel):
    url: str


def _voer_taak_uit(taak_id, url):
    taak = taken[taak_id]

    def meld(stap):
        taak["stap"] = stap

    try:
        # Transcriptbron kiezen:
        # - Supadata (gehost): haalt de YouTube-transcriptie op zonder dat het
        #   datacenter-IP geblokkeerd wordt. Geen audio/Whisper-stap.
        # - Lokaal (yt-dlp): ondertitels + eventueel audio via OpenAI (Whisper).
        if supadata.beschikbaar():
            entries = supadata.haal_transcript(url, voortgang=meld)
            titel = _titel_uit_cache(url) or "YouTube-dienst"
            meld("Preekgedeelte zoeken...")
            seg = ts.segmenteer(entries, titel=titel)
        else:
            seg = haal_preek_segmentatie(url, voortgang=meld)

        meta = seg["meta"]
        taak["meta"] = meta
        delen = f", {meta['delen']} delen" if meta.get("delen", 1) > 1 else ""
        gevonden = (
            f"Preek gevonden ({meta['preek_start']}–{meta['preek_einde']}"
            f"{delen}, ±{meta['duur_minuten']} min). "
        )

        transcript = seg["ondertitel_tekst"]
        if supadata.beschikbaar():
            bron = "YouTube-ondertitels via Supadata"
        else:
            # Lokaal: bij voorkeur audio via OpenAI (betere kwaliteit),
            # anders de ondertitels. Valt automatisch terug.
            bron = "ondertitels"
            if provider_bereikbaar():
                try:
                    meld(gevonden + "Audio ophalen en transcriberen...")
                    transcript = transcribeer_preek(
                        url, seg["tijden"], voortgang=meld
                    )
                    bron = "audio (OpenAI-transcriptie)"
                except Exception:  # noqa: BLE001 — terugval op ondertitels
                    transcript = seg["ondertitel_tekst"]
                    bron = "ondertitels (audio niet beschikbaar)"
        meta["transcriptie_bron"] = bron

        meld(gevonden + f"Bron: {bron}. Verwerken met AI — dit kan enkele "
             "minuten duren...")
        taak["resultaat"] = verwerk_preek(transcript, seg["welkom"])
        taak["status"] = "klaar"
    except Exception as fout:  # noqa: BLE001 — alles netjes aan de gebruiker melden
        melding = str(fout)
        if "not a bot" in melding or "Sign in to confirm" in melding:
            melding += "\n\nDiagnose: " + pot_provider_diagnose()
        taak["status"] = "fout"
        taak["fout"] = melding


@app.get("/api/diagnose")
def diagnose():
    return {
        "yt_dlp_versie": yt_dlp.version.__version__,
        "transcript_bron": (
            "Supadata" if supadata.beschikbaar() else "yt-dlp (lokaal)"
        ),
        "supadata": supadata.diagnose(),
        "pot_provider": pot_provider_diagnose(),
        "openai_sleutel_ingesteld": bool(os.environ.get("OPENAI_API_KEY")),
    }


@app.get("/api/diensten")
def diensten(vernieuw: bool = False):
    nu = time.time()
    verouderd = nu - _diensten_cache["tijd"] > DIENSTEN_CACHE_SECONDEN
    if _diensten_cache["data"] is None or verouderd or vernieuw:
        try:
            _diensten_cache["data"] = lijst_diensten(KANAAL_URL)
            _diensten_cache["tijd"] = nu
        except Exception as fout:  # noqa: BLE001
            if _diensten_cache["data"] is None:
                raise HTTPException(
                    502, f"De dienstenlijst kon niet worden opgehaald: {fout}"
                )
            # Verouderde lijst is beter dan geen lijst.
    return _diensten_cache["data"]


@app.post("/api/verwerk")
def start_verwerking(verzoek: VerwerkVerzoek):
    url = verzoek.url.strip()
    if "youtube.com/" not in url and "youtu.be/" not in url:
        raise HTTPException(400, "Geef een geldige YouTube-link op.")
    taak_id = uuid.uuid4().hex
    taken[taak_id] = {
        "status": "bezig",
        "stap": "Starten...",
        "resultaat": None,
        "fout": None,
        "meta": None,
    }
    threading.Thread(target=_voer_taak_uit, args=(taak_id, url), daemon=True).start()
    return {"taak_id": taak_id}


@app.get("/api/status/{taak_id}")
def status(taak_id: str):
    taak = taken.get(taak_id)
    if taak is None:
        raise HTTPException(404, "Onbekende taak.")
    return taak


@app.get("/")
def index():
    return FileResponse("static/index.html")
