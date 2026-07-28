"""Sleutel-normalisatie (Afrikaans-fix) en rendering."""

import llm
import render


def test_normaliseer_afrikaanse_sleutels():
    kapot = {
        "title": "Toets", "samevatting": "opsomming",
        "dae": [{
            "opskrif": "Dag een", "bybelteks": "Gal 5:25",
            "gedagte": "die oordenking", "vraag_volwassenes": "V?", "vraag_kinders": "K?",
        }],
    }
    schoon = llm.normaliseer(dict(kapot))
    dag = schoon["dagen"][0]
    assert schoon["titel"] == "Toets"
    assert schoon["samenvatting"] == "opsomming"
    assert dag["gedachte"] == "die oordenking"
    assert dag["bijbeltekst"] == "Gal 5:25"
    assert dag["vraag_volwassenen"] == "V?"
    assert dag["vraag_kinderen"] == "K?"


def test_normaliseer_idempotent():
    d = {"titel": "x", "dagen": [{"gedachte": "g"}]}
    assert llm.normaliseer(llm.normaliseer(d))["dagen"][0]["gedachte"] == "g"


def test_labels_talen():
    assert render.labels("nl")["dag"] == "Dag"
    assert render.labels("en")["dag"] == "Day"
    assert render.labels("af")["gedachte"] == "Oordenking"


def test_naar_tekst_bevat_kernvelden():
    data = {
        "taal": "nl", "titel": "Preek X", "bijbelgedeelte": "Ps 1",
        "samenvatting": "een samenvatting",
        "dagen": [{"titel": f"D{i}", "bijbeltekst": "Ps 1:1", "gedachte": "g",
                   "vraag_volwassenen": "v", "vraag_kinderen": "k"} for i in range(7)],
    }
    tekst = render.naar_tekst(data)
    assert "Preek X" in tekst
    assert "een samenvatting" in tekst
    assert "Ps 1" in tekst
