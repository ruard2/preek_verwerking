"""Een gestructureerde preekverwerking (dict) omzetten naar weergave en PDF.

De inhoud (titel, samenvatting, dagen, vragen) komt in de taal van de preek
van het taalmodel. De vaste kopjes (Samenvatting, Dag, Bijbeltekst, ...) zetten
we hier in dezelfde taal, met Engels als terugval voor onbekende talen.
"""

import io

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
    },
}


def labels(taal):
    return LABELS.get((taal or "nl").split("-")[0].lower(), LABELS["en"])


def naar_tekst(data):
    """Platte, kopieerbare tekstversie (voor de kopieerknop / terugval)."""
    L = labels(data.get("taal"))
    r = [data.get("titel", ""), ""]
    if data.get("bijbelgedeelte"):
        r.append(f"{L['bijbelgedeelte']}: {data['bijbelgedeelte']}")
    if data.get("voorganger"):
        r.append(f"{L['voorganger']}: {data['voorganger']}")
    r += ["", L["samenvatting"], data.get("samenvatting", ""), ""]
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
    flow.append(_p(L["samenvatting"], s["kop"]))
    flow.append(_p(data.get("samenvatting", ""), s["tekst"]))

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

    if data.get("liturgie"):
        flow.append(_p(L["liturgie"], s["kop"]))
        flow.append(_p(data["liturgie"], s["tekst"]))

    doc.build(flow)
    return buf.getvalue()
