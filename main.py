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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

import yt_dlp

import admin
import audio
import db as database
import kerkdienstgemist
import kerkomroep
import render
import store
import supadata
import transcript as ts
from audio import transcribeer_preek
from llm import verwerk_preek
from llm import normaliseer as llm_normaliseer
from llm import schoon_transcript as llm_schoon_transcript
from transcript import (
    haal_preek_segmentatie,
    lijst_diensten,
    pot_provider_diagnose,
    provider_bereikbaar,
)

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("aftersermon")

app = FastAPI(title="Preekverwerker")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Ondertekende sessie-cookie voor de admin-login. SECRET_KEY op Railway zetten.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get("SECRET_KEY", "dev-onveilig-wijzig-mij"),
    https_only=bool(os.environ.get("RAILWAY_GIT_COMMIT_SHA")),
    max_age=60 * 60 * 24 * 30,
)
app.include_router(admin.router)


def _base_url_env():
    if os.environ.get("BASE_URL"):
        return os.environ["BASE_URL"].rstrip("/")
    domein = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    return f"https://{domein}" if domein else "http://127.0.0.1:8123"


@app.on_event("startup")
def _startup():
    database.init_db()
    # Automatisering (scan → goedkeuring → gepland versturen). Lokaal standaard
    # uit; op Railway aan. Forceer met AUTOMATISERING=aan / =uit.
    keuze = os.environ.get("AUTOMATISERING", "").lower()
    aan = keuze == "aan" or (keuze != "uit" and bool(os.environ.get("RAILWAY_PUBLIC_DOMAIN")))
    if aan:
        import automatisering

        automatisering.start(_base_url_env())
        print("[automatisering] achtergrond-lus gestart")


VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/live/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")

# Takenlijst in het geheugen (kortlevend, alleen voor de voortgang tijdens één
# verwerking). De uiteindelijke resultaten leven persistent in store.
taken = {}


class VerwerkVerzoek(BaseModel):
    url: str
    herverwerk: bool = False


class BewerkVerzoek(BaseModel):
    velden: dict


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
    if kerkomroep.is_kerkomroep(url):
        return ("kerkomroep", "enkel" if "/audio/" in u else "kanaal")
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
            elif typ == "kerkomroep":
                nieuw = kerkomroep.lijst_diensten(kanaal_url)
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
    """YouTube-kanaallijst.

    yt-dlp geeft het juiste, nieuwste-eerst overzicht van het streams-tabblad
    (waar de wekelijkse diensten staan), maar vaak zonder datum in de titel.
    Supadata's kanaal-endpoint mist juist die livestreams. Daarom: lijst via
    yt-dlp, en de datums van de nieuwste diensten aanvullen via Supadata (dat
    werkt gehost en geeft de echte uploaddatum per video)."""
    try:
        diensten = lijst_diensten(_youtube_kanaal_url(kanaal_url))
    except Exception:  # noqa: BLE001 — yt-dlp geblokkeerd: val terug op Supadata-lijst
        if supadata.beschikbaar():
            return supadata.lijst_kanaal(kanaal_url)
        raise
    if supadata.beschikbaar():
        _verrijk_datums_via_supadata(diensten)
    return diensten


def _verrijk_datums_via_supadata(diensten, maximum=10):
    """Vul de datum aan van de nieuwste diensten die er nog geen hebben.

    Alleen de nieuwste `maximum` datumloze diensten (yt-dlp levert nieuwste
    eerst), zodat de scan het recente venster dekt zonder de rate limit te raken.
    """
    import time
    from datetime import date

    vandaag = date.today().isoformat()
    gedaan = 0
    for d in diensten:
        if gedaan >= maximum:
            break
        if d.get("datum"):
            continue
        datum = supadata.video_datum(d.get("id"))
        gedaan += 1
        time.sleep(1.2)  # gratis tier heeft een strakke rate limit
        if datum:
            d["datum"] = datum
            if datum > vandaag:
                d["gepland"] = True


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
    return data, tekst, meta, o["titel"], transcript


def _proces_audio_bron(o, bronnaam, meld):
    """Generiek: een hele preek-mp3 transcriberen en verwerken.

    `o` bevat mp3_url, duur, titel en optioneel voorganger/bijbelgedeelte/liturgie.
    Gebruikt voor Kerkomroep en SermonAudio (geen preek-markering in de audio).
    """
    meld(
        f"Audio ophalen en transcriberen met OpenAI (±{round((o.get('duur') or 0)/60)} "
        "min) — dit kan enkele minuten duren..."
    )
    transcript = audio.transcribeer_audio(o["mp3_url"], o.get("duur"), voortgang=meld)

    context = []
    if o.get("bijbelgedeelte"):
        context.append(f"Bijbelgedeelte (preektekst): {o['bijbelgedeelte']}")
    if o.get("voorganger"):
        context.append(f"Voorganger: {o['voorganger']}")

    meld("Verwerken met AI — dit kan enkele minuten duren...")
    data = verwerk_preek(transcript, extra_context="\n".join(context) or None)
    if o.get("liturgie"):
        data["liturgie"] = o["liturgie"]
    tekst = render.naar_tekst(data)
    meta = {
        "titel": o["titel"],
        "voorganger": o.get("voorganger"),
        "duur_minuten": round((o.get("duur") or 0) / 60),
        "transcriptie_bron": f"{bronnaam} (audio via OpenAI)",
    }
    return data, tekst, meta, o["titel"], transcript


def _proces_kerkomroep(url, meld):
    """Kerkomroep: de hele dienst-mp3 transcriberen (geen preek-markering)."""
    meld("Uitzending ophalen (Kerkomroep)...")
    return _proces_audio_bron(kerkomroep.haal_opname(url), "Kerkomroep", meld)


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
    return data, tekst, meta, meta.get("titel"), transcript


def verwerk_en_bewaar(url, herverwerk=False, meld=None):
    """Verwerk een dienst (of laad uit cache) en bewaar het resultaat.

    Herbruikbaar vanuit de interactieve taak én de automatisering. Geeft een dict
    met o.a. video_id, data, tekst, meta, transcript_ruw, preek_schoon, uit_cache.
    """
    meld = meld or (lambda _s: None)
    is_kdg = kerkdienstgemist.is_kerkdienstgemist(url)
    is_ko = kerkomroep.is_kerkomroep(url)
    if is_kdg:
        vid = kerkdienstgemist.video_id(url)
    elif is_ko:
        vid = kerkomroep.video_id(url)
    else:
        vid = _video_id(url)

    # 1. Al eerder verwerkt? Dan uit de cache (met sleutel-normalisatie).
    if vid and not herverwerk:
        bewaard = store.resultaat_ophalen(vid)
        if bewaard and bewaard.get("data"):
            data = llm_normaliseer(bewaard["data"])
            tekst = render.naar_tekst(data)
            payload = {**bewaard, "data": data, "tekst": tekst}
            store.resultaat_opslaan(vid, payload)
            return {"video_id": vid, "uit_cache": True, **payload}

    # 2. Verwerken via de juiste bron.
    if is_kdg:
        data, tekst, meta, ondertitel, transcript_ruw = _proces_kerkdienstgemist(url, meld)
    elif is_ko:
        data, tekst, meta, ondertitel, transcript_ruw = _proces_kerkomroep(url, meld)
    else:
        data, tekst, meta, ondertitel, transcript_ruw = _proces_youtube(url, meld)

    # 2b. Opgeschoonde, volledige preektekst (aparte AI-stap; niet fataal).
    preek_schoon = ""
    try:
        meld("Volledige preektekst opschonen...")
        preek_schoon = llm_schoon_transcript(transcript_ruw, data.get("taal"))
    except Exception:  # noqa: BLE001 — zonder schone preek gaan we gewoon door
        preek_schoon = ""

    payload = {
        "data": data, "tekst": tekst, "meta": meta, "ondertitel": ondertitel,
        "transcript_ruw": transcript_ruw, "preek_schoon": preek_schoon,
    }
    if vid:
        store.resultaat_opslaan(vid, payload)
    return {"video_id": vid, "uit_cache": False, **payload}


def verwerk_tekst_en_bewaar(video_id, tekst, titel_hint=None):
    """Verwerk een aangeleverde preektekst (upload) en bewaar het resultaat.

    De tekst is de preek zelf (manuscript), dus die geldt meteen als de
    opgeschoonde volledige preek — geen transcriptie/opschoonstap nodig.
    """
    data = verwerk_preek(tekst)
    if titel_hint and not data.get("titel"):
        data["titel"] = titel_hint
    rendered = render.naar_tekst(data)
    payload = {
        "data": data, "tekst": rendered,
        "meta": {"transcriptie_bron": "geüpload document"},
        "ondertitel": titel_hint, "transcript_ruw": tekst, "preek_schoon": tekst,
    }
    store.resultaat_opslaan(video_id, payload)
    return data


def _voer_taak_uit(taak_id, url):
    taak = taken[taak_id]

    def meld(stap):
        taak["stap"] = stap

    try:
        r = verwerk_en_bewaar(url, herverwerk=taak.get("_herverwerk"), meld=meld)
        taak["meta"] = r["meta"]
        taak["resultaat"] = {
            "data": _met_labels(r["data"]),
            "tekst": r["tekst"],
            "video_id": r["video_id"],
            "heeft_preek": bool(r.get("preek_schoon")),
            "heeft_ruw": bool((r.get("transcript_ruw") or "").strip()),
        }
        if r["uit_cache"]:
            taak["stap"] = "Uit opslag geladen."
        taak["status"] = "klaar"
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
        "ffmpeg": audio.ffmpeg_diagnose(),
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
    """Herken een geplakte link: kanaal → dienstenlijst; enkele preek → verwerken."""
    url = (url or "").strip()
    if not url:
        raise HTTPException(400, "Plak eerst een kanaal- of preeklink.")
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
        or kerkomroep.is_kerkomroep(url)
    )
    if not geldig:
        raise HTTPException(
            400, "Geef een geldige YouTube-, Kerkdienstgemist- of Kerkomroep-link op."
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


def _bestandsnaam(data, achtervoegsel, ext):
    naam = re.sub(r"[^\w\- ]", "", (data.get("titel") or "preek")).strip()
    naam = re.sub(r"\s+", "-", naam) or "preek"
    return f"{naam[:70]}{achtervoegsel}.{ext}"


def _bestand(inhoud, media_type, bestandsnaam):
    if isinstance(inhoud, str):
        inhoud = inhoud.encode("utf-8")
    return Response(
        content=inhoud,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{bestandsnaam}"'},
    )


def _ophalen_of_404(video_id):
    bewaard = store.resultaat_ophalen(video_id)
    if not bewaard or not bewaard.get("data"):
        raise HTTPException(404, "Voor deze dienst is nog geen verwerking beschikbaar.")
    return bewaard


DAG_VELDEN = ("titel", "bijbeltekst", "gedachte", "vraag_volwassenen",
              "vraag_kinderen")


@app.post("/api/bewerk/{video_id}")
def bewerk(video_id: str, verzoek: BewerkVerzoek):
    """Handmatige bewerkingen opslaan; PDF/tekst gebruiken daarna deze versie."""
    bewaard = _ophalen_of_404(video_id)
    data = dict(bewaard["data"])
    v = verzoek.velden or {}
    for veld in ("titel", "bijbelgedeelte", "samenvatting", "liturgie"):
        if isinstance(v.get(veld), str):
            data[veld] = v[veld]
    if "voorganger" in v:
        data["voorganger"] = (v["voorganger"] or "").strip() or None
    if isinstance(v.get("dagen"), list):
        dagen = [dict(d) for d in (data.get("dagen") or [])]
        for i, nieuw in enumerate(v["dagen"]):
            if i < len(dagen) and isinstance(nieuw, dict):
                for veld in DAG_VELDEN:
                    if isinstance(nieuw.get(veld), str):
                        dagen[i][veld] = nieuw[veld]
        data["dagen"] = dagen
    tekst = render.naar_tekst(data)
    store.resultaat_opslaan(video_id, {**bewaard, "data": data, "tekst": tekst})
    return {"data": _met_labels(data), "tekst": tekst, "video_id": video_id}


@app.get("/api/pdf/{video_id}")
def pdf(video_id: str):
    bewaard = _ophalen_of_404(video_id)
    data = bewaard["data"]
    inhoud = render.naar_pdf(data, ondertitel=bewaard.get("ondertitel"))
    return _bestand(inhoud, "application/pdf", _bestandsnaam(data, "", "pdf"))


@app.get("/api/preek/{video_id}.{ext}")
def preek(video_id: str, ext: str):
    """Volledige, opgeschoonde preek als PDF of tekst."""
    bewaard = _ophalen_of_404(video_id)
    tekst = bewaard.get("preek_schoon")
    if not tekst:
        raise HTTPException(
            404, "Voor deze dienst is nog geen volledige preektekst beschikbaar. "
            "Verwerk de dienst opnieuw."
        )
    data = bewaard["data"]
    onder = bewaard.get("ondertitel")
    if ext == "pdf":
        inhoud = render.naar_preek_pdf(data, tekst, ondertitel=onder)
        return _bestand(inhoud, "application/pdf", _bestandsnaam(data, "-preek", "pdf"))
    if ext == "txt":
        inhoud = render.preek_naar_tekst(data, tekst, ondertitel=onder)
        return _bestand(inhoud, "text/plain; charset=utf-8",
                        _bestandsnaam(data, "-preek", "txt"))
    raise HTTPException(400, "Onbekend formaat (gebruik pdf of txt).")


@app.get("/api/transcript/{video_id}.txt")
def transcript_ruw(video_id: str):
    """Het ruwe, onbewerkte transcript zoals uitgesproken."""
    bewaard = _ophalen_of_404(video_id)
    tekst = bewaard.get("transcript_ruw")
    if not tekst:
        raise HTTPException(
            404, "Voor deze dienst is geen ruw transcript bewaard. "
            "Verwerk de dienst opnieuw."
        )
    return _bestand(tekst, "text/plain; charset=utf-8",
                    _bestandsnaam(bewaard["data"], "-transcript", "txt"))


@app.get("/demo")
def demo():
    # De preekverwerker-tool zelf, nu als demo. De homepage (/) is de
    # landings-/loginpagina (static/admin.html).
    return FileResponse(
        "static/index.html", headers={"Cache-Control": "no-cache"}
    )


if __name__ == "__main__":
    # Zelfstandig starten (Docker/Railway): lees de poort uit de omgeving, zodat
    # we niet afhankelijk zijn van shell-expansie van $PORT in het startcommando.
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
