"""Stap B: gespreksvragen voor groepen (optie 3) — begrensd en op aanvraag."""

import json
from unittest.mock import patch

import llm
import main


def _stored():
    return {
        "data": {"titel": "T", "taal": "nl", "bijbelgedeelte": "Joh 3", "dagen": [],
                 "voorbereid": True},
        "preek_schoon": "schone preektekst", "transcript_ruw": "ruw",
        "meta": {"titel": "T"}, "bron_info": {"volledige_dienst": True},
    }


def test_verdeel_gelijk():
    assert llm._verdeel(10, 3) == [4, 3, 3]
    assert llm._verdeel(5, 2) == [3, 2]
    assert llm._verdeel(20, 4) == [5, 5, 5, 5]


def test_maak_groepsvragen_parseert_en_filtert():
    antwoord = json.dumps({"verdiepen": ["a", "b"], "handen": ["c"], "onzin": ["x"]})
    with patch.dict("os.environ", {"OPENAI_API_KEY": "x"}), \
         patch.object(llm, "client_chat", return_value=antwoord):
        uit = llm.maak_groepsvragen(
            "preektekst", ["verdiepen", "handen", "onbekend"], aantal=6, taal_hint="nl"
        )
    assert set(uit.keys()) == {"verdiepen", "handen"}   # onbekende categorie gefilterd
    assert uit["verdiepen"] == ["a", "b"]


def test_maak_groepsvragen_zonder_categorie_faalt():
    with patch.dict("os.environ", {"OPENAI_API_KEY": "x"}):
        try:
            llm.maak_groepsvragen("tekst", [], aantal=5)
            assert False, "verwachtte ValueError"
        except ValueError:
            pass


def test_genereer_groepsvragen_en_bewaar():
    with patch.object(main, "llm_maak_groepsvragen",
                      return_value={"verdiepen": ["v1"], "handen": ["v2"]}) as mg, \
         patch.object(main.store, "resultaat_ophalen", return_value=_stored()), \
         patch.object(main.store, "resultaat_opslaan"):
        r = main.genereer_groepsvragen_en_bewaar(
            "vid", {"categorieen": ["verdiepen", "handen"], "aantal": 10, "leeftijd": "Tieners"}
        )
    mg.assert_called_once()
    gv = r["data"]["groepsvragen"]
    assert gv["vragen"] == {"verdiepen": ["v1"], "handen": ["v2"]}
    assert gv["leeftijd"] == "Tieners"
    assert "voorbereid" not in r["data"]
