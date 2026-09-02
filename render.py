"""Een gestructureerde preekverwerking (dict) omzetten naar weergave en PDF.

De inhoud (titel, samenvatting, dagen, vragen) komt in de taal van de preek
van het taalmodel. De vaste kopjes (Samenvatting, Dag, Bijbeltekst, ...) zetten
we hier in dezelfde taal, met Engels als terugval voor onbekende talen.
"""

import io
import re

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    HRFlowable,
    KeepTogether,
)
from xml.sax.saxutils import escape

LABELS = {
    "nl": {
        "bijbelgedeelte": "Bijbelgedeelte",
        "voorganger": "Voorganger",
        "samenvatting": "Samenvatting",
        "dag": "Dag",
        "bijbeltekst": "Bijbeltekst",
        "gedachte": "Gedachte",
        "vraag": "Vraag",
        "vraag_kinderen": "Vraag voor kinderen",
        "week": "Weekboekje bij de preek",
        "liturgie": "Liturgie",
        "preek": "Preek",
        "nabespreking": "Vragen voor nabespreking",
        "hoofd": "Hoofd — begrijpen en doordenken",
        "hart": "Hart — persoonlijk en innerlijk",
        "handen": "Handen — doen en leven",
        "transcript": "Preektranscript",
    },
    "en": {
        "bijbelgedeelte": "Scripture",
        "voorganger": "Preacher",
        "samenvatting": "Summary",
        "dag": "Day",
        "bijbeltekst": "Bible text",
        "gedachte": "Reflection",
        "vraag": "Question",
        "vraag_kinderen": "Question for children",
        "week": "Weekly devotional",
        "liturgie": "Order of service",
        "preek": "Sermon",
        "nabespreking": "Questions for discussion",
        "hoofd": "Head — understand and reflect",
        "hart": "Heart — personal and inward",
        "handen": "Hands — living it out",
        "transcript": "Sermon transcript",
    },
    "af": {
        "bijbelgedeelte": "Skrifgedeelte",
        "voorganger": "Voorganger",
        "samenvatting": "Opsomming",
        "dag": "Dag",
        "bijbeltekst": "Bybelteks",
        "gedachte": "Oordenking",
        "vraag": "Vraag",
        "vraag_kinderen": "Vraag vir kinders",
        "week": "Weeklikse oordenking",
        "liturgie": "Liturgie",
        "preek": "Preek",
        "nabespreking": "Vrae vir nabespreking",
        "hoofd": "Kop — verstaan en deurdink",
        "hart": "Hart — persoonlik en innerlik",
        "handen": "Hande — doen en leef",
        "transcript": "Preektranskripsie",
    },
}


UITVOER_TYPEN = ("dagstukjes", "preeksamenvatting", "preektranscript", "nabespreking")


def gekozen_typen(data):
    """Welke uitvoer(en) dit resultaat bevat; terugval op dagstukjes (oud gedrag)."""
    typen = data.get("uitvoer_typen")
    if isinstance(typen, list) and typen:
        return [t for t in typen if t in UITVOER_TYPEN] or ["dagstukjes"]
    return ["dagstukjes"]


def labels(taal):
    return LABELS.get((taal or "nl").split("-")[0].lower(), LABELS["en"])


def pas_bewerking_toe(data, velden):
    """Werk de bewerkbare velden bij vanuit een {veld: waarde, dagen:[...]}-dict."""
    for k in ("titel", "bijbelgedeelte", "voorganger", "samenvatting", "liturgie"):
        if velden.get(k) is not None:
            data[k] = velden[k]
    if isinstance(velden.get("dagen"), list):
        dagen = data.get("dagen") or []
        for i, d in enumerate(velden["dagen"]):
            if i < len(dagen) and isinstance(d, dict):
                for kk in ("titel", "bijbeltekst", "gedachte",
                           "vraag_volwassenen", "vraag_kinderen"):
                    if d.get(kk) is not None:
                        dagen[i][kk] = d[kk]
        data["dagen"] = dagen
    if velden.get("preektranscript") is not None:
        data["preektranscript"] = velden["preektranscript"]
    if isinstance(velden.get("nabespreking"), dict):
        nb = data.get("nabespreking") or {}
        for cat in ("hoofd", "hart", "handen"):
            if isinstance(velden["nabespreking"].get(cat), list):
                nb[cat] = [str(v).strip() for v in velden["nabespreking"][cat] if str(v).strip()]
        data["nabespreking"] = nb
    return data


def naar_tekst(data):
    """Platte, kopieerbare tekstversie (voor de kopieerknop / terugval).

    Toont alleen de door de kerk gekozen uitvoer(en): dagstukjes, samenvatting,
    nabespreking en/of preektranscript.
    """
    L = labels(data.get("taal"))
    typen = gekozen_typen(data)
    r = [data.get("titel", ""), ""]
    if data.get("bijbelgedeelte"):
        r.append(f"{L['bijbelgedeelte']}: {data['bijbelgedeelte']}")
    if data.get("voorganger"):
        r.append(f"{L['voorganger']}: {data['voorganger']}")
    if ("dagstukjes" in typen or "preeksamenvatting" in typen) and data.get("samenvatting"):
        r += ["", L["samenvatting"], data.get("samenvatting", "")]
    if "dagstukjes" in typen:
        r.append("")
        for i, dag in enumerate(data.get("dagen", []), 1):
            r.append(f"{L['dag']} {i} – {dag.get('titel', '')}")
            r.append(L["bijbeltekst"])
            r.append(dag.get("bijbeltekst", ""))
            r.append(L["gedachte"])
            r.append(dag.get("gedachte", ""))
            r.append(L["vraag"])
            r.append(dag.get("vraag_volwassenen", ""))
            r.append(L["vraag_kinderen"])
            r.append(dag.get("vraag_kinderen", ""))
            r.append("")
    if "nabespreking" in typen and data.get("nabespreking"):
        r += ["", L["nabespreking"], ""]
        for cat in ("hoofd", "hart", "handen"):
            vragen = (data["nabespreking"] or {}).get(cat) or []
            if vragen:
                r.append(L[cat])
                for v in vragen:
                    r.append(f"- {v}")
                r.append("")
    if "preektranscript" in typen and data.get("preektranscript"):
        r += ["", L["transcript"], "", data["preektranscript"]]
    if data.get("liturgie"):
        r += ["", L["liturgie"], data["liturgie"]]
    return "\n".join(r).strip()


def _stijlen():
    basis = getSampleStyleSheet()
    groen = colors.HexColor("#2c5f2d")
    return {
        "titel": ParagraphStyle(
            "Titel", parent=basis["Title"], fontSize=22, leading=26,
            textColor=groen, spaceAfter=6,
        ),
        "onder": ParagraphStyle(
            "Onder", parent=basis["Normal"], fontSize=10.5, leading=14,
            textColor=colors.HexColor("#555555"), alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "kop": ParagraphStyle(
            "Kop", parent=basis["Heading2"], fontSize=14, leading=17,
            textColor=groen, spaceBefore=14, spaceAfter=4,
        ),
        "label": ParagraphStyle(
            "Label", parent=basis["Normal"], fontSize=9, leading=11,
            textColor=groen, spaceBefore=6, spaceAfter=1,
            fontName="Helvetica-Bold",
        ),
        "tekst": ParagraphStyle(
            "Tekst", parent=basis["Normal"], fontSize=10.5, leading=15,
            spaceAfter=2,
        ),
        "citaat": ParagraphStyle(
            "Citaat", parent=basis["Normal"], fontSize=10.5, leading=15,
            leftIndent=10, textColor=colors.HexColor("#333333"),
            fontName="Helvetica-Oblique", spaceAfter=2,
        ),
    }


def _p(tekst, stijl):
    return Paragraph(escape(str(tekst or "")).replace("\n", "<br/>"), stijl)


def naar_pdf(data, ondertitel=None):
    """Bouw een nette PDF en geef de bytes terug."""
    L = labels(data.get("taal"))
    s = _stijlen()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=data.get("titel", L["week"]),
    )
    flow = [_p(data.get("titel", ""), s["titel"])]

    onder = []
    if data.get("bijbelgedeelte"):
        onder.append(f"{L['bijbelgedeelte']}: {data['bijbelgedeelte']}")
    if data.get("voorganger"):
        onder.append(f"{L['voorganger']}: {data['voorganger']}")
    if ondertitel:
        onder.append(ondertitel)
    for regel in onder:
        flow.append(_p(regel, s["onder"]))

    flow.append(Spacer(1, 6))
    flow.append(HRFlowable(width="100%", thickness=1.2,
                           color=colors.HexColor("#2c5f2d")))
    typen = gekozen_typen(data)
    if ("dagstukjes" in typen or "preeksamenvatting" in typen) and data.get("samenvatting"):
        flow.append(_p(L["samenvatting"], s["kop"]))
        flow.append(_p(data.get("samenvatting", ""), s["tekst"]))

    if "dagstukjes" in typen:
        for i, dag in enumerate(data.get("dagen", []), 1):
            blok = [
                _p(f"{L['dag']} {i} – {dag.get('titel', '')}", s["kop"]),
                _p(L["bijbeltekst"], s["label"]),
                _p(dag.get("bijbeltekst", ""), s["citaat"]),
                _p(L["gedachte"], s["label"]),
                _p(dag.get("gedachte", ""), s["tekst"]),
                _p(L["vraag"], s["label"]),
                _p(dag.get("vraag_volwassenen", ""), s["tekst"]),
                _p(L["vraag_kinderen"], s["label"]),
                _p(dag.get("vraag_kinderen", ""), s["tekst"]),
            ]
            # Houd een daggedeelte zoveel mogelijk bij elkaar op één pagina.
            flow.append(KeepTogether(blok))

    if "nabespreking" in typen and data.get("nabespreking"):
        flow.append(_p(L["nabespreking"], s["kop"]))
        for cat in ("hoofd", "hart", "handen"):
            vragen = (data["nabespreking"] or {}).get(cat) or []
            if not vragen:
                continue
            flow.append(_p(L[cat], s["label"]))
            for v in vragen:
                flow.append(_p(f"• {v}", s["tekst"]))

    if "preektranscript" in typen and data.get("preektranscript"):
        flow.append(_p(L["transcript"], s["kop"]))
        for a in re.split(r"\n\s*\n", data["preektranscript"]):
            if a.strip():
                flow.append(_p(a.strip(), s["tekst"]))

    if data.get("liturgie"):
        flow.append(_p(L["liturgie"], s["kop"]))
        flow.append(_p(data["liturgie"], s["tekst"]))

    doc.build(flow)
    return buf.getvalue()


def preek_naar_tekst(data, preek_tekst, ondertitel=None):
    """Platte tekstversie van de volledige (opgeschoonde) preek."""
    L = labels(data.get("taal"))
    r = [data.get("titel", ""), ""]
    if data.get("bijbelgedeelte"):
        r.append(f"{L['bijbelgedeelte']}: {data['bijbelgedeelte']}")
    if data.get("voorganger"):
        r.append(f"{L['voorganger']}: {data['voorganger']}")
    if ondertitel:
        r.append(ondertitel)
    r += ["", (preek_tekst or "").strip()]
    return "\n".join(r).strip()


def naar_preek_pdf(data, preek_tekst, ondertitel=None):
    """PDF van de volledige (opgeschoonde) preek: kop + lopende alinea's."""
    L = labels(data.get("taal"))
    s = _stijlen()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"{data.get('titel', L['preek'])} – {L['preek']}",
    )
    flow = [_p(data.get("titel", ""), s["titel"])]
    onder = []
    if data.get("bijbelgedeelte"):
        onder.append(f"{L['bijbelgedeelte']}: {data['bijbelgedeelte']}")
    if data.get("voorganger"):
        onder.append(f"{L['voorganger']}: {data['voorganger']}")
    if ondertitel:
        onder.append(ondertitel)
    for regel in onder:
        flow.append(_p(regel, s["onder"]))
    flow.append(Spacer(1, 6))
    flow.append(HRFlowable(width="100%", thickness=1.2,
                           color=colors.HexColor("#2c5f2d")))
    flow.append(Spacer(1, 6))
    # Elke alinea (gescheiden door lege regels) als eigen paragraaf.
    alineas = [a.strip() for a in re.split(r"\n\s*\n", preek_tekst or "") if a.strip()]
    for a in alineas:
        flow.append(_p(a, s["tekst"]))
    doc.build(flow)
    return buf.getvalue()


GROEPSLABELS = {
    "terughalen": "Terughalen",
    "verdiepen": "Verdiepen",
    "landen": "Laten landen",
    "handen": "Handen en voeten",
}


def groepsvragen_naar_pdf(data, ondertitel=None):
    """PDF met gespreksvragen voor groepen (per categorie genummerd)."""
    L = labels(data.get("taal"))
    s = _stijlen()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title=f"{data.get('titel', '')} - gespreksvragen",
    )
    flow = [_p(data.get("titel", ""), s["titel"])]
    gv = data.get("groepsvragen") or {}
    onder = []
    if data.get("bijbelgedeelte"):
        onder.append(f"{L['bijbelgedeelte']}: {data['bijbelgedeelte']}")
    if data.get("voorganger"):
        onder.append(f"{L['voorganger']}: {data['voorganger']}")
    if gv.get("leeftijd"):
        onder.append(f"Leeftijd: {gv['leeftijd']}")
    if ondertitel:
        onder.append(ondertitel)
    for regel in onder:
        flow.append(_p(regel, s["onder"]))
    flow.append(Spacer(1, 6))
    flow.append(HRFlowable(width="100%", thickness=1.2,
                           color=colors.HexColor("#2c5f2d")))
    for cat, lijst in (gv.get("vragen") or {}).items():
        if not lijst:
            continue
        flow.append(_p(GROEPSLABELS.get(cat, cat), s["kop"]))
        for i, v in enumerate(lijst, 1):
            flow.append(_p(f"{i}. {v}", s["tekst"]))
    doc.build(flow)
    return buf.getvalue()
