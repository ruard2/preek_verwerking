"""Route 2: met een residentiële proxy kiest YouTube de eigen yt-dlp+Whisper-route,
met Supadata als automatische terugval."""

from unittest.mock import patch

import main


def _noop(_s):
    pass


def test_proxy_kiest_eigen_ytdlp_route():
    with patch.object(main.ts, "proxy_actief", return_value=True), \
         patch.object(main.supadata, "beschikbaar", return_value=True), \
         patch.object(main, "_youtube_via_ytdlp", return_value={"bron": "ytdlp"}) as y, \
         patch.object(main, "_youtube_via_supadata", return_value={"bron": "supa"}) as s:
        r = main._transcribeer_youtube("https://youtu.be/x", _noop)
    assert r["bron"] == "ytdlp"
    y.assert_called_once()
    s.assert_not_called()


def test_zonder_proxy_kiest_supadata():
    with patch.object(main.ts, "proxy_actief", return_value=False), \
         patch.object(main.supadata, "beschikbaar", return_value=True), \
         patch.object(main, "_youtube_via_ytdlp", return_value={"bron": "ytdlp"}) as y, \
         patch.object(main, "_youtube_via_supadata", return_value={"bron": "supa"}) as s:
        r = main._transcribeer_youtube("https://youtu.be/x", _noop)
    assert r["bron"] == "supa"
    y.assert_not_called()
    s.assert_called_once()


def test_eigen_route_faalt_valt_terug_op_supadata():
    with patch.object(main.ts, "proxy_actief", return_value=True), \
         patch.object(main.supadata, "beschikbaar", return_value=True), \
         patch.object(main, "_youtube_via_ytdlp", side_effect=RuntimeError("boem")), \
         patch.object(main, "_youtube_via_supadata", return_value={"bron": "supa"}) as s:
        r = main._transcribeer_youtube("https://youtu.be/x", _noop)
    assert r["bron"] == "supa"
    s.assert_called_once()


def test_zonder_proxy_en_zonder_supadata_faalt_zonder_terugval():
    with patch.object(main.ts, "proxy_actief", return_value=False), \
         patch.object(main.supadata, "beschikbaar", return_value=False), \
         patch.object(main, "_youtube_via_ytdlp", side_effect=RuntimeError("boem")), \
         patch.object(main, "_youtube_via_supadata") as s:
        try:
            main._transcribeer_youtube("https://youtu.be/x", _noop)
            assert False, "verwachtte een fout"
        except RuntimeError:
            pass
    s.assert_not_called()
