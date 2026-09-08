"""Verwerking van het preektranscript via de OpenAI API."""

import json
import os

from openai import OpenAI

MODEL = os.environ.get("OPENAI_MODEL", "gpt-5")
SCHOON_MODEL = os.environ.get("OPENAI_SCHOON_MODEL", MODEL)

SCHOON_PROMPT = """\
Je krijgt een ruw, automatisch gegenereerd transcript van één christelijke preek.
Jouw taak: kopieer de VOLLEDIGE preek letterlijk — verander GEEN enkel woord.

Regels:
* Kopieer elke zin, elk woord, elke herhaling, elke verspreking, elk 'eh'/'uhm' —
  precies zoals de predikant het zei. 100% letterlijk.
* Vat NIET samen, kort NIET in, verbeter NIETS, herschrijf NIETS.
* Verander de theologische strekking niet en voeg niets toe.
* Alleen tijdcodes (bijv. [00:23:45]) mogen worden verwijderd als ze in de tekst staan.
* Deel de tekst in logische alinea's in per gedachtegang, maar verander de woorden niet.
* Herstel alleen flagrante herkenningsfouten in namen van Bijbelboeken of Bijbelse
  personen waarbij de context 100% zeker is — wees terughoudend.
* Als de preek uit meerdere delen bestaat (gemarkeerd met [VOLGEND PREEKDEEL]),
  voeg die samen tot één doorlopende tekst; laat de markering zelf weg.

Uitvoer: ALLEEN de letterlijk gekopieerde preektekst als lopende alinea's. Geen titel,
geen kopjes, geen samenvatting, geen commentaar, geen opsomming — puur de preek.
Schrijf in dezelfde taal als de preek.
"""

SYSTEEM_PROMPT = """\
API-opdracht: preektranscript verwerken

Je ontvangt een ruwe, automatisch gegenereerde transcriptie van een christelijke preek. De transcriptie kan spreektaal, herhalingen, onafgemaakte zinnen, tijdcodes, fouten in namen en Bijbelverwijzingen en verkeerd herkende woorden bevatten.

Verwerk de aangeleverde tekst in twee stappen.

Stap 1 – Transcript lezen (intern)
Lees het transcript zorgvuldig. De tekst is 100% letterlijk — alle woorden van de
predikant, inclusief herhalingen, aarzelingen en spreektaal. Gebruik het als bron.

* Verander NIETS aan de woorden van de predikant.
* Verwijder alleen tijdcodes als die aanwezig zijn.
* Noteer intern: centrale boodschap, structuur, Bijbelteksten, voorbeelden.
* Schrijf het transcript NIET opnieuw uit — gebruik het puur als bronmateriaal.
* Voeg geen nieuwe theologische ideeën, voorbeelden of conclusies toe.
* Maak onzekerheden niet stilzwijgend zeker.

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
Schrijf een samenvatting van minimaal 400 tot maximaal 600 woorden.
De samenvatting moet:

* de centrale boodschap van de preek benoemen;
* de structuur en opbouw van de preek duidelijk weergeven (inleiding, hoofdpunten, conclusie/toepassing);
* per thema of gedachtegang een eigen alinea gebruiken — schrijf dus niet in één aaneengesloten blok maar werk met witregels;
* de belangrijkste onderbouwing, voorbeelden of Bijbelverwijzingen die de voorganger gebruikt noemen;
* duidelijk maken wat de preek van de hoorder vraagt of oproept;
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
  "samenvatting": "<samenvatting van 400 tot 600 woorden, gestructureerd in alinea's>",
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
vragen — ALTIJD in de taal van de preek zelf. Is de preek in het Nederlands, \
schrijf dan in het Nederlands. Is de preek in het Afrikaans, schrijf dan in \
het Afrikaans. Is de preek in het Engels, schrijf dan in het Engels. \
Vertaal de inhoud NOOIT naar een andere taal — schrijf uitsluitend in de \
taal van de preek.
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


def _harde_taalinstructie(taal: str) -> str:
    """Geeft een onontkoombare taalinstructie terug als gebruikertekst.

    Wordt als eerste regel van de user-message geplaatst zodat het model hem
    niet kan negeren. De ISO-code staat er twee keer in: eenmaal als tekst,
    eenmaal als expliciete sleutel-waarde voor het JSON-veld 'taal'.
    """
    return (
        f"\n\n⚠ HARDE TAALEIS (niet onderhandelbaar): schrijf de VOLLEDIGE uitvoer "
        f"— titel, bijbelgedeelte, samenvatting, alle zeven daggedeelten, alle vragen — "
        f"UITSLUITEND in de taal met ISO-code '{taal}'. "
        f"Zet ook het JSON-veld \"taal\" op \"{taal}\". "
        f"Gebruik GEEN andere taal, ook niet als de preek in een andere taal lijkt te zijn. "
        f"Dit is een absolute systeemeis.\n\n"
    )


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
        inhoud += _harde_taalinstructie(taal_hint)
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
        inhoud += _harde_taalinstructie(taal_hint)
    inhoud += "--- RUW TRANSCRIPT ---\n" + transcript
    antwoord = client.chat.completions.create(
        model=SCHOON_MODEL,
        messages=[
            {"role": "system", "content": SCHOON_PROMPT},
            {"role": "user", "content": inhoud},
        ],
    )
    return (antwoord.choices[0].message.content or "").strip()


_EXTRAHEER_PROMPT = """\
Je ontvangt een ruwe automatische transcriptie van een VOLLEDIGE kerkdienst.

Je werkt in TWEE stappen. Doe stap 1 volledig voordat je aan stap 2 begint.

════════════════════════════════════════════════════════════════════════════════
STAP 1 — STRUCTUURANALYSE (schrijf dit op als <analyse>…</analyse>)
════════════════════════════════════════════════════════════════════════════════
Ga door de transcriptie en benoem elk onderdeel van de dienst in volgorde:

  Votum / Groet / Drempelwoord
  Lied / Psalm / Gezang           ← herkenbaar: korte versregels, rijm,
                                     archaïsch taalgebruik, regelmatige maat
  Wetslezing / Tien Geboden
  Schriftlezing                   ← voorganger leest Bijbeltekst voor (geen uitleg)
  Gebed (preekgebed / dankgebed)
  PREEK of PREEKDEEL              ← uitleg van Bijbeltekst, toepassing, voorbeelden,
                                     langere zinnen, modern taalgebruik
  Geloofsbelijdenis / Zegen / Wegzending
  Mededelingen / Collecte

Schrijf het overzicht als:
<analyse>
1. Votum + Groet
2. Lied (Psalm 25:1,2)
3. Wetslezing
4. Lied (Psalm 25:3)
5. Gebed
6. Schriftlezing (Johannes 3:1-17)
7. Preekgebed
8. PREEK DEEL 1 — "Nicodemus komt 's nachts..."
9. Lied (Gezang 12)
10. PREEK DEEL 2 — "Zo lief heeft God de wereld..."
11. Dankgebed
12. Lied
13. Zegen
</analyse>

Let bij de analyse op:
• Liederen zijn korte rijmende regels in vaste maat — ook als de tekst
  niet heel archaïsch is. Duidelijk ANDERS dan gesproken prediking.
• Een schriftlezing is herkenbaar doordat de voorganger letterlijk de
  Bijbeltekst voorleest zonder er uitleg bij te geven.
• De preek begint DIRECT na het preekgebed — de eerste preekwoorden zijn
  vaak: "Gemeente...", "We lazen zojuist...", "Het gaat vanmorgen over..."
• Bij een meerdelig preek: liederen TUSSEN preekdelen horen er NIET bij,
  maar het volgende preekdeel WEL — ook als de stijl even verschilt.
• Als de voorganger in de preek een psalmregel citeert ter illustratie:
  dat hoort bij de preek. Als de gemeente zingt: dat is een lied.

════════════════════════════════════════════════════════════════════════════════
STAP 2 — EXTRACTIE (na de </analyse> tag)
════════════════════════════════════════════════════════════════════════════════
Kopieer nu LETTERLIJK alle preek(delen) die je in stap 1 hebt geïdentificeerd.

Regels:
• Verander GEEN ENKEL WOORD. Geen verbeteringen, geen herschrijven.
• 'eh', 'uhm', herhalingen, versprekingen, onafgemaakte zinnen: alles erin.
• Alleen tijdcodes (bijv. [00:23:45]) mogen weg.
• Meerdere preekdelen: scheid ze met [PREEKDEEL VERVOLGT].
• Deel de tekst in alinea's in per gedachtegang (alleen witregels — geen
  titels, geen nummering, geen kopjes).

Na de </analyse> tag: ALLEEN de letterlijke preektekst.
Geen JSON, geen commentaar, geen opmerkingen. Schrijf in de taal van de preek.
"""


def extraheer_en_schoon_preek(transcript: str) -> str:
    """Extraheer de preek uit een volledige-dienst transcriptie én schoon hem meteen op.

    Combineert twee stappen in één LLM-aanroep:
    1. AI lokaliseert het preekgedeelte (ook bij meerdere preekdelen)
    2. AI levert meteen de opgeschoonde, leesbare preektekst

    Dit vervangt zowel de (onbetrouwbare) heuristische blokdetectie in transcript.py
    als de aparte schoon_transcript-stap — alles in één gerichte call.

    Bij een fout of leeg resultaat wordt het originele transcript teruggegeven
    zodat de verwerking gewoon doorgaat (minder mooi maar niet geblokkeerd).
    """
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is niet ingesteld.")
    if not (transcript or "").strip():
        return transcript or ""
    client = OpenAI()
    antwoord = client.chat.completions.create(
        model=SCHOON_MODEL,  # zelfde model als schoon_transcript — snel en goedkoop
        messages=[
            {"role": "system", "content": _EXTRAHEER_PROMPT},
            {"role": "user", "content": "--- VOLLEDIGE DIENST TRANSCRIPTIE ---\n" + transcript},
        ],
        # Een 40-minuten preek is al gauw 7.000–9.500 tokens output; zonder limiet
        # valt OpenAI terug op ~4.096 en kapt de tekst halverwege af.
        # 16.384 is het model-maximum (GPT-4o / GPT-5).
        # Nieuwere modellen (o-serie, gpt-5) vereisen max_completion_tokens i.p.v. max_tokens.
        max_completion_tokens=16384,
    )
    resultaat = (antwoord.choices[0].message.content or "").strip()

    # Verwijder de <analyse>…</analyse> redeneerblok — alleen de preektekst bewaren.
    import re as _re
    resultaat = _re.sub(r"<analyse>.*?</analyse>", "", resultaat, flags=_re.DOTALL).strip()

    # Terugval: als model niets terugstuurt of minder dan 15% van het origineel,
    # is er iets mis — geef het origineel terug zodat de verwerking niet blokkeert.
    if len(resultaat) < max(200, len(transcript) * 0.15):
        return transcript
    return resultaat


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
        + _harde_taalinstructie(taal)
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
voorganger of null, (5) een samenvatting van 400–600 woorden die de centrale
boodschap, de structuur (inleiding/hoofdpunten/conclusie), de belangrijkste
voorbeelden en wat de preek van de hoorder vraagt weergeeft — gebruik alinea's,
niet één aaneengesloten blok.

Schrijf de VOLLEDIGE inhoud (titel, bijbelgedeelte, samenvatting) in de taal van
de preek zelf — Nederlands voor een Nederlandse preek, Afrikaans voor een
Afrikaanse preek, Engels voor een Engelse preek. Vertaal de inhoud NOOIT.

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
        inhoud += _harde_taalinstructie(taal_hint)
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
        inhoud += _harde_taalinstructie(taal_hint)
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
        inhoud += _harde_taalinstructie(taal_hint)
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
