"""Tests voor de Bijbeltekst-lookup (parsing + verrijking + veilige terugval)."""

import os

import bijbeltekst as bt

_HEEFT_DATA = os.path.isfile(os.path.join(bt._DIR, "nbv21.json"))


def test_parse_verwijzing_talen_en_afkortingen():
    assert bt.parse_verwijzing("Johannes 3:16") == ("JHN", 3, 16)
    assert bt.parse_verwijzing("Joh 3:16") == ("JHN", 3, 16)
    assert bt.parse_verwijzing("1 Korintiërs 13:4") == ("1CO", 13, 4)
    assert bt.parse_verwijzing("1 Kor 13:4-7") == ("1CO", 13, 4)  # bereik -> eerste vers
    assert bt.parse_verwijzing("Romeine 8:28") == ("ROM", 8, 28)  # Afrikaans
    assert bt.parse_verwijzing("Openbaring 21:4") == ("REV", 21, 4)


def test_parse_verwijzing_ongeldig():
    assert bt.parse_verwijzing("Psalm 23") is None  # geen vers
    assert bt.parse_verwijzing("Onzin 1:1") is None  # onbekend boek
    assert bt.parse_verwijzing("") is None


def test_niet_lokale_vertaling_blijft_ongewijzigd():
    data = {"dagen": [{"bijbeltekst": "John 3:16"}]}
    bt.verrijk_dagen(data, {"vertaling": "niv", "citaat_volledig": True})
    assert data["dagen"][0]["bijbeltekst"] == "John 3:16"


def test_alleen_verwijzing_wordt_niet_verrijkt():
    data = {"dagen": [{"bijbeltekst": "Johannes 3:16"}]}
    bt.verrijk_dagen(data, {"vertaling": "nbv21", "citaat_volledig": False})
    assert data["dagen"][0]["bijbeltekst"] == "Johannes 3:16"


if _HEEFT_DATA:
    def test_verrijking_voegt_exacte_tekst_toe():
        data = {"dagen": [{"bijbeltekst": "Johannes 3:16"}]}
        bt.verrijk_dagen(data, {"vertaling": "nbv21", "citaat_volledig": True})
        tekst = data["dagen"][0]["bijbeltekst"]
        assert tekst.startswith("Johannes 3:16 — ")
        assert "(NBV21)" in tekst
        assert "wereld" in tekst

    def test_onbekend_boek_valt_veilig_terug():
        # Richteren ontbreekt in de NL-data -> verwijzing blijft staan.
        data = {"dagen": [{"bijbeltekst": "Richteren 6:12"}]}
        bt.verrijk_dagen(data, {"vertaling": "nbv21", "citaat_volledig": True})
        assert data["dagen"][0]["bijbeltekst"] == "Richteren 6:12"
