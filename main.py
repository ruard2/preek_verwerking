"""Preekverwerker: YouTube-link in, preekverwerking (weekboekje) uit.

De verwerking duurt enkele minuten, daarom loopt die als achtergrondtaak
en pollt de frontend op /api/status/<id>.
"""

import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from llm import verwerk_preek
from transcript import haal_preek_transcript

app = FastAPI(title="Preekverwerker")

# Eenvoudige takenlijst in het geheugen; volstaat voor één Railway-instantie.
taken = {}


class VerwerkVerzoek(BaseModel):
    url: str


def _voer_taak_uit(taak_id, url):
    taak = taken[taak_id]
    try:
        preek, meta = haal_preek_transcript(
            url, voortgang=lambda stap: taak.update(stap=stap)
        )
        taak["meta"] = meta
        taak["stap"] = (
            f"Preek gevonden ({meta['preek_start']}–{meta['preek_einde']}, "
            f"±{meta['duur_minuten']} min). Verwerken met AI — dit kan enkele "
            "minuten duren..."
        )
        taak["resultaat"] = verwerk_preek(preek)
        taak["status"] = "klaar"
    except Exception as fout:  # noqa: BLE001 — alles netjes aan de gebruiker melden
        taak["status"] = "fout"
        taak["fout"] = str(fout)


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
