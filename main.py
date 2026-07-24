"""Preekverwerker: kies een dienst, krijg een weekboekje (samenvatting + 7 dagen).

De verwerking duurt enkele minuten, daarom loopt die als achtergrondtaak en
pollt de frontend op /api/status/<id>. Resultaten worden per video op schijf
bewaard (store.py): een dienst wordt maar één keer verwerkt.
"""

import os
import re
import threading
import uuid

from dotenv import load_dotenv

load_dotenv()  # leest een .env-bestand in de projectmap (lokaal gebruik)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

import yt_dlp

import render
import store
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

app = FastAPI(title="Preekverwerker")

KANAAL_URL = os.environ.get(
    "KANAAL_URL", "https://www.youtube.com/@GKvMiddelharnis_HetBaken/streams"
)

VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/live/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")

# Takenlijst in het geheugen (kortlevend, alleen voor de voortgang tijdens één
# verwerking). De uiteindelijke resultaten leven persistent in store.
taken = {}


class VerwerkVerzoek(BaseModel):
    url: str


def _video_id(url):
    m = VIDEO_ID_RE.search(url or "")
    return m.group(1) if m else None


def _met_labels(data):
    """Voeg de taal-specifieke kopjes toe voor de frontend (kopie; de opgeslagen
    data blijft schoon zodat labels na een code-update niet verouderen)."""
    verrijkt = dict(data)
    verrijkt["_labels"] = render.labels(data.get("taal"))
    return verrijkt


def _titel_uit_cache(url):
    """Titel van de dienst uit de (persistente) dienstenlijst, zodat we geen
    geblokkeerde yt-dlp-info-call nodig hebben."""
    vid = _video_id(url)
    lijst, _ = store.diensten_ophalen()
    if not vid or not lijst:
        return None
    for d in lijst:
        if d.get("id") == vid:
            return d.get("titel")
    return None


def _voer_taak_uit(taak_id, url):
    taak = taken[taak_id]

    def meld(stap):
        taak["stap"] = stap

    try:
        vid = _video_id(url)

        # 1. Al eerder verwerkt? Dan meteen uit de cache.
        if vid:
            bewaard = store.resultaat_ophalen(vid)
            if bewaard and bewaard.get("data"):
                taak["meta"] = bewaard.get("meta")
                taak["resultaat"] = {
                    "data": _met_labels(bewaard["data"]),
                    "tekst": bewaard.get("tekst") or render.naar_tekst(bewaard["data"]),
                    "video_id": vid,
                }
                taak["stap"] = "Uit opslag geladen."
                taak["status"] = "klaar"
                return

        # 2. Transcriptbron kiezen:
        # - Supadata (gehost): haalt de YouTube-transcriptie op zonder dat het
        #   datacenter-IP geblokkeerd wordt. Taal wordt automatisch gedetecteerd.
        # - Lokaal (yt-dlp): ondertitels + eventueel audio via OpenAI (Whisper).
        if supadata.beschikbaar():
            entries, taal = supadata.haal_transcript(url, voortgang=meld)
            titel = _titel_uit_cache(url) or "YouTube-dienst"
            meld("Preekgedeelte zoeken...")
            seg = ts.segmenteer(entries, titel=titel, taal=taal or "nl")
            taal_hint = taal
        else:
            seg = haal_preek_segmentatie(url, voortgang=meld)
            taal_hint = (seg["meta"].get("taal") or "nl").split("-")[0]

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
        data = verwerk_preek(transcript, seg["welkom"], taal_hint=taal_hint)
        tekst = render.naar_tekst(data)

        taak["resultaat"] = {"data": _met_labels(data), "tekst": tekst, "video_id": vid}
        taak["status"] = "klaar"

        # 3. Permanent bewaren zodat deze dienst nooit opnieuw verwerkt hoeft.
        if vid:
            store.resultaat_opslaan(
                vid,
                {"data": data, "tekst": tekst, "meta": meta,
                 "ondertitel": meta.get("titel")},
            )
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
        "data_map": store.DATA_DIR,
    }


@app.get("/api/diensten")
def diensten(vernieuw: bool = False):
    """Persistente dienstenlijst; ververst één keer per week (na zondag)."""
    lijst, vers = store.diensten_ophalen()
    if vernieuw or not vers:
        try:
            nieuw = lijst_diensten(KANAAL_URL)
            store.diensten_opslaan(nieuw)
            lijst = nieuw
        except Exception as fout:  # noqa: BLE001
            if not lijst:
                raise HTTPException(
                    502, f"De dienstenlijst kon niet worden opgehaald: {fout}"
                )
            # Verouderde lijst is beter dan geen lijst.
    return lijst


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


def _pdf_bestandsnaam(data):
    naam = re.sub(r"[^\w\- ]", "", (data.get("titel") or "preekverwerking")).strip()
    naam = re.sub(r"\s+", "-", naam) or "preekverwerking"
    return f"{naam[:80]}.pdf"


@app.get("/api/pdf/{video_id}")
def pdf(video_id: str):
    bewaard = store.resultaat_ophalen(video_id)
    if not bewaard or not bewaard.get("data"):
        raise HTTPException(404, "Voor deze dienst is nog geen verwerking beschikbaar.")
    data = bewaard["data"]
    inhoud = render.naar_pdf(data, ondertitel=bewaard.get("ondertitel"))
    return Response(
        content=inhoud,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{_pdf_bestandsnaam(data)}"'
        },
    )


@app.get("/")
def index():
    # no-cache: de browser haalt na een update altijd de nieuwste pagina op
    # (voorkomt dat een oude versie blijft hangen na een deploy).
    return FileResponse(
        "static/index.html", headers={"Cache-Control": "no-cache"}
    )
