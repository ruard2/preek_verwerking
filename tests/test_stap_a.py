"""Stap A: verwerken = alleen transcript+opschonen; genereren pas op aanvraag."""

from unittest.mock import patch

import main


def _stored():
    return {
        "data": {"titel": "T", "taal": "nl", "dagen": [], "voorbereid": True},
        "preek_schoon": "schone preektekst", "transcript_ruw": "ruwe tekst",
        "meta": {"titel": "T"}, "ondertitel": "T",
        "bron_info": {"volledige_dienst": True},
    }


def _bron():
    return {"transcript": "ruwe tekst", "taal_hint": "nl", "welkom": None,
            "extra_context": None, "volledige_dienst": False, "liturgie": None,
            "ondertitel": "T", "meta": {"titel": "T"}}


def test_alleen_transcript_genereert_niets():
    with patch.object(main, "_transcribeer_bron", return_value=_bron()), \
         patch.object(main, "verwerk_preek") as vp, \
         patch.object(main, "llm_maak_basis") as mb, \
         patch.object(main, "llm_schoon_transcript", return_value="schoon"), \
         patch.object(main.store, "resultaat_ophalen", return_value=None), \
         patch.object(main.store, "resultaat_opslaan"):
        r = main.verwerk_en_bewaar(
            "https://www.youtube.com/watch?v=abcdefghijk", alleen_transcript=True
        )
    vp.assert_not_called()
    mb.assert_not_called()
    assert r["data"].get("voorbereid") is True
    assert r["data"].get("dagen") == []
    assert r["preek_schoon"] == "schoon"   # opschonen gebeurt wél


def test_genereer_dagstukjes_op_aanvraag():
    with patch.object(main, "verwerk_preek",
                      return_value={"taal": "nl", "titel": "T2", "dagen": [{"titel": "d"}]}) as vp, \
         patch.object(main, "llm_maak_basis") as mb, \
         patch.object(main.store, "resultaat_ophalen", return_value=_stored()), \
         patch.object(main.store, "resultaat_opslaan"):
        r = main.genereer_en_bewaar("vid", "dagstukjes")
    vp.assert_called_once()
    mb.assert_not_called()
    assert r["data"]["dagen"]
    assert "voorbereid" not in r["data"]


def test_genereer_samenvatting_op_aanvraag():
    with patch.object(main, "verwerk_preek") as vp, \
         patch.object(main, "llm_maak_basis",
                      return_value={"taal": "nl", "titel": "T", "bijbelgedeelte": "Joh 3",
                                    "samenvatting": "S"}) as mb, \
         patch.object(main.store, "resultaat_ophalen", return_value=_stored()), \
         patch.object(main.store, "resultaat_opslaan"):
        r = main.genereer_en_bewaar("vid", "samenvatting")
    mb.assert_called_once()
    vp.assert_not_called()
    assert r["data"]["samenvatting"] == "S"
    assert r["data"]["dagen"] == []   # samenvatting maakt geen dagstukjes


def test_genereer_zonder_transcript_faalt():
    with patch.object(main.store, "resultaat_ophalen", return_value={"data": {}}):
        try:
            main.genereer_en_bewaar("vid", "dagstukjes")
            assert False, "verwachtte ValueError"
        except ValueError:
            pass
