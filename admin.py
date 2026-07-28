"""Admin-API: registratie, login, e-mailverificatie, reset en kanaalinstelling.

Server-rendered pagina is static/admin.html; hier zitten de JSON-endpoints en
de sessie-afhandeling (ondertekende cookie via Starlette SessionMiddleware).
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel

import os
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
        request.session.clear()
        request.session["kerk_id"] = kerk.id
        return RedirectResponse("/admin", status_code=303)
    except Exception:
        db.rollback()
        return RedirectResponse("/admin?error=community-tools", status_code=303)


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
    tijdzone: str = "Europe/Amsterdam"
    verzend_dag: int = 0
    verzend_tijd: str = "07:00"
    versturen_zonder_goedkeuring: bool = False
    ai_disclaimer: bool = True
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
        "tijdzone": kerk.tijdzone,
        "verzend_dag": kerk.verzend_dag,
        "verzend_tijd": kerk.verzend_tijd,
        "versturen_zonder_goedkeuring": kerk.versturen_zonder_goedkeuring,
        "ai_disclaimer": kerk.ai_disclaimer,
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
    kerk.verzend_dag = int(body.verzend_dag) % 7
    kerk.verzend_tijd = (body.verzend_tijd or "07:00").strip()
    kerk.versturen_zonder_goedkeuring = bool(body.versturen_zonder_goedkeuring)
    kerk.ai_disclaimer = bool(body.ai_disclaimer)
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
    aantal = levering.verstuur_weekboekje(db, kerk, bewaard["data"], _basis_url(request))
    uitzending = db.scalar(select(Uitzending).where(
        Uitzending.kerk_id == kerk.id, Uitzending.video_id == video_id
    ))
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
        data = main.verwerk_tekst_en_bewaar(video_id, tekst, titel_hint=file.filename)
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
    uit.goedgekeurd_op = datetime.utcnow()
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
    return {
        "titel": uit.titel, "datum": str(uit.datum), "goedgekeurd": uit.goedgekeurd,
        "goedgekeurd_op": uit.goedgekeurd_op.isoformat() if uit.goedgekeurd_op else None,
        "goedgekeurd_door": uit.goedgekeurd_door or None,
        "video_id": uit.video_id, "data": _met_labels(data),
        "tekst": bewaard.get("tekst", ""),
        "verwerkt": bool(data),
    }


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
            main.verwerk_en_bewaar(uit.url)
        except Exception as fout:  # noqa: BLE001
            raise HTTPException(502, f"Verwerken lukte niet: {fout}")
        bewaard = store.resultaat_ophalen(uit.video_id) or {}
    data = bewaard.get("data") or {}
    return {"ok": True, "data": _met_labels(data), "tekst": bewaard.get("tekst", "")}


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
        data = main.verwerk_tekst_en_bewaar(uit.video_id, tekst, titel_hint=uit.titel)
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
    return {"naam": kerk.naam or "AfterSermon", "inschrijf_taal": kerk.inschrijf_taal}


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
    doel = (
        f"/inschrijven?kerk={sub.kerk_id}&bevestigd=1"
        if sub else "/inschrijven?bevestig_mislukt=1"
    )
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
