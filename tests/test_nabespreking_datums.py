"""Groepsvragen op vaste datums: aparte mail, idempotent, tijd-afhankelijk."""

from datetime import date, datetime

import automatisering as a
import store
from db import Church, NabesprekingBezorging, Subscriber, Uitzending


def _maak_kerk(db, **extra):
    velden = dict(
        email=f"np{next(iter([id(extra)]))}@test.nl", wachtwoord_hash="x", naam="Testkerk",
        tijdzone="Europe/Amsterdam", verzend_tijd="07:00", versturen_zonder_goedkeuring=False,
        uitvoer_typen="dagstukjes,nabespreking",
        nabespreking_schema="datums", nabespreking_datums="2026-09-03",
    )
    velden.update(extra)
    k = Church(**velden)
    db.add(k)
    db.commit()
    return k


def _stel_op(db, kerk):
    sub = Subscriber(kerk_id=kerk.id, email="lid@test.nl", bevestigd=True,
                     frequentie="wekelijks", voorkeur_token="tok")
    db.add(sub)
    uit = Uitzending(kerk_id=kerk.id, video_id="vidnp", url="u", titel="Preek",
                     datum=date(2026, 9, 1), week_start=date(2026, 8, 31), goedgekeurd=True)
    db.add(uit)
    db.commit()
    store.resultaat_opslaan("vidnp", {"data": {
        "titel": "Preek", "uitvoer_typen": ["nabespreking"],
        "nabespreking": {"hoofd": ["v1"], "hart": ["v2"], "handen": ["v3"]},
    }, "ondertitel": ""})


def test_verstuurt_op_datum_en_is_idempotent(client, db, _knijp_extern_af):
    verzonden = _knijp_extern_af
    kerk = _maak_kerk(db, email="datum1@test.nl")
    _stel_op(db, kerk)
    nu = datetime(2026, 9, 3, 8, 0)  # de vaste datum, ná verzend_tijd

    assert a.bezorg_nabespreking(db, kerk, "http://x", nu_lokaal=nu) == 1
    assert len(verzonden) == 1
    # tweede run op dezelfde dag: niets extra (idempotent)
    assert a.bezorg_nabespreking(db, kerk, "http://x", nu_lokaal=nu) == 0
    assert len(verzonden) == 1


def test_niet_voor_de_tijd(client, db, _knijp_extern_af):
    verzonden = _knijp_extern_af
    kerk = _maak_kerk(db, email="datum2@test.nl")
    _stel_op(db, kerk)
    vroeg = datetime(2026, 9, 3, 6, 0)  # vóór 07:00
    assert a.bezorg_nabespreking(db, kerk, "http://x", nu_lokaal=vroeg) == 0
    assert verzonden == []


def test_schema_mee_stuurt_niets_apart(client, db, _knijp_extern_af):
    kerk = _maak_kerk(db, email="datum3@test.nl", nabespreking_schema="mee")
    _stel_op(db, kerk)
    nu = datetime(2026, 9, 3, 8, 0)
    assert a.bezorg_nabespreking(db, kerk, "http://x", nu_lokaal=nu) == 0
