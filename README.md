# Preekverwerker

Kies een dienst van NGK Middelharnis; de app zoekt het preekgedeelte op (het
langste aaneengesloten blok spraak tussen de liederen), transcribeert de audio
van dat stuk via OpenAI en verwerkt die tot een preekverwerking: titel,
voorganger, samenvatting en zeven daggedeelten met vragen voor volwassenen en
kinderen.

## Aanbevolen: lokaal draaien (Windows)

De app draait het best **lokaal op je eigen pc**. YouTube blokkeert namelijk
downloads vanaf datacenter-IP's (zoals Railway); vanaf je thuis-IP niet. Lokaal
heb je dus geen cookies of proxy nodig.

**Eenmalig instellen:**
1. Zorg dat [Python](https://www.python.org/) en
   [Docker Desktop](https://www.docker.com/products/docker-desktop/) zijn
   geïnstalleerd.
2. Kopieer `.env.example` naar `.env` en vul je `OPENAI_API_KEY` in.

**Gebruiken:** dubbelklik op **`start.bat`**. Dat installeert (de eerste keer)
de pakketten, start de PO-token-provider in Docker, opent de browser en start
de app op http://127.0.0.1:8123. Kies een dienst en wacht op het resultaat.
Sluit het zwarte venster om te stoppen.

### Transcriptie: audio of ondertitels

- Draait de token-provider (via `start.bat`/Docker), dan wordt de **audio**
  van de preek getranscribeerd met OpenAI — de beste kwaliteit.
- Lukt dat niet (Docker uit), dan valt de app automatisch terug op de
  **YouTube-ondertitels**. Je krijgt altijd een resultaat; de statusregel laat
  zien welke bron is gebruikt.

Kosten per preek: naast de tekstverwerking ongeveer een paar dubbeltjes voor de
audio-transcriptie (model `gpt-4o-mini-transcribe`).

## Opbouw

- `main.py` — FastAPI-app: orkestreert segmentatie → transcriptie → verwerking,
  als achtergrondtaak; de frontend pollt de status.
- `transcript.py` — ondertitels ophalen met yt-dlp en het preekgedeelte (met
  tijden) detecteren; ook de yt-dlp-opties (provider/proxy/cookies).
- `audio.py` — de preekaudio downloaden, per deel knippen met ffmpeg en
  transcriberen via de OpenAI-audio-API.
- `llm.py` — de verwerkingsinstructie (systeemprompt) en de OpenAI-aanroep.
- `static/index.html` — frontend: klikbare dienstenlijst per dag.
- `start.bat` — lokale één-klik-starter (provider + app + browser).

## Instellingen (.env of omgevingsvariabelen)

- `OPENAI_API_KEY` — verplicht.
- `POT_PROVIDER_URL` — adres van de PO-token-provider (lokaal
  `http://127.0.0.1:4416`, door `start.bat` gestart).
- `OPENAI_MODEL` — verwerkingsmodel, standaard `gpt-5`.
- `OPENAI_TRANSCRIBE_MODEL` — transcriptiemodel, standaard `gpt-4o-mini-transcribe`.
- `KANAAL_URL` — standaard de streams-pagina van NGK Middelharnis.
- `YTDLP_PROXY` / `YTDLP_COOKIES` / `YTDLP_COOKIES_B64` — alleen nodig bij
  hosten op een datacenter-IP; lokaal niet.

## Eventueel: hosten op Railway

Lokaal draaien heeft de voorkeur. Wil je het tóch hosten, houd er dan rekening
mee dat YouTube het datacenter-IP blokkeert. Nodig:

1. Tweede service in het project: **Docker Image**
   `brainicism/bgutil-ytdlp-pot-provider:latest`, en bij de app-service
   `POT_PROVIDER_URL=http://<servicenaam>.railway.internal:4416`.
2. Vaak aanvullend een residentiële proxy (`YTDLP_PROXY`) of ingelogde cookies
   (`YTDLP_COOKIES_B64`, base64 van een `cookies.txt`), omdat de audiodownload
   zwaarder wordt geblokkeerd dan alleen ondertitels. Cookies verlopen na
   verloop van tijd; lokaal draaien voorkomt dit gedoe volledig.

## Overige aandachtspunten

- **Geen ondertitels?** De app gebruikt de ondertitels om het preekgedeelte te
  vinden. Zonder (automatische) ondertitels volgt een nette foutmelding.
  Vrijwel alle diensten op het kanaal hebben automatische ondertitels.
- De takenlijst leeft in het geheugen: na een herstart zijn lopende taken weg.
  Voor dit gebruik (één verwerking tegelijk) is dat prima.
