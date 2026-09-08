"""Inschrijverlogica: aanmelden (double opt-in), bevestigen, voorkeuren, afmelden."""

import secrets
from datetime import datetime, timedelta

import bcrypt
from sqlalchemy import select

from db import Church, Subscriber

FREQUENTIES = ("wekelijks", "dagelijks")


class InschrijfFout(Exception):
    pass


def _token():
    return secrets.token_urlsafe(24)


def _op_email(db, kerk_id, email):
    return db.scalar(
        select(Subscriber).where(
            Subscriber.kerk_id == kerk_id,
            Subscriber.email == email.strip().lower(),
        )
    )


def lijst(db, kerk_id):
    return list(db.scalars(
        select(Subscriber).where(Subscriber.kerk_id == kerk_id)
        .order_by(Subscriber.aangemaakt.desc())
    ))


DIENSTVOORKEUREN = ("beide", "ochtend", "avond")


KANALEN = ("email", "push", "beide")
UITVOER_TYPEN = ("dagstukjes", "preeksamenvatting", "preektranscript", "nabespreking")


def _schoon_uitvoer(waarde):
    """Normaliseer een uitvoer-voorkeur (lijst of komma-tekst) naar een geldige
    komma-tekst; onbekende types eruit. Leeg = alles wat de kerk stuurt."""
    if isinstance(waarde, str):
        waarde = waarde.split(",")
    schoon = [t.strip() for t in (waarde or []) if t and t.strip() in UITVOER_TYPEN]
    return ",".join(dict.fromkeys(schoon))


def maak_inschrijver(db, kerk_id, naam, email, telefoon="", frequentie="wekelijks",
                     ontvang_dag=0, ontvang_tijd="07:00", bevestigd=False,
                     dienstvoorkeur="beide", kanaal="email", uitvoer_voorkeur=None):
    """Maak (of werk bij) een inschrijver. Geeft (subscriber, is_nieuw)."""
    uitvoer = _schoon_uitvoer(uitvoer_voorkeur)
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise InschrijfFout("Geef een geldig e-mailadres op.")
    if frequentie not in FREQUENTIES:
        frequentie = "wekelijks"
    if dienstvoorkeur not in DIENSTVOORKEUREN:
        dienstvoorkeur = "beide"
    if kanaal not in KANALEN:
        kanaal = "email"
    bestaand = _op_email(db, kerk_id, email)
    if bestaand:
        # Niet dupliceren; voorkeuren bijwerken en (indien nodig) opnieuw bevestigen.
        bestaand.naam = (naam or bestaand.naam or "").strip()
        bestaand.telefoon = (telefoon or bestaand.telefoon or "").strip()
        bestaand.frequentie = frequentie
        bestaand.dienstvoorkeur = dienstvoorkeur
        bestaand.kanaal = kanaal
        if uitvoer_voorkeur is not None:
            bestaand.uitvoer_voorkeur = uitvoer
        bestaand.ontvang_dag = ontvang_dag
        bestaand.ontvang_tijd = ontvang_tijd
        if bevestigd:
            bestaand.bevestigd = True
        elif not bestaand.bevestigd and not bestaand.bevestig_token:
            bestaand.bevestig_token = _token()
        if not bestaand.voorkeur_token:
            bestaand.voorkeur_token = _token()
        db.commit()
        return bestaand, False

    sub = Subscriber(
        kerk_id=kerk_id, naam=(naam or "").strip(), email=email,
        telefoon=(telefoon or "").strip(), frequentie=frequentie,
        dienstvoorkeur=dienstvoorkeur, kanaal=kanaal, uitvoer_voorkeur=uitvoer,
        ontvang_dag=ontvang_dag, ontvang_tijd=ontvang_tijd,
        bevestigd=bevestigd,
        bevestig_token="" if bevestigd else _token(),
        voorkeur_token=_token(),
    )
    db.add(sub)
    db.commit()
    return sub, True


def bevestig(db, token):
    sub = db.scalar(select(Subscriber).where(Subscriber.bevestig_token == token))
    if not sub or not token:
        return None
    sub.bevestigd = True
    sub.bevestig_token = ""
    db.commit()
    return sub


def op_voorkeur_token(db, token):
    if not token:
        return None
    return db.scalar(select(Subscriber).where(Subscriber.voorkeur_token == token))


def werk_voorkeuren_bij(db, sub, **velden):
    if velden.get("frequentie") in FREQUENTIES:
        sub.frequentie = velden["frequentie"]
    if velden.get("dienstvoorkeur") in DIENSTVOORKEUREN:
        sub.dienstvoorkeur = velden["dienstvoorkeur"]
    if velden.get("uitvoer_voorkeur") is not None:
        sub.uitvoer_voorkeur = _schoon_uitvoer(velden["uitvoer_voorkeur"])
    if "naam" in velden:
        sub.naam = (velden["naam"] or "").strip()
    if "telefoon" in velden:
        sub.telefoon = (velden["telefoon"] or "").strip()
    if "ontvang_dag" in velden and velden["ontvang_dag"] is not None:
        sub.ontvang_dag = int(velden["ontvang_dag"]) % 7
    if velden.get("ontvang_tijd"):
        sub.ontvang_tijd = velden["ontvang_tijd"]
    if "uitvoer_taal" in velden:
        sub.uitvoer_taal = (velden["uitvoer_taal"] or "").strip().lower()
    db.commit()
    return sub


def afmelden(db, sub):
    db.delete(sub)
    db.commit()


# ── Gebruikers-authenticatie (gemeenteleden) ─────────────────────────────────

def _hash(wachtwoord: str) -> str:
    return bcrypt.hashpw(wachtwoord.encode(), bcrypt.gensalt()).decode()


def _check(wachtwoord: str, hash_: str) -> bool:
    try:
        return bool(hash_) and bcrypt.checkpw(wachtwoord.encode(), hash_.encode())
    except (ValueError, TypeError):
        return False


def stel_wachtwoord_in(db, sub, wachtwoord: str):
    """Sla een nieuw wachtwoord op voor een inschrijver."""
    if len(wachtwoord or "") < 8:
        raise InschrijfFout("Kies een wachtwoord van minstens 8 tekens.")
    sub.wachtwoord_hash = _hash(wachtwoord)
    sub.wachtwoord_reset_token = ""
    sub.wachtwoord_reset_verloopt = None
    db.commit()


def inloggen_gebruiker(db, email: str, wachtwoord: str):
    """Geeft lijst van Subscriber-rijen die bij dit e-mailadres + wachtwoord passen.

    Eén e-mailadres kan bij meerdere kerken ingeschreven zijn (elk met eigen voorkeur).
    Geeft lege lijst als inloggen mislukt.
    """
    email = (email or "").strip().lower()
    subs = list(db.scalars(
        select(Subscriber).where(Subscriber.email == email)
    ))
    return [s for s in subs if _check(wachtwoord, s.wachtwoord_hash or "")]


def start_wachtwoord_reset(db, email: str):
    """Maak een reset-token voor de inschrijver met dit e-mailadres.

    Geeft (sub, token) of (None, None) als het adres niet gevonden wordt.
    Werkt voor de eerste gevonden bevestigde inschrijver; is er geen
    bevestigde, dan de eerste niet-bevestigde.
    """
    email = (email or "").strip().lower()
    subs = list(db.scalars(select(Subscriber).where(Subscriber.email == email)))
    if not subs:
        return None, None
    sub = next((s for s in subs if s.bevestigd), subs[0])
    token = secrets.token_urlsafe(32)
    sub.wachtwoord_reset_token = token
    sub.wachtwoord_reset_verloopt = datetime.now() + timedelta(hours=2)
    db.commit()
    return sub, token


def reset_wachtwoord(db, token: str, nieuw: str):
    """Stel nieuw wachtwoord in via reset-token. Geeft Subscriber of None."""
    if len(nieuw or "") < 8:
        raise InschrijfFout("Kies een wachtwoord van minstens 8 tekens.")
    sub = db.scalar(
        select(Subscriber).where(Subscriber.wachtwoord_reset_token == token)
    )
    if (
        not sub
        or not token
        or not sub.wachtwoord_reset_verloopt
        or sub.wachtwoord_reset_verloopt < datetime.now()
    ):
        return None
    stel_wachtwoord_in(db, sub, nieuw)
    return sub


def zoek_kerken(db, q: str, limit: int = 10):
    """Zoek kerken op naam (bevat-zoekopdracht). Geeft lijst van dicts."""
    q = (q or "").strip()
    if not q:
        return []
    rijen = list(db.scalars(
        select(Church)
        .where(Church.naam.ilike(f"%{q}%"))
        .order_by(Church.naam)
        .limit(limit)
    ))
    return [{"id": k.id, "naam": k.naam} for k in rijen if k.inschrijving_open]
