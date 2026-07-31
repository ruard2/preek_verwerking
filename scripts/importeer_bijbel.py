"""Consolideer gescrapete Bijbel-JSON (per hoofdstuk) tot compacte lookup-bestanden.

Leest mappen als bijbel_nbv21/ (bestanden BOOK_NNN.json met {book, chapter,
verses:[{verse, text}]}) en schrijft per vertaling één minified JSON:
    data/bijbel/<code>.json  →  {"JHN.3.16": "Want God had de wereld zo lief ...", ...}

Alleen bestanden met een canonieke Paratext-boekcode én verzen in objectvorm
worden meegenomen; de vervuilde varianten (Dutch-coded, *_full, complete_bible)
worden overgeslagen. Verssplitsingen (zelfde versnummer, meerdere fragmenten)
worden samengevoegd.

LET OP: NBV21/HSV/BGT (© NVB Bijbelgenootschap) en AFR-1953 (© Bybelgenootskap
van SA) zijn auteursrechtelijk beschermd. Alleen gebruiken met licentie.
"""

import json
import os
import sys

CANON = {
    "GEN", "EXO", "LEV", "NUM", "DEU", "JOS", "JDG", "RUT", "1SA", "2SA",
    "1KI", "2KI", "1CH", "2CH", "EZR", "NEH", "EST", "JOB", "PSA", "PRO",
    "ECC", "SNG", "ISA", "JER", "LAM", "EZK", "DAN", "HOS", "JOL", "AMO",
    "OBA", "JON", "MIC", "NAM", "HAB", "ZEP", "HAG", "ZEC", "MAL", "MAT",
    "MRK", "LUK", "JHN", "ACT", "ROM", "1CO", "2CO", "GAL", "EPH", "PHP",
    "COL", "1TH", "2TH", "1TI", "2TI", "TIT", "PHM", "HEB", "JAS", "1PE",
    "2PE", "1JN", "2JN", "3JN", "JUD", "REV",
}


def _laad_map(map_pad):
    """Geef {"BOOK.C.V": text} voor één vertaalmap; sla vervuilde bestanden over."""
    verzen = {}
    boeken = set()
    for naam in sorted(os.listdir(map_pad)):
        if not naam.endswith(".json"):
            continue
        if naam.endswith("_full.json") or naam == "complete_bible.json":
            continue
        pad = os.path.join(map_pad, naam)
        try:
            with open(pad, encoding="utf-8") as f:
                doc = json.load(f)
        except (ValueError, OSError):
            continue
        if not isinstance(doc, dict):
            continue
        boek = doc.get("book")
        hfd = doc.get("chapter")
        rijen = doc.get("verses")
        if boek not in CANON or not isinstance(hfd, int) or not isinstance(rijen, list):
            continue
        # Verzen samenvoegen: opeenvolgende fragmenten met hetzelfde nummer aan elkaar.
        per_vers = {}
        volgorde = []
        schoon = True
        for r in rijen:
            if not isinstance(r, dict) or "verse" not in r or "text" not in r:
                schoon = False
                break
            try:
                vnr = int(r["verse"])
            except (TypeError, ValueError):
                schoon = False
                break
            tekst = (r["text"] or "").strip()
            if vnr in per_vers:
                per_vers[vnr] = (per_vers[vnr] + " " + tekst).strip()
            else:
                per_vers[vnr] = tekst
                volgorde.append(vnr)
        if not schoon:
            continue
        boeken.add(boek)
        for vnr in volgorde:
            if per_vers[vnr]:
                verzen[f"{boek}.{hfd}.{vnr}"] = per_vers[vnr]
    return verzen, boeken


def main():
    bron = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Ruard"
    uit = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bijbel")
    os.makedirs(uit, exist_ok=True)
    mappen = {
        "nbv21": "bijbel_nbv21",
        "hsv": "bijbel_hsv",
        "bgt": "bijbel_BGT",
        "afr1953": "bijbel_AFR53",
    }
    for code, mapnaam in mappen.items():
        map_pad = os.path.join(bron, mapnaam)
        if not os.path.isdir(map_pad):
            print(f"[!] {code}: map niet gevonden ({map_pad}) — overgeslagen")
            continue
        verzen, boeken = _laad_map(map_pad)
        doel = os.path.join(uit, f"{code}.json")
        with open(doel, "w", encoding="utf-8") as f:
            json.dump(verzen, f, ensure_ascii=False, separators=(",", ":"))
        kb = os.path.getsize(doel) // 1024
        print(f"[ok] {code}: {len(verzen)} verzen, {len(boeken)}/66 boeken, {kb} kB -> {doel}")


if __name__ == "__main__":
    main()
