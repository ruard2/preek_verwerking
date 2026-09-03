"""Lid kiest zelf welke uitvoer(en) het wil; admin kan inschrijving sluiten."""

from types import SimpleNamespace

import levering


def _kerk():
    return SimpleNamespace(id=1, naam="Testkerk", email="k@test.nl", logo="",
                           communicatie_taal="nl", ai_disclaimer=True, accentkleur="#2c5f2d")


def _sub(voorkeur):
    return SimpleNamespace(email="lid@test.nl", kanaal="email", voorkeur_token="tok",
                           push_abonnement="", uitvoer_voorkeur=voorkeur)


DATA = {"titel": "Preek", "uitvoer_typen": ["dagstukjes", "nabespreking"],
        "samenvatting": "S", "dagen": [{"titel": "D1", "bijbeltekst": "x", "gedachte": "g",
                                        "vraag_volwassenen": "a", "vraag_kinderen": "k"}],
        "nabespreking": {"hoofd": ["v1"]}}


def test_lid_krijgt_alleen_eigen_keuze(_knijp_extern_af):
    verzonden = _knijp_extern_af
    # Kerk stuurt beide; lid wil alleen nabespreking -> mail gaat uit (1x), zonder dagstukjes.
    levering.verstuur_een(_kerk(), DATA, "http://x", _sub("nabespreking"),
                          bezorg_typen=["dagstukjes", "nabespreking"])
    assert len(verzonden) == 1


def test_lid_zonder_overlap_krijgt_niets(_knijp_extern_af):
    verzonden = _knijp_extern_af
    # Lid wil alleen preektekst, maar kerk stuurt die niet -> niets versturen.
    levering.verstuur_een(_kerk(), DATA, "http://x", _sub("preektranscript"),
                          bezorg_typen=["dagstukjes", "nabespreking"])
    assert verzonden == []


def test_lege_voorkeur_krijgt_alles(_knijp_extern_af):
    verzonden = _knijp_extern_af
    levering.verstuur_een(_kerk(), DATA, "http://x", _sub(""),
                          bezorg_typen=["dagstukjes", "nabespreking"])
    assert len(verzonden) == 1


def test_inschrijving_gesloten_weigert(client, db):
    from db import Church
    kerk = Church(email="dicht@test.nl", wachtwoord_hash="x", naam="Dicht",
                  email_geverifieerd=True, inschrijving_open=False)
    db.add(kerk)
    db.commit()
    r = client.post("/api/inschrijven", json={"kerk_id": kerk.id, "email": "nieuw@test.nl"})
    assert r.status_code == 403
