"""Borgt dat we één keer transcriberen en alleen de gekozen uitvoer genereren."""

from unittest.mock import patch

import main


def _bron_info():
    return {
        "transcript": "ruwe preektekst", "taal_hint": "nl", "welkom": None,
        "extra_context": None, "volledige_dienst": False, "liturgie": None,
        "ondertitel": "Titel", "meta": {"titel": "Titel"},
    }


def _draai(uitvoer_typen):
    """Draai verwerk_en_bewaar met alle externe stappen gemockt; geef de mocks terug."""
    with patch.object(main, "_transcribeer_bron", return_value=_bron_info()) as t, \
         patch.object(main, "verwerk_preek",
                      return_value={"taal": "nl", "titel": "T", "dagen": [{"titel": "d"}]}) as vp, \
         patch.object(main, "llm_maak_basis",
                      return_value={"taal": "nl", "titel": "T", "dagen": []}) as mb, \
         patch.object(main, "llm_schoon_transcript", return_value="schone preek") as sc, \
         patch.object(main, "llm_maak_nabespreking",
                      return_value={"hoofd": ["h"], "hart": ["a"], "handen": ["n"]}) as nb, \
         patch.object(main.store, "resultaat_ophalen", return_value=None), \
         patch.object(main.store, "resultaat_opslaan"):
        r = main.verwerk_en_bewaar(
            "https://www.youtube.com/watch?v=abcdefghijk",
            uitvoer_typen=uitvoer_typen,
        )
    return r, {"transcribeer": t, "verwerk_preek": vp, "maak_basis": mb,
               "schoon": sc, "nabespreking": nb}


def test_alleen_nabespreking_slaat_dagstukjes_generatie_over():
    r, m = _draai(["nabespreking"])
    assert m["transcribeer"].call_count == 1        # één keer luisteren/transcriberen
    assert m["verwerk_preek"].call_count == 0       # geen dure 7-daagse generatie
    assert m["maak_basis"].call_count == 1          # wel een lichte basis
    assert m["nabespreking"].call_count == 1        # nabespreking wél gemaakt
    assert r["data"].get("nabespreking")
    assert not r["data"].get("dagen")               # geen dagstukjes


def test_dagstukjes_gebruikt_volledige_generatie():
    r, m = _draai(["dagstukjes"])
    assert m["transcribeer"].call_count == 1
    assert m["verwerk_preek"].call_count == 1        # weekboekje wél
    assert m["maak_basis"].call_count == 0
    assert m["nabespreking"].call_count == 0         # niet gevraagd
    assert r["data"].get("dagen")


def test_transcript_output_hergebruikt_schone_tekst():
    r, m = _draai(["preektranscript"])
    assert m["transcribeer"].call_count == 1
    assert m["verwerk_preek"].call_count == 0
    assert r["data"].get("preektranscript") == "schone preek"


def test_herverwerk_transcribeert_nooit_opnieuw():
    """Met een opgeslagen transcript wordt er nooit opnieuw gedownload/getranscribeerd."""
    stored = {
        "data": {"taal": "nl", "titel": "T", "dagen": []},
        "transcript_ruw": "eerdere ruwe tekst", "preek_schoon": "eerder schoon",
        "meta": {"titel": "T"}, "ondertitel": "T",
        "bron_info": {"taal_hint": "nl", "welkom": None, "extra_context": None,
                      "volledige_dienst": False, "liturgie": None,
                      "ondertitel": "T", "meta": {"titel": "T"}},
    }
    with patch.object(main, "_transcribeer_bron") as t, \
         patch.object(main, "verwerk_preek",
                      return_value={"taal": "nl", "titel": "T", "dagen": [{"titel": "d"}]}) as vp, \
         patch.object(main, "llm_maak_basis", return_value={"taal": "nl", "dagen": []}), \
         patch.object(main, "llm_schoon_transcript", return_value="opnieuw schoon") as sc, \
         patch.object(main, "llm_maak_nabespreking",
                      return_value={"hoofd": ["h"], "hart": ["a"], "handen": ["n"]}), \
         patch.object(main.store, "resultaat_ophalen", return_value=stored), \
         patch.object(main.store, "resultaat_opslaan"):
        r = main.verwerk_en_bewaar(
            "https://www.youtube.com/watch?v=abcdefghijk", herverwerk=True,
            uitvoer_typen=["dagstukjes", "nabespreking"],
        )
    t.assert_not_called()             # NOOIT opnieuw transcriberen/downloaden
    sc.assert_not_called()            # opgeslagen schone tekst hergebruikt
    assert vp.call_count == 1         # wél opnieuw genereren (herverwerk)
    assert r["data"].get("nabespreking")
