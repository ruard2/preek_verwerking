"""Admin-API: registratie, login, e-mailverificatie, reset en kanaalinstelling.

Server-rendered pagina is static/admin.html; hier zitten de JSON-endpoints en
de sessie-afhandeling (ondertekende cookie via Starlette SessionMiddleware).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

import auth
import brevo
from db import Church, SessionLocal

router = APIRouter()


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
    frequentie: str = "wekelijks"


# ---- E-mails ----
def _stuur_verificatie(request, kerk, token):
    link = f"{_basis_url(request)}/api/admin/verify?token={token}"
    brevo.verzend(
        kerk.email,
        "Bevestig je Preekverwerker-account",
        f"<p>Welkom{' ' + kerk.naam if kerk.naam else ''}!</p>"
        f"<p>Bevestig je account via deze link:</p>"
        f'<p><a href="{link}">{link}</a></p>',
        tekst=f"Bevestig je account: {link}",
    )


def _stuur_reset(request, kerk, token):
    link = f"{_basis_url(request)}/admin?reset={token}"
    brevo.verzend(
        kerk.email,
        "Wachtwoord opnieuw instellen",
        f"<p>Stel een nieuw wachtwoord in via deze link (2 uur geldig):</p>"
        f'<p><a href="{link}">{link}</a></p>',
        tekst=f"Nieuw wachtwoord instellen: {link}",
    )


# ---- Endpoints ----
@router.post("/api/admin/register")
def register(body: RegistratieBody, request: Request, db=Depends(get_db)):
    try:
        kerk, token = auth.registreer(db, body.naam, body.email, body.wachtwoord)
    except auth.RegistratieFout as fout:
        raise HTTPException(400, str(fout))
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
        "naam": kerk.naam,
        "email": kerk.email,
        "kanaal_url": kerk.kanaal_url,
        "auto_versturen": kerk.auto_versturen,
        "frequentie": kerk.frequentie,
    }


@router.post("/api/admin/kanaal")
def kanaal(body: KanaalBody, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    kerk.kanaal_url = (body.kanaal_url or "").strip()
    kerk.auto_versturen = bool(body.auto_versturen)
    kerk.frequentie = body.frequentie if body.frequentie in ("wekelijks", "dagelijks") else "wekelijks"
    db.commit()
    return {"ok": True, "kanaal_url": kerk.kanaal_url}


@router.get("/admin")
def admin_pagina():
    return FileResponse("static/admin.html", headers={"Cache-Control": "no-cache"})
