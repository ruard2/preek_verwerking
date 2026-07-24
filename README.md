# Preekverwerker

Plak een **kanaal** (een YouTube-kanaal of een Kerkdienstgemist-kerk) om alle
diensten als klikbare lijst te zien, of een **directe link** naar één preek. De
app zoekt het preekgedeelte op, transcribeert dat en verwerkt het tot een
preekverwerking: titel, voorganger, samenvatting en zeven daggedeelten met
vragen voor volwassenen en kinderen.

**Functies**

- Eén invoerveld: kanaal-URL → dienstenlijst per dag (gestreamde diensten
  aanklikbaar, geplande apart en uitgegrijsd); of een directe preeklink →
  meteen verwerken. YouTube en Kerkdienstgemist worden automatisch herkend.
- Verwerking tot een verzorgd weekboekje; op het scherm en als **PDF-download**.
- **Automatische taal**: een Afrikaanse preek levert een Afrikaans weekboekje,
  Engels levert Engels, enzovoort — inclusief de kopjes.
- **Caching**: de dienstenlijst ververst één keer per week (na zondag), per
  kanaal; een verwerkte preek wordt permanent bewaard en nooit dubbel
  berekend/betaald.
- Twee soorten bronnen:
  - **YouTube** — via **Supadata** (gehost, geen YouTube-blokkade) of
    **yt-dlp + OpenAI-audio (Whisper)** (lokaal, beste kwaliteit).
  - **Kerkdienstgemist** — via de publieke API: leest preek-starttijd,
    voorganger en liturgie, haalt **alleen het preekgedeelte** uit de HLS-stream
    en transcribeert dat met OpenAI (Whisper-kwaliteit, werkt ook gehost — geen
    datacenter-blokkade).
- **Liturgie** wordt bij Kerkdienstgemist altijd meebewaard en getoond
  (YouTube levert die niet); het Bijbelgedeelte wordt eruit afgeleid.

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

- `main.py` — FastAPI-app: herkent het geplakte type (kanaal vs. enkele preek,
  YouTube vs. Kerkdienstgemist) en orkestreert bron → segmentatie →
  transcriptie → verwerking, als achtergrondtaak; de frontend pollt de status.
  Endpoints: `/api/kanaal`, `/api/verwerk`, `/api/status/<id>`,
  `/api/pdf/<video_id>`, `/api/diagnose`.
- `transcript.py` — ondertitels ophalen met yt-dlp en het preekgedeelte (met
  tijden) detecteren; gedeelde segmentatie; ook de yt-dlp-opties
  (provider/proxy/cookies).
- `supadata.py` — transcript ophalen via de Supadata-API (gehost, met
  automatische taaldetectie).
- `kerkdienstgemist.py` — opname-info ophalen van Kerkdienstgemist (HLS-stream,
  preek-starttijd, voorganger, liturgie → Bijbelgedeelte).
- `audio.py` — de preekaudio downloaden, per deel knippen met ffmpeg en
  transcriberen via de OpenAI-audio-API (lokale Whisper-route).
- `llm.py` — de verwerkingsinstructie (systeemprompt) en de OpenAI-aanroep;
  levert gestructureerde JSON.
- `render.py` — JSON → kopieerbare tekst en → PDF (reportlab), met kopjes in de
  taal van de preek.
- `store.py` — persistente cache op schijf: dienstenlijst (wekelijks) en
  verwerkte preken (permanent).
- `static/index.html` — frontend: klikbare dienstenlijst per dag, verzorgde
  weergave, kopieer- en PDF-knop.
- `start.bat` — lokale één-klik-starter (provider + app + browser).

## Instellingen (.env of omgevingsvariabelen)

- `OPENAI_API_KEY` — verplicht.
- `POT_PROVIDER_URL` — adres van de PO-token-provider (lokaal
  `http://127.0.0.1:4416`, door `start.bat` gestart).
- `SUPADATA_API_KEY` — gehost gebruik: transcript via Supadata i.p.v. yt-dlp
  (lost YouTube's IP-blokkade op). Lokaal leeg laten.
- `OPENAI_MODEL` — verwerkingsmodel, standaard `gpt-5`.
- `OPENAI_TRANSCRIBE_MODEL` — transcriptiemodel, standaard `gpt-4o-mini-transcribe`.
- `KANAAL_URL` — standaard de streams-pagina van NGK Middelharnis.
- `DATA_DIR` — opslagmap voor de cache, standaard `./data`. Op Railway: koppel
  hier een volume aan zodat de cache een redeploy overleeft (zie hosten).
- `DIENSTEN_WEEKGRENS_UUR` — uur op zondag waarna de dienstenlijst als
  verouderd geldt en opnieuw wordt opgehaald (standaard 20).
- `KDG_TOKEN` — alleen nodig als de (publieke, anonieme) Kerkdienstgemist-token
  ooit verandert; normaal leeg laten.
- `YTDLP_PROXY` / `YTDLP_COOKIES` / `YTDLP_COOKIES_B64` — alleen nodig bij
  hosten op een datacenter-IP via de eigen yt-dlp-route; lokaal niet.

## Hosten op Railway (aanbevolen: via Supadata)

YouTube blokkeert downloads vanaf datacenter-IP's (zoals Railway). Gehost werkt
daarom het eenvoudigst via **Supadata**: een kant-en-klare dienst die de
YouTube-transcriptie ophaalt en die blokkade aan hún kant oplost. De gratis
tier volstaat voor een kerk met enkele diensten per week.

1. Maak een account op [supadata.ai](https://supadata.ai) en kopieer je
   API-sleutel.
2. Zet in Railway bij **Variables**: `SUPADATA_API_KEY=...` (en `OPENAI_API_KEY`).
3. Klaar. De app gebruikt dan Supadata i.p.v. yt-dlp; de PO-token-provider,
   proxy of cookies zijn niet nodig. De kanaallijst gaat eerst via yt-dlp
   (lichte aanvraag) en valt bij een blokkade **automatisch terug op Supadata**
   (recente video's, `SUPADATA_KANAAL_MAX`, standaard 20).

Controleer na deploy `https://<app>/api/diagnose`: bij `transcript_bron` moet
"Supadata" staan.

**Cache laten overleven (aanbevolen):** de app bewaart verwerkte preken op
schijf. Railway's bestandssysteem wordt bij elke redeploy gewist, dus koppel
een **Volume** aan de app-service en zet `DATA_DIR` op het mountpad (bijv.
`/data`). Zonder volume werkt alles nog steeds, maar wordt een preek na een
redeploy opnieuw opgehaald en verwerkt (en dus opnieuw betaald).

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

## Kerkdienstgemist

Plak óf een **station-URL** (`kerkdienstgemist.nl/stations/<station>` of
`.../stations/<station>/events`) voor de dienstenlijst, óf een directe
**opname-link** (`.../stations/<station>/events/recording/<id>`). Bij een
opname doet de app:

1. leest via de publieke API de preek-starttijd (`sermon_start_time`), duur,
   voorganger (`artist`) en liturgie (`description`);
2. haalt met ffmpeg **alleen het preekgedeelte** uit de HLS-stream (niet de hele
   dienst) en transcribeert dat met OpenAI;
3. leidt het Bijbelgedeelte uit de liturgie af en geeft dat samen met de
   voorganger als vaststaand mee aan het model.

Kerkdienstgemist is een gewone mediasite: **geen datacenter-blokkade**, dus dit
werkt ook gehost zonder Supadata/proxy.

## Caching

- **Dienstenlijst**: eens per week verversen, zo snel mogelijk na zondag
  (grens: zondag `DIENSTEN_WEEKGRENS_UUR`:00). Daartussen uit de cache. De knop
  "Vernieuw lijst" forceert een verse ophaal.
- **Verwerkte preken**: per video één keer berekend (transcript + verwerking)
  en daarna permanent uit `DATA_DIR/resultaten/<video_id>.json`. Een tweede
  klik op dezelfde dienst is meteen klaar en levert direct de PDF.

## Overige aandachtspunten

- **Geen ondertitels?** De app gebruikt de ondertitels om het preekgedeelte te
  vinden. Zonder (automatische) ondertitels volgt een nette foutmelding.
  Vrijwel alle diensten op het kanaal hebben automatische ondertitels.
- De voortgang van een lopende verwerking leeft in het geheugen (verdwijnt bij
  een herstart); de uitkomst zelf wordt op schijf bewaard.
