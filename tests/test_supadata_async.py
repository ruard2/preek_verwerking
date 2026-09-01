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
