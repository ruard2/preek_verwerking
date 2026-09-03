"""Admin-API: registratie, login, e-mailverificatie, reset en kanaalinstelling.

Server-rendered pagina is static/admin.html; hier zitten de JSON-endpoints en
de sessie-afhandeling (ondertekende cookie via Starlette SessionMiddleware).
"""

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel

import os
import re
import secrets
import threading

from sqlalchemy import func, select

import auth
import automatisering
import brevo
import ratelimit
import levering
import render
import store
import push
import subscribers
import ui_i18n
import community_tools
from db import Church, Medebeheerder, SessionLocal, Subscriber, Uitzending, Verzending

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


@router.get("/api/community-tools/sso")
def community_tools_sso(ct_ticket: str, request: Request, db=Depends(get_db)):
    """Wissel een eenmalig centraal ticket en open de gekoppelde kerkomgeving."""
    # Een centrale login mag nooit terugvallen op een eerder lokaal account.
    # Wis daarom de bestaande identiteit vóór ticketvalidatie; alleen een
    # volledig geslaagde exchange mag hieronder een nieuwe sessie zetten.
    request.session.clear()
    try:
        context = community_tools.wissel_ticket(ct_ticket)
        gebruiker = context["user"]
        organisatie = context["organization"]
        kerk = db.scalar(
            select(Church).where(
                Church.community_tools_organization_id == organisatie["id"]
            )
        )
        if not kerk:
            kerk = db.scalar(
                select(Church).where(Church.email == gebruiker["email"].lower())
            )
        if not kerk:
            medebeheerder = db.scalar(
                select(Medebeheerder).where(
                    Medebeheerder.email == gebruiker["email"].lower()
                )
            )
            kerk = db.get(Church, medebeheerder.kerk_id) if medebeheerder else None

        if not kerk:
            kerk = Church(
                naam=organisatie["name"],
                email=gebruiker["email"].lower(),
                wachtwoord_hash=auth.hash_wachtwoord(secrets.token_urlsafe(48)),
                email_geverifieerd=True,
                community_tools_organization_id=organisatie["id"],
                community_tools_user_id=gebruiker["id"],
            )
            db.add(kerk)
            db.flush()
        else:
            if (
                kerk.community_tools_organization_id
                and kerk.community_tools_organization_id != organisatie["id"]
            ):
                raise ValueError("Lokale kerk is al aan een andere organisatie gekoppeld.")
            kerk.community_tools_organization_id = organisatie["id"]
            if kerk.email.lower() == gebruiker["email"].lower():
                if (
                    kerk.community_tools_user_id
                    and kerk.community_tools_user_id != gebruiker["id"]
                ):
                    raise ValueError("Hoofdaccount is al aan een andere gebruiker gekoppeld.")
                kerk.community_tools_user_id = gebruiker["id"]
            else:
                medebeheerder = db.scalar(
                    select(Medebeheerder).where(
                        (Medebeheerder.community_tools_user_id == gebruiker["id"])
                        | (Medebeheerder.email == gebruiker["email"].lower())
                    )
                )
                if medebeheerder and medebeheerder.kerk_id != kerk.id:
                    raise ValueError("Beheerder hoort bij een andere lokale kerk.")
                if not medebeheerder:
                    medebeheerder = Medebeheerder(
                        kerk_id=kerk.id,
                        naam=gebruiker.get("name", ""),
                        email=gebruiker["email"].lower(),
                        community_tools_user_id=gebruiker["id"],
                        email_geverifieerd=True,
                    )
                    db.add(medebeheerder)
                else:
                    medebeheerder.community_tools_user_id = gebruiker["id"]
                    medebeheerder.email_geverifieerd = True

        db.commit()
        request.session["kerk_id"] = kerk.id
        return RedirectResponse("/admin", status_code=303)
    except Exception:
        db.rollback()
        return RedirectResponse("/admin?error=community-tools", status_code=303)


@router.get("/api/community-tools/v1/organizations/{organization_id}/users")
def community_tools_organization_users(
    organization_id: str,
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
):
    """Geef uitsluitend beheeraccounts van de gekoppelde kerk terug.

    Dit endpoint is aanvullend op de bestaande standalone login en leest geen
    inschrijvers, preken of andere inhoudelijke kerkgegevens uit.
    """
    if not community_tools.verifieer_beheer_token(authorization):
        raise HTTPException(401, "Ongeldige Community Tools-beheerverbinding.")

    kerk = db.scalar(
        select(Church).where(
            Church.community_tools_organization_id == organization_id
        )
    )
    if not kerk:
        raise HTTPException(404, "Organisatie is nog niet aan AfterSermon gekoppeld.")

    medebeheerders = db.scalars(
        select(Medebeheerder)
        .where(Medebeheerder.kerk_id == kerk.id)
        .order_by(Medebeheerder.naam, Medebeheerder.email)
    ).all()
    gebruikers = [
        {
            "id": f"church:{kerk.id}",
            "communityToolsUserId": kerk.community_tools_user_id,
            "name": kerk.naam or kerk.email,
            "email": kerk.email,
            "role": "owner",
            "status": "active" if kerk.email_geverifieerd else "pending",
            "kind": "admin",
        }
    ]
    gebruikers.extend(
        {
            "id": f"co-admin:{beheerder.id}",
            "communityToolsUserId": beheerder.community_tools_user_id,
            "name": beheerder.naam or beheerder.email,
            "email": beheerder.email,
            "role": "editor",
            "status": "active" if beheerder.email_geverifieerd else "pending",
            "kind": "admin",
        }
        for beheerder in medebeheerders
    )
    gebruikers.extend(
        {
            "id": f"subscriber:{subscriber.id}",
            "communityToolsUserId": None,
            "name": subscriber.naam or subscriber.email,
            "email": subscriber.email,
            "role": "subscriber",
            "status": "active" if subscriber.bevestigd else "pending",
            "kind": "user",
        }
        for subscriber in db.scalars(
            select(Subscriber)
            .where(Subscriber.kerk_id == kerk.id)
            .order_by(Subscriber.naam, Subscriber.email)
        ).all()
    )
    return {
        "version": "1",
        "product": "sermon_processing",
        "organizationId": organization_id,
        "users": gebruikers,
    }


@router.patch("/api/community-tools/v1/organizations/{organization_id}/users/{managed_user_id}")
def community_tools_update_user(
    organization_id: str,
    managed_user_id: str,
    body: dict,
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
):
    kerk = _management_church(db, organization_id, authorization)
    name = str(body.get("name") or "").strip()
    email = str(body.get("email") or "").strip().lower()
    status = str(body.get("status") or "active")
    if not name or not email:
        raise HTTPException(400, "Naam en e-mail zijn verplicht.")
    soort, _, raw_id = managed_user_id.partition(":")
    record_id = int(raw_id) if raw_id.isdigit() else 0
    if soort == "subscriber":
        record = db.get(Subscriber, record_id)
        if not record or record.kerk_id != kerk.id:
            raise HTTPException(404, "Gebruiker niet gevonden.")
        record.naam, record.email = name, email
        record.bevestigd = status == "active"
    elif soort == "co-admin":
        record = db.get(Medebeheerder, record_id)
        if not record or record.kerk_id != kerk.id:
            raise HTTPException(404, "Beheerder niet gevonden.")
        record.naam, record.email = name, email
        record.email_geverifieerd = status == "active"
    elif soort == "church" and record_id == kerk.id:
        kerk.naam = name
    else:
        raise HTTPException(400, "Dit account kan hier niet worden aangepast.")
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(409, "E-mailadres is al in gebruik.")
    return {"ok": True}


@router.post("/api/community-tools/v1/organizations/{organization_id}/users")
def community_tools_invite_user(
    organization_id: str, body: dict, request: Request,
    authorization: str | None = Header(default=None), db=Depends(get_db),
):
    kerk = _management_church(db, organization_id, authorization)
    name = str(body.get("name") or "").strip()
    email = str(body.get("email") or "").strip().lower()
    role = str(body.get("role") or "")
    if not name or not email:
        raise HTTPException(400, "Naam en e-mail zijn verplicht.")
    if role == "subscriber":
        try:
            record, _ = subscribers.maak_inschrijver(db, kerk.id, name, email)
        except subscribers.InschrijfFout as exc:
            raise HTTPException(400, str(exc))
        _send_subscriber_invitation(kerk, record, request)
        return {"id": f"subscriber:{record.id}"}
    if role == "editor":
        if db.scalar(select(Medebeheerder).where(Medebeheerder.email == email)):
            raise HTTPException(409, "Dit e-mailadres is al in gebruik.")
        token = secrets.token_urlsafe(24)
        record = Medebeheerder(kerk_id=kerk.id, naam=name, email=email, token=token)
        db.add(record); db.commit()
        _send_editor_invitation(kerk, record, request)
        return {"id": f"co-admin:{record.id}"}
    raise HTTPException(400, "Ongeldige rol.")


@router.post("/api/community-tools/v1/organizations/{organization_id}/users/{managed_user_id}/resend")
def community_tools_resend_invitation(
    organization_id: str, managed_user_id: str, request: Request,
    authorization: str | None = Header(default=None), db=Depends(get_db),
):
    kerk = _management_church(db, organization_id, authorization)
    soort, _, raw_id = managed_user_id.partition(":")
    record_id = int(raw_id) if raw_id.isdigit() else 0
    if soort == "subscriber":
        record = db.get(Subscriber, record_id)
        if not record or record.kerk_id != kerk.id: raise HTTPException(404, "Niet gevonden.")
        if not record.bevestig_token:
            record.bevestig_token = secrets.token_urlsafe(24); record.bevestigd = False; db.commit()
        _send_subscriber_invitation(kerk, record, request)
    elif soort == "co-admin":
        record = db.get(Medebeheerder, record_id)
        if not record or record.kerk_id != kerk.id: raise HTTPException(404, "Niet gevonden.")
        record.token = secrets.token_urlsafe(24); db.commit(); _send_editor_invitation(kerk, record, request)
    else: raise HTTPException(400, "Dit account heeft geen uitnodiging.")
    return {"ok": True}


def _send_subscriber_invitation(kerk, record, request):
    link = f"{_basis_url(request)}/api/inschrijven/bevestig?token={record.bevestig_token}"
    brevo.verzend(record.email, f"Uitnodiging van {kerk.naam}", f'<p>Je bent uitgenodigd voor AfterSermon.</p><p><a href="{link}">Uitnodiging accepteren</a></p>', tekst=f"Uitnodiging accepteren: {link}")


def _send_editor_invitation(kerk, record, request):
    link = f"{_basis_url(request)}/admin?uitnodiging={record.token}"
    brevo.verzend(record.email, f"Je bent uitgenodigd als beheerder van {kerk.naam}", f'<p><a href="{link}">Account instellen</a></p>', tekst=f"Account instellen: {link}")


@router.delete("/api/community-tools/v1/organizations/{organization_id}/users/{managed_user_id}")
def community_tools_remove_user(
    organization_id: str,
    managed_user_id: str,
    authorization: str | None = Header(default=None),
    db=Depends(get_db),
):
    kerk = _management_church(db, organization_id, authorization)
    soort, _, raw_id = managed_user_id.partition(":")
    record_id = int(raw_id) if raw_id.isdigit() else 0
    if soort == "subscriber":
        record = db.get(Subscriber, record_id)
    elif soort == "co-admin":
        record = db.get(Medebeheerder, record_id)
    else:
        raise HTTPException(409, "De hoofdbeheerder kan niet worden verwijderd.")
    if not record or record.kerk_id != kerk.id:
        raise HTTPException(404, "Account niet gevonden.")
    db.delete(record)
    db.commit()
    return {"ok": True}


def _management_church(db, organization_id: str, authorization: str | None):
    if not community_tools.verifieer_beheer_token(authorization):
        raise HTTPException(401, "Ongeldige Community Tools-beheerverbinding.")
    kerk = db.scalar(select(Church).where(Church.community_tools_organization_id == organization_id))
    if not kerk:
        raise HTTPException(404, "Organisatie is nog niet gekoppeld.")
    return kerk


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


def _rate(request: Request, actie: str, maximum: int):
    ip = ratelimit.ip_van(request)
    if not ratelimit.toegestaan(f"{actie}:{ip}", maximum):
        raise HTTPException(429, "Te veel verzoeken. Probeer het later opnieuw.")


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
    auto_verwerken: bool = False
    tijdzone: str = "Europe/Amsterdam"
    verzend_dag: int = 0
    verzend_tijd: str = "07:00"
    versturen_zonder_goedkeuring: bool = False
    ai_disclaimer: bool = True
    admin_taal: str = "auto"
    inschrijf_taal: str = "auto"
    communicatie_taal: str = "nl"
    citaat_volledig: bool = True
    bijbelvertaling: str = "vrij"
    accentkleur: str = "#2c5f2d"
    toon: str = "warm"
    lengte: str = "middel"
    uitvoer_typen: list[str] = ["dagstukjes"]
    bezorg_typen: list[str] = []
    nabespreking_schema: str = "mee"
    nabespreking_datums: list[str] = []


class InschrijverBody(BaseModel):
    naam: str = ""
    email: str
    telefoon: str = ""
    frequentie: str = "wekelijks"
    dienstvoorkeur: str = "beide"
    ontvang_dag: int = 0
    ontvang_tijd: str = "07:00"


class InschrijvenBody(BaseModel):
    kerk_id: int
    naam: str = ""
    email: str
    telefoon: str = ""
    frequentie: str = "wekelijks"
    dienstvoorkeur: str = "beide"
    kanaal: str = "email"  # email | push | beide


class VoorkeurBody(BaseModel):
    token: str
    naam: str = ""
    telefoon: str = ""
    frequentie: str = "wekelijks"
    dienstvoorkeur: str = "beide"
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
    _rate(request, "register", 10)
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
    _rate(request, "login", 20)
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
    _rate(request, "reset", 10)
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
        "auto_verwerken": kerk.auto_verwerken,
        "tijdzone": kerk.tijdzone,
        "verzend_dag": kerk.verzend_dag,
        "verzend_tijd": kerk.verzend_tijd,
        "versturen_zonder_goedkeuring": kerk.versturen_zonder_goedkeuring,
        "ai_disclaimer": kerk.ai_disclaimer,
        "admin_taal": kerk.admin_taal,
        "inschrijf_taal": kerk.inschrijf_taal,
        "communicatie_taal": kerk.communicatie_taal,
        "citaat_volledig": kerk.citaat_volledig,
        "bijbelvertaling": kerk.bijbelvertaling,
        "heeft_logo": bool(kerk.logo),
        "accentkleur": kerk.accentkleur or "#2c5f2d",
        "toon": kerk.toon or "warm",
        "lengte": kerk.lengte or "middel",
        "uitvoer_typen": (kerk.uitvoer_typen or "dagstukjes").split(","),
        "bezorg_typen": (kerk.bezorg_typen or "").split(",") if (kerk.bezorg_typen or "").strip() else [],
        "nabespreking_schema": getattr(kerk, "nabespreking_schema", "mee") or "mee",
        "nabespreking_datums": [d for d in (getattr(kerk, "nabespreking_datums", "") or "").split(",") if d],
    }


@router.post("/api/admin/kanaal")
def kanaal(body: KanaalBody, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    kerk.kanaal_url = (body.kanaal_url or "").strip()
    kerk.auto_versturen = bool(body.auto_versturen)
    kerk.auto_verwerken = bool(body.auto_verwerken)
    kerk.tijdzone = (body.tijdzone or "Europe/Amsterdam").strip()
    kerk.verzend_dag = int(body.verzend_dag) % 7
    kerk.verzend_tijd = (body.verzend_tijd or "07:00").strip()
    kerk.versturen_zonder_goedkeuring = bool(body.versturen_zonder_goedkeuring)
    kerk.ai_disclaimer = bool(body.ai_disclaimer)
    kerk.admin_taal = ui_i18n.valid(body.admin_taal, "auto")
    kerk.inschrijf_taal = ui_i18n.valid(body.inschrijf_taal, "auto")
    kerk.communicatie_taal = ui_i18n.valid(
        body.communicatie_taal, "nl", allow_auto=False
    )
    kerk.citaat_volledig = bool(body.citaat_volledig)
    _vertalingen = {"vrij", "nbv21", "hsv", "bgt", "afr1953", "kjv", "esv", "niv"}
    kerk.bijbelvertaling = (
        body.bijbelvertaling if body.bijbelvertaling in _vertalingen else "vrij"
    )
    kleur = (body.accentkleur or "").strip()
    kerk.accentkleur = kleur if re.fullmatch(r"#[0-9a-fA-F]{6}", kleur) else "#2c5f2d"
    kerk.toon = body.toon if body.toon in {"warm", "nuchter", "toegankelijk", "verdiepend"} else "warm"
    kerk.lengte = body.lengte if body.lengte in {"kort", "middel", "lang"} else "middel"
    _geldig = {"dagstukjes", "preeksamenvatting", "preektranscript", "nabespreking"}
    _uitvoer = [t for t in (body.uitvoer_typen or []) if t in _geldig]
    kerk.uitvoer_typen = ",".join(_uitvoer) if _uitvoer else "dagstukjes"
    # Alleen types die ook gemaakt worden mogen bezorgd worden. Leeg = alles.
    _bezorg = [t for t in (body.bezorg_typen or []) if t in _uitvoer]
    kerk.bezorg_typen = ",".join(_bezorg)
    # Groepsvragen-planning: 'mee' (in de wekelijkse mail) of 'datums' (vaste data).
    kerk.nabespreking_schema = body.nabespreking_schema if body.nabespreking_schema in {"mee", "datums"} else "mee"
    _datums = []
    for d in (body.nabespreking_datums or []):
        d = (d or "").strip()[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
            _datums.append(d)
    kerk.nabespreking_datums = ",".join(sorted(set(_datums)))
    db.commit()
    return {"ok": True, "kanaal_url": kerk.kanaal_url}


# ---- Inschrijverbeheer (admin) ----
def _sub_json(s):
    data = {
        "id": s.id, "naam": s.naam, "email": s.email, "telefoon": s.telefoon,
        "frequentie": s.frequentie, "dienstvoorkeur": getattr(s, "dienstvoorkeur", "beide"),
        "ontvang_dag": s.ontvang_dag,
        "ontvang_tijd": s.ontvang_tijd, "bevestigd": s.bevestigd,
    }
    if getattr(s, "kerk", None):
        data["communicatie_taal"] = s.kerk.communicatie_taal
        data["accentkleur"] = s.kerk.accentkleur or "#2c5f2d"
    return data


@router.get("/api/admin/recente-preken")
def recente_preken(request: Request, db=Depends(get_db)):
    """Dienst(en) van afgelopen zondag, met of ze al (voor)verwerkt zijn."""
    from datetime import timedelta
    import automatisering
    kerk = _vereis_kerk(request, db)
    nu = automatisering._nu_lokaal(kerk).date()
    zondag = nu - timedelta(days=(nu.weekday() + 1) % 7)
    uitz = db.scalars(
        select(Uitzending).where(
            Uitzending.kerk_id == kerk.id, Uitzending.datum == zondag
        ).order_by(Uitzending.dagdeel)
    ).all()
    preken = []
    for u in uitz:
        bewaard = store.resultaat_ophalen(u.video_id)
        preken.append({
            "video_id": u.video_id, "url": u.url, "titel": u.titel,
            "datum": str(u.datum), "dagdeel": u.dagdeel or "",
            "klaar": bool(bewaard and (bewaard.get("transcript_ruw") or "").strip()),
            "heeft_preek": bool(bewaard and bewaard.get("preek_schoon")),
        })
    # Login-freshness: is auto-verwerken aan en staat er (nog) niets, start dan op de
    # achtergrond een scan + voorverwerking (niet wachten op de trage tick).
    if kerk.auto_verwerken and kerk.kanaal_url and not uitz:
        base = _basis_url(request)
        kerk_id = kerk.id

        def _bg():
            d = SessionLocal()
            try:
                k = d.get(Church, kerk_id)
                automatisering.scan_kerk(d, k, base)
                automatisering.preverwerk_kerk(d, k, base)
            except Exception:  # noqa: BLE001
                d.rollback()
            finally:
                d.close()
        threading.Thread(target=_bg, daemon=True).start()
    return {"zondag": str(zondag), "auto_verwerken": bool(kerk.auto_verwerken), "preken": preken}


@router.get("/api/admin/analytics")
def analytics(request: Request, db=Depends(get_db)):
    from datetime import datetime, timedelta

    kerk = _vereis_kerk(request, db)
    subs = subscribers.lijst(db, kerk.id)
    grens = datetime.now() - timedelta(days=30)

    def _recent(s):
        try:
            return bool(s.aangemaakt) and s.aangemaakt >= grens
        except Exception:  # noqa: BLE001
            return False

    totaal = len(subs)
    bevestigd = sum(1 for s in subs if s.bevestigd)
    uit_ids = [
        u.id for u in db.scalars(
            select(Uitzending).where(Uitzending.kerk_id == kerk.id)
        )
    ]
    verzonden, laatste = 0, None
    if uit_ids:
        verzonden = db.scalar(
            select(func.count()).select_from(Verzending)
            .where(Verzending.uitzending_id.in_(uit_ids))
        ) or 0
        laatste = db.scalar(
            select(func.max(Verzending.verzonden_op))
            .where(Verzending.uitzending_id.in_(uit_ids))
        )
    return {
        "inschrijvers_totaal": totaal,
        "inschrijvers_bevestigd": bevestigd,
        "inschrijvers_onbevestigd": totaal - bevestigd,
        "wekelijks": sum(1 for s in subs if s.frequentie == "wekelijks"),
        "dagelijks": sum(1 for s in subs if s.frequentie == "dagelijks"),
        "nieuw_30d": sum(1 for s in subs if _recent(s)),
        "verzonden_totaal": verzonden,
        "diensten_verwerkt": len(uit_ids),
        "laatste_verzending": laatste.strftime("%Y-%m-%d %H:%M") if laatste else None,
    }


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
def qr(request: Request, download: bool = False, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    url = f"{_basis_url(request)}/inschrijven?kerk={kerk.id}"
    svg = _qr_svg(url)
    headers = {}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="aftersermon-qr.svg"'
    return Response(content=svg, media_type="image/svg+xml", headers=headers)


@router.post("/api/admin/verstuur/{video_id}")
def verstuur(video_id: str, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    bewaard = store.resultaat_ophalen(video_id)
    if not bewaard or not bewaard.get("data"):
        raise HTTPException(404, "Voor deze dienst is nog geen verwerking beschikbaar.")
    uitzending = db.scalar(select(Uitzending).where(
        Uitzending.kerk_id == kerk.id, Uitzending.video_id == video_id
    ))
    dagdeel = (uitzending.dagdeel if uitzending else "") or ""
    aantal = levering.verstuur_weekboekje(
        db, kerk, bewaard["data"], _basis_url(request), dagdeel=dagdeel
    )
    if uitzending:
        for sub in subscribers.lijst(db, kerk.id):
            if not sub.bevestigd:
                continue
            bestaat = db.scalar(select(Verzending).where(
                Verzending.uitzending_id == uitzending.id,
                Verzending.subscriber_id == sub.id,
                Verzending.dag == 0,
            ))
            if not bestaat:
                db.add(Verzending(
                    uitzending_id=uitzending.id, subscriber_id=sub.id, dag=0
                ))
        db.commit()
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
        bewaard = store.resultaat_ophalen(u.video_id) or {}
        uit.append({
            "video_id": u.video_id, "titel": u.titel, "datum": str(u.datum),
            "goedgekeurd": u.goedgekeurd, "verzonden": aantal or 0,
            "verwerkt": bool(bewaard.get("data")),
            "bron_url": u.url,
            "bewerk_url": (
                f"/uitzending?token={u.goedkeur_token}"
                if u.goedkeur_token else f"/demo?url={u.url}"
            ),
        })
    return uit


@router.get("/api/admin/scan-diagnose")
def scan_diagnose(request: Request, db=Depends(get_db)):
    """Leg uit waarom de scan wel/geen diensten vindt (zonder te verwerken)."""
    import main
    from datetime import timedelta

    kerk = _vereis_kerk(request, db)
    url = (kerk.kanaal_url or "").strip()
    uit = {"kanaal_url": url}
    if not url:
        uit["probleem"] = "Er is nog geen kanaal-URL ingesteld bij Basisinstellingen."
        return uit

    typ, soort = main._classificeer(url)
    uit["type"] = typ
    uit["soort"] = soort
    if not typ:
        uit["probleem"] = "De kanaal-URL wordt niet herkend als YouTube of Kerkdienstgemist."
        return uit
    if soort != "kanaal":
        uit["probleem"] = (
            "Dit is een link naar één preek, geen kanaal/station. Zet bij "
            "Basisinstellingen de kanaal- of station-URL (de lijst met diensten)."
        )
        return uit

    try:
        diensten = main._laad_diensten(typ, url, vernieuw=True)
    except Exception as fout:  # noqa: BLE001
        uit["probleem"] = f"De kanaallijst kon niet worden opgehaald: {fout}"
        return uit

    nu = automatisering._nu_lokaal(kerk)
    grens = nu.date() - timedelta(days=automatisering.SCAN_TERUG_DAGEN)
    uit["nu"] = nu.date().isoformat()
    uit["ondergrens_datum"] = grens.isoformat()
    uit["aantal_in_lijst"] = len(diensten)
    uit["aantal_gepland"] = sum(1 for d in diensten if d.get("gepland"))

    binnen, te_oud, in_toekomst = [], 0, 0
    for d in diensten:
        if d.get("gepland"):
            continue
        datum = automatisering._naar_datum(d.get("datum"))
        if not datum:
            continue
        if datum < grens:
            te_oud += 1
        elif datum > nu.date():
            in_toekomst += 1
        else:
            binnen.append(d.get("datum"))
    uit["binnen_venster"] = binnen
    uit["te_oud"] = te_oud
    uit["in_toekomst"] = in_toekomst
    if not binnen:
        uit["probleem"] = (
            "Er staan geen gestreamde diensten in het venster van de laatste "
            f"{automatisering.SCAN_TERUG_DAGEN} dagen. Voorbeelden uit de lijst: "
            + ", ".join(str(d.get("datum")) for d in diensten[:5])
        )
    else:
        uit["ok"] = f"{len(binnen)} dienst(en) zouden verwerkt worden."
    return uit


@router.post("/api/admin/scan-nu")
def scan_nu(request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    kerk_id, base = kerk.id, _basis_url(request)

    def werk():
        s = SessionLocal()
        try:
            # Handmatige scan: verse kanaallijst ophalen (niet de cache), zodat
            # net-toegevoegde of net-gedateerde diensten meteen meekomen.
            automatisering.scan_kerk(s, s.get(Church, kerk_id), base, vernieuw=True)
        except Exception:  # noqa: BLE001
            import traceback

            traceback.print_exc()
        finally:
            s.close()

    threading.Thread(target=werk, daemon=True).start()
    return {"ok": True, "gestart": True}


@router.api_route("/api/cron/tick", methods=["GET", "POST"])
def cron_tick(request: Request, token: str = ""):
    """Externe trigger voor één scan+bezorg-ronde.

    Laat een externe cron (Railway-cron of bijv. cron-job.org) dit elke ~10 min
    aanroepen. Zo draait de planning betrouwbaar door, ook als het interne
    achtergrond-draadje door een containerherstart of -slaap stilvalt: een
    inkomend verzoek wekt de container. De bezorging is idempotent (verzendlog),
    dus dubbel aanroepen is veilig.
    """
    verwacht = os.environ.get("CRON_TOKEN")
    if verwacht and token != verwacht:
        raise HTTPException(403, "Ongeldige cron-token.")
    automatisering.tick(_basis_url(request))
    return {"ok": True}


@router.post("/api/admin/upload")
async def upload_preek(
    request: Request, file: UploadFile = File(...), datum: str = Form(""),
    db=Depends(get_db),
):
    """Eigen preek als document (PDF/DOCX/TXT) of audio (MP3) → weekboekje."""
    import audio as audio_mod
    import documenten
    import main
    from datetime import date, datetime

    kerk = _vereis_kerk(request, db)
    inhoud = await file.read()
    try:
        if audio_mod.is_audio(file.filename):
            tekst = audio_mod.transcribeer_upload(inhoud, file.filename)
        else:
            tekst = documenten.haal_tekst(file.filename, inhoud)
    except ValueError as fout:
        raise HTTPException(400, str(fout))
    except Exception as fout:  # noqa: BLE001 — transcriptiefouten netjes tonen
        raise HTTPException(502, f"Verwerken van het bestand lukte niet: {fout}")
    if len(tekst) < 200:
        raise HTTPException(400, "Het bestand bevat te weinig tekst voor een preek.")

    video_id = "upload_" + secrets.token_hex(8)
    try:
        # Alleen transcriberen/opslaan — genereren gebeurt op aanvraag (de 4 knoppen),
        # zodat de AI niet onnodig draait bij het uploaden.
        data = main.verwerk_tekst_en_bewaar(
            video_id, tekst, titel_hint=file.filename,
            volledige_dienst=audio_mod.is_audio(file.filename),
            alleen_transcript=True,
        )
    except Exception as fout:  # noqa: BLE001
        raise HTTPException(502, f"Verwerken lukte niet: {fout}")

    try:
        d = datetime.strptime(datum[:10], "%Y-%m-%d").date() if datum else date.today()
    except ValueError:
        d = date.today()
    uit = Uitzending(
        kerk_id=kerk.id, video_id=video_id, url="",
        titel=data.get("titel") or file.filename, datum=d,
        week_start=automatisering.komende_maandag(d),
        goedgekeurd=bool(kerk.auto_versturen),
        goedkeur_token=secrets.token_urlsafe(24),
    )
    db.add(uit)
    db.commit()
    return {"ok": True, "video_id": video_id, "bewerk_url": f"/uitzending?token={uit.goedkeur_token}"}


_LOGO_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif", "image/svg+xml"}
_LOGO_MAX = 500 * 1024  # 500 kB


@router.post("/api/admin/logo")
async def logo_upload(request: Request, file: UploadFile = File(...), db=Depends(get_db)):
    """Upload het logo van de kerk (PNG/JPG/WEBP/GIF/SVG, max 500 kB)."""
    import base64
    kerk = _vereis_kerk(request, db)
    ctype = (file.content_type or "").split(";")[0].strip().lower()
    if ctype not in _LOGO_TYPES:
        raise HTTPException(400, "Alleen PNG, JPG, WEBP, GIF of SVG is toegestaan.")
    inhoud = await file.read()
    if not inhoud:
        raise HTTPException(400, "Leeg bestand.")
    if len(inhoud) > _LOGO_MAX:
        raise HTTPException(400, "Het logo mag maximaal 500 kB zijn.")
    kerk.logo = base64.b64encode(inhoud).decode("ascii")
    kerk.logo_type = ctype
    db.commit()
    return {"ok": True, "logo_url": f"/logo/{kerk.id}"}


@router.delete("/api/admin/logo")
def logo_verwijder(request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    kerk.logo = ""
    kerk.logo_type = ""
    db.commit()
    return {"ok": True}


@router.put("/api/admin/inschrijvers/{sub_id}")
def inschrijver_wijzig(sub_id: int, body: InschrijverBody, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    sub = db.get(Subscriber, sub_id)
    if not sub or sub.kerk_id != kerk.id:
        raise HTTPException(404, "Inschrijver niet gevonden.")
    sub.naam = (body.naam or "").strip()
    if body.email and "@" in body.email:
        sub.email = body.email.strip().lower()
    sub.telefoon = (body.telefoon or "").strip()
    if body.frequentie in subscribers.FREQUENTIES:
        sub.frequentie = body.frequentie
    db.commit()
    return _sub_json(sub)


@router.post("/api/admin/test-verzenden")
def test_verzenden(request: Request, db=Depends(get_db)):
    """Stuur de nieuwste verwerkte overdenking als test naar het eigen adres."""
    kerk = _vereis_kerk(request, db)
    rijen = db.scalars(
        select(Uitzending).where(Uitzending.kerk_id == kerk.id)
        .order_by(Uitzending.datum.desc())
    )
    for u in rijen:
        bewaard = store.resultaat_ophalen(u.video_id)
        if bewaard and bewaard.get("data"):
            onderwerp, html = levering.bouw_email(
                bewaard["data"], kerk.naam or "AfterSermon", _basis_url(request),
                "test", None, kerk.communicatie_taal,
            )
            brevo.verzend(
                kerk.email, "[TEST] " + onderwerp, html,
                van_naam=kerk.naam or None, antwoord_naar=kerk.email or None,
            )
            return {"ok": True, "naar": kerk.email}
    raise HTTPException(400, "Er is nog geen verwerkte dienst om te testen.")


@router.get("/api/admin/medebeheerders")
def medebeheerders_lijst(request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    rijen = db.scalars(select(Medebeheerder).where(Medebeheerder.kerk_id == kerk.id))
    return [
        {"id": m.id, "email": m.email, "naam": m.naam,
         "actief": bool(m.wachtwoord_hash and m.email_geverifieerd)}
        for m in rijen
    ]


@router.post("/api/admin/medebeheerders")
def medebeheerder_uitnodigen(body: EmailBody, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    email = (body.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Geef een geldig e-mailadres op.")
    if auth._kerk_op_email(db, email) or db.scalar(
        select(Medebeheerder).where(Medebeheerder.email == email)
    ):
        raise HTTPException(400, "Dit e-mailadres is al in gebruik.")
    token = secrets.token_urlsafe(24)
    db.add(Medebeheerder(kerk_id=kerk.id, email=email, token=token))
    db.commit()
    link = f"{_basis_url(request)}/admin?uitnodiging={token}"
    brevo.verzend(
        email, f"Je bent uitgenodigd als beheerder van {kerk.naam or 'een kerk'}",
        f"<p>Je bent uitgenodigd om mee te beheren in AfterSermon. Stel via deze "
        f"link je wachtwoord in:</p><p><a href=\"{link}\">{link}</a></p>",
        tekst=f"Stel je wachtwoord in: {link}",
    )
    return {"ok": True}


@router.delete("/api/admin/medebeheerders/{mb_id}")
def medebeheerder_verwijderen(mb_id: int, request: Request, db=Depends(get_db)):
    kerk = _vereis_kerk(request, db)
    mb = db.get(Medebeheerder, mb_id)
    if not mb or mb.kerk_id != kerk.id:
        raise HTTPException(404, "Beheerder niet gevonden.")
    db.delete(mb)
    db.commit()
    return {"ok": True}


@router.post("/api/admin/medebeheerder-instellen")
def medebeheerder_instellen(body: ResetBody, db=Depends(get_db)):
    """Uitgenodigde beheerder stelt via de token zijn wachtwoord in."""
    if len(body.wachtwoord or "") < 8:
        raise HTTPException(400, "Kies een wachtwoord van minstens 8 tekens.")
    mb = db.scalar(select(Medebeheerder).where(Medebeheerder.token == body.token))
    if not mb or not body.token:
        raise HTTPException(400, "Deze uitnodiging is ongeldig of verlopen.")
    mb.wachtwoord_hash = auth.hash_wachtwoord(body.wachtwoord)
    mb.email_geverifieerd = True
    mb.token = ""
    db.commit()
    return {"ok": True}


@router.post("/api/brevo/webhook")
def brevo_webhook(body: dict, token: str = "", db=Depends(get_db)):
    """Brevo-events: bij een harde bounce/klacht de inschrijver opschonen."""
    verwacht = os.environ.get("BREVO_WEBHOOK_TOKEN")
    if verwacht and token != verwacht:
        raise HTTPException(403, "Ongeldige webhook-token.")
    event = (body or {}).get("event", "")
    email = ((body or {}).get("email") or "").strip().lower()
    if email and event in ("hard_bounce", "spam", "blocked", "invalid_email", "unsubscribed"):
        for s in db.scalars(select(Subscriber).where(Subscriber.email == email)):
            db.delete(s)
        db.commit()
    return {"ok": True}


# ---- Goedkeuren / bewerken via magische link (geen login) ----
@router.get("/api/uitzending/goedkeuren")
def uitzending_goedkeuren_link(token: str, db=Depends(get_db)):
    uit = _uit_op_token(db, token)
    if uit:
        kerk = db.get(Church, uit.kerk_id)
        _keur_goed(db, uit, kerk.email if kerk else "")
        return RedirectResponse(f"/uitzending?token={token}&goedgekeurd=1", status_code=303)
    return RedirectResponse("/uitzending?fout=1", status_code=303)


def _keur_goed(db, uit, door):
    from datetime import datetime

    uit.goedgekeurd = True
    uit.goedgekeurd_op = datetime.now()
    uit.goedgekeurd_door = door or ""
    db.commit()


@router.post("/api/uitzending/goedkeuren")
def uitzending_goedkeuren(body: dict, request: Request, db=Depends(get_db)):
    uit = _uit_op_token(db, (body or {}).get("token", ""))
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    kerk = db.get(Church, uit.kerk_id)
    _keur_goed(db, uit, (kerk.email if kerk else "") )
    return {"ok": True}


@router.post("/api/uitzending/concept")
def uitzending_concept(body: dict, db=Depends(get_db)):
    """Terug naar concept: goedkeuring intrekken."""
    uit = _uit_op_token(db, (body or {}).get("token", ""))
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    uit.goedgekeurd = False
    uit.goedgekeurd_op = None
    uit.goedgekeurd_door = ""
    db.commit()
    return {"ok": True}


@router.get("/api/uitzending/{token}")
def uitzending_data(token: str, db=Depends(get_db)):
    uit = _uit_op_token(db, token)
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    bewaard = store.resultaat_ophalen(uit.video_id) or {}
    data = bewaard.get("data") or {}
    kerk = db.get(Church, uit.kerk_id)
    return {
        "titel": uit.titel, "datum": str(uit.datum), "goedgekeurd": uit.goedgekeurd,
        "goedgekeurd_op": uit.goedgekeurd_op.isoformat() if uit.goedgekeurd_op else None,
        "goedgekeurd_door": uit.goedgekeurd_door or None,
        "video_id": uit.video_id, "data": _met_labels(data),
        "tekst": bewaard.get("tekst", ""),
        "verwerkt": bool(data),
        "communicatie_taal": kerk.communicatie_taal if kerk else "nl",
    }


@router.post("/api/uitzending/test")
def uitzending_test(body: dict, request: Request, db=Depends(get_db)):
    """Stuur deze (verwerkte) overdenking als test naar het e-mailadres van de kerk."""
    uit = _uit_op_token(db, (body or {}).get("token", ""))
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    bewaard = store.resultaat_ophalen(uit.video_id)
    if not bewaard or not bewaard.get("data"):
        raise HTTPException(400, "Verwerk de dienst eerst voordat je een test stuurt.")
    kerk = db.get(Church, uit.kerk_id)
    base = _basis_url(request)
    logo_url = f"{base}/logo/{kerk.id}" if getattr(kerk, "logo", "") else None
    onderwerp, html = levering.bouw_email(
        bewaard["data"], kerk.naam or "AfterSermon", base, "test",
        None, kerk.communicatie_taal, getattr(kerk, "ai_disclaimer", True),
        logo_url, getattr(kerk, "accentkleur", None),
    )
    brevo.verzend(
        kerk.email, "[TEST] " + onderwerp, html,
        van_naam=kerk.naam or None, antwoord_naar=kerk.email or None,
    )
    return {"ok": True, "naar": kerk.email}


@router.post("/api/uitzending/verwerk")
def uitzending_verwerk(body: dict, db=Depends(get_db)):
    """Verwerk deze dienst op verzoek (transcript + AI). Kan even duren."""
    uit = _uit_op_token(db, (body or {}).get("token", ""))
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    bewaard = store.resultaat_ophalen(uit.video_id)
    if not bewaard or not bewaard.get("data"):
        import main

        try:
            main.verwerk_en_bewaar(
                uit.url, bijbel=main.bijbel_van_kerk(db.get(Church, uit.kerk_id)),
                uitvoer_typen=main.uitvoer_van_kerk(db.get(Church, uit.kerk_id)),
            )
        except Exception as fout:  # noqa: BLE001
            raise HTTPException(502, f"Verwerken lukte niet: {fout}")
        bewaard = store.resultaat_ophalen(uit.video_id) or {}
    data = bewaard.get("data") or {}
    return {"ok": True, "data": _met_labels(data), "tekst": bewaard.get("tekst", "")}


@router.post("/api/uitzending/hergenereer-dag")
def uitzending_hergenereer_dag(body: dict, db=Depends(get_db)):
    """Genereer één dag-overdenking opnieuw voor deze dienst."""
    import main
    uit = _uit_op_token(db, (body or {}).get("token", ""))
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    try:
        dag_index = int((body or {}).get("dag"))
    except (TypeError, ValueError):
        raise HTTPException(400, "Geef een geldige dag op.")
    try:
        r = main.hergenereer_dag_en_bewaar(
            uit.video_id, dag_index,
            bijbel=main.bijbel_van_kerk(db.get(Church, uit.kerk_id)),
        )
    except ValueError as fout:
        raise HTTPException(400, str(fout))
    except Exception as fout:  # noqa: BLE001
        raise HTTPException(502, f"Opnieuw genereren lukte niet: {fout}")
    return {"ok": True, "data": _met_labels(r["data"]), "tekst": r.get("tekst", "")}


@router.post("/api/uitzending/nabespreking")
def uitzending_nabespreking(body: dict, db=Depends(get_db)):
    """Genereer (of vernieuw) de nabespreekvragen voor deze dienst."""
    import main
    uit = _uit_op_token(db, (body or {}).get("token", ""))
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    try:
        r = main.hergenereer_nabespreking_en_bewaar(uit.video_id)
    except ValueError as fout:
        raise HTTPException(400, str(fout))
    except Exception as fout:  # noqa: BLE001
        raise HTTPException(502, f"Nabespreking maken lukte niet: {fout}")
    return {"ok": True, "data": _met_labels(r["data"]), "tekst": r.get("tekst", "")}


@router.post("/api/uitzending/upload")
async def uitzending_upload(
    token: str = Form(...), file: UploadFile = File(...), db=Depends(get_db),
):
    """Eigen preektekst of audio aanleveren voor deze dienst i.p.v. via het kanaal."""
    import audio as audio_mod
    import documenten
    import main

    uit = _uit_op_token(db, token)
    if not uit:
        raise HTTPException(404, "Onbekende of verlopen link.")
    inhoud = await file.read()
    try:
        if audio_mod.is_audio(file.filename):
            tekst = audio_mod.transcribeer_upload(inhoud, file.filename)
        else:
            tekst = documenten.haal_tekst(file.filename, inhoud)
    except ValueError as fout:
        raise HTTPException(400, str(fout))
    except Exception as fout:  # noqa: BLE001
        raise HTTPException(502, f"Verwerken van het bestand lukte niet: {fout}")
    if len(tekst) < 200:
        raise HTTPException(400, "Het bestand bevat te weinig tekst voor een preek.")
    try:
        data = main.verwerk_tekst_en_bewaar(
            uit.video_id, tekst, titel_hint=uit.titel,
            volledige_dienst=audio_mod.is_audio(file.filename),
            bijbel=main.bijbel_van_kerk(db.get(Church, uit.kerk_id)),
            uitvoer_typen=main.uitvoer_van_kerk(db.get(Church, uit.kerk_id)),
        )
    except Exception as fout:  # noqa: BLE001
        raise HTTPException(502, f"Verwerken lukte niet: {fout}")
    return {"ok": True, "data": _met_labels(data), "tekst": ""}


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


@router.get("/privacy")
def privacy_pagina():
    return FileResponse("static/privacy.html", headers={"Cache-Control": "no-cache"})


# ---- Publieke inschrijving (geen login) ----
@router.get("/api/kerk/{kerk_id}")
def kerk_info(kerk_id: int, db=Depends(get_db)):
    kerk = db.get(Church, kerk_id)
    if not kerk:
        raise HTTPException(404, "Kerk niet gevonden.")
    return {
        "naam": kerk.naam or "AfterSermon",
        "inschrijf_taal": kerk.inschrijf_taal,
        "heeft_logo": bool(kerk.logo),
        "accentkleur": kerk.accentkleur or "#2c5f2d",
    }


@router.get("/logo/{kerk_id}")
def kerk_logo(kerk_id: int, db=Depends(get_db)):
    """Publiek logo van de kerk — bruikbaar als <img src> in mail en op de site."""
    import base64
    kerk = db.get(Church, kerk_id)
    if not kerk or not kerk.logo:
        raise HTTPException(404, "Geen logo.")
    try:
        ruw = base64.b64decode(kerk.logo)
    except Exception:  # noqa: BLE001
        raise HTTPException(404, "Geen logo.")
    return Response(
        content=ruw,
        media_type=kerk.logo_type or "image/png",
        headers={"Cache-Control": "public, max-age=300"},
    )


@router.post("/api/inschrijven")
def inschrijven(body: InschrijvenBody, request: Request, db=Depends(get_db)):
    _rate(request, "inschrijven", 15)
    _rate(request, f"inschrijven-mail:{(body.email or '').lower()}", 3)
    kerk = db.get(Church, body.kerk_id)
    if not kerk:
        raise HTTPException(404, "Kerk niet gevonden.")
    try:
        sub, _ = subscribers.maak_inschrijver(
            db, kerk.id, body.naam, body.email, body.telefoon, body.frequentie,
            dienstvoorkeur=body.dienstvoorkeur, kanaal=body.kanaal,
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
    if not sub:
        return RedirectResponse("/inschrijven?bevestig_mislukt=1", status_code=303)
    doel = f"/inschrijven?kerk={sub.kerk_id}&bevestigd=1"
    # Koos deze inschrijver meldingen? Geef het voorkeur-token mee zodat de
    # bedankt-pagina ze meteen kan aanzetten.
    if sub.kanaal in ("push", "beide"):
        doel += f"&vt={sub.voorkeur_token}"
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
        dienstvoorkeur=body.dienstvoorkeur,
        ontvang_dag=body.ontvang_dag, ontvang_tijd=body.ontvang_tijd,
    )
    return {"ok": True}


@router.post("/api/afmelden")
def afmelden(body: dict, db=Depends(get_db)):
    sub = subscribers.op_voorkeur_token(db, (body or {}).get("token", ""))
    if sub:
        subscribers.afmelden(db, sub)
    return {"ok": True}


# ---- Web-push (PWA-meldingen) ----
@router.get("/api/push/publickey")
def push_publickey():
    return {"beschikbaar": push.beschikbaar(), "key": push.publieke_sleutel()}


@router.post("/api/push/abonneer")
def push_abonneer(body: dict, db=Depends(get_db)):
    """Sla het browser-push-abonnement op bij de inschrijver (via voorkeur-token)."""
    import json as _json

    sub = subscribers.op_voorkeur_token(db, (body or {}).get("token", ""))
    if not sub:
        raise HTTPException(404, "Onbekende of verlopen link.")
    abonnement = (body or {}).get("abonnement")
    if not abonnement:
        raise HTTPException(400, "Geen push-abonnement meegegeven.")
    sub.push_abonnement = _json.dumps(abonnement)
    # Kanaal bijwerken naar de keuze (email/push/beide); standaard 'beide'.
    kanaal = (body or {}).get("kanaal")
    if kanaal in ("email", "push", "beide"):
        sub.kanaal = kanaal
    elif sub.kanaal == "email":
        sub.kanaal = "beide"
    db.commit()
    return {"ok": True}


@router.post("/api/push/test")
def push_test(body: dict, db=Depends(get_db)):
    """Stuur een testmelding naar dit push-abonnement."""
    import json as _json

    sub = subscribers.op_voorkeur_token(db, (body or {}).get("token", ""))
    if not sub or not sub.push_abonnement:
        raise HTTPException(400, "Geen push-abonnement gevonden.")
    try:
        push.stuur(
            _json.loads(sub.push_abonnement),
            "AfterSermon", "Melding-test: je ontvangt voortaan de overdenkingen hier.",
        )
    except push.PushVerlopen:
        sub.push_abonnement = ""
        db.commit()
        raise HTTPException(410, "Het push-abonnement is verlopen; zet meldingen opnieuw aan.")
    except Exception as fout:  # noqa: BLE001
        raise HTTPException(502, f"Versturen mislukte: {fout}")
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
