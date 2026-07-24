"""Eenvoudige, bestand-gebaseerde opslag (cache) op schijf.

- Dienstenlijst: één keer per week verversen, zo snel mogelijk na zondag.
  Daarna uit de cache.
- Preekresultaten: per video één keer berekenen (transcript + verwerking),
  daarna permanent uit de cache.

Opslagmap via DATA_DIR (standaard ./data). Op Railway koppel je daar een
volume aan zodat de cache een herstart/redeploy overleeft.
"""

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timedelta

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
_RESULT_DIR = os.path.join(DATA_DIR, "resultaten")
_DIENSTEN_DIR = os.path.join(DATA_DIR, "diensten")
# Kerkweek-grens: zondag 20:00 (na de avonddienst). Na dit moment geldt de
# dienstenlijst als verouderd tot hij opnieuw is opgehaald.
WEEKGRENS_UUR = int(os.environ.get("DIENSTEN_WEEKGRENS_UUR", "20"))


def _zorg_map(pad):
    os.makedirs(pad, exist_ok=True)


def _schrijf_atomisch(pad, data):
    _zorg_map(os.path.dirname(pad))
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(pad), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, pad)


def _lees(pad):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ---- Dienstenlijst -------------------------------------------------------

def _laatste_weekgrens(nu):
    """Meest recente zondag WEEKGRENS_UUR:00 op of vóór `nu`."""
    dagen_sinds_zondag = (nu.weekday() + 1) % 7  # ma=0..zo=6 -> zo=0
    zondag = (nu - timedelta(days=dagen_sinds_zondag)).replace(
        hour=WEEKGRENS_UUR, minute=0, second=0, microsecond=0
    )
    if zondag > nu:
        zondag -= timedelta(days=7)
    return zondag


def _diensten_pad(kanaal):
    sleutel = hashlib.sha1((kanaal or "").encode("utf-8")).hexdigest()[:16]
    return os.path.join(_DIENSTEN_DIR, sleutel + ".json")


def diensten_ophalen(kanaal):
    """(diensten, is_vers) voor dit kanaal. is_vers=False = geen/verouderde cache."""
    data = _lees(_diensten_pad(kanaal))
    if not data or "diensten" not in data:
        return None, False
    try:
        opgehaald = datetime.fromisoformat(data.get("opgehaald", ""))
    except ValueError:
        return data["diensten"], False
    vers = opgehaald >= _laatste_weekgrens(datetime.now())
    return data["diensten"], vers


def diensten_opslaan(kanaal, diensten):
    _schrijf_atomisch(
        _diensten_pad(kanaal),
        {"opgehaald": datetime.now().isoformat(timespec="seconds"),
         "kanaal": kanaal, "diensten": diensten},
    )


def zoek_dienst_titel(video_id):
    """Zoek de titel van een dienst in alle gecachete kanaallijsten."""
    if not os.path.isdir(_DIENSTEN_DIR):
        return None
    for naam in os.listdir(_DIENSTEN_DIR):
        data = _lees(os.path.join(_DIENSTEN_DIR, naam))
        for d in (data or {}).get("diensten", []):
            if d.get("id") == video_id:
                return d.get("titel")
    return None


# ---- Preekresultaten -----------------------------------------------------

def _veilig(video_id):
    return re.sub(r"[^A-Za-z0-9_-]", "_", video_id)[:64]


def _resultaat_pad(video_id):
    return os.path.join(_RESULT_DIR, _veilig(video_id) + ".json")


def resultaat_ophalen(video_id):
    return _lees(_resultaat_pad(video_id))


def resultaat_opslaan(video_id, payload):
    _schrijf_atomisch(_resultaat_pad(video_id), payload)
