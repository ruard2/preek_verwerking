"""Bron-herkenning en URL-/datumparsers."""

import kerkdienstgemist as kdg
import kerkomroep as ko
import main


def test_classificeer_youtube():
    assert main._classificeer("https://www.youtube.com/@Kerk/streams") == ("youtube", "kanaal")
    assert main._classificeer("https://www.youtube.com/watch?v=ywC8JRyGmbo") == ("youtube", "enkel")


def test_classificeer_kerkdienstgemist():
    assert main._classificeer("https://kerkdienstgemist.nl/stations/2154") == ("kdg", "kanaal")
    assert main._classificeer(
        "https://kerkdienstgemist.nl/stations/2154/events/recording/178447860002154"
    ) == ("kdg", "enkel")


def test_classificeer_kerkomroep():
    assert main._classificeer("https://kerkomroep.nl/kerken/11101") == ("kerkomroep", "kanaal")
    assert main._classificeer("https://kerkomroep.nl/kerken/11101/audio/2607261649") == (
        "kerkomroep", "enkel",
    )


def test_classificeer_onbekend():
    assert main._classificeer("https://example.com/iets") == (None, None)


def test_kerkomroep_video_id():
    assert ko.video_id("https://kerkomroep.nl/kerken/11101/audio/2607261649") == "ko_11101_2607261649"


def test_kerkdienstgemist_video_id():
    vid = kdg.video_id("https://kerkdienstgemist.nl/stations/2154/events/recording/178447860002154")
    assert vid == "kdg_2154_178447860002154"
