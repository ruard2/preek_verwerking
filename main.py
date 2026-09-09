"""Preekverwerker: kies een dienst, krijg een weekboekje (samenvatting + 7 dagen).

De verwerking duurt enkele minuten, daarom loopt die als achtergrondtaak en
pollt de frontend op /api/status/<id>. Resultaten worden per video op schijf
bewaard (store.py): een dienst wordt maar één keer verwerkt.
"""

import logging
import os
import re
import threading
import uuid

from dotenv import load_dotenv

load_dotenv()  # leest een .env-bestand in de projectmap (lokaal gebruik)

# Centrale logging zodat fouten (auto-migratie, scan, bezorging) zichtbaar zijn
# in de Railway-logs. Niveau instelbaar via LOG_LEVEL.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

import yt_dlp

import admin
import audio
import brevo
import db as database
import kerkdienstgemist
import kerkomroep
import bijbeltekst
import render
import store
import supadata
import transcript as ts
from audio import transcribeer_preek
from audio import transcribeer_hele_video
from llm import verwerk_preek
from llm import maak_basis as llm_maak_basis
from llm import hergenereer_dag as llm_hergenereer_dag
from llm import maak_nabespreking as llm_maak_nabespreking
from llm import maak_groepsvragen as llm_maak_groepsvragen
from llm import normaliseer as llm_normaliseer
from llm import schoon_transcript as llm_schoon_transcript
from llm import extraheer_en_schoon_preek as llm_extraheer_en_schoon_preek
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
    # Achtergrond-lus tijdelijk volledig uitgeschakeld.
    # Zet AUTOMATISERING=aan om hem terug in te schakelen.
    keuze = os.environ.get("AUTOMATISERING", "").lower()
    if keuze == "aan":
        import automatisering

        automatisering.start(_base_url_env())
        print("[automatisering] achtergrond-lus gestart")
    else:
        print("[automatisering] uitgeschakeld")


VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/live/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")

# Takenlijst in het geheugen (kortlevend, alleen voor de voortgang tijdens één
# verwerking). De uiteindelijke resultaten leven persistent in store.
taken = {}


class VerwerkVerzoek(BaseModel):
    url: str
    herverwerk: bool = False
    # Handmatig ingestelde preektijden: [[start_sec, eind_sec], ...].
    # Als opgegeven, wordt alleen dat audio-segment gedownload en getranscribeerd.
    preek_tijden: list[list[int]] = []


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
    # Datums aanvullen via Supadata alleen als er GÉÉN proxy is; met een proxy werkt
    # yt-dlp en willen we Supadata (en de credits) helemaal niet meer aanraken.
    if supadata.beschikbaar() and not ts.proxy_actief():
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
        if d.get("datum"):
            continue
        # Al eerder opgehaald? Dan uit de gedeelde cache (geen Supadata-call).
        gecachet = store.datum_ophalen(d.get("id"))
        if gecachet:
            d["datum"] = gecachet
            if gecachet > vandaag:
                d["gepland"] = True
            continue
        if gedaan >= maximum:
            break
        try:
            datum = supadata.video_datum(d.get("id"))
        except Exception as fout:  # noqa: BLE001
            # Supadata-fout (bv. 429 quota op) mag de yt-dlp-lijst NOOIT weggooien.
            # Stop het aanvullen; diensten met een datum in de titel blijven werken.
            logging.getLogger("aftersermon").warning(
                "Supadata datum-verrijking gestopt: %s", str(fout)[:120]
            )
            break
        gedaan += 1
        time.sleep(1.2)  # gratis tier heeft een strakke rate limit
        if datum:
            store.datum_opslaan(d.get("id"), datum)  # gedeeld onthouden
            d["datum"] = datum
            if datum > vandaag:
                d["gepland"] = True


def _context_uit_opname(o):
    """Bouw de extra-contextregels (bijbelgedeelte/voorganger) uit een opname-dict."""
    context = []
    if o.get("bijbelgedeelte"):
        context.append(f"Bijbelgedeelte (preektekst): {o['bijbelgedeelte']}")
    if o.get("voorganger"):
        context.append(f"Voorganger: {o['voorganger']}")
    return "\n".join(context) or None


def _transcribeer_kerkdienstgemist(url, meld):
    """Kerkdienstgemist: alleen het preekgedeelte transcriberen via OpenAI.

    Geeft een uniforme bron_info dict terug (transcript + context, geen AI-generatie).
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
    return {
        "transcript": transcript, "taal_hint": "nl", "welkom": None,
        "extra_context": _context_uit_opname(o), "volledige_dienst": False,
        "liturgie": o.get("liturgie"), "ondertitel": o["titel"],
        "meta": {
            "titel": o["titel"], "voorganger": o.get("voorganger"),
            "duur_minuten": preek_min,
            "transcriptie_bron": "Kerkdienstgemist (audio via OpenAI)",
        },
    }


def _transcribeer_audio_bron(o, bronnaam, meld):
    """Generiek: een hele preek-mp3 transcriberen (Kerkomroep e.d.)."""
    meld(
        f"Audio ophalen en transcriberen met OpenAI (±{round((o.get('duur') or 0)/60)} "
        "min) — dit kan enkele minuten duren..."
    )
    transcript = audio.transcribeer_audio(o["mp3_url"], o.get("duur"), voortgang=meld)
    return {
        "transcript": transcript, "taal_hint": None, "welkom": None,
        "extra_context": _context_uit_opname(o), "volledige_dienst": True,
        "liturgie": o.get("liturgie"), "ondertitel": o["titel"],
        "meta": {
            "titel": o["titel"], "voorganger": o.get("voorganger"),
            "duur_minuten": round((o.get("duur") or 0) / 60),
            "transcriptie_bron": f"{bronnaam} (audio via OpenAI)",
        },
    }


def _transcribeer_kerkomroep(url, meld):
    """Kerkomroep: de hele dienst-mp3 transcriberen (geen preek-markering)."""
    meld("Uitzending ophalen (Kerkomroep)...")
    return _transcribeer_audio_bron(kerkomroep.haal_opname(url), "Kerkomroep", meld)


def _transcribeer_youtube(url, meld, preek_tijden=None):
    """YouTube-transcriptbron kiezen.

    Altijd via yt-dlp + Whisper (eigen proxy). Supadata wordt niet meer gebruikt
    als fallback voor de audio-transcriptie — als yt-dlp faalt, gooit de fout
    omhoog zodat het probleem zichtbaar is en opgelost kan worden.
    """
    return _youtube_via_ytdlp(url, meld, preek_tijden=preek_tijden or [])


def _youtube_via_supadata(url, meld):
    """YouTube-transcript via Supadata (ondertitels of AI-transcriptie aan hun kant)."""
    entries, taal = supadata.haal_transcript(url, voortgang=meld)
    titel = _titel_uit_cache(url) or "YouTube-dienst"
    meld("Preekgedeelte zoeken...")
    seg = ts.segmenteer(entries, titel=titel, taal=taal or "nl")
    meta = seg["meta"]
    meta["transcriptie_bron"] = "YouTube-ondertitels via Supadata"
    return {
        "transcript": seg["ondertitel_tekst"], "taal_hint": taal,
        "welkom": seg["welkom"], "extra_context": None,
        "volledige_dienst": seg.get("volledige_dienst", False),
        "liturgie": None, "ondertitel": meta.get("titel"), "meta": meta,
    }


def _youtube_via_ytdlp(url, meld, preek_tijden=None):
    """YouTube-transcript via onze eigen yt-dlp-download + Whisper (residentiële proxy).

    Strategie:
    1. Als handmatige preek_tijden opgegeven zijn: gebruik die direct.
    2. Anders: val terug op hele dienst transcriberen + LLM-extractie.
       (Subtitle-segmentatie overgeslagen — onbetrouwbaar voor livestreams.)
    """
    tijden = [t for t in (preek_tijden or []) if len(t) == 2 and t[1] > t[0]]

    if tijden:
        meld("Preekaudio downloaden en transcriberen (handmatige tijdmarkering)...")
        transcript = transcribeer_preek(url, tijden, voortgang=meld)
        if len((transcript or "").strip()) >= 200:
            titel = _titel_uit_cache(url) or "YouTube-dienst"
            return {
                "transcript": transcript, "taal_hint": None, "welkom": None,
                "extra_context": None, "volledige_dienst": False, "liturgie": None,
                "ondertitel": titel,
                "meta": {"titel": titel, "transcriptie_bron": "audio via proxy (OpenAI, preeksegmenten)"},
            }
        log.warning("Preektijden opgegeven maar transcript te kort; val terug op hele dienst.")

    # Terugval: hele dienst transcriberen
    meld("Audio ophalen en transcriberen (OpenAI, via eigen proxy, hele dienst)...")
    transcript = transcribeer_hele_video(url, voortgang=meld)
    if len((transcript or "").strip()) < 200:
        raise RuntimeError(
            "De audio-transcriptie leverde te weinig tekst op (download mislukt of "
            "geen spraak)."
        )
    titel = _titel_uit_cache(url) or "YouTube-dienst"
    return {
        "transcript": transcript, "taal_hint": None, "welkom": None,
        "extra_context": None, "volledige_dienst": True, "liturgie": None,
        "ondertitel": titel,
        "meta": {"titel": titel, "transcriptie_bron": "audio via proxy (OpenAI, hele dienst)"},
    }


def _transcribeer_bron(url, is_kdg, is_ko, meld, preek_tijden=None):
    """Kies de juiste transcriptiebron en geef een uniforme bron_info dict terug."""
    if is_kdg:
        return _transcribeer_kerkdienstgemist(url, meld)
    if is_ko:
        return _transcribeer_kerkomroep(url, meld)
    return _transcribeer_youtube(url, meld, preek_tijden=preek_tijden or [])


def _genereer_basis(bron_info, bijbel, typen, meld):
    """Maak de basis (dagstukjes via verwerk_preek, of een lichte basis zonder dagen).

    Zo slaan we de dure 7-daagse generatie over als de kerk geen dagstukjes wil.

    Bij volledige_dienst=True wordt eerst een dedicated extractiestap gedaan die
    de preektekst uit de hele dienst haalt EN meteen opschoont. Dat geeft verwerk_preek
    een gerichte, schone preek in plaats van een onbewerkte dienst-transcriptie.
    Het resultaat van de extractie wordt ook teruggegeven als 'preek_schoon'
    zodat de aparte schoon_transcript-stap later overgeslagen kan worden.
    """
    transcript = bron_info["transcript"]
    volledige_dienst = bron_info.get("volledige_dienst", False)

    # ── Stap 0: bij volledige dienst eerst preek extraheren + opschonen ───────
    # Dit vervangt de onbetrouwbare heuristische blokdetectie in transcript.py
    # én de aparte schoon_transcript-stap — alles in één gerichte LLM-call.
    preek_schoon_uit_extractie = None
    if volledige_dienst:
        meld("Preekgedeelte uit de volledige dienst halen en opschonen...")
        preek_schoon_uit_extractie = llm_extraheer_en_schoon_preek(transcript)
        # Gebruik de geëxtraheerde preek voor verdere verwerking.
        # Als de extractie mislukte (terugval = origineel), werkt verwerk_preek
        # nog steeds — dan via de VOLLEDIGE_DIENST_INSTRUCTIE in het prompt.
        transcript_voor_verwerking = preek_schoon_uit_extractie
        # Na extractie weten we zeker dat het alleen de preek is.
        volledige_dienst_voor_verwerking = False
    else:
        transcript_voor_verwerking = transcript
        volledige_dienst_voor_verwerking = False

    # bijbel kan taal_hint bevatten (kerkinstelling); bron_info heeft eigen taal_hint
    # (detectie/upload). Kerkinstelling wint; verwijder uit bijbel-copy om dubbele kwarg te voorkomen.
    bijbel_schoon = dict(bijbel or {})
    taal_hint_kerk = bijbel_schoon.pop("taal_hint", None)
    taal_hint_bron = bron_info.get("taal_hint")
    gemeen = dict(
        welkom=bron_info.get("welkom"),
        taal_hint=taal_hint_kerk or taal_hint_bron,  # kerkinstelling overrides bron
        extra_context=bron_info.get("extra_context"),
        volledige_dienst=volledige_dienst_voor_verwerking,
    )
    if "dagstukjes" in typen:
        meld("Weekboekje maken met AI — dit kan enkele minuten duren...")
        data = verwerk_preek(transcript_voor_verwerking, **gemeen, **bijbel_schoon)
        bijbeltekst.verrijk_dagen(data, bijbel or {})
    else:
        meld("Kernpunten van de preek samenvatten...")
        data = llm_maak_basis(transcript_voor_verwerking, **gemeen)
    if bron_info.get("liturgie"):
        data["liturgie"] = bron_info["liturgie"]
    # Geef de reeds-opgeschoonde preektekst mee zodat de aanroeper de aparte
    # schoon_transcript-stap kan overslaan.
    data["_preek_schoon_uit_extractie"] = preek_schoon_uit_extractie
    return data


def bijbel_van_kerk(kerk):
    """Bouw de verwerk-opties (Bijbeltekst + stijl + taal) uit een Church-record.

    Het resultaat wordt als **kwargs aan verwerk_preek doorgegeven: citaat_volledig,
    vertaling, toon, lengte en taal_hint. Verdraagt None (losse verwerking zonder
    kerk) → dan de standaardwaarden van verwerk_preek.

    taal_hint is None als uitvoer_taal='auto' (model detecteert de preektaal zelf);
    anders de ISO-code die de kerk heeft ingesteld (harde eis).
    """
    if kerk is None:
        return None
    uitvoer_taal = getattr(kerk, "uitvoer_taal", "auto") or "auto"
    return {
        "citaat_volledig": getattr(kerk, "citaat_volledig", True),
        "vertaling": getattr(kerk, "bijbelvertaling", "vrij") or "vrij",
        "toon": getattr(kerk, "toon", "warm") or "warm",
        "lengte": getattr(kerk, "lengte", "middel") or "middel",
        # Geeft None door als 'auto': model detecteert de preektaal zelf.
        "taal_hint": None if uitvoer_taal == "auto" else uitvoer_taal,
    }


_UITVOER_GELDIG = ("dagstukjes", "preeksamenvatting", "preektranscript", "nabespreking")


def parse_uitvoer(waarde):
    """Normaliseer een komma-string of lijst naar een geldige lijst uitvoertypen."""
    if isinstance(waarde, str):
        waarde = waarde.split(",")
    gekozen = [str(t).strip() for t in (waarde or []) if str(t).strip() in _UITVOER_GELDIG]
    return gekozen or ["dagstukjes"]


def uitvoer_van_kerk(kerk):
    """Welke uitvoer(en) een kerk maakt; terugval op dagstukjes."""
    if kerk is None:
        return ["dagstukjes"]
    return parse_uitvoer(getattr(kerk, "uitvoer_typen", "") or "dagstukjes")


def bezorg_van_kerk(kerk):
    """Welke uitvoer(en) automatisch naar de verzendlijst worden gemaild.

    Leeg `bezorg_typen` → terugval op alles wat de kerk maakt (oud gedrag).
    Altijd een deelverzameling van uitvoer_typen (je kunt niets versturen dat
    niet gemaakt wordt).
    """
    gemaakt = uitvoer_van_kerk(kerk)
    ruw = (getattr(kerk, "bezorg_typen", "") or "").strip() if kerk is not None else ""
    lijst = [t for t in parse_uitvoer(ruw) if t in gemaakt] or gemaakt if ruw else list(gemaakt)
    # Groepsvragen op vaste datums? Dan gaan ze niet mee in de wekelijkse mail.
    if kerk is not None and getattr(kerk, "nabespreking_schema", "mee") == "datums":
        lijst = [t for t in lijst if t != "nabespreking"]
    return lijst


def _pas_uitvoer_toe(data, uitvoer_typen, preek_schoon, transcript_ruw, meld):
    """Vul `data` aan met de gekozen uitvoer: transcript en/of nabespreking.

    Dagstukjes en samenvatting zitten al in `data`; hier voegen we de extra
    producten toe. Fouten bij de nabespreking zijn niet fataal.
    """
    typen = parse_uitvoer(uitvoer_typen)
    data["uitvoer_typen"] = typen
    bron = (preek_schoon or "").strip() or (transcript_ruw or "").strip()
    if "preektranscript" in typen:
        data["preektranscript"] = bron
    if "nabespreking" in typen:
        try:
            meld("Nabespreekvragen opstellen...")
            data["nabespreking"] = llm_maak_nabespreking(
                bron, bijbelgedeelte=data.get("bijbelgedeelte"),
                titel=data.get("titel"), samenvatting=data.get("samenvatting"),
                taal_hint=data.get("taal"),
            )
        except Exception:  # noqa: BLE001 — zonder nabespreking gaan we gewoon door
            data.setdefault("nabespreking", {})
    return data


def verwerk_en_bewaar(url, herverwerk=False, meld=None, bijbel=None, uitvoer_typen=None,
                      alleen_transcript=False, preek_tijden=None):
    """Verwerk een dienst (of laad uit cache) en bewaar het resultaat.

    Herbruikbaar vanuit de interactieve taak én de automatisering. `bijbel` is een
    optioneel dict {citaat_volledig, vertaling} met de Bijbeltekst-voorkeur van de
    kerk. Geeft een dict met o.a. video_id, data, tekst, meta, uit_cache.
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

    # Eventueel eerder opgeslagen resultaat (voor de cache én — belangrijker — om het
    # transcript te hergebruiken zodat we NOOIT twee keer downloaden/transcriberen).
    bewaard = store.resultaat_ophalen(vid) if vid else None

    # 1. Volledig resultaat in cache? Dan direct terug (geen hergeneratie).
    if bewaard and bewaard.get("data") and not herverwerk:
        data = llm_normaliseer(bewaard["data"])
        tekst = render.naar_tekst(data)
        payload = {**bewaard, "data": data, "tekst": tekst}
        store.resultaat_opslaan(vid, payload)
        return {"video_id": vid, "uit_cache": True, **payload}

    typen = parse_uitvoer(uitvoer_typen)

    # 2. Transcript: automatisch downloaden/transcriberen gebeurt HOOGSTENS ÉÉN KEER.
    #    Is er al een transcript opgeslagen, dan hergebruiken we dat (bij het toevoegen
    #    van een uitvoer, lui verwerken, enz.) — nooit ongevraagd opnieuw luisteren.
    #    Bij een BEWUSTE 'Opnieuw verwerken' (herverwerk=True) transcriberen we wél
    #    opnieuw — zo kun je een slecht transcript vervangen door een betere bron.
    preek_schoon = ""
    if bewaard and bewaard.get("transcript_ruw") and not herverwerk:
        transcript_ruw = bewaard["transcript_ruw"]
        opgeslagen_data = bewaard.get("data") or {}
        bron_info = {
            "transcript": transcript_ruw,
            "taal_hint": opgeslagen_data.get("taal"),
            "welkom": None, "extra_context": None,
            "volledige_dienst": is_ko,
            "liturgie": opgeslagen_data.get("liturgie"),
            "ondertitel": bewaard.get("ondertitel"),
            "meta": bewaard.get("meta") or {},
            **(bewaard.get("bron_info") or {}),  # opgeslagen hints hebben voorrang
        }
        bron_info["transcript"] = transcript_ruw
        preek_schoon = bewaard.get("preek_schoon") or ""
        meld("Bestaand transcript hergebruiken (niet opnieuw transcriberen)...")
    else:
        bron_info = _transcribeer_bron(url, is_kdg, is_ko, meld, preek_tijden=preek_tijden or [])
        transcript_ruw = bron_info["transcript"]
    meta = bron_info["meta"]
    ondertitel = bron_info.get("ondertitel")

    # 3. Basis genereren — of, bij alleen_transcript, NIETS genereren (bespaart AI-
    #    kosten). Dan alleen transcript + opschonen; de gebruiker kiest later per
    #    uitvoer wat er gemaakt wordt (zie genereer_en_bewaar).
    if alleen_transcript:
        data = {
            "taal": bron_info.get("taal_hint"),
            "titel": (meta.get("titel") or ondertitel or "Preek"),
            "bijbelgedeelte": "", "voorganger": None, "samenvatting": "", "dagen": [],
            "voorbereid": True,  # transcript klaar, nog niets gegenereerd
        }
        if bron_info.get("liturgie"):
            data["liturgie"] = bron_info["liturgie"]
    else:
        data = _genereer_basis(bron_info, bijbel, typen, meld)

    # 4. Opgeschoonde, herbruikbare preektekst — ook één keer: hergebruik indien aanwezig.
    # Bij volledige_dienst heeft _genereer_basis de extractie + opschoning al gedaan;
    # gebruik dat resultaat en sla de aparte schoon_transcript-stap over.
    preek_uit_extractie = data.pop("_preek_schoon_uit_extractie", None)
    if not preek_schoon:
        if preek_uit_extractie:
            preek_schoon = preek_uit_extractie
        else:
            try:
                meld("Volledige preektekst opschonen...")
                preek_schoon = llm_schoon_transcript(transcript_ruw, data.get("taal"))
            except Exception:  # noqa: BLE001 — zonder schone preek gaan we gewoon door
                preek_schoon = ""

    # 5. Alleen de gekozen extra uitvoer(en) maken (transcript, nabespreking).
    if not alleen_transcript:
        _pas_uitvoer_toe(data, uitvoer_typen, preek_schoon, transcript_ruw, meld)
    tekst = render.naar_tekst(data)

    # De brongegevens (zonder de grote transcript-tekst) meebewaren voor trouwe
    # hergeneratie zonder opnieuw te transcriberen.
    bron_bewaar = {k: v for k, v in bron_info.items() if k != "transcript"}
    payload = {
        "data": data, "tekst": tekst, "meta": meta, "ondertitel": ondertitel,
        "transcript_ruw": transcript_ruw, "preek_schoon": preek_schoon,
        "bron_info": bron_bewaar,
    }
    if vid:
        store.resultaat_opslaan(vid, payload)
    return {"video_id": vid, "uit_cache": False, **payload}


def verwerk_tekst_en_bewaar(video_id, tekst, titel_hint=None, volledige_dienst=False,
                            bijbel=None, uitvoer_typen=None, alleen_transcript=False):
    """Verwerk een aangeleverde preektekst of dienst-transcript en bewaar het.

    Bij een document (preekmanuscript) is de tekst de preek zelf. Bij audio van
    een volledige dienst (volledige_dienst=True) moet het model zelf het
    preekgedeelte eruit halen. Met alleen_transcript=True wordt er niets
    gegenereerd (alleen opgeslagen), zodat de gebruiker daarna zelf kiest.
    """
    typen = parse_uitvoer(uitvoer_typen)
    # taal_hint: uit de bijbel-opties (kerk-instelling) of None (auto-detect).
    # Verwijder taal_hint uit bijbel-copy om dubbele kwarg te voorkomen bij **-spreading.
    bijbel_schoon = dict(bijbel or {})
    taal_hint_upload = bijbel_schoon.pop("taal_hint", None)

    # Bij een volledige dienst: eerst preek extraheren + opschonen,
    # dan verwerken als gewone (niet-volledige) preek.
    preek_schoon_upload = tekst  # standaard: uploadtekst is de preek zelf
    if volledige_dienst and not alleen_transcript:
        preek_schoon_upload = llm_extraheer_en_schoon_preek(tekst)
        tekst_voor_verwerking = preek_schoon_upload
        volledige_dienst_vlag = False
    else:
        tekst_voor_verwerking = tekst
        volledige_dienst_vlag = volledige_dienst

    if alleen_transcript:
        data = {"taal": None, "titel": (titel_hint or "Preek"), "bijbelgedeelte": "",
                "voorganger": None, "samenvatting": "", "dagen": [], "voorbereid": True}
    elif "dagstukjes" in typen:
        data = verwerk_preek(tekst_voor_verwerking, volledige_dienst=volledige_dienst_vlag,
                             taal_hint=taal_hint_upload, **bijbel_schoon)
        bijbeltekst.verrijk_dagen(data, bijbel or {})
    else:
        data = llm_maak_basis(tekst_voor_verwerking, volledige_dienst=volledige_dienst_vlag,
                              taal_hint=taal_hint_upload)
    if titel_hint and not data.get("titel"):
        data["titel"] = titel_hint
    # Bij upload is de aangeleverde (of geëxtraheerde) tekst de preek.
    if not alleen_transcript:
        _pas_uitvoer_toe(data, typen, preek_schoon_upload, tekst, lambda _s: None)
    rendered = render.naar_tekst(data)
    payload = {
        "data": data, "tekst": rendered,
        "meta": {"transcriptie_bron": "geüpload document"},
        "ondertitel": titel_hint, "transcript_ruw": tekst, "preek_schoon": preek_schoon_upload,
    }
    store.resultaat_opslaan(video_id, payload)
    return data


def hergenereer_dag_en_bewaar(video_id, dag_index, bijbel=None):
    """Genereer één dag opnieuw voor een reeds verwerkt weekboekje en bewaar het.

    Gebruikt de opgeschoonde preektekst (of het ruwe transcript) als bron. Geeft
    het bijgewerkte resultaat-dict terug (met nieuwe `data` en `tekst`).
    """
    bewaard = store.resultaat_ophalen(video_id)
    if not bewaard or not bewaard.get("data"):
        raise ValueError("Deze dienst is nog niet verwerkt.")
    data = llm_normaliseer(bewaard["data"])
    bron = bewaard.get("preek_schoon") or bewaard.get("transcript_ruw") or ""
    opties = bijbel or {}
    nieuwe_dag = llm_hergenereer_dag(
        data, dag_index, bron,
        toon=opties.get("toon", "warm"), lengte=opties.get("lengte", "middel"),
        citaat_volledig=opties.get("citaat_volledig", True),
        vertaling=opties.get("vertaling", "vrij"),
    )
    dagen = data.get("dagen") or []
    if not (0 <= dag_index < len(dagen)):
        raise ValueError("Ongeldige dag.")
    # Exacte Bijbeltekst aanvullen (alleen deze nieuwe dag; de rest bleef ongewijzigd).
    bijbeltekst.verrijk_dag(
        nieuwe_dag, opties.get("vertaling"), opties.get("citaat_volledig", True)
    )
    # Bestaande sleutels behouden, alleen de gegenereerde velden vervangen.
    dagen[dag_index].update({k: v for k, v in nieuwe_dag.items() if v})
    tekst = render.naar_tekst(data)
    payload = {**bewaard, "data": data, "tekst": tekst}
    store.resultaat_opslaan(video_id, payload)
    return {"video_id": video_id, **payload}


def hergenereer_nabespreking_en_bewaar(video_id):
    """Genereer de nabespreekvragen (opnieuw) voor een verwerkte dienst en bewaar."""
    bewaard = store.resultaat_ophalen(video_id)
    if not bewaard or not bewaard.get("data"):
        raise ValueError("Deze dienst is nog niet verwerkt.")
    data = llm_normaliseer(bewaard["data"])
    bron = bewaard.get("preek_schoon") or bewaard.get("transcript_ruw") or ""
    data["nabespreking"] = llm_maak_nabespreking(
        bron, bijbelgedeelte=data.get("bijbelgedeelte"), titel=data.get("titel"),
        samenvatting=data.get("samenvatting"), taal_hint=data.get("taal"),
    )
    typen = parse_uitvoer(data.get("uitvoer_typen"))
    if "nabespreking" not in typen:
        typen.append("nabespreking")
    data["uitvoer_typen"] = typen
    tekst = render.naar_tekst(data)
    payload = {**bewaard, "data": data, "tekst": tekst}
    store.resultaat_opslaan(video_id, payload)
    return {"video_id": video_id, **payload}


def genereer_en_bewaar(video_id, wat, bijbel=None):
    """Genereer op AANVRAAG één uitvoer uit het opgeslagen transcript, zonder opnieuw
    te transcriberen. Zo draait de AI alleen voor wat de gebruiker echt kiest.

    `wat`: 'samenvatting' (titel/bijbelgedeelte/samenvatting) of 'dagstukjes' (het
    volledige weekboekje met 7 dagen). Werkt het opgeslagen resultaat bij.
    """
    bewaard = store.resultaat_ophalen(video_id)
    bron = (bewaard or {}).get("preek_schoon") or (bewaard or {}).get("transcript_ruw")
    if not bron:
        raise ValueError("Deze dienst is nog niet voorbereid (geen transcript).")
    volledig = bool((bewaard.get("bron_info") or {}).get("volledige_dienst"))
    data = dict(bewaard.get("data") or {})
    data.pop("voorbereid", None)
    # Gebruik de eerder gedetecteerde preektaal als fallback; kerk-instelling wint.
    # Verwijder taal_hint uit bijbel-copy om dubbele kwarg te voorkomen bij **-spreading.
    bijbel_schoon = dict(bijbel or {})
    taal_hint_kerk = bijbel_schoon.pop("taal_hint", None)
    opgeslagen_taal = data.get("taal") or (bewaard.get("bron_info") or {}).get("taal_hint")
    taal_hint_gen = taal_hint_kerk or opgeslagen_taal
    if wat == "dagstukjes":
        gegenereerd = verwerk_preek(bron, volledige_dienst=volledig,
                                    taal_hint=taal_hint_gen, **bijbel_schoon)
        bijbeltekst.verrijk_dagen(gegenereerd, bijbel or {})
        data = gegenereerd
    elif wat == "samenvatting":
        basis = llm_maak_basis(bron, volledige_dienst=volledig, taal_hint=taal_hint_gen)
        for k in ("taal", "titel", "bijbelgedeelte", "voorganger", "samenvatting"):
            if basis.get(k):
                data[k] = basis[k]
        data.setdefault("dagen", [])
    else:
        raise ValueError("Onbekende uitvoer.")
    tekst = render.naar_tekst(data)
    store.resultaat_opslaan(video_id, {**bewaard, "data": data, "tekst": tekst})
    return {"video_id": video_id, "data": data, "tekst": tekst}


def genereer_groepsvragen_en_bewaar(video_id, opties):
    """Maak op aanvraag gespreksvragen voor groepen uit het opgeslagen transcript."""
    bewaard = store.resultaat_ophalen(video_id)
    bron = (bewaard or {}).get("preek_schoon") or (bewaard or {}).get("transcript_ruw")
    if not bron:
        raise ValueError("Deze dienst is nog niet voorbereid (geen transcript).")
    data = dict(bewaard.get("data") or {})
    data.pop("voorbereid", None)
    vragen = llm_maak_groepsvragen(
        bron, categorieen=opties.get("categorieen") or [],
        aantal=int(opties.get("aantal") or 10),
        leeftijd=(opties.get("leeftijd") or None),
        bijbelgedeelte=data.get("bijbelgedeelte"), titel=data.get("titel"),
        samenvatting=data.get("samenvatting"), taal_hint=data.get("taal"),
    )
    data["groepsvragen"] = {
        "vragen": vragen,
        "leeftijd": opties.get("leeftijd") or "",
        "aantal": int(opties.get("aantal") or 10),
        "categorieen": list(vragen.keys()),
    }
    tekst = render.naar_tekst(data)
    store.resultaat_opslaan(video_id, {**bewaard, "data": data, "tekst": tekst})
    return {"video_id": video_id, "data": data, "tekst": tekst, "groepsvragen": vragen}


def _voer_taak_uit(taak_id, url):
    taak = taken[taak_id]

    def meld(stap):
        taak["stap"] = stap

    try:
        # De interactieve tool transcribeert + schoont alleen op; genereren gebeurt
        # daarna op aanvraag (de gebruiker kiest zelf) — dat bespaart AI-kosten.
        r = verwerk_en_bewaar(
            url, herverwerk=taak.get("_herverwerk"), meld=meld, alleen_transcript=True,
            preek_tijden=taak.get("_preek_tijden") or [],
        )
        taak["meta"] = r["meta"]
        taak["resultaat"] = {
            "data": _met_labels(r["data"]),
            "tekst": r["tekst"],
            "video_id": r["video_id"],
            "voorbereid": bool(r["data"].get("voorbereid")),
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


# ---- Demo: e-mail alle resultaten ----------------------------------------

def _stuur_demo_email(naar_email: str, r: dict, groepsvragen=None):
    """Bouw en verstuur een demo-e-mail met alle 4 uitvoertypes als PDF-bijlagen."""
    import base64
    import render as _render

    data = r.get("data") or {}
    preek_schoon = r.get("preek_schoon") or ""
    base_url = _base_url_env()

    titel = data.get("titel") or "Preek"
    samenvatting = data.get("samenvatting") or ""
    bijbelgedeelte = data.get("bijbelgedeelte") or ""
    voorganger = data.get("voorganger") or ""
    dagen = data.get("dagen") or []

    # ---- 4 PDF-bijlagen genereren ----
    bijlagen = []

    if preek_schoon:
        try:
            pdf = _render.naar_preek_pdf(data, preek_schoon)
            bijlagen.append({"content": base64.b64encode(pdf).decode(), "name": "preektekst.pdf"})
        except Exception as e:  # noqa: BLE001
            log.warning(f"[demo] preektekst PDF mislukt: {e}")

    if samenvatting:
        try:
            pdf = _render.samenvatting_naar_pdf(data)
            bijlagen.append({"content": base64.b64encode(pdf).decode(), "name": "samenvatting.pdf"})
        except Exception as e:  # noqa: BLE001
            log.warning(f"[demo] samenvatting PDF mislukt: {e}")

    if dagen:
        try:
            pdf = _render.dagstukjes_naar_pdf(data)
            bijlagen.append({"content": base64.b64encode(pdf).decode(), "name": "dagstukjes.pdf"})
        except Exception as e:  # noqa: BLE001
            log.warning(f"[demo] dagstukjes PDF mislukt: {e}")

    if groepsvragen:
        try:
            pdf = _render.demo_groepsvragen_naar_pdf(data, groepsvragen)
            bijlagen.append({"content": base64.b64encode(pdf).decode(), "name": "groepsvragen.pdf"})
        except Exception as e:  # noqa: BLE001
            log.warning(f"[demo] groepsvragen PDF mislukt: {e}")

    # ---- Metadata ----
    meta_delen = []
    if bijbelgedeelte:
        meta_delen.append(bijbelgedeelte)
    if voorganger:
        meta_delen.append(f"Voorganger: {voorganger}")
    meta_html = (" &nbsp;·&nbsp; ".join(meta_delen)) if meta_delen else ""

    # ---- Bijlagen-overzicht voor in de mail ----
    bijlage_namen = [b["name"] for b in bijlagen]
    bijlage_html = "".join(
        f'<li style="margin:3px 0">{naam}</li>' for naam in bijlage_namen
    )

    html = f"""<!DOCTYPE html>
<html lang="nl">
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:600px;margin:0 auto;color:#222">

<div style="background:#5a67d8;color:#fff;padding:20px 24px;border-radius:8px 8px 0 0">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:.1em;opacity:.75;margin-bottom:4px">AfterSermon — demo</div>
  <h1 style="margin:0 0 6px;font-size:22px">{titel}</h1>
  {f'<div style="font-size:13px;opacity:.85">{meta_html}</div>' if meta_html else ''}
</div>

<div style="padding:20px 24px;background:#fff;border:1px solid #e2e6ff;border-top:none;border-radius:0 0 8px 8px">

  <p style="margin:0 0 16px;line-height:1.6">
    Hierbij de vier AfterSermon-documenten voor <b>{titel}</b> als bijlage:
  </p>

  <ul style="margin:0 0 20px;padding-left:1.4rem;line-height:1.8;font-size:14px">
    {bijlage_html if bijlage_html else '<li>Geen bijlagen gegenereerd.</li>'}
  </ul>

  <p style="font-size:13px;color:#555;line-height:1.6;margin:0 0 20px">
    AfterSermon verwerkt elke week de preek van jouw kerk automatisch en stuurt
    overdenkingen, dagstukjes en vragen naar je gemeenteleden.
  </p>

  <a href="{base_url}/admin"
     style="display:inline-block;padding:10px 18px;background:#5a67d8;color:#fff;text-decoration:none;border-radius:6px;font-size:14px">
    Stel je kerk in →
  </a>

  <hr style="border:none;border-top:1px solid #e2e6ff;margin:24px 0">
  <p style="font-size:12px;color:#888;margin:0">Dit is een automatisch gegenereerde demo van <b>AfterSermon</b>.</p>
</div>
</body>
</html>"""

    tekst = f"""AfterSermon demo — {titel}
{"=" * 50}
{bijbelgedeelte}{" · " + voorganger if voorganger else ""}

Hierbij de vier AfterSermon-documenten als bijlage:
{chr(10).join("- " + n for n in bijlage_namen)}

Stel je kerk in: {base_url}/admin
"""

    brevo.verzend(
        naar_email=naar_email,
        onderwerp=f"AfterSermon demo — {titel}",
        html=html,
        tekst=tekst,
        van_naam="AfterSermon",
        bijlagen=bijlagen or None,
    )


def _demo_verwerk_en_mail(url: str, email: str, preek_tijden=None):
    """Verwerk een preek volledig en mail alle 4 uitvoertypes. Draait in achtergrond-thread."""
    try:
        log.info(f"[demo] Verwerking gestart: url={url} email={email} tijden={preek_tijden}")

        r = verwerk_en_bewaar(url, meld=lambda s: log.info(f"[demo] {s}"),
                              preek_tijden=preek_tijden or [])
        video_id = r.get("video_id")
        if not video_id:
            raise ValueError("Kon geen video-id bepalen uit de opgegeven URL.")
        log.info(f"[demo] Verwerking klaar: video_id={video_id}")

        # Stap 2: groepsvragen (extra, met standaard-instellingen; niet fataal als mislukt).
        groepsvragen = None
        try:
            gv_res = genereer_groepsvragen_en_bewaar(video_id, {
                "leeftijd": "Volwassenen",
                "aantal": 8,
                "categorieen": ["terughalen", "verdiepen", "landen", "handen"],
            })
            groepsvragen = gv_res.get("groepsvragen")
            log.info(f"[demo] Groepsvragen klaar: video_id={video_id}")
        except Exception as gv_fout:  # noqa: BLE001
            log.warning(f"[demo] Groepsvragen mislukten (niet fataal): {gv_fout}")

        # Stap 3: lees meest recente store-versie (groepsvragen kunnen erin zitten).
        finaal = store.resultaat_ophalen(video_id) or {}
        r_email = {**r, "data": finaal.get("data") or r.get("data")}
        log.info(f"[demo] E-mail voorbereiden voor {email}...")
        _stuur_demo_email(email, r_email, groepsvragen)
        log.info(f"[demo] E-mail verstuurd naar {email}")
    except Exception as fout:  # noqa: BLE001
        log.error(f"[demo] Verwerking mislukt voor {url}: {fout}", exc_info=True)
        # Stuur foutmelding naar demo-gebruiker — log elke stap zodat er geen silent fail is
        log.info(f"[demo] Foutmail sturen naar {email}...")
        try:
            brevo.verzend(
                naar_email=email,
                onderwerp="AfterSermon demo — verwerking mislukt",
                html=f"<p>Sorry, de verwerking van de preek is mislukt: {fout}</p>"
                     "<p>Probeer het opnieuw op de <a href='" + _base_url_env() + "/demo'>demo-pagina</a>.</p>",
                tekst=f"Sorry, de verwerking mislukt: {fout}",
                van_naam="AfterSermon",
            )
            log.info(f"[demo] Foutmail verstuurd naar {email}")
        except Exception as mail_fout:  # noqa: BLE001
            log.error(f"[demo] Foutmail OOK mislukt voor {email}: {mail_fout}", exc_info=True)


def _debug_transcribeer_en_mail(url: str, email: str, n_delen: int):
    """Download audio, splits in n gelijke stukken, transcribeer elk rauw (geen filtering),
    en stuur alles per mail als .txt bijlagen. Bedoeld om te zien wat Whisper werkelijk
    teruggeeft en welke segmenten muziek vs. spraak zijn."""
    import base64
    import tempfile
    from openai import OpenAI

    log.info(f"[debug] transcriptie gestart: url={url} n_delen={n_delen} email={email}")
    try:
        ffmpeg = audio._ffmpeg()
        client = OpenAI()

        with tempfile.TemporaryDirectory() as tmp:
            # ── 1. Download ──────────────────────────────────────────────────
            log.info("[debug] audio downloaden...")
            bron = audio._download_audio_gecached(url, tmp)
            duur = audio._duur_van(ffmpeg, bron)
            grootte_mb = os.path.getsize(bron) / 1e6
            log.info(f"[debug] gedownload: {grootte_mb:.1f}MB, duur={duur}s")
            if not duur:
                raise RuntimeError("Kon duur van audio niet bepalen via ffmpeg.")

            # ── 2. Splits in n_delen gelijke stukken ─────────────────────────
            deel_sec = duur / n_delen
            bijlagen = []
            samenvatting = [
                f"URL:          {url}",
                f"Duur:         {duur}s  ({duur//60:.0f}m {duur%60:.0f}s)",
                f"Bestand:      {grootte_mb:.1f} MB",
                f"Whisper model: {audio.TRANSCRIBE_MODEL}",
                f"Aantal delen:  {n_delen}  (~{deel_sec/60:.1f} min elk)",
                "",
            ]

            for i in range(n_delen):
                start = i * deel_sec
                stop = min((i + 1) * deel_sec, duur)
                pad = os.path.join(tmp, f"deel_{i+1}.mp3")
                log.info(f"[debug] knippen deel {i+1}: {start:.0f}s–{stop:.0f}s")
                audio._knip(ffmpeg, bron, start, stop, pad)
                deel_kb = os.path.getsize(pad) / 1024

                # ── Rauwe transcriptie (geen verbose_json, geen filtering) ───
                log.info(f"[debug] transcriberen deel {i+1}...")
                with open(pad, "rb") as f:
                    ruw_resp = client.audio.transcriptions.create(
                        file=f, model=audio.TRANSCRIBE_MODEL, response_format="text"
                    )
                ruw_tekst = ruw_resp if isinstance(ruw_resp, str) else getattr(ruw_resp, "text", str(ruw_resp))
                ruw_tekst = (ruw_tekst or "").strip()

                # ── Verbose_json voor segment-scores ─────────────────────────
                segment_regels = []
                try:
                    with open(pad, "rb") as f:
                        vb = client.audio.transcriptions.create(
                            file=f, model=audio.TRANSCRIBE_MODEL,
                            response_format="verbose_json"
                        )
                    for s in (getattr(vb, "segments", None) or []):
                        if isinstance(s, dict):
                            t0 = s.get("start", 0); tx = s.get("text", "")
                            nsp = s.get("no_speech_prob"); lp = s.get("avg_logprob")
                        else:
                            t0 = getattr(s, "start", 0); tx = getattr(s, "text", "")
                            nsp = getattr(s, "no_speech_prob", None)
                            lp = getattr(s, "avg_logprob", None)
                        score = ""
                        if nsp is not None:
                            score += f" nsp={nsp:.2f}"
                        if lp is not None:
                            score += f" lp={lp:.2f}"
                        muziek = " ← MUZIEK?" if (
                            (nsp is not None and nsp > 0.5) or
                            (lp is not None and lp < -1.2)
                        ) else ""
                        # Tijdstempel relatief aan start van het hele bestand
                        abs_t = start + t0
                        segment_regels.append(
                            f"[{abs_t//60:.0f}m{abs_t%60:04.1f}s]{score}{muziek}  {tx}"
                        )
                except Exception as ve:
                    segment_regels.append(f"(verbose_json niet beschikbaar: {ve})")

                woordtelling = len(ruw_tekst.split())
                samenvatting += [
                    f"── Deel {i+1}/{n_delen}  ({start:.0f}s – {stop:.0f}s, {deel_kb:.0f} KB) ──",
                    f"   Woorden:  {woordtelling}",
                    f"   Begin:    {ruw_tekst[:120]}",
                    f"   Einde:    ...{ruw_tekst[-120:]}",
                    "",
                ]

                bijlage_inhoud = (
                    f"DEEL {i+1}/{n_delen}  [{start:.0f}s – {stop:.0f}s]  ({deel_kb:.0f} KB)\n"
                    f"Whisper model: {audio.TRANSCRIBE_MODEL}\n"
                    f"Woorden (ruw): {woordtelling}\n"
                    f"{'='*70}\n\n"
                    f"RUWE TRANSCRIPTIE (response_format=text, geen filtering)\n"
                    f"{'-'*70}\n"
                    f"{ruw_tekst}\n\n"
                    f"SEGMENT-SCORES (verbose_json)\n"
                    f"{'-'*70}\n"
                    f"Formaat: [MM:SS.s] nsp=no_speech_prob lp=avg_logprob  tekst\n"
                    f"nsp > 0.5 of lp < -1.2 = verdacht (muziek/ruis)\n\n"
                ) + "\n".join(segment_regels)

                bijlagen.append({
                    "content": base64.b64encode(bijlage_inhoud.encode("utf-8")).decode(),
                    "name": f"deel_{i+1}_van_{n_delen}.txt",
                })

            samenvatting_tekst = "\n".join(samenvatting)
            brevo.verzend(
                naar_email=email,
                onderwerp=f"[DEBUG] Transcriptie {_video_id(url) or 'video'} ({n_delen} delen)",
                html=f"<pre style='font-family:monospace;font-size:12px'>{samenvatting_tekst}</pre>",
                tekst=samenvatting_tekst,
                van_naam="AfterSermon Debug",
                bijlagen=bijlagen,
            )
            log.info(f"[debug] mail met {n_delen} bijlagen verstuurd naar {email}")

    except Exception as fout:
        log.error(f"[debug] transcriptie mislukt: {fout}", exc_info=True)
        try:
            brevo.verzend(
                naar_email=email,
                onderwerp="[DEBUG] Transcriptie mislukt",
                html=f"<pre>{fout}</pre>",
                tekst=str(fout),
                van_naam="AfterSermon Debug",
            )
        except Exception:
            pass


@app.post("/api/debug/transcribeer")
def debug_transcribeer(body: dict, request: Request):
    """Debug-endpoint: download audio, splits in N delen, transcribeer elk rauw
    en stuur alles als .txt bijlagen per mail.

    Vereist een actieve admin-sessie ÓÓF de DEBUG_SLEUTEL env-variabele als
    'sleutel' in de request-body. Stel DEBUG_SLEUTEL in Railway in als tijdelijke
    sleutel; haal hem daarna weg.

    Body: {url, email, sleutel?, n_delen? (standaard 5, max 10)}
    """
    sleutel_env = os.environ.get("DEBUG_SLEUTEL", "")
    sleutel_req = (body or {}).get("sleutel", "").strip()
    heeft_sessie = bool(request.session.get("kerk_id"))
    sleutel_ok = sleutel_env and sleutel_req == sleutel_env

    if not heeft_sessie and not sleutel_ok:
        raise HTTPException(403, "Log in als admin of geef de DEBUG_SLEUTEL mee.")

    url = (body or {}).get("url", "").strip()
    email = (body or {}).get("email", "").strip()
    n_delen = max(1, min(int((body or {}).get("n_delen", 5)), 10))

    if not url:
        raise HTTPException(400, "URL vereist.")
    if not email or "@" not in email:
        raise HTTPException(400, "Geldig e-mailadres vereist.")

    threading.Thread(
        target=_debug_transcribeer_en_mail, args=(url, email, n_delen), daemon=True
    ).start()
    return {"status": "gestart", "n_delen": n_delen, "email": email}


@app.post("/api/demo/verwerk")
def demo_verwerk(body: dict):
    """Demo-endpoint: verwerk een preek op de achtergrond en mail alle resultaten."""
    url = (body or {}).get("url", "").strip()
    email = (body or {}).get("email", "").strip()
    preek_tijden = (body or {}).get("preek_tijden") or []
    if not url:
        raise HTTPException(400, "Plak eerst een preeklink.")
    if not email or not re.match(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Vul een geldig e-mailadres in.")
    threading.Thread(target=_demo_verwerk_en_mail, args=(url, email, preek_tijden), daemon=True).start()
    return {"status": "ok"}


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
    """Herken een geplakte link: kanaal → dienstenlijst; enkele preek → verwerken.

    Bij een enkelvoudige preeklink proberen we automatisch het bijbehorende kanaal
    te vinden (werkt voor alle drie platforms). Als dat lukt, geven we de volledige
    dienstenlijst terug — de beheerder hoeft dan niet apart de kanaal-URL te zoeken.
    """
    url = (url or "").strip()
    if not url:
        raise HTTPException(400, "Plak eerst een kanaal- of preeklink.")
    typ, soort = _classificeer(url)
    if typ is None:
        raise HTTPException(400, "Geef een YouTube-, Kerkdienstgemist- of Kerkomroep-link op.")
    if soort == "enkel":
        kanaal_url = _kanaal_van_enkele(url)
        if kanaal_url:
            kanaal_typ, _ = _classificeer(kanaal_url)
            return {
                "soort": "lijst",
                "kanaal": kanaal_url,
                "enkel_url": url,          # originele preeklink bewaren voor referentie
                "diensten": _laad_diensten(kanaal_typ or typ, kanaal_url, vernieuw),
            }
        # Kanaal-detect mislukt (onverwachte URL-vorm): geef de enkel-URL terug
        # zodat de UI de beheerder om de kanaal-URL kan vragen.
        return {"soort": "enkel", "url": url}
    return {
        "soort": "lijst",
        "kanaal": url,
        "diensten": _laad_diensten(typ, url, vernieuw),
    }


def _kanaal_van_enkele(url):
    """Best-effort: leid het kanaal (streams-tabblad) af van één preeklink.

    - YouTube: yt-dlp geeft het kanaal-URL van de video.
    - Kerkdienstgemist: station-id zit in de recording-URL; geen API nodig.
    - Kerkomroep: kerk-id zit in de audio-URL; geen API nodig.
    """
    u = (url or "").lower()

    # Kerkdienstgemist: .../stations/{id}/events/recording/{rid} → .../stations/{id}
    if kerkdienstgemist.is_kerkdienstgemist(url) and "/recording/" in u:
        m = kerkdienstgemist.STATION_RE.search(url)
        if m:
            return f"https://kerkdienstgemist.nl/stations/{m.group(1)}"
        return None

    # Kerkomroep: .../kerken/{id}/audio/{sid} → .../kerken/{id}
    if kerkomroep.is_kerkomroep(url) and "/audio/" in u:
        m = kerkomroep.KERK_RE.search(url)
        if m:
            return f"https://kerkomroep.nl/kerken/{m.group(1)}"
        return None

    # YouTube: yt-dlp haalt het kanaal-URL op via de video-info.
    if not ("youtube.com" in u or "youtu.be" in u):
        return None
    try:
        info = ts._haal_info(url) or {}
    except Exception:  # noqa: BLE001
        return None
    kanaal = (
        info.get("channel_url")
        or info.get("uploader_url")
        or info.get("uploader_id")
    )
    if not kanaal:
        return None
    if not kanaal.startswith("http"):
        kanaal = "https://www.youtube.com/" + kanaal.lstrip("/")
    return _youtube_kanaal_url(kanaal)


@app.get("/api/kanaal-van-preek")
def kanaal_van_preek(url: str = ""):
    """Probeer het kanaal af te leiden van één geplakte preeklink (voor 'automatiseer')."""
    return {"kanaal_url": _kanaal_van_enkele((url or "").strip())}


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
        "_preek_tijden": verzoek.preek_tijden or [],
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
    # Gebruik `is None`-check: een lege dict {} (alleen-transcript-tussenstand)
    # is wél geldig; ontbrekende sleutel (None) betekent "niet verwerkt".
    if bewaard is None or bewaard.get("data") is None:
        raise HTTPException(404, "Voor deze dienst is nog geen verwerking beschikbaar.")
    return bewaard


DAG_VELDEN = ("titel", "bijbeltekst", "gedachte", "vraag_volwassenen",
              "vraag_kinderen")


@app.post("/api/genereer/{video_id}")
def genereer(video_id: str, body: dict):
    """Genereer op aanvraag één uitvoer uit het opgeslagen transcript (geen AI tenzij
    de gebruiker hier expliciet om vraagt). `wat`: 'samenvatting' of 'dagstukjes'."""
    wat = (body or {}).get("wat", "")
    if wat not in ("samenvatting", "dagstukjes"):
        raise HTTPException(400, "Kies 'samenvatting' of 'dagstukjes'.")
    try:
        r = genereer_en_bewaar(video_id, wat)
    except ValueError as fout:
        raise HTTPException(400, str(fout))
    except Exception as fout:  # noqa: BLE001
        raise HTTPException(502, f"Genereren lukte niet: {fout}")
    return {"data": _met_labels(r["data"]), "tekst": r["tekst"], "video_id": video_id}


@app.post("/api/groepsvragen/{video_id}")
def groepsvragen(video_id: str, body: dict):
    """Gespreksvragen voor groepen (optie 3): leeftijd, aantal en soorten vragen."""
    try:
        r = genereer_groepsvragen_en_bewaar(video_id, body or {})
    except ValueError as fout:
        raise HTTPException(400, str(fout))
    except Exception as fout:  # noqa: BLE001
        raise HTTPException(502, f"Vragen maken lukte niet: {fout}")
    return {"data": _met_labels(r["data"]), "groepsvragen": r["groepsvragen"],
            "video_id": video_id}


@app.get("/api/groepsvragen/{video_id}.pdf")
def groepsvragen_pdf(video_id: str):
    bewaard = _ophalen_of_404(video_id)
    data = bewaard["data"]
    if not (data.get("groepsvragen") or {}).get("vragen"):
        raise HTTPException(404, "Er zijn nog geen groepsvragen gegenereerd.")
    inhoud = render.groepsvragen_naar_pdf(data, ondertitel=bewaard.get("ondertitel"))
    return _bestand(inhoud, "application/pdf", _bestandsnaam(data, "-groepsvragen", "pdf"))


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


@app.get("/api/data/{video_id}")
def data_ophalen(video_id: str):
    """Huidige (opgeslagen) verwerking voor de editor — regenereert niets."""
    bewaard = store.resultaat_ophalen(video_id)
    if not bewaard:
        raise HTTPException(404, "Voor deze dienst is nog geen verwerking beschikbaar.")
    data = bewaard.get("data") or {}
    return {
        "video_id": video_id,
        "data": _met_labels(data),
        "heeft_dagen": bool(data.get("dagen")),
        "heeft_samenvatting": bool((data.get("samenvatting") or "").strip()),
        "heeft_groepsvragen": bool((data.get("groepsvragen") or {}).get("vragen")),
        "heeft_preek": bool(bewaard.get("preek_schoon")),
        "heeft_ruw": bool((bewaard.get("transcript_ruw") or "").strip()),
    }


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


@app.get("/setup")
def setup():
    """Stap-voor-stap onboarding-wizard voor nieuwe beheerders."""
    return FileResponse(
        "static/setup.html", headers={"Cache-Control": "no-cache"}
    )


if __name__ == "__main__":
    # Zelfstandig starten (Docker/Railway): lees de poort uit de omgeving, zodat
    # we niet afhankelijk zijn van shell-expansie van $PORT in het startcommando.
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
