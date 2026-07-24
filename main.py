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

import audio
import kerkdienstgemist
import render
import store
import supadata
import transcript as ts
from audio import transcribeer_preek
from llm import verwerk_preek
from llm import normaliseer as llm_normaliseer
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
    herverwerk: bool = False


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
    """Titel van de dienst uit de gecachete kanaallijsten (geen yt-dlp-call)."""
    vid = _video_id(url)
    return store.zoek_dienst_titel(vid) if vid else None


def _classificeer(url):
    """(type, soort) — type: 'youtube'|'kdg'|None; soort: 'kanaal'|'enkel'."""
    u = (url or "").lower()
    if kerkdienstgemist.is_kerkdienstgemist(url):
        return ("kdg", "enkel" if "/recording/" in u else "kanaal")
    if "youtube.com" in u or "youtu.be" in u:
        enkel = _video_id(url) and any(
            m in u for m in ("watch", "v=", "youtu.be/", "/live/", "/shorts/")
        )
        return ("youtube", "enkel" if enkel else "kanaal")
    return (None, None)


def _youtube_kanaal_url(url):
    """Zorg dat we het streams-tabblad van een YouTube-kanaal ophalen."""
    if re.search(r"/(streams|videos|featured|playlists)\b", url):
        return url
    return url.rstrip("/") + "/streams"


def _laad_diensten(typ, kanaal_url, vernieuw=False):
    lijst, vers = store.diensten_ophalen(kanaal_url)
    if vernieuw or not vers:
        try:
            if typ == "kdg":
                nieuw = kerkdienstgemist.lijst_diensten(kanaal_url)
            else:
                nieuw = _lijst_youtube(kanaal_url)
            store.diensten_opslaan(kanaal_url, nieuw)
            lijst = nieuw
        except Exception as fout:  # noqa: BLE001
            if not lijst:
                raise HTTPException(
                    502, f"De dienstenlijst kon niet worden opgehaald: {fout}"
                )
            # Verouderde lijst is beter dan geen lijst.
    return lijst


def _lijst_youtube(kanaal_url):
    """YouTube-kanaallijst via yt-dlp; bij een blokkade terugvallen op Supadata."""
    try:
        return lijst_diensten(_youtube_kanaal_url(kanaal_url))
    except Exception as fout:  # noqa: BLE001
        if supadata.beschikbaar():
            return supadata.lijst_kanaal(kanaal_url)
        raise fout


def _proces_kerkdienstgemist(url, meld):
    """Kerkdienstgemist: alleen het preekgedeelte transcriberen via OpenAI.

    Geeft (data, tekst, meta, ondertitel) terug.
    """
    meld("Opname-informatie ophalen (Kerkdienstgemist)...")
    o = kerkdienstgemist.haal_opname(url)
    preek_min = round((o["duur"] - o["sermon_start"]) / 60)
    meld(
        f"Preek gevonden (±{preek_min} min). Audio ophalen en transcriberen "
        "met OpenAI — dit kan enkele minuten duren..."
    )
    transcript = audio.transcribeer_hls(
        o["hls_url"], o["sermon_start"], o["duur"], voortgang=meld
    )

    context = []
    if o.get("bijbelgedeelte"):
        context.append(f"Bijbelgedeelte (preektekst): {o['bijbelgedeelte']}")
    if o.get("voorganger"):
        context.append(f"Voorganger: {o['voorganger']}")

    meld("Verwerken met AI — dit kan enkele minuten duren...")
    data = verwerk_preek(
        transcript, taal_hint="nl", extra_context="\n".join(context) or None
    )
    # Liturgie altijd meebewaren (Kerkdienstgemist levert die; YouTube niet).
    if o.get("liturgie"):
        data["liturgie"] = o["liturgie"]
    tekst = render.naar_tekst(data)
    meta = {
        "titel": o["titel"],
        "voorganger": o.get("voorganger"),
        "duur_minuten": preek_min,
        "transcriptie_bron": "Kerkdienstgemist (audio via OpenAI)",
    }
    return data, tekst, meta, o["titel"]


def _proces_youtube(url, meld):
    """YouTube: transcriptbron kiezen (Supadata gehost / yt-dlp lokaal).

    Geeft (data, tekst, meta, ondertitel) terug.
    """
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
    delen = f", {meta['delen']} delen" if meta.get("delen", 1) > 1 else ""
    gevonden = (
        f"Preek gevonden ({meta['preek_start']}–{meta['preek_einde']}"
        f"{delen}, ±{meta['duur_minuten']} min). "
    )

    transcript = seg["ondertitel_tekst"]
    if supadata.beschikbaar():
        bron = "YouTube-ondertitels via Supadata"
    else:
        bron = "ondertitels"
        if provider_bereikbaar():
            try:
                meld(gevonden + "Audio ophalen en transcriberen...")
                transcript = transcribeer_preek(url, seg["tijden"], voortgang=meld)
                bron = "audio (OpenAI-transcriptie)"
            except Exception:  # noqa: BLE001 — terugval op ondertitels
                transcript = seg["ondertitel_tekst"]
                bron = "ondertitels (audio niet beschikbaar)"
    meta["transcriptie_bron"] = bron

    meld(gevonden + f"Bron: {bron}. Verwerken met AI — dit kan enkele "
         "minuten duren...")
    data = verwerk_preek(transcript, seg["welkom"], taal_hint=taal_hint)
    tekst = render.naar_tekst(data)
    return data, tekst, meta, meta.get("titel")


def _voer_taak_uit(taak_id, url):
    taak = taken[taak_id]

    def meld(stap):
        taak["stap"] = stap

    try:
        is_kdg = kerkdienstgemist.is_kerkdienstgemist(url)
        vid = kerkdienstgemist.video_id(url) if is_kdg else _video_id(url)

        # 1. Al eerder verwerkt? Dan meteen uit de cache.
        if vid and not taken[taak_id].get("_herverwerk"):
            bewaard = store.resultaat_ophalen(vid)
            if bewaard and bewaard.get("data"):
                # Oudere caches kunnen vertaalde sleutels bevatten (leeg veld);
                # normaliseren herstelt dat en we bewaren de gerepareerde versie.
                data = llm_normaliseer(bewaard["data"])
                tekst = render.naar_tekst(data)
                store.resultaat_opslaan(vid, {**bewaard, "data": data, "tekst": tekst})
                taak["meta"] = bewaard.get("meta")
                taak["resultaat"] = {
                    "data": _met_labels(data),
                    "tekst": tekst,
                    "video_id": vid,
                }
                taak["stap"] = "Uit opslag geladen."
                taak["status"] = "klaar"
                return

        # 2. Verwerken via de juiste bron.
        if is_kdg:
            data, tekst, meta, ondertitel = _proces_kerkdienstgemist(url, meld)
        else:
            data, tekst, meta, ondertitel = _proces_youtube(url, meld)

        taak["meta"] = meta
        taak["resultaat"] = {"data": _met_labels(data), "tekst": tekst, "video_id": vid}
        taak["status"] = "klaar"

        # 3. Permanent bewaren zodat deze dienst nooit opnieuw verwerkt hoeft.
        if vid:
            store.resultaat_opslaan(
                vid,
                {"data": data, "tekst": tekst, "meta": meta, "ondertitel": ondertitel},
            )
    except Exception as fout:  # noqa: BLE001 — alles netjes aan de gebruiker melden
        melding = str(fout)
        if "not a bot" in melding or "Sign in to confirm" in melding:
            melding += "\n\nDiagnose: " + pot_provider_diagnose()
        taak["status"] = "fout"
        taak["fout"] = melding


VERSIE = (
    os.environ.get("RAILWAY_GIT_COMMIT_SHA")
    or os.environ.get("SOURCE_VERSION")
    or "lokaal"
)[:12]


@app.get("/api/diagnose")
def diagnose():
    return {
        "versie": VERSIE,
        "yt_dlp_versie": yt_dlp.version.__version__,
        "transcript_bron": (
            "Supadata" if supadata.beschikbaar() else "yt-dlp (lokaal)"
        ),
        "supadata": supadata.diagnose(),
        "pot_provider": pot_provider_diagnose(),
        "openai_sleutel_ingesteld": bool(os.environ.get("OPENAI_API_KEY")),
        "data_map": store.DATA_DIR,
    }


@app.get("/api/kanaal")
def kanaal(url: str = "", vernieuw: bool = False):
    """Herken een geplakte link: kanaal → dienstenlijst; enkele preek → verwerken.

    Zonder url: het standaardkanaal (KANAAL_URL)."""
    url = (url or "").strip() or KANAAL_URL
    typ, soort = _classificeer(url)
    if typ is None:
        raise HTTPException(400, "Geef een YouTube- of Kerkdienstgemist-link op.")
    if soort == "enkel":
        return {"soort": "enkel", "url": url}
    return {
        "soort": "lijst",
        "kanaal": url,
        "diensten": _laad_diensten(typ, url, vernieuw),
    }


@app.post("/api/verwerk")
def start_verwerking(verzoek: VerwerkVerzoek):
    url = verzoek.url.strip()
    geldig = (
        "youtube.com/" in url
        or "youtu.be/" in url
        or kerkdienstgemist.is_kerkdienstgemist(url)
    )
    if not geldig:
        raise HTTPException(
            400, "Geef een geldige YouTube- of Kerkdienstgemist-link op."
        )
    taak_id = uuid.uuid4().hex
    taken[taak_id] = {
        "status": "bezig",
        "stap": "Starten...",
        "resultaat": None,
        "fout": None,
        "meta": None,
        "_herverwerk": verzoek.herverwerk,
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
