"""Tests voor de uitvoerkeuze (dagstukjes/samenvatting/transcript/nabespreking)."""

import main
import render


def test_parse_uitvoer_filtert_en_valt_terug():
    assert main.parse_uitvoer("nabespreking, dagstukjes, onzin") == ["nabespreking", "dagstukjes"]
    assert main.parse_uitvoer("") == ["dagstukjes"]
    assert main.parse_uitvoer(["preektranscript"]) == ["preektranscript"]
    assert main.parse_uitvoer(None) == ["dagstukjes"]


def _data():
    return {
        "taal": "nl", "titel": "T", "bijbelgedeelte": "Joh 3", "samenvatting": "S",
        "dagen": [{"titel": "d", "bijbeltekst": "Joh 3:16", "gedachte": "g",
                   "vraag_volwassenen": "v", "vraag_kinderen": "k"}],
        "nabespreking": {"hoofd": ["h1"], "hart": ["ha1"], "handen": ["hn1"]},
        "preektranscript": "Alinea een.\n\nAlinea twee.",
    }


def test_naar_tekst_toont_alleen_gekozen_secties():
    d = _data(); d["uitvoer_typen"] = ["nabespreking"]
    t = render.naar_tekst(d)
    assert "h1" in t and "nabespreking" in t.lower()
    assert "Gedachte" not in t  # geen dagstukjes

    d["uitvoer_typen"] = ["dagstukjes", "preektranscript"]
    t2 = render.naar_tekst(d)
    assert "Gedachte" in t2 and "Alinea een." in t2
    assert "h1" not in t2  # geen nabespreking


def test_terugval_zonder_uitvoer_typen_is_dagstukjes():
    d = _data()  # geen uitvoer_typen -> oud gedrag
    t = render.naar_tekst(d)
    assert "Gedachte" in t
    assert "h1" not in t


def test_pas_bewerking_toe_bewerkt_nabespreking_en_transcript():
    d = _data()
    render.pas_bewerking_toe(d, {
        "nabespreking": {"hoofd": ["nieuw1", " "], "hart": ["nieuw2"], "handen": ["nieuw3"]},
        "preektranscript": "Aangepast.",
    })
    assert d["nabespreking"]["hoofd"] == ["nieuw1"]  # lege vraag eruit gefilterd
    assert d["preektranscript"] == "Aangepast."


def test_naar_pdf_smoke_met_nabespreking():
    d = _data(); d["uitvoer_typen"] = ["dagstukjes", "nabespreking", "preektranscript"]
    pdf = render.naar_pdf(d)
    assert pdf[:4] == b"%PDF"
