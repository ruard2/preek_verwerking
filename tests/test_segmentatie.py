"""Preekdetectie: markeer 'volledige dienst' als er geen duidelijk preekblok is.

Zonder muziekmarkeringen (typisch voor YouTube-auto-ondertitels) kan de preek
niet worden afgebakend; dan geven we de hele dienst door met de vlag zodat het
taalmodel zelf het preekgedeelte eruit haalt.
"""

import transcript as ts


def test_geen_preekblok_valt_terug_op_volledige_dienst():
    # Korte tekst zonder muziekmarkeringen -> geen preekblok van 8+ min.
    entries = [(0, "welkom allen"), (60, "we lezen samen"), (120, "amen")]
    seg = ts.segmenteer(entries, titel="Dienst", taal="nl")
    assert seg["volledige_dienst"] is True
    assert "welkom allen" in seg["ondertitel_tekst"]


def test_duidelijk_preekblok_is_geen_volledige_dienst():
    # Muziek-intro (3 markeringen binnen 30s) + een spraakblok van 9 min.
    entries = [(0, "[muziek]"), (5, "[muziek]"), (10, "[muziek]")]
    entries += [(t, f"preekzin op {t}") for t in range(60, 601, 30)]  # 60..600s = 9 min
    seg = ts.segmenteer(entries, titel="Dienst", taal="nl")
    assert seg["volledige_dienst"] is False
    assert "[muziek]" not in seg["ondertitel_tekst"]     # muziek is eruit gefilterd
    assert "preekzin op 60" in seg["ondertitel_tekst"]
