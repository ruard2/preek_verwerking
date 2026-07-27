"""Admin-API: registratie, login, e-mailverificatie, reset en kanaalinstelling.

Server-rendered pagina is static/admin.html; hier zitten de JSON-endpoints en
de sessie-afhandeling (ondertekende cookie via Starlette SessionMiddleware).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel

import threading

from sqlalchemy import func, select

import auth
import automatisering
import brevo
import levering
import render
import store
import subscribers
import ui_i18n
from db import Church, SessionLocal, Subscriber, Uitzending, Verzending

router = APIRouter()


def _met_labels(data):
    v = dict(data)
    v["_labels"] = render.labels(data.get("taal"))
    return v


def _uit_op_token(db, token):
    return db.scalar(
        select(Uitzending).where(Uitzending.goedkeur_token == token)
    ) if token else None


def _qr_svg(data: str) -> bytes:
    """Genereer een QR-code als SVG (geen externe afhankelijkheden nodig)."""
    import qrcode
    import qrcode.image.svg

    img = qrcode.make(data, image_factory=qrcode.image.svg.SvgPathImage, box_size=10)
    import io

    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def huidige_kerk(request: Request, db) -> Church | None:
    kid = request.session.get("kerk_id")
    return db.get(Church, kid) if kid else None


def _vereis_kerk(request: Request, db) -> Church:
    kerk = huidige_kerk(request, db)
    if not kerk:
        raise HTTPException(401, "Niet ingelogd.")
    return kerk


def _basis_url(request: Request) -> str:
    return str(request.base_url).rstrip("/")


# ---- Verzoekmodellen ----
class RegistratieBody(BaseModel):
    naam: str = ""
    email: str
    wachtwoord: str
    taal: str = "auto"


class LoginBody(BaseModel):
    email: str
    wachtwoord: str


class EmailBody(BaseModel):
    email: str


class ResetBody(BaseModel):
    token: str
    wachtwoord: str


class KanaalBody(BaseModel):
    kanaal_url: str = ""
    auto_versturen: bool = False
    tijdzone: str = "Europe/Amsterdam"
    versturen_zonder_goedkeuring: bool = False
    admin_taal: str = "auto"
    inschrijf_taal: str = "auto"
    communicatie_taal: str = "nl"


class InschrijverBody(BaseModel):
    naam: str = ""
    email: str
    telefoon: str = ""
    frequentie: str = "wekelijks"
    ontvang_dag: int = 0
    ontvang_tijd: str = "07:00"


class InschrijvenBody(BaseModel):
    kerk_id: int
    naam: str = ""
    email: str
    telefoon: str = ""
    frequentie: str = "wekelijks"


class VoorkeurBody(BaseModel):
    token: str
    naam: str = ""
    telefoon: str = ""
    frequentie: str = "wekelijks"
    ontvang_dag: int = 0
    ontvang_tijd: str = "07:00"


# ---- E-mails ----
def _stuur_verificatie(request, kerk, token):
    link = f"{_basis_url(request)}/api/admin/verify?token={token}"
    t = ui_i18n.messages(kerk.communicatie_taal)
    brevo.verzend(
        kerk.email,
        t["verify_subject"],
        f"<p>{t['welcome']}{' ' + kerk.naam if kerk.naam else ''}!</p>"
        f"<p>{t['verify_account']}</p>"
        f'<p><a href="{link}">{link}</a></p>',
        tekst=f"{t['verify_account']} {link}",
    )


def _stuur_reset(request, kerk, token):
    link = f"{_basis_url(request)}/admin?reset={token}"
    t = ui_i18n.messages(kerk.communicatie_taal)
    brevo.verzend(
        kerk.email,
        t["reset_subject"],
        f"<p>{t['reset_body']}</p>"
        f'<p><a href="{link}">{link}</a></p>',
        tekst=f"{t['reset_subject']}: {link}",
    )


# ---- Endpoints ----
@router.post("/api/admin/register")
def register(body: RegistratieBody, request: Request, db=Depends(get_db)):
    try:
        kerk, token = auth.registreer(db, body.naam, body.email, body.wachtwoord)
    except auth.RegistratieFout as fout:
        raise HTTPException(400, str(fout))
    kerk.admin_taal = ui_i18n.valid(body.taal, "auto")
    kerk.inschrijf_taal = kerk.admin_taal
    kerk.communicatie_taal = ui_i18n.valid(body.taal, "nl", allow_auto=False)
    db.commit()
    _stuur_verificatie(request, kerk, token)
    return {"ok": True, "email": kerk.email}


@router.get("/api/admin/verify")
def verify(token: str, request: Request, db=Depends(get_db)):
    kerk = auth.verifieer_email(db, token)
    doel = "/admin?geverifieerd=1" if kerk else "/admin?verify_mislukt=1"
    return RedirectResponse(doel, status_code=303)


@router.post("/api/admin/login")
def login(body: LoginBody, request: Request, db=Depends(get_db)):
    resultaat = auth.login(db, body.email, body.wachtwoord)
    if resultaat is None:
        raise HTTPException(400, "Onjuist e-mailadres of wachtwoord.")
    if resultaat is False:
        raise HTTPException(403, "Bevestig eerst je e-mailadres via de link in je mail.")
    request.session["kerk_id"] = resultaat.id
    return {"ok": True}


@router.post("/api/admin/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.post("/api/admin/reset-aanvraag")
def reset_aanvraag(body: EmailBody, request: Request, db=Depends(get_db)):
    token = auth.start_reset(db, body.email)
    if token:
        kerk = auth._kerk_op_email(db, body.email)
        _stuur_reset(request, kerk, token)
    # Altijd hetzelfde antwoord (verklap niet of het adres bestaat).
    return {"ok": True}


@router.post("/api/admin/reset")
def reset(body: ResetBody, db=Depends(get_db)):
    try:
        kerk = auth.reset_wachtwoord(db, body.token, body.wachtwoord)
    except auth.RegistratieFout as fout:
        raise HTTPException(400, str(fout))
    if not kerk:
        raise HTTPException(400, "Deze reset-link is ongeldig of verlopen.")
    return {"ok": True}


@router.get("/api/admin/mij")
def mij(request: Request, db=Depends(get_db)):
    kerk = huidige_kerk(request, db)
    if not kerk:
        return {"ingelogd": False}
    return {
        "ingelogd": True,
        "id": kerk.id,
        "naam": kerk.naam,
        "email": kerk.email,
        "kanaal_url": kerk.kanaal_url,
        "auto_versturen": kerk.auto_versturen,
        "tijdzone": kerk.tijdzone,
        "versturen_zonder_goedkeuring": kerk.versturen_zonder_goedkeuring,
        "admin_taal": kerk.admin_taal,
        "inschrijf_taal": kerk.inschrijf_taal,
        "communicatie_taal": kerk.communicatie_taal,
    }


@router.post("/api/admin/kanaal")
def kanaal(body: KanaalBody, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    kerk.kanaal_url = (body.kanaal_url or "").strip()
    kerk.auto_versturen = bool(body.auto_versturen)
    kerk.tijdzone = (body.tijdzone or "Europe/Amsterdam").strip()
    kerk.versturen_zonder_goedkeuring = bool(body.versturen_zonder_goedkeuring)
    kerk.admin_taal = ui_i18n.valid(body.admin_taal, "auto")
    kerk.inschrijf_taal = ui_i18n.valid(body.inschrijf_taal, "auto")
    kerk.communicatie_taal = ui_i18n.valid(
        body.communicatie_taal, "nl", allow_auto=False
    )
    db.commit()
    return {"ok": True, "kanaal_url": kerk.kanaal_url}


# ---- Inschrijverbeheer (admin) ----
def _sub_json(s):
    data = {
        "id": s.id, "naam": s.naam, "email": s.email, "telefoon": s.telefoon,
        "frequentie": s.frequentie, "ontvang_dag": s.ontvang_dag,
        "ontvang_tijd": s.ontvang_tijd, "bevestigd": s.bevestigd,
    }
    if getattr(s, "kerk", None):
        data["communicatie_taal"] = s.kerk.communicatie_taal
    return data


@router.get("/api/admin/inschrijvers")
def inschrijvers_lijst(request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    return [_sub_json(s) for s in subscribers.lijst(db, kerk.id)]


@router.post("/api/admin/inschrijvers")
def inschrijver_toevoegen(body: InschrijverBody, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    try:
        # Door de kerk zelf toegevoegd → direct bevestigd (kerk staat ervoor in).
        sub, _ = subscribers.maak_inschrijver(
            db, kerk.id, body.naam, body.email, body.telefoon, body.frequentie,
            body.ontvang_dag, body.ontvang_tijd, bevestigd=True,
        )
    except subscribers.InschrijfFout as fout:
        raise HTTPException(400, str(fout))
    return _sub_json(sub)


@router.delete("/api/admin/inschrijvers/{sub_id}")
def inschrijver_verwijderen(sub_id: int, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    sub = db.get(Subscriber, sub_id)
    if not sub or sub.kerk_id != kerk.id:
        raise HTTPException(404, "Inschrijver niet gevonden.")
    subscribers.afmelden(db, sub)
    return {"ok": True}


@router.get("/api/admin/inschrijflink")
def inschrijflink(request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    return {"url": f"{_basis_url(request)}/inschrijven?kerk={kerk.id}"}


@router.get("/api/admin/qr")
def qr(request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    url = f"{_basis_url(request)}/inschrijven?kerk={kerk.id}"
    svg = _qr_svg(url)
    return Response(content=svg, media_type="image/svg+xml")


@router.post("/api/admin/verstuur/{video_id}")
def verstuur(video_id: str, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    bewaard = store.resultaat_ophalen(video_id)
    if not bewaard or not bewaard.get("data"):
        raise HTTPException(404, "Voor deze dienst is nog geen verwerking beschikbaar.")
    aantal = levering.verstuur_weekboekje(db, kerk, bewaard["data"], _basis_url(request))
    return {"ok": True, "verzonden": aantal}


# ---- Uitzendingen / automatisering (admin) ----
@router.get("/api/admin/uitzendingen")
def uitzendingen(request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    rijen = db.scalars(
        select(Uitzending).where(Uitzending.kerk_id == kerk.id)
        .order_by(Uitzending.datum.desc())
    )
    uit = []
    for u in rijen:
        aantal = db.scalar(
            select(func.count()).select_from(Verzending)
            .where(Verzending.uitzending_id == u.id)
        )
        uit.append({
            "video_id": u.video_id, "titel": u.titel, "datum": str(u.datum),
            "goedgekeurd": u.goedgekeurd, "verzonden": aantal or 0,
        })
    return uit


@router.post("/api/admin/scan-nu")
def scan_nu(request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    kerk_id, base = kerk.id, _basis_url(request)

    def werk():
        s = SessionLocal()
        try:
            automatisering.scan_kerk(s, s.get(Church, kerk_id), base)
        except Exception:  # noqa: BLE001
            import traceback

            traceback.print_exc()
        finally:
            s.close()

    threading.Thread(target=werk, daemon=True).start()
    return {"ok": True, "gestart": True}


# ---- Goedkeuren / bewerken via magische link (geen login) ----
@router.get("/api/uitzending/goedkeuren")
def uitzending_goedkeuren_link(token: str, db=Depends(get_db)):
    uit = _uit_op_token(db, token)
    if uit:
        uit.goedgekeurd = True
        db.commit()
        return RedirectResponse(f"/uitzending?token={token}&goedgekeurd=1", status_code=303)
    return RedirectResponse("/uitzending?fout=1", status_code=303)


@router.post("/api/uitzending/goedkeuren")
def uitzending_goedkeuren(body: dict, db=Depends(get_db)):
    uit = _uit_op_token(db, (body or {}).get("token", ""))
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    uit.goedgekeurd = True
    db.commit()
    return {"ok": True}


@router.get("/api/uitzending/{token}")
def uitzending_data(token: str, db=Depends(get_db)):
    uit = _uit_op_token(db, token)
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    bewaard = store.resultaat_ophalen(uit.video_id) or {}
    data = bewaard.get("data") or {}
    return {
        "titel": uit.titel, "datum": str(uit.datum), "goedgekeurd": uit.goedgekeurd,
        "video_id": uit.video_id, "data": _met_labels(data),
        "tekst": bewaard.get("tekst", ""),
    }


@router.post("/api/uitzending/bewerk")
def uitzending_bewerk(body: dict, db=Depends(get_db)):
    uit = _uit_op_token(db, (body or {}).get("token", ""))
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    bewaard = store.resultaat_ophalen(uit.video_id)
    if not bewaard or not bewaard.get("data"):
        raise HTTPException(404, "Geen resultaat gevonden.")
    data = render.pas_bewerking_toe(bewaard["data"], (body or {}).get("velden") or {})
    tekst = render.naar_tekst(data)
    store.resultaat_opslaan(uit.video_id, {**bewaard, "data": data, "tekst": tekst})
    return {"ok": True, "data": _met_labels(data), "tekst": tekst}


@router.get("/uitzending")
def uitzending_pagina():
    return FileResponse("static/uitzending.html", headers={"Cache-Control": "no-cache"})


# ---- Publieke inschrijving (geen login) ----
@router.get("/api/kerk/{kerk_id}")
def kerk_info(kerk_id: int, db=Depends(get_db)):
    kerk = db.get(Church, kerk_id)
    if not kerk:
        raise HTTPException(404, "Kerk niet gevonden.")
    return {"naam": kerk.naam or "AfterSermon", "inschrijf_taal": kerk.inschrijf_taal}


@router.post("/api/inschrijven")
def inschrijven(body: InschrijvenBody, request: Request, db=Depends(get_db)):
    kerk = db.get(Church, body.kerk_id)
    if not kerk:
        raise HTTPException(404, "Kerk niet gevonden.")
    try:
        sub, _ = subscribers.maak_inschrijver(
            db, kerk.id, body.naam, body.email, body.telefoon, body.frequentie,
        )
    except subscribers.InschrijfFout as fout:
        raise HTTPException(400, str(fout))
    if not sub.bevestigd and sub.bevestig_token:
        link = f"{_basis_url(request)}/api/inschrijven/bevestig?token={sub.bevestig_token}"
        t = ui_i18n.messages(kerk.communicatie_taal)
        brevo.verzend(
            sub.email,
            t["subscribe_subject"].format(church=kerk.naam or t["church"]),
            f"<p>{t['subscribe_body']}</p>"
            f'<p><a href="{link}">{link}</a></p>'
            f"<p>{t['ignore']}</p>",
            tekst=f"{t['subscribe_body']} {link}",
            van_naam=kerk.naam or None, antwoord_naar=kerk.email or None,
        )
    return {"ok": True}


@router.get("/api/inschrijven/bevestig")
def inschrijven_bevestig(token: str, db=Depends(get_db)):
    sub = subscribers.bevestig(db, token)
    doel = "/inschrijven?bevestigd=1" if sub else "/inschrijven?bevestig_mislukt=1"
    return RedirectResponse(doel, status_code=303)


@router.get("/api/voorkeuren/{token}")
def voorkeuren_ophalen(token: str, db=Depends(get_db)):
    sub = subscribers.op_voorkeur_token(db, token)
    if not sub:
        raise HTTPException(404, "Onbekende of verlopen link.")
    return _sub_json(sub)


@router.post("/api/voorkeuren")
def voorkeuren_opslaan(body: VoorkeurBody, db=Depends(get_db)):
    sub = subscribers.op_voorkeur_token(db, body.token)
    if not sub:
        raise HTTPException(404, "Onbekende of verlopen link.")
    subscribers.werk_voorkeuren_bij(
        db, sub, naam=body.naam, telefoon=body.telefoon, frequentie=body.frequentie,
        ontvang_dag=body.ontvang_dag, ontvang_tijd=body.ontvang_tijd,
    )
    return {"ok": True}


@router.post("/api/afmelden")
def afmelden(body: dict, db=Depends(get_db)):
    sub = subscribers.op_voorkeur_token(db, (body or {}).get("token", ""))
    if sub:
        subscribers.afmelden(db, sub)
    return {"ok": True}


@router.get("/inschrijven")
def inschrijven_pagina():
    return FileResponse("static/inschrijven.html", headers={"Cache-Control": "no-cache"})


@router.get("/voorkeuren")
def voorkeuren_pagina():
    return FileResponse("static/voorkeuren.html", headers={"Cache-Control": "no-cache"})


@router.get("/afmelden")
def afmelden_pagina():
    return FileResponse("static/voorkeuren.html", headers={"Cache-Control": "no-cache"})


@router.get("/")
@router.get("/admin")
def admin_pagina():
    return FileResponse("static/admin.html", headers={"Cache-Control": "no-cache"})
