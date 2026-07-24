"""Verwerking van het preektranscript via de OpenAI API."""

import json
import os

from openai import OpenAI

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")

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
* Citeer Bijbelteksten in natuurlijk Nederlands.
* Wanneer geen Bijbelvertaling is opgegeven, gebruik dan bij voorkeur de NBV21.
* Vermijd lange citaten. Kies per dag één of enkele verzen die echt bij de hoofdgedachte passen.

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
      "bijbeltekst": "<passend Bijbelexcerpt>",
      "gedachte": "<overdenking van ongeveer 100 tot 160 woorden>",
      "vraag_volwassenen": "<één reflectievraag voor volwassenen>",
      "vraag_kinderen": "<één eenvoudige gespreksvraag voor kinderen>"
    }
  ]
}

De lijst "dagen" bevat precies zeven objecten (dag 1 tot en met dag 7), in
volgorde. Gebruik geen extra velden en laat geen veld weg; alleen "voorganger"
mag null zijn.

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
* Citeer Bijbelteksten in diezelfde taal, uit een gangbare vertaling in die \
taal (Nederlands: NBV21; Engels: bijvoorbeeld de NIV; Afrikaans: de Afrikaanse \
Bybel), tenzij in de preek een andere vertaling wordt gebruikt.
* Zet in het veld "taal" de ISO-code van die taal (nl, af, en, ...).
"""

GEBRUIKER_INLEIDING = """\
Hieronder staat de ruwe, automatisch gegenereerde transcriptie van de preek \
(afkomstig uit YouTube-ondertitels). Aan het begin en het einde kunnen nog \
restanten van de rest van de kerkdienst staan, zoals liederen, mededelingen \
of gebeden; laat die buiten beschouwing en verwerk alleen de preek zelf. \
Geef alleen het eindresultaat in de voorgeschreven structuur.
"""


def verwerk_preek(transcript, welkom=None, taal_hint=None):
    """Verwerk het transcript tot een gestructureerd resultaat (dict).

    Geeft een dict met de velden: taal, titel, bijbelgedeelte, voorganger,
    samenvatting, dagen[7]. Werpt een fout bij een ongeldig antwoord.
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is niet ingesteld. Voeg deze toe als "
            "omgevingsvariabele (in Railway: Variables)."
        )
    client = OpenAI()
    inhoud = GEBRUIKER_INLEIDING
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
    inhoud += "\n--- TRANSCRIPTIE VAN DE PREEK ---\n" + transcript
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


def _valideer(data, taal_hint):
    if not isinstance(data, dict) or "dagen" not in data:
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
