"""Authenticatie voor kerk-accounts: registratie, verificatie, login, reset."""

import secrets
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import select

from db import Church, EmailToken


def hash_wachtwoord(wachtwoord):
    return bcrypt.hashpw(wachtwoord.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def controleer_wachtwoord(wachtwoord, hash_):
    try:
        return bcrypt.checkpw(wachtwoord.encode("utf-8"), hash_.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _kerk_op_email(db, email):
    return db.scalar(select(Church).where(Church.email == email.strip().lower()))


def maak_token(db, kerk, soort, geldig_uren=24):
    token = secrets.token_urlsafe(32)
    db.add(EmailToken(
        kerk_id=kerk.id, token=token, soort=soort,
        verloopt=datetime.utcnow() + timedelta(hours=geldig_uren),
    ))
    db.commit()
    return token


def _gebruik_token(db, token, soort):
    rij = db.scalar(select(EmailToken).where(EmailToken.token == token))
    if (
        not rij or rij.soort != soort or rij.gebruikt
        or rij.verloopt < datetime.utcnow()
    ):
        return None
    return rij


class RegistratieFout(Exception):
    pass


def registreer(db, naam, email, wachtwoord):
    """Maak een (nog niet geverifieerd) kerk-account. Geeft (kerk, verify_token)."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise RegistratieFout("Geef een geldig e-mailadres op.")
    if len(wachtwoord or "") < 8:
        raise RegistratieFout("Kies een wachtwoord van minstens 8 tekens.")
    if _kerk_op_email(db, email):
        raise RegistratieFout("Er bestaat al een account met dit e-mailadres.")
    kerk = Church(
        naam=(naam or "").strip(), email=email,
        wachtwoord_hash=hash_wachtwoord(wachtwoord),
    )
    db.add(kerk)
    db.commit()
    return kerk, maak_token(db, kerk, "verify")


def verifieer_email(db, token):
    rij = _gebruik_token(db, token, "verify")
    if not rij:
        return None
    rij.gebruikt = True
    rij.kerk.email_geverifieerd = True
    db.commit()
    return rij.kerk


def login(db, email, wachtwoord):
    """Geef de kerk terug bij juiste inlog én geverifieerd e-mailadres, anders None."""
    kerk = _kerk_op_email(db, email)
    if not kerk or not controleer_wachtwoord(wachtwoord, kerk.wachtwoord_hash):
        return None
    return kerk if kerk.email_geverifieerd else False  # False = wel juist, niet geverifieerd


def start_reset(db, email):
    kerk = _kerk_op_email(db, email)
    if not kerk:
        return None
    return maak_token(db, kerk, "reset", geldig_uren=2)


def reset_wachtwoord(db, token, nieuw_wachtwoord):
    if len(nieuw_wachtwoord or "") < 8:
        raise RegistratieFout("Kies een wachtwoord van minstens 8 tekens.")
    rij = _gebruik_token(db, token, "reset")
    if not rij:
        return None
    rij.gebruikt = True
    rij.kerk.wachtwoord_hash = hash_wachtwoord(nieuw_wachtwoord)
    db.commit()
    return rij.kerk
