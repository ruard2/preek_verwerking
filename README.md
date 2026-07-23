# Preekverwerker

Plak een YouTube-link van een kerkdienst; de app zoekt het preekgedeelte op
(het langste aaneengesloten blok spraak), haalt de automatische ondertitels op
en verwerkt die via de OpenAI API tot een preekverwerking: titel, samenvatting
en zeven daggedeelten met vragen voor volwassenen en kinderen.

## Opbouw

- `main.py` — FastAPI-app: start verwerking als achtergrondtaak, frontend pollt de status.
- `transcript.py` — ondertitels ophalen met yt-dlp en het preekblok detecteren.
- `llm.py` — de verwerkingsinstructie (systeemprompt) en de OpenAI-aanroep.
- `static/index.html` — frontend: één invoerveld voor de link.

## Deployen op Railway

1. Zet deze map in een GitHub-repository en push.
2. Maak op [railway.app](https://railway.app) een nieuw project → *Deploy from GitHub repo*.
3. Zet bij **Variables**:
   - `OPENAI_API_KEY` — verplicht.
   - `POT_PROVIDER_URL` — sterk aangeraden, zie "YouTube-botdetectie" hieronder.
   - `OPENAI_MODEL` — optioneel, standaard `gpt-5`.
   - `KANAAL_URL` — optioneel, standaard de streams-pagina van NGK Middelharnis.
   - `YTDLP_COOKIES` — optioneel, noodoplossing (zie hieronder).
4. Genereer onder **Settings → Networking** een publiek domein.

Railway herkent het project automatisch als Python (via `requirements.txt` en
de `Procfile`).

## Lokaal draaien

```bash
pip install -r requirements.txt
set OPENAI_API_KEY=sk-...   # Windows; op Linux/Mac: export
uvicorn main:app --reload
```

Open daarna http://127.0.0.1:8000.

## YouTube-botdetectie (belangrijk voor Railway)

YouTube blokkeert verzoeken vanaf datacenter-IP's ("Sign in to confirm you're
not a bot"). De structurele oplossing is een PO-token-provider naast de app:

1. Voeg in hetzelfde Railway-project een tweede service toe:
   **New → Docker Image** → `brainicism/bgutil-ytdlp-pot-provider:latest`.
   Geef hem bijvoorbeeld de naam `pot-provider`. Geen publiek domein nodig.
2. Zet bij de app-service de variabele
   `POT_PROVIDER_URL=http://pot-provider.railway.internal:4416`
   (vervang `pot-provider` door de werkelijke servicenaam). De provider
   luistert op IPv6 en werkt dus met Railway's interne netwerk.
3. De bijbehorende yt-dlp-plugin (`bgutil-ytdlp-pot-provider` in
   `requirements.txt`) pakt dit automatisch op.

Blijft de blokkade ondanks de provider terugkomen, dan is er een noodoplossing:
exporteer cookies van een ingelogde YouTube-sessie (extensie "Get cookies.txt
LOCALLY", bij voorkeur vanuit een incognitovenster met een apart account) en
plak de inhoud in de variabele `YTDLP_COOKIES`. Cookies verlopen na verloop
van tijd; de token-provider niet.

## Overige aandachtspunten

- **Geen ondertitels?** Zonder (automatische) ondertitels kan de app niet
  transcriberen; dan volgt een nette foutmelding. Vrijwel alle YouTube-video's
  hebben automatische ondertitels.
- De takenlijst leeft in het geheugen: na een herstart van de server zijn
  lopende taken weg. Voor dit gebruik (één verwerking tegelijk) is dat prima.
