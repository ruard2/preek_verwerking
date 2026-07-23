"""Preekverwerker: YouTube-link in, preekverwerking (weekboekje) uit.

De verwerking duurt enkele minuten, daarom loopt die als achtergrondtaak
en pollt de frontend op /api/status/<id>.
"""

import os
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

import yt_dlp

from llm import verwerk_preek
from transcript import haal_preek_transcript, lijst_diensten, pot_provider_diagnose

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
    try:
        preek, welkom, meta = haal_preek_transcript(
            url, voortgang=lambda stap: taak.update(stap=stap)
        )
        taak["meta"] = meta
        delen = f", {meta['delen']} delen" if meta.get("delen", 1) > 1 else ""
        taak["stap"] = (
            f"Preek gevonden ({meta['preek_start']}–{meta['preek_einde']}"
            f"{delen}, ±{meta['duur_minuten']} min). Verwerken met AI — dit "
            "kan enkele minuten duren..."
        )
        taak["resultaat"] = verwerk_preek(preek, welkom)
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
