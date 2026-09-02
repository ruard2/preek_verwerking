"""Supadata async-transcriptie: pollen tot 'completed', nette time-out-melding.

Video's > 20 min geven HTTP 202 + {jobId}; /transcript/{jobId} geeft eerst
{"status":"queued"|"active"} en pas bij 'completed' de content.
"""

import pytest

import supadata


def test_async_polling_haalt_transcript_op():
    responses = [
        {"jobId": "job1"},                                   # eerste /transcript
        {"status": "queued"},                                # poll 1
        {"status": "active"},                                # poll 2
        {"status": "completed",                              # poll 3: klaar
         "content": [{"text": "Hallo gemeente", "offset": 0}], "lang": "nl"},
    ]
    beurten = {"i": 0}

    def nep_get(pad, params, _herkansing=True):
        r = responses[beurten["i"]]
        beurten["i"] += 1
        return r

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(supadata, "_get", nep_get)
        mp.setattr(supadata.time, "sleep", lambda *_: None)
        mp.setattr(supadata, "MIN_TRANSCRIPT_TEKENS", 5)
        entries, taal = supadata.haal_transcript("https://youtu.be/x")

    assert entries == [(0, "Hallo gemeente")]
    assert taal == "nl"


def test_async_timeout_geeft_nette_fout():
    def nep_get(pad, params, _herkansing=True):
        if pad == "transcript":
            return {"jobId": "job1"}
        return {"status": "active"}  # blijft eeuwig 'active'

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(supadata, "_get", nep_get)
        mp.setattr(supadata.time, "sleep", lambda *_: None)
        mp.setattr(supadata, "JOB_TIMEOUT", 10)
        mp.setattr(supadata, "POLL_INTERVAL", 5)
        with pytest.raises(RuntimeError, match="nog bezig met transcriberen"):
            supadata.haal_transcript("https://youtu.be/x")


def test_naar_entries_verdraagt_vormvarianten():
    n = supadata._naar_entries
    # standaard: lijst van segmenten met offset (ms)
    assert n([{"text": "a", "offset": 2000}]) == [(2, "a")]
    # geneste content-sleutel
    assert n({"content": [{"text": "b", "offset": 0}]}) == [(0, "b")]
    # alternatieve tijd-sleutels
    assert n([{"text": "c", "startMs": 3000}]) == [(3, "c")]
    # lijst van kale regels zonder tijdcodes -> één blok
    assert n(["hallo", "wereld"]) == [(0, "hallo\nwereld")]
    # leeg blijft leeg
    assert n([]) == []
    assert n("") == []


def test_lege_auto_valt_terug_op_generate():
    """Lege 'auto' (lege captions-track) -> herkansing met 'generate' (AI uit audio)."""
    def nep_get(pad, params, _herkansing=True):
        if pad == "transcript":
            if params.get("mode") == "auto":
                return {"content": [], "lang": "nl"}          # lege ondertitels
            return {"content": [{"text": "Preek uit audio", "offset": 0}], "lang": "nl"}
        return {}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(supadata, "_get", nep_get)
        mp.setattr(supadata.time, "sleep", lambda *_: None)
        mp.setattr(supadata, "MODE", "auto")
        mp.setattr(supadata, "MIN_TRANSCRIPT_TEKENS", 5)
        entries, taal = supadata.haal_transcript("https://youtu.be/x")

    assert entries == [(0, "Preek uit audio")]
    assert taal == "nl"


def test_te_kort_fragment_valt_terug_op_generate():
    """Een paar losse woorden (lege captiontrack met ruis) telt óók als onbruikbaar."""
    lang = "Vandaag lezen we uit Johannes drie. " * 10  # ruim > drempel

    def nep_get(pad, params, _herkansing=True):
        if pad == "transcript":
            if params.get("mode") == "auto":
                return {"content": [{"text": "there is one", "offset": 0}], "lang": "en"}
            return {"content": [{"text": lang, "offset": 0}], "lang": "nl"}
        return {}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(supadata, "_get", nep_get)
        mp.setattr(supadata.time, "sleep", lambda *_: None)
        mp.setattr(supadata, "MODE", "auto")
        entries, taal = supadata.haal_transcript("https://youtu.be/x")

    assert entries == [(0, lang.strip())]     # het te korte fragment is genegeerd
    assert taal == "nl"


def test_overal_te_kort_geeft_nette_fout():
    def nep_get(pad, params, _herkansing=True):
        if pad == "transcript":
            return {"content": [{"text": "there is one", "offset": 0}], "lang": "en"}
        return {}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(supadata, "_get", nep_get)
        mp.setattr(supadata.time, "sleep", lambda *_: None)
        mp.setattr(supadata, "MODE", "auto")
        with pytest.raises(RuntimeError, match="geen bruikbaar transcript"):
            supadata.haal_transcript("https://youtu.be/x")


def test_async_failed_geeft_fout():
    def nep_get(pad, params, _herkansing=True):
        if pad == "transcript":
            return {"jobId": "job1"}
        return {"status": "failed", "error": {"code": "no_captions"}}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(supadata, "_get", nep_get)
        mp.setattr(supadata.time, "sleep", lambda *_: None)
        with pytest.raises(RuntimeError, match="kon de transcriptie niet maken"):
            supadata.haal_transcript("https://youtu.be/x")
