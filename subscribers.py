"""Inschrijverlogica: aanmelden (double opt-in), bevestigen, voorkeuren, afmelden."""

import secrets

from sqlalchemy import select

from db import Subscriber

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
    db.commit()
    return sub


def afmelden(db, sub):
    db.delete(sub)
    db.commit()
