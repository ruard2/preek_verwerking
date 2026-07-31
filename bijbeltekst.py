"""Exacte Bijbeltekst opzoeken uit de lokale, geconsolideerde vertaaldata.

De LLM levert voor deze vertalingen alleen de verwijzing (boek hoofdstuk:vers);
hier vullen we de exacte verstekst aan uit data/bijbel/<code>.json. Zo komt er
nooit een verzonnen ('gehallucineerd') vers in het weekboekje.

LET OP — auteursrecht: NBV21/HSV/BGT (© Nederlands-Vlaams Bijbelgenootschap) en
AFR-1953 (© Bybelgenootskap van Suid-Afrika) zijn beschermd. Deze data hoort
alleen in productie met een geldige licentie. Zonder licentie: zet de kerk op
'alleen verwijzing' of op een publiek-domein/vrije vertaling.
"""

import json
import os
import re
import unicodedata

_DIR = os.path.join(os.path.dirname(__file__), "data", "bijbel")

# Vertalingen waarvoor we lokale, exacte verstekst hebben (rest: model levert tekst).
LOKALE_VERTALINGEN = {"nbv21", "hsv", "bgt", "afr1953"}
_ATTRIB = {"nbv21": "NBV21", "hsv": "HSV", "bgt": "BGT", "afr1953": "1953"}

_cache = {}  # code -> {"JHN.3.16": tekst}


def _laad(code):
    if code not in _cache:
        pad = os.path.join(_DIR, f"{code}.json")
        try:
            with open(pad, encoding="utf-8") as f:
                _cache[code] = json.load(f)
        except (OSError, ValueError):
            _cache[code] = {}
    return _cache[code]


# --- Boeknaam -> Paratext-code (Nederlands, Afrikaans, Engels + afkortingen) ---
_BOEKEN = {
    "GEN": ["genesis", "gen"],
    "EXO": ["exodus", "eksodus", "ex", "exo"],
    "LEV": ["leviticus", "lev"],
    "NUM": ["numeri", "numbers", "num"],
    "DEU": ["deuteronomium", "deuteronomy", "deut", "deu"],
    "JOS": ["jozua", "josua", "joshua", "joz", "jos"],
    "JDG": ["richteren", "rechters", "rigters", "judges", "recht", "ric"],
    "RUT": ["ruth", "rut"],
    "1SA": ["1samuel", "1samuel", "1sam", "1sa"],
    "2SA": ["2samuel", "2sam", "2sa"],
    "1KI": ["1koningen", "1konings", "1kings", "1kon", "1ki"],
    "2KI": ["2koningen", "2konings", "2kings", "2kon", "2ki"],
    "1CH": ["1kronieken", "1kronieke", "1chronicles", "1kron", "1kr", "1ch"],
    "2CH": ["2kronieken", "2kronieke", "2chronicles", "2kron", "2kr", "2ch"],
    "EZR": ["ezra", "esra", "ezr"],
    "NEH": ["nehemia", "nehemiah", "neh"],
    "EST": ["ester", "esther", "est"],
    "JOB": ["job"],
    "PSA": ["psalm", "psalmen", "psalms", "ps", "psa"],
    "PRO": ["spreuken", "spreuke", "proverbs", "spr", "pro"],
    "ECC": ["prediker", "ecclesiastes", "pred", "ecc"],
    "SNG": ["hooglied", "hoogl", "song", "songofsongs", "sng", "hoo"],
    "ISA": ["jesaja", "isaiah", "jes", "isa"],
    "JER": ["jeremia", "jeremiah", "jer"],
    "LAM": ["klaagliederen", "klaagliedere", "lamentations", "klaagl", "kla", "lam"],
    "EZK": ["ezechiel", "esegiel", "ezekiel", "ezech", "eze", "ezk"],
    "DAN": ["daniel", "dan"],
    "HOS": ["hosea", "hos"],
    "JOL": ["joel", "joël", "jol", "joe"],
    "AMO": ["amos", "amo"],
    "OBA": ["obadja", "obadiah", "ob", "oba"],
    "JON": ["jona", "jonah", "jon"],
    "MIC": ["micha", "miga", "micah", "mic"],
    "NAM": ["nahum", "nam", "nah"],
    "HAB": ["habakuk", "habakkuk", "hab"],
    "ZEP": ["sefanja", "zephaniah", "zef", "sef", "zep"],
    "HAG": ["haggai", "haggaï", "hag"],
    "ZEC": ["zacharia", "sagaria", "zechariah", "zach", "zac", "zec"],
    "MAL": ["maleachi", "maleagi", "malachi", "mal"],
    "MAT": ["mateus", "matteus", "mattheus", "matthew", "mat", "mt"],
    "MRK": ["marcus", "markus", "mark", "mar", "mrk", "mk"],
    "LUK": ["lucas", "lukas", "luke", "luk", "luc", "lk"],
    "JHN": ["johannes", "john", "joh", "jhn", "jn"],
    "ACT": ["handelingen", "handelinge", "acts", "hand", "act", "hd"],
    "ROM": ["romeinen", "romeine", "romans", "rom"],
    "1CO": ["1korintiers", "1korinthiers", "1corinthians", "1kor", "1co"],
    "2CO": ["2korintiers", "2korinthiers", "2corinthians", "2kor", "2co"],
    "GAL": ["galaten", "galasiers", "galatians", "gal"],
    "EPH": ["efeziers", "efesiers", "ephesians", "ef", "efe", "eph"],
    "PHP": ["filippenzen", "filippense", "philippians", "fil", "flp", "php"],
    "COL": ["colossenzen", "kolossenzen", "kolossense", "colossians", "kol", "col"],
    "1TH": ["1tessalonicenzen", "1thessalonicenzen", "1thessalonisense",
            "1thessalonians", "1tess", "1tes", "1th"],
    "2TH": ["2tessalonicenzen", "2thessalonicenzen", "2thessalonians", "2tess", "2tes", "2th"],
    "1TI": ["1timoteus", "1timotheus", "1timothy", "1tim", "1ti"],
    "2TI": ["2timoteus", "2timotheus", "2timothy", "2tim", "2ti"],
    "TIT": ["titus", "tit"],
    "PHM": ["filemon", "philemon", "filem", "phm"],
    "HEB": ["hebreeen", "hebreers", "hebrews", "heb"],
    "JAS": ["jakobus", "jacobus", "james", "jak", "jas"],
    "1PE": ["1petrus", "1peter", "1pet", "1pe"],
    "2PE": ["2petrus", "2peter", "2pet", "2pe"],
    "1JN": ["1johannes", "1john", "1joh", "1jn", "1jo"],
    "2JN": ["2johannes", "2john", "2joh", "2jn", "2jo"],
    "3JN": ["3johannes", "3john", "3joh", "3jn", "3jo"],
    "JUD": ["judas", "jude", "jud"],
    "REV": ["openbaring", "revelation", "openb", "ope", "op", "rev"],
}


def _normaliseer(s):
    """lower, diacrieten weg, punten weg, Romeinse/woord-telwoorden -> cijfer, spaties weg."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", " ").strip()
    for woord, cijfer in (("eerste", "1"), ("tweede", "2"), ("derde", "3"),
                          ("iii ", "3 "), ("ii ", "2 "), ("i ", "1 ")):
        if s.startswith(woord):
            s = cijfer + " " + s[len(woord):].strip()
            break
    return re.sub(r"\s+", "", s)


_NAAM_NAAR_CODE = {}
for _code, _namen in _BOEKEN.items():
    for _n in _namen:
        _NAAM_NAAR_CODE[_normaliseer(_n)] = _code


_REF = re.compile(r"^(.*?)(\d+)\s*[:\.]\s*(\d+)")


def parse_verwijzing(verwijzing):
    """Geef (code, hoofdstuk, vers) uit 'Johannes 3:16' / '1 Kor 13:4-7'. Anders None."""
    m = _REF.match(verwijzing or "")
    if not m:
        return None
    boekdeel, hfd, vers = m.group(1), m.group(2), m.group(3)
    code = _NAAM_NAAR_CODE.get(_normaliseer(boekdeel))
    if not code:
        return None
    return code, int(hfd), int(vers)


def haal_vers(vertaling, verwijzing):
    """Geef de exacte verstekst voor deze vertaling + verwijzing, of None."""
    if vertaling not in LOKALE_VERTALINGEN:
        return None
    ontleed = parse_verwijzing(verwijzing)
    if not ontleed:
        return None
    code, hfd, vers = ontleed
    return _laad(vertaling).get(f"{code}.{hfd}.{vers}")


def verrijk_dag(dag, vertaling, citaat_volledig=True):
    """Vervang in één dag-dict de verwijzing door 'verwijzing — “exacte tekst” (bron)'.

    Alleen bij een lokale vertaling én volledige weergave. Lukt de lookup niet
    (onbekend boek/vers), dan blijft de verwijzing ongewijzigd staan.
    """
    if not citaat_volledig or vertaling not in LOKALE_VERTALINGEN:
        return
    ref = (dag.get("bijbeltekst") or "").strip()
    if not ref:
        return
    tekst = haal_vers(vertaling, ref)
    if tekst:
        dag["bijbeltekst"] = f"{ref} — “{tekst}” ({_ATTRIB[vertaling]})"


def verrijk_dagen(data, opties):
    """Verrijk alle dagen van een resultaat-dict met exacte verstekst."""
    if not isinstance(data, dict) or not isinstance(opties, dict):
        return data
    vertaling = opties.get("vertaling")
    citaat_volledig = opties.get("citaat_volledig", True)
    if vertaling not in LOKALE_VERTALINGEN:
        return data
    for dag in data.get("dagen") or []:
        if isinstance(dag, dict):
            verrijk_dag(dag, vertaling, citaat_volledig)
    return data
