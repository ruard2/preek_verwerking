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

## Hosten op Railway (aanbevolen: via Supadata)

YouTube blokkeert downloads vanaf datacenter-IP's (zoals Railway). Gehost werkt
daarom het eenvoudigst via **Supadata**: een kant-en-klare dienst die de
YouTube-transcriptie ophaalt en die blokkade aan hún kant oplost. De gratis
tier volstaat voor een kerk met enkele diensten per week.

1. Maak een account op [supadata.ai](https://supadata.ai) en kopieer je
   API-sleutel.
2. Zet in Railway bij **Variables**: `SUPADATA_API_KEY=...` (en `OPENAI_API_KEY`).
3. Klaar. De app gebruikt dan Supadata i.p.v. yt-dlp; de PO-token-provider,
   proxy of cookies zijn niet nodig. De kanaallijst blijft via yt-dlp lopen
   (die lichte aanvraag wordt niet geblokkeerd).

Controleer na deploy `https://<app>/api/diagnose`: bij `transcript_bron` moet
"Supadata" staan.

> Let op: via Supadata krijg je YouTube's *automatische* ondertitels — prima
> bruikbaar, maar ruwer dan de audio-transcriptie (Whisper) die je lokaal
> krijgt. Wil je gehost tóch Whisper-kwaliteit, dan is een residentiële proxy
> (`YTDLP_PROXY`) met de PO-token-provider nodig; dat kost een paar euro per
> maand.

### Alternatief: eigen yt-dlp gehost

Zonder Supadata, met de PO-token-provider (Docker-image
`brainicism/bgutil-ytdlp-pot-provider:latest`, `POT_PROVIDER_URL=...`) plus een
residentiële proxy (`YTDLP_PROXY`) of ingelogde cookies (`YTDLP_COOKIES_B64`).
Bewerkelijker en cookies verlopen; Supadata of lokaal draaien is eenvoudiger.

## Overige aandachtspunten

- **Geen ondertitels?** De app gebruikt de ondertitels om het preekgedeelte te
  vinden. Zonder (automatische) ondertitels volgt een nette foutmelding.
  Vrijwel alle diensten op het kanaal hebben automatische ondertitels.
- De takenlijst leeft in het geheugen: na een herstart zijn lopende taken weg.
  Voor dit gebruik (één verwerking tegelijk) is dat prima.
