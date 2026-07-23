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
   - `OPENAI_MODEL` — optioneel, standaard `gpt-5`.
   - `YTDLP_COOKIES` — optioneel, zie hieronder.
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

## Bekende aandachtspunten

- **YouTube kan server-IP's blokkeren.** Railway draait in een datacenter en
  YouTube weigert soms verzoeken daarvandaan ("Sign in to confirm you're not a
  bot"). Oplossing: exporteer cookies uit je eigen browser (bijvoorbeeld met de
  extensie "Get cookies.txt LOCALLY") en plak de inhoud van dat bestand in de
  Railway-variabele `YTDLP_COOKIES`.
- **Geen ondertitels?** Zonder (automatische) ondertitels kan de app niet
  transcriberen; dan volgt een nette foutmelding. Vrijwel alle YouTube-video's
  hebben automatische ondertitels.
- De takenlijst leeft in het geheugen: na een herstart van de server zijn
  lopende taken weg. Voor dit gebruik (één verwerking tegelijk) is dat prima.
