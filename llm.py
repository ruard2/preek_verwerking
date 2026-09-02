"""Verwerking van het preektranscript via de OpenAI API."""

import json
import os

from openai import OpenAI

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")
SCHOON_MODEL = os.environ.get("OPENAI_SCHOON_MODEL", MODEL)

SCHOON_PROMPT = """\
Je krijgt een ruw, automatisch gegenereerd transcript van één christelijke preek
en maakt daarvan een betrouwbare, goed leesbare versie van de VOLLEDIGE preek.

Regels:
* Behoud alle inhoud, boodschap, argumentatie en voorbeelden van de spreker.
* Vat NIET samen en kort NIET in — dit is de hele preek, alleen opgeschoond.
* Verander de theologische strekking niet en voeg niets toe (geen nieuwe ideeën,
  voorbeelden of conclusies).
* Verwijder tijdcodes, herhalingen, stopwoorden en versprekingen.
* Maak kromme of onafgemaakte zinnen grammaticaal correct; zet spreektaal om in
  natuurlijk, goedlopend geschreven Nederlands (of de taal van de preek).
* Deel de tekst in logische alinea's in.
* Herstel duidelijke transcriptiefouten en corrigeer namen van Bijbelboeken en
  Bijbelse personen. Maak onzekere details niet stilzwijgend zeker.
* Als de preek uit meerdere delen bestaat (gemarkeerd met [VOLGEND PREEKDEEL]),
  voeg die samen tot één doorlopende tekst; laat de markering zelf weg.

Uitvoer: ALLEEN de opgeschoonde preektekst als lopende alinea's. Geen titel,
geen kopjes, geen samenvatting, geen commentaar, geen opsomming — puur de preek.
Schrijf in dezelfde taal als de preek.
"""

SYSTEEM_PROMPT = """\
API-opdracht: preektranscript verwerken

Je ontvangt een ruwe, automatisch gegenereerde transcriptie van een christelijke preek. De transcriptie kan spreektaal, herhalingen, onafgemaakte zinnen, tijdcodes, fouten in namen en Bijbelverwijzingen en verkeerd herkende woorden bevatten.

Verwerk de aangeleverde tekst in twee stappen.

Stap 1 – Transcript opschonen
Maak eerst intern een betrouwbare, goed leesbare versie van het transcript.
Houd je daarbij aan de volgende regels:

* Behoud de inhoud, boodschap, argumentatie en voorbeelden van de spreker.
* Verander de theologische strekking niet.
* Verwijder tijdcodes.
* Verwijder onnodige herhalingen, stopwoorden en versprekingen.
* Maak onafgemaakte of kromme zinnen grammaticaal correct.
* Zet spreektaal om in natuurlijk, goedlopend Nederlands.
* Deel lange tekstblokken logisch in.
* Herstel duidelijke transcriptiefouten.
* Corrigeer namen van Bijbelboeken en Bijbelse personen.
* Controleer of genoemde Bijbelteksten en verwijzingen logisch kloppen met de context.
* Voeg geen nieuwe theologische ideeën, voorbeelden of conclusies toe.
* Maak onzekerheden niet stilzwijgend zeker. Laat twijfelachtige details liever algemeen weg of formuleer voorzichtig.
* Schrijf de opgeschoonde transcriptie niet volledig uit in het eindresultaat, tenzij daar afzonderlijk om wordt gevraagd. Gebruik deze versie als basis voor de verdere verwerking.

Stap 2 – Preekverwerking maken
Maak op basis van het opgeschoonde transcript de volgende onderdelen:

1. Een titel
2. Het centrale Bijbelgedeelte
3. Een samenvatting
4. Zeven daggedeelten
5. Per dag:
   * een korte titel;
   * een passend Bijbelexcerpt;
   * een korte overdenking;
   * één reflectievraag voor volwassenen;
   * één eenvoudige vraag voor kinderen in de basisschoolleeftijd.

Algemene eisen

* Schrijf in helder, warm en toegankelijk taalgebruik, in de taal van de preek.
* Blijf dicht bij de inhoud en accenten van de preek.
* Maak de tekst geschikt voor gebruik door gemeenteleden thuis, alleen of als gezin.
* Vermijd kerkelijk jargon waar een eenvoudiger woord mogelijk is.
* Gebruik geen overdreven vrome, zoete of algemene formuleringen.
* Maak de toepassing concreet en persoonlijk.
* Vermijd dat de vragen voor volwassenen en kinderen inhoudelijk hetzelfde zijn.
* De vraag voor volwassenen mag confronterend en verdiepend zijn.
* De kindervraag moet begrijpelijk zijn voor kinderen van ongeveer 6 tot 12 jaar.
* De kindervraag moet uitnodigen tot een echt gesprek en niet alleen met ja of nee te beantwoorden zijn.
* Gebruik per dag één hoofdgedachte. Probeer niet de hele preek in ieder daggedeelte te herhalen.
* Zorg dat de zeven dagen samen de belangrijkste lijn van de preek volgen.
* Gebruik alleen Bijbelteksten die in de preek worden genoemd of duidelijk rechtstreeks aansluiten bij de boodschap.
* Voor het veld "bijbeltekst": volg exact de aparte instructie onderaan (volledig vers of alleen de verwijzing, en welke vertaling). Kies altijd hooguit ÉÉN vers.

Lengte

Samenvatting
Schrijf een samenvatting van ongeveer 150 tot 200 woorden.
De samenvatting moet:

* de centrale boodschap van de preek benoemen;
* de belangrijkste opbouw of gedachtegang weergeven;
* duidelijk maken wat de preek van de hoorder vraagt;
* waar passend eindigen bij Christus, het evangelie of Gods genade, wanneer dat ook de lijn van de preek is.

Daggedeelten
Maak precies zeven daggedeelten.
Iedere overdenking bestaat uit ongeveer 100 tot 160 woorden.
Een daggedeelte moet zelfstandig te begrijpen zijn, maar tegelijk onderdeel zijn van de doorgaande lijn van de week.

Uitvoer
Geef je antwoord UITSLUITEND als één geldig JSON-object, zonder enige tekst
eromheen, met exact deze velden:

{
  "taal": "<ISO-taalcode van de preek, bijvoorbeeld nl, af of en>",
  "titel": "<titel van de preekverwerking>",
  "bijbelgedeelte": "<centraal Bijbelgedeelte>",
  "voorganger": "<naam van de voorganger, of null als die onbekend of onzeker is>",
  "samenvatting": "<samenvatting van 150 tot 200 woorden>",
  "dagen": [
    {
      "titel": "<korte titel>",
      "bijbeltekst": "<precies één vers met verwijzing; NL=Statenvertaling, EN=KJV/WEB, AF=1933/1953-vertaling met (1953)>",
      "gedachte": "<overdenking van ongeveer 100 tot 160 woorden>",
      "vraag_volwassenen": "<één reflectievraag voor volwassenen>",
      "vraag_kinderen": "<één eenvoudige gespreksvraag voor kinderen>"
    }
  ]
}

De lijst "dagen" bevat precies zeven objecten (dag 1 tot en met dag 7), in
volgorde. Gebruik geen extra velden en laat geen veld weg; alleen "voorganger"
mag null zijn.

BELANGRIJK: de JSON-sleutels (veldnamen zoals "titel", "bijbeltekst",
"gedachte", "vraag_volwassenen", "vraag_kinderen", "samenvatting", "dagen")
blijven ALTIJD exact zoals hierboven, in het Nederlands. Vertaal de sleutels
NOOIT, ook niet als de inhoud in het Afrikaans, Engels of een andere taal is.
Alleen de waarden staan in de taal van de preek; de sleutels niet.

Inhoudelijke controle vóór uitvoer
Controleer vóór je het eindresultaat geeft:

* Is de centrale boodschap trouw aan de preek?
* Zijn transcriptiefouten niet overgenomen?
* Zijn de zeven dagen inhoudelijk verschillend?
* Volgen de dagen samen de lijn van de preek?
* Is ieder Bijbelexcerpt passend?
* Is iedere overdenking begrijpelijk zonder het oorspronkelijke transcript?
* Is er per dag precies één vraag voor volwassenen?
* Is er per dag precies één vraag voor kinderen?
* Zijn de kindervragen werkelijk geschikt voor de basisschoolleeftijd?
* Zijn toepassingen niet toegevoegd wanneer ze niet uit de preek voortkomen?
* Is de tekst gereed om zonder verdere bewerking in een app, gemeentemail of weekboekje te plaatsen?
"""

AANVULLENDE_INSTRUCTIES = """\

Aanvullende instructies

* De preek kan uit meerdere delen bestaan wanneer er tussendoor gezongen \
wordt; die delen zijn gemarkeerd met [VOLGEND PREEKDEEL — hiervoor werd \
gezongen]. Behandel alle delen samen als één doorlopende preek.
* In de preek kunnen korte interactieve momenten voorkomen waarin \
gemeenteleden antwoorden op een vraag van de voorganger; dat hoort bij de \
preek.
* Soms is een fragment van het welkomstwoord van het begin van de dienst \
bijgevoegd. Daarin wordt vaak de voorganger genoemd (bijvoorbeeld: "vanmorgen \
gaat dominee ... voor"). Als de naam van de voorganger daaruit of uit de \
preek blijkt, vul dan het veld "voorganger" met die naam. Is de naam niet te \
vinden of onzeker, zet "voorganger" dan op null; gok nooit een naam. Gebruik \
het welkomstfragment nergens anders voor.

Taal van de uitvoer
* Schrijf de VOLLEDIGE inhoud — titel, samenvatting, alle dagen en beide \
vragen — in de taal van de preek zelf. Is de preek in het Afrikaans, schrijf \
dan in het Afrikaans; is hij in het Engels, in het Engels; enzovoort. Vertaal \
de inhoud niet naar het Nederlands.
* Schrijf de bijbelboeknaam in de verwijzing in diezelfde taal (bijvoorbeeld \
Engels "Zechariah 4:6", Afrikaans "Sagaria 4:6"). De verstekst: Nederlands uit \
de Statenvertaling, Engels uit de KJV/World English Bible, Afrikaans uit de \
1933/1953-vertaling met "(1953)" erbij. Altijd precies één vers, nooit meer.
* Zet in het veld "taal" de ISO-code van die taal (nl, af, en, ...).
"""

GEBRUIKER_INLEIDING = """\
Hieronder staat de ruwe, automatisch gegenereerde transcriptie van de preek \
(afkomstig uit YouTube-ondertitels). Aan het begin en het einde kunnen nog \
restanten van de rest van de kerkdienst staan, zoals liederen, mededelingen \
of gebeden; laat die buiten beschouwing en verwerk alleen de preek zelf. \
Geef alleen het eindresultaat in de voorgeschreven structuur.
"""


VOLLEDIGE_DIENST_INSTRUCTIE = """\

LET OP: de onderstaande transcriptie is van een VOLLEDIGE kerkdienst, niet alleen
de preek. Bepaal zelf welk deel de preek is: dat is het lange, aaneengesloten
onderwijs van de voorganger waarin één Bijbelgedeelte wordt uitgelegd en toegepast
(vrijwel altijd het langste ononderbroken stuk spreken van één persoon). Baseer de
preekverwerking UITSLUITEND op dat preekgedeelte. Negeer al het overige volledig:
liederen en gezang, votum en groet, wetslezing, Schriftlezingen, gebeden,
mededelingen, collecte, geloofsbelijdenis, welkom en afsluiting. Neem geen inhoud
uit die onderdelen over in de samenvatting, de dagen of de vragen.
"""


# Auteursrechtelijk beschermde vertalingen: (volledige naam, bronvermelding).
_VERTALINGEN = {
    "nbv21": ("NBV21", "(NBV21)"),
    "hsv": ("Herziene Statenvertaling", "(HSV)"),
    "niv": ("New International Version", "(NIV)"),
    "esv": ("English Standard Version", "(ESV)"),
    "kjv": ("King James Version", "(KJV)"),
    "afr1953": ("Afrikaanse Bybelvertaling van 1953", "(1953)"),
}


# Vertalingen waarvoor de exacte tekst lokaal wordt opgezocht (bijbeltekst.py):
# het model geeft dan ALLEEN de verwijzing, wij vullen de verstekst aan.
_LOKALE_VERTALINGEN = {"nbv21", "hsv", "bgt", "afr1953"}


def _bijbel_instructie(citaat_volledig, vertaling):
    if not citaat_volledig:
        return (
            '\nBIJBELTEKST-INSTRUCTIE: zet in het veld "bijbeltekst" ALLEEN de '
            "verwijzing (bijbelboek hoofdstuk:vers), zónder de verstekst.\n"
        )
    if vertaling in _LOKALE_VERTALINGEN:
        return (
            '\nBIJBELTEKST-INSTRUCTIE: zet in het veld "bijbeltekst" ALLEEN de '
            "verwijzing (bijbelboek hoofdstuk:vers) van precies ÉÉN kernvers, in de "
            "taal van de overdenking. De exacte verstekst wordt automatisch "
            "toegevoegd; schrijf de verstekst dus NIET zelf.\n"
        )
    if vertaling in _VERTALINGEN:
        naam, kort = _VERTALINGEN[vertaling]
        return (
            f'\nBIJBELTEKST-INSTRUCTIE: zet in "bijbeltekst" precies ÉÉN vers met de '
            f"verwijzing, uit de {naam}, en zet {kort} als bronvermelding achter het "
            "vers. Nooit meer dan één vers.\n"
        )
    return (
        '\nBIJBELTEKST-INSTRUCTIE: zet in "bijbeltekst" precies ÉÉN vers met de '
        "verwijzing, uit een vrije (publiek-domein) vertaling — Nederlands = "
        "Statenvertaling, Engels = King James Version of World English Bible, "
        'Afrikaans = 1933/1953-vertaling met "(1953)". Nooit meer dan één vers.\n'
    )


_TONEN = {
    "warm": "warm, pastoraal en bemoedigend",
    "nuchter": "nuchter, bijbelgetrouw en verdiepend, zonder sentimentaliteit",
    "toegankelijk": "eigentijds, toegankelijk en concreet, met voorbeelden uit het dagelijks leven",
    "verdiepend": "theologisch verdiepend en rijk, maar begrijpelijk voor een brede gemeente",
}
_LENGTES = {
    "kort": "Houd elke overdenking beknopt: de gedachte is 2 tot 3 zinnen.",
    "middel": "Houd elke overdenking gemiddeld van lengte: de gedachte is 4 tot 6 zinnen.",
    "lang": "Maak elke overdenking uitgebreider: de gedachte is een volle alinea van 7 tot 10 zinnen.",
}


def _stijl_instructie(toon, lengte):
    t = _TONEN.get(toon or "warm", _TONEN["warm"])
    l = _LENGTES.get(lengte or "middel", _LENGTES["middel"])
    return f"\nSTIJL: schrijf de overdenkingen in een {t} toon. {l}\n"


def verwerk_preek(transcript, welkom=None, taal_hint=None, extra_context=None,
                  volledige_dienst=False, citaat_volledig=True, vertaling="vrij",
                  toon="warm", lengte="middel"):
    """Verwerk het transcript tot een gestructureerd resultaat (dict).

    Geeft een dict met de velden: taal, titel, bijbelgedeelte, voorganger,
    samenvatting, dagen[7]. Werpt een fout bij een ongeldig antwoord. Met
    volledige_dienst=True bevat de transcriptie de hele dienst. citaat_volledig
    en vertaling bepalen hoe het Bijbelvers wordt getoond.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is niet ingesteld. Voeg deze toe als "
            "omgevingsvariabele (in Railway: Variables)."
        )
    client = OpenAI()
    inhoud = GEBRUIKER_INLEIDING + _bijbel_instructie(citaat_volledig, vertaling)
    inhoud += _stijl_instructie(toon, lengte)
    if volledige_dienst:
        inhoud += VOLLEDIGE_DIENST_INSTRUCTIE
    if extra_context:
        inhoud += (
            "\nBekende gegevens uit de liturgie (betrouwbaar; neem deze over in "
            "de betreffende velden en verzin niets anders):\n" + extra_context + "\n"
        )
    if taal_hint:
        inhoud += (
            f"\nDe preek is (automatisch gedetecteerd) in de taal met code "
            f"'{taal_hint}'. Schrijf de volledige uitvoer in die taal.\n"
        )
    if welkom:
        inhoud += (
            "\n--- FRAGMENT WELKOMSTWOORD (alleen voor de naam van de "
            "voorganger) ---\n" + welkom + "\n"
        )
    kop = "VOLLEDIGE DIENST" if volledige_dienst else "PREEK"
    inhoud += f"\n--- TRANSCRIPTIE VAN DE {kop} ---\n" + transcript
    antwoord = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEEM_PROMPT + AANVULLENDE_INSTRUCTIES},
            {"role": "user", "content": inhoud},
        ],
    )
    ruw = antwoord.choices[0].message.content
    try:
        data = json.loads(ruw)
    except (json.JSONDecodeError, TypeError) as fout:
        raise RuntimeError(f"Ongeldig JSON-antwoord van het model: {fout}") from None
    return _valideer(data, taal_hint)


# Als het model bij een andere taal (bijv. Afrikaans) tóch de JSON-sleutels
# vertaalt, herstellen we ze hiermee. Per canonieke sleutel een lijst mogelijke
# vertalingen/varianten (Afrikaans, Engels, spelvarianten).
_DATA_SYNONIEMEN = {
    "titel": ["title", "tital"],
    "bijbelgedeelte": ["bybelgedeelte", "skrifgedeelte", "skriflesing",
                        "bible_passage", "scripture_passage", "passage", "gedeelte"],
    "samenvatting": ["samevatting", "opsomming", "summary"],
    "voorganger": ["predikant", "prediker", "dominee", "preacher"],
    "taal": ["language", "lang", "taalkode"],
    "dagen": ["dae", "days"],
}
_DAG_SYNONIEMEN = {
    "titel": ["title", "opskrif"],
    "bijbeltekst": ["bybelteks", "bibeltekst", "bible_text", "bibletext",
                    "scripture", "teks", "text", "vers", "verse"],
    "gedachte": ["gedagte", "oordenking", "overdenking", "besinning",
                 "bespreking", "meditation", "reflection", "thought"],
    "vraag_volwassenen": ["vraag_volwassenes", "vraag_volwasse",
                          "vraag_grootmense", "vraag_vir_volwassenes",
                          "adult_question", "question_adults"],
    "vraag_kinderen": ["vraag_kinders", "vraag_vir_kinders", "kindervraag",
                       "child_question", "children_question", "question_children"],
}


def _vul_synoniemen(d, synoniemen):
    if not isinstance(d, dict):
        return
    for canoniek, varianten in synoniemen.items():
        if not d.get(canoniek):
            for v in varianten:
                if d.get(v):
                    d[canoniek] = d[v]
                    break


def normaliseer(data):
    """Herstel eventueel vertaalde JSON-sleutels naar de canonieke namen.

    Idempotent, zodat we het ook op al opgeslagen (mogelijk kapotte) resultaten
    kunnen toepassen bij het inlezen.
    """
    if not isinstance(data, dict):
        return data
    _vul_synoniemen(data, _DATA_SYNONIEMEN)
    for dag in data.get("dagen") or []:
        _vul_synoniemen(dag, _DAG_SYNONIEMEN)
    return data


def schoon_transcript(transcript, taal_hint=None):
    """Herschrijf het ruwe transcript tot een opgeschoonde, leesbare volledige
    preek (lopende tekst). Aparte AI-stap; geen samenvatting."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")
    if not (transcript or "").strip():
        return ""
    client = OpenAI()
    inhoud = ""
    if taal_hint:
        inhoud += (
            f"De preek is in de taal met code '{taal_hint}'. Schrijf de "
            "opgeschoonde preek in díé taal.\n\n"
        )
    inhoud += "--- RUW TRANSCRIPT ---\n" + transcript
    antwoord = client.chat.completions.create(
        model=SCHOON_MODEL,
        messages=[
            {"role": "system", "content": SCHOON_PROMPT},
            {"role": "user", "content": inhoud},
        ],
    )
    return (antwoord.choices[0].message.content or "").strip()


def hergenereer_dag(data, dag_index, bron="", toon="warm", lengte="middel",
                    citaat_volledig=True, vertaling="vrij"):
    """Genereer één dag-overdenking opnieuw, passend bij het weekthema.

    `data` is het bestaande resultaat (titel/bijbelgedeelte/samenvatting/dagen);
    `dag_index` is 0-geïndexeerd; `bron` is (optioneel) de opgeschoonde preektekst.
    Geeft een nieuw dag-dict (titel, bijbeltekst, gedachte, vraag_volwassenen,
    vraag_kinderen). Werpt een fout bij een ongeldig antwoord.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")
    dagen = data.get("dagen") or []
    if not (0 <= dag_index < len(dagen)):
        raise ValueError("Ongeldige dag.")
    client = OpenAI()
    taal = data.get("taal") or "nl"
    context = [
        f"Titel van de week: {data.get('titel', '')}",
        f"Bijbelgedeelte: {data.get('bijbelgedeelte', '')}",
        f"Samenvatting van de preek: {data.get('samenvatting', '')}",
    ]
    andere = [
        f"Dag {i + 1}: {d.get('titel', '')}"
        for i, d in enumerate(dagen) if i != dag_index
    ]
    if andere:
        context.append("De andere dagen gaan al over:\n" + "\n".join(andere))
    inhoud = (
        f"Schrijf ÉÉN nieuwe dagelijkse overdenking (dag {dag_index + 1} van "
        f"{len(dagen)}) bij deze preek. Kies een invalshoek die de andere dagen "
        "aanvult en niet in herhaling valt.\n"
        + _bijbel_instructie(citaat_volledig, vertaling)
        + _stijl_instructie(toon, lengte)
        + f"\nSchrijf in de taal met code '{taal}'.\n"
        + "\n".join(context)
    )
    if bron:
        inhoud += "\n\n--- PREEKTEKST ---\n" + bron[:12000]
    inhoud += (
        '\n\nGeef UITSLUITEND JSON terug in de vorm: {"dag": {"titel": "...", '
        '"bijbeltekst": "...", "gedachte": "...", "vraag_volwassenen": "...", '
        '"vraag_kinderen": "..."}}'
    )
    antwoord = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEEM_PROMPT + AANVULLENDE_INSTRUCTIES},
            {"role": "user", "content": inhoud},
        ],
    )
    ruw = antwoord.choices[0].message.content
    try:
        obj = json.loads(ruw)
    except (json.JSONDecodeError, TypeError) as fout:
        raise RuntimeError(f"Ongeldig JSON-antwoord van het model: {fout}") from None
    dag = obj.get("dag") if isinstance(obj, dict) and isinstance(obj.get("dag"), dict) else obj
    if not isinstance(dag, dict):
        raise RuntimeError("Het model gaf geen bruikbare dag terug.")
    _vul_synoniemen(dag, _DAG_SYNONIEMEN)
    return dag


_NABESPREKING_PROMPT = """\
Je stelt vragen op voor de NABESPREKING van een preek, bedoeld voor een kring,
gesprekskring of gezin. Je ontvangt de geschreven (opgeschoonde) preek en het
Bijbelgedeelte. Maak op grond DAARVAN vragen die passen bij deze specifieke preek
en dit Bijbelgedeelte.

Doel: de boodschap laten LANDEN en VERDIEPEN — niet overhoren, niet de preek
herhalen, en geen feitenvragen ('wat zei de dominee over ...'). De vragen mogen
open, eerlijk en soms confronterend zijn, en nodigen uit tot echt gesprek.

Maak precies 15 vragen, verdeeld over drie categorieën (5 per categorie):

* "hoofd" — begrijpen en doordenken: wat betekent dit Bijbelgedeelte en deze
  boodschap, welke waarheid over God/mens/genade komt naar voren, welke vragen of
  spanningen roept het op om verder over na te denken.
* "hart" — persoonlijk en innerlijk: wat doet dit met je, waar raakt het je
  verlangen, angst, geloof of weerstand, hoe verhoudt het zich tot je relatie met
  God en met anderen.
* "handen" — doen en leven: hoe ziet dit er deze week concreet uit in je leven,
  keuzes, gewoonten en omgang met anderen; concreet en toepasbaar, geen clichés.

Eisen:
* Schrijf in dezelfde taal als de preek.
* Elke vraag staat op zichzelf en is één zin (soms twee), zonder nummering.
* Vermijd herhaling tussen de vragen en tussen de categorieën.
* Verwijs waar passend naar het Bijbelgedeelte, maar maak er geen quiz van.

Uitvoer: UITSLUITEND geldig JSON, exact deze vorm (sleutels in het Nederlands):
{"hoofd": ["...","...","...","...","..."],
 "hart": ["...","...","...","...","..."],
 "handen": ["...","...","...","...","..."]}
"""


_BASIS_PROMPT = """\
Je ontvangt een (ruwe) transcriptie van een christelijke preek. Maak eerst intern
een betrouwbare, opgeschoonde versie en lever daarna UITSLUITEND de kernonderdelen
hieronder — GEEN daggedeelten, overdenkingen of vragen.

Opschonen: behoud inhoud, boodschap, argumentatie en voorbeelden; verander de
theologische strekking niet; verwijder tijdcodes, herhalingen en versprekingen;
herstel namen van Bijbelboeken en personen; voeg niets toe; maak onzekerheden niet
stilzwijgend zeker.

Lever: (1) de taal, (2) een titel, (3) het centrale Bijbelgedeelte, (4) de
voorganger of null, (5) een samenvatting van 150–200 woorden die de centrale
boodschap, de opbouw/gedachtegang en wat de preek van de hoorder vraagt weergeeft.

Uitvoer UITSLUITEND als geldig JSON, met exact deze Nederlandse sleutels (vertaal
de sleutels nooit):
{"taal":"<ISO-code>","titel":"...","bijbelgedeelte":"...","voorganger":"... of null","samenvatting":"..."}
"""


def maak_basis(transcript, welkom=None, taal_hint=None, extra_context=None,
               volledige_dienst=False):
    """Lichte verwerking zonder daggedeelten: titel, bijbelgedeelte, samenvatting.

    Gebruikt wanneer de kerk géén dagstukjes wil (dan slaan we de dure 7-daagse
    generatie over). Geeft dezelfde basisvelden als verwerk_preek, met dagen=[].
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")
    client = OpenAI()
    inhoud = ""
    if volledige_dienst:
        inhoud += VOLLEDIGE_DIENST_INSTRUCTIE
    if extra_context:
        inhoud += (
            "\nBekende gegevens uit de liturgie (betrouwbaar; neem over, verzin "
            "niets anders):\n" + extra_context + "\n"
        )
    if taal_hint:
        inhoud += (
            f"\nDe preek is in de taal met code '{taal_hint}'. Schrijf de uitvoer "
            "in die taal.\n"
        )
    if welkom:
        inhoud += (
            "\n--- FRAGMENT WELKOMSTWOORD (alleen voor de naam van de "
            "voorganger) ---\n" + welkom + "\n"
        )
    kop = "VOLLEDIGE DIENST" if volledige_dienst else "PREEK"
    inhoud += f"\n--- TRANSCRIPTIE VAN DE {kop} ---\n" + transcript
    antwoord = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _BASIS_PROMPT},
            {"role": "user", "content": inhoud},
        ],
    )
    ruw = antwoord.choices[0].message.content
    try:
        data = json.loads(ruw)
    except (json.JSONDecodeError, TypeError) as fout:
        raise RuntimeError(f"Ongeldig JSON-antwoord van het model: {fout}") from None
    if not isinstance(data, dict):
        raise RuntimeError("Het model gaf geen bruikbare basis terug.")
    normaliseer(data)
    data.setdefault("dagen", [])
    if taal_hint and not data.get("taal"):
        data["taal"] = taal_hint
    return data


def maak_nabespreking(bron, bijbelgedeelte=None, titel=None, samenvatting=None,
                      taal_hint=None):
    """Maak 15 nabespreekvragen (hoofd/hart/handen) op grond van de preektekst.

    Geeft {"hoofd": [5], "hart": [5], "handen": [5]}. Werpt een fout bij een
    ongeldig antwoord.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")
    if not (bron or samenvatting or "").strip():
        raise ValueError("Geen preektekst beschikbaar voor de nabespreking.")
    client = OpenAI()
    inhoud = ""
    if taal_hint:
        inhoud += f"De preek is in de taal met code '{taal_hint}'. Schrijf de vragen in díé taal.\n"
    if titel:
        inhoud += f"Titel: {titel}\n"
    if bijbelgedeelte:
        inhoud += f"Bijbelgedeelte: {bijbelgedeelte}\n"
    if samenvatting:
        inhoud += f"Samenvatting: {samenvatting}\n"
    inhoud += "\n--- GESCHREVEN PREEK ---\n" + (bron or samenvatting)[:16000]
    antwoord = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _NABESPREKING_PROMPT},
            {"role": "user", "content": inhoud},
        ],
    )
    ruw = antwoord.choices[0].message.content
    try:
        obj = json.loads(ruw)
    except (json.JSONDecodeError, TypeError) as fout:
        raise RuntimeError(f"Ongeldig JSON-antwoord van het model: {fout}") from None
    if not isinstance(obj, dict):
        raise RuntimeError("Het model gaf geen bruikbare nabespreking terug.")
    uit = {}
    for cat in ("hoofd", "hart", "handen"):
        rij = obj.get(cat)
        uit[cat] = [str(v).strip() for v in rij if str(v).strip()] if isinstance(rij, list) else []
    if not any(uit.values()):
        raise RuntimeError("Het model gaf geen bruikbare nabespreking terug.")
    return uit


# Categorieën voor groepsvragen (optie 3), met een strikte doelomschrijving.
GROEPSCATEGORIEEN = {
    "terughalen": "Terughalen — help de groep zich te herinneren wat er in de preek "
                  "werd gezegd (de kernboodschap en hoofdlijn, geen triviale details).",
    "verdiepen": "Verdiepen — laat de groep het Bijbelgedeelte én de boodschap dieper "
                 "doordenken: betekenis, spanningen, wat het zegt over God, mens en genade.",
    "landen": "Laten landen — help de boodschap persoonlijk en emotioneel te laten "
              "landen: wat raakt je, waar zit verlangen, weerstand, angst of geloof.",
    "handen": "Handen en voeten — maak het concreet en toepasbaar: hoe ziet dit er deze "
              "week uit in keuzes, gewoonten en de omgang met anderen. Geen clichés.",
}


def _verdeel(aantal, n):
    """Verdeel `aantal` vragen zo gelijk mogelijk over `n` categorieën."""
    basis, rest = divmod(max(aantal, 0), max(n, 1))
    return [basis + (1 if i < rest else 0) for i in range(n)]


def maak_groepsvragen(bron, categorieen, aantal=10, leeftijd=None, bijbelgedeelte=None,
                      titel=None, samenvatting=None, taal_hint=None):
    """Maak gespreksvragen voor groepen, strikt op grond van de preek + Bijbelgedeelte.

    `categorieen`: lijst uit GROEPSCATEGORIEEN (volgorde bepaalt de weergave).
    `aantal`: totaal aantal vragen, verdeeld over de gekozen categorieën.
    Geeft {categorie: [vragen]} voor de gekozen categorieën.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")
    cats = [c for c in (categorieen or []) if c in GROEPSCATEGORIEEN]
    if not cats:
        raise ValueError("Kies minstens één soort vragen.")
    if not (bron or samenvatting or "").strip():
        raise ValueError("Geen preektekst beschikbaar voor de vragen.")
    per_cat = dict(zip(cats, _verdeel(aantal, len(cats))))

    doelen = "\n".join(f"* {GROEPSCATEGORIEEN[c]} — maak hiervan precies {per_cat[c]} vraag/vragen "
                       f'(sleutel "{c}").' for c in cats)
    systeem = (
        "Je stelt vragen op voor een GROEPSGESPREK (kring, gemeente of gezin) over een "
        "preek. Je krijgt de geschreven preek en het Bijbelgedeelte.\n\n"
        "STRIKTE REGELS:\n"
        "* Baseer de vragen UITSLUITEND op de aangeleverde preek en het Bijbelgedeelte. "
        "Verzin geen feiten, citaten, gebeurtenissen of toepassingen die daar niet in staan.\n"
        "* Blijf dicht bij de boodschap en de accenten van de preek; geen algemene vroomheid.\n"
        "* Elke vraag is open (niet met ja/nee te beantwoorden) en nodigt uit tot gesprek.\n"
        "* Vermijd herhaling tussen de vragen en tussen de categorieën.\n"
        "* Bij onzekerheid: stel liever een voorzichtige, open vraag dan iets te beweren.\n\n"
        "Maak per categorie exact het gevraagde aantal:\n" + doelen +
        "\n\nUitvoer UITSLUITEND als geldig JSON, met exact deze sleutels: "
        + ", ".join(f'"{c}"' for c in cats) +
        " — elk een lijst met de gevraagde aantallen vragen."
    )
    inhoud = ""
    if taal_hint:
        inhoud += f"Schrijf de vragen in de taal met code '{taal_hint}'.\n"
    if leeftijd:
        inhoud += f"Pas taal, toon en voorbeelden aan op de leeftijdsgroep: {leeftijd}.\n"
    if titel:
        inhoud += f"Titel: {titel}\n"
    if bijbelgedeelte:
        inhoud += f"Bijbelgedeelte: {bijbelgedeelte}\n"
    if samenvatting:
        inhoud += f"Samenvatting: {samenvatting}\n"
    inhoud += "\n--- GESCHREVEN PREEK ---\n" + (bron or samenvatting)[:16000]

    antwoord = client_chat(systeem, inhoud)
    try:
        obj = json.loads(antwoord)
    except (json.JSONDecodeError, TypeError) as fout:
        raise RuntimeError(f"Ongeldig JSON-antwoord van het model: {fout}") from None
    if not isinstance(obj, dict):
        raise RuntimeError("Het model gaf geen bruikbare groepsvragen terug.")
    uit = {}
    for c in cats:
        rij = obj.get(c)
        uit[c] = [str(v).strip() for v in rij if str(v).strip()] if isinstance(rij, list) else []
    if not any(uit.values()):
        raise RuntimeError("Het model gaf geen bruikbare groepsvragen terug.")
    return uit


def client_chat(systeem, inhoud):
    """Kleine helper: één JSON-chatcompletion en geef de ruwe tekst terug."""
    client = OpenAI()
    antwoord = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": systeem},
            {"role": "user", "content": inhoud},
        ],
    )
    return antwoord.choices[0].message.content


def _valideer(data, taal_hint):
    if not isinstance(data, dict):
        raise RuntimeError("Het model gaf geen bruikbare preekverwerking terug.")
    normaliseer(data)
    if "dagen" not in data:
        raise RuntimeError("Het model gaf geen bruikbare preekverwerking terug.")
    dagen = data.get("dagen") or []
    if not isinstance(dagen, list) or not dagen:
        raise RuntimeError("De preekverwerking bevat geen daggedeelten.")
    for dag in dagen:
        for veld in ("titel", "bijbeltekst", "gedachte", "vraag_volwassenen",
                     "vraag_kinderen"):
            dag.setdefault(veld, "")
    data["dagen"] = dagen
    data.setdefault("titel", "Preekverwerking")
    data.setdefault("bijbelgedeelte", "")
    data.setdefault("samenvatting", "")
    data.setdefault("voorganger", None)
    if not data.get("taal"):
        data["taal"] = (taal_hint or "nl")
    return data
