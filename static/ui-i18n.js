/* Shared UI translations. Add a language here to make it available everywhere. */
window.AfterSermonI18n = (() => {
  const languages = {
    nl: {flag:"🇳🇱", name:"Nederlands"},
    en: {flag:"🇬🇧", name:"English"},
    af: {flag:"🇿🇦", name:"Afrikaans"}
  };
  const en = {
    "Welke dienst(en)?":"Which service(s)?",
    "Hoe wil je ontvangen?":"How would you like to receive it?",
    "Per e-mail":"By email","Als melding op mijn telefoon of computer":"As a notification on my phone or computer","Allebei":"Both",
    "Meldingen op je iPhone":"Notifications on your iPhone",
    "Tik onderin op Deel en kies \"Zet op beginscherm\". Open AfterSermon daarna vanaf je beginscherm en zet meldingen aan.":"Tap Share at the bottom and choose \"Add to Home Screen\". Then open AfterSermon from your home screen and turn on notifications.",
    "Meldingen aanzetten":"Turn on notifications",
    "Meldingen op dit apparaat aanzetten":"Turn on notifications on this device",
    "Dit apparaat/deze browser ondersteunt geen meldingen.":"This device/browser does not support notifications.",
    "Meldingen aanzetten mislukte:":"Turning on notifications failed:",
    "Ontvang de overdenkingen als melding op dit apparaat.":"Receive the devotionals as a notification on this device.",
    "Dit apparaat of deze browser ondersteunt geen meldingen.":"This device or browser does not support notifications.",
    "Meldingen zijn nog niet beschikbaar.":"Notifications are not available yet.",
    "Je hebt meldingen niet toegestaan.":"You did not allow notifications.",
    "Meldingen staan aan — je hebt een testmelding ontvangen.":"Notifications are on — you received a test notification.",
    "Meldingen aanzetten is mislukt. Probeer het later opnieuw.":"Turning on notifications failed. Please try again later.",
    "Beheerders":"Administrators",
    "Nodig extra mensen uit om deze kerk mee te beheren. Zij krijgen een e-mail om een eigen wachtwoord in te stellen.":"Invite others to help manage this church. They receive an email to set their own password.",
    "E-mailadres uitnodigen":"Email address to invite","Uitnodigen":"Invite","Uitnodiging verstuurd.":"Invitation sent.",
    "Goedgekeurd. De overdenkingen worden op de ingestelde tijden verstuurd.":"Approved. The devotionals will be sent at the configured times.",
    "Deze link is ongeldig of verlopen.":"This link is invalid or has expired.","Geen geldige link.":"No valid link.",
    "Dienst van":"Service of","Optie 1 — via het kanaal":"Option 1 — via the channel",
    "Laat de preek automatisch ophalen en transcriberen, en maak er een weekboekje van. Dat kan een paar minuten duren.":"Automatically fetch and transcribe the sermon and turn it into a devotional. This may take a few minutes.",
    "Verwerk deze preek":"Process this sermon","Bezig met verwerken…":"Processing…",
    "Optie 2 — je eigen preektekst of audio":"Option 2 — your own sermon text or audio",
    "Heb je je preek als document (PDF, DOCX, TXT) of als audio (MP3)? Upload hem hier; daar wordt direct een weekboekje van gemaakt. Bij een document hoeft er niets beluisterd te worden; audio wordt eerst getranscribeerd en het bestand daarna direct verwijderd.":"Do you have your sermon as a document (PDF, DOCX, TXT) or audio (MP3)? Upload it here and a devotional is created directly. A document needs no listening; audio is transcribed first and the file is deleted immediately afterwards.",
    "Verwerk geüploade tekst":"Process uploaded file","Kies eerst een bestand.":"Please choose a file first.",
    "Wijzigingen opslaan":"Save changes","Stuur test naar mezelf":"Send test to myself",
    "Opnieuw versturen goedkeuren":"Approve resend","Goedkeuren & versturen":"Approve & send",
    "Versturen…":"Sending…","Testmail verstuurd naar":"Test email sent to","Terug naar concept":"Back to draft",
    "Welke dienst(en) wil je ontvangen?":"Which service(s) would you like to receive?",
    "Beide diensten":"Both services","Alleen de ochtenddienst":"Morning service only","Alleen de avonddienst":"Evening service only",
    "Download mijn gegevens":"Download my data","Opslaan":"Save","Afmelden":"Unsubscribe","Je voorkeuren zijn opgeslagen.":"Your preferences have been saved.",
    "Basisinstellingen":"Settings","Verzendlijst":"Recipients","Berichten":"Messages","Analyse":"Analytics",
    "Aan de slag":"Getting started",
    "Nog een paar stappen tot je eerste overdenkingen uitgaan:":"A few steps before your first devotionals go out:",
    "Kanaal ingesteld":"Channel set",
    "Zet je YouTube-, Kerkdienstgemist- of Kerkomroep-kanaal bij Basisinstellingen (of upload je preek bij Berichten).":"Set your YouTube, Kerkdienstgemist or Kerkomroep channel under Settings (or upload your sermon under Messages).",
    "bevestigde inschrijver(s)":"confirmed subscriber(s)",
    "Deel je inschrijflink of QR-code (tab Verzendlijst) zodat gemeenteleden zich aanmelden.":"Share your signup link or QR code (Recipients tab) so members can subscribe.",
    "Laden…":"Loading…","Kon de cijfers niet laden.":"Could not load the figures.",
    "Bevestigd":"Confirmed","Nieuw (30 dagen)":"New (30 days)","Verzonden e-mails":"Emails sent",
    "Verwerkte diensten":"Processed services","Laatste verzending:":"Last send:","Nog niet bevestigd:":"Not yet confirmed:",
    "Van zondagse preek naar een week vol verdieping.":"Turn Sunday’s sermon into a week of reflection.",
    "Inloggen":"Sign in","Account aanmaken":"Create account","E-mailadres":"Email address",
    "Wachtwoord":"Password","Wachtwoord vergeten?":"Forgot password?","Naam van de kerk":"Church name",
    "Wachtwoord (min. 8 tekens)":"Password (at least 8 characters)","Kanaal":"Sermon source",
    "Kanaal-URL":"Channel URL","Instellingen opslaan":"Save settings","Instellingen opgeslagen.":"Settings saved.",
    "Diensten & verzending":"Services & delivery","Scan nu op nieuwe diensten":"Scan for new services",
    "Inschrijvers":"Subscribers","Handmatig toevoegen":"Add manually","Naam":"Name",
    "Telefoon (optioneel)":"Phone (optional)","Frequentie":"Frequency","Wekelijks":"Weekly",
    "Dagelijks":"Daily","Toevoegen":"Add","Inschrijfpagina delen":"Share signup page",
    "Uitloggen":"Sign out","Nog geen verwerkte diensten.":"No processed services yet.",
    "Nog geen inschrijvers.":"No subscribers yet.","verwijderen":"remove",
    "Tijdzone (waar de diensten gehouden worden)":"Time zone (where services take place)",
    "Automatisch versturen (uit = eerst zelf goedkeuren via de mail die je krijgt)":"Send automatically (off = approve via email first)",
    "Tóch versturen als goedkeuring op tijd uitblijft":"Send anyway if approval is late",
    "Beheeromgeving":"Workspace","Overzicht":"Overview","Bron instellen":"Connect source",
    "Communicatie instellen":"Set communication","Inschrijvers uitnodigen":"Invite subscribers",
    "Klaar voor automatische verwerking":"Ready for automatic processing",
    "Talen":"Languages","Taal beheeromgeving":"Admin language","Taal inschrijfpagina":"Signup-page language",
    "Taal communicatie":"Communication language","Automatisch (browsertaal)":"Automatic (browser language)",
    "Bijbeltekst":"Bible text","Weergave van de Bijbeltekst":"How to show the Bible text",
    "Volledige verstekst tonen":"Show the full verse text","Alleen de verwijzing tonen":"Show only the reference",
    "Vertaling":"Translation","Automatisch (publiek domein)":"Automatic (public domain)",
    "Kies of het dagstukje de volledige verstekst toont of alleen de verwijzing, en uit welke vertaling. Er wordt altijd hoogstens één vers getoond, met bronvermelding.":"Choose whether the devotional shows the full verse text or only the reference, and from which translation. At most one verse is ever shown, with attribution.",
    "Logo":"Logo","Logo opslaan":"Save logo","Logo verwijderen":"Remove logo","Logo opgeslagen.":"Logo saved.",
    "Logo verwijderd.":"Logo removed.","Kies eerst een afbeelding.":"Choose an image first.",
    "Uploaden mislukt.":"Upload failed.","Verwijderen mislukt.":"Removing failed.",
    "Upload het logo van je kerk. Het verschijnt bovenaan de mails en op de inschrijfpagina. PNG, JPG, WEBP, GIF of SVG, maximaal 500 kB.":"Upload your church's logo. It appears at the top of the emails and on the signup page. PNG, JPG, WEBP, GIF or SVG, max 500 kB.",
    "Kleur":"Colour","Accentkleur":"Accent colour",
    "Kies de accentkleur voor je mails en de inschrijfpagina.":"Choose the accent colour for your emails and the signup page.",
    "Stijl van de overdenkingen":"Style of the devotionals","Toon":"Tone","Lengte":"Length",
    "Bepaal de toon en de lengte van de overdenkingen die de AI schrijft.":"Set the tone and length of the devotionals the AI writes.",
    "Warm en pastoraal":"Warm and pastoral","Nuchter en bijbelgetrouw":"Sober and biblical",
    "Eigentijds en toegankelijk":"Contemporary and accessible","Theologisch verdiepend":"Theologically in-depth",
    "Kort":"Short","Gemiddeld":"Medium","Uitgebreid":"Extended",
    "Herschrijf deze dag":"Rewrite this day","Bezig…":"Working…","Deze dag is opnieuw geschreven.":"This day has been rewritten.",
    "Wat maakt AfterSermon van de preek?":"What should AfterSermon make from the sermon?",
    "Kies één of meer uitvoeren. De standaard is dagstukjes.":"Choose one or more outputs. The default is daily devotionals.",
    "Dagstukjes (weekboekje met 7 dagen)":"Daily devotionals (7-day booklet)",
    "Preeksamenvatting":"Sermon summary",
    "Preektranscript (volledige preektekst)":"Sermon transcript (full text)",
    "Vragen voor nabespreking (hoofd, hart, handen)":"Discussion questions (head, heart, hands)",
    "Genereer nabespreekvragen":"Generate discussion questions","Vernieuw nabespreekvragen":"Refresh discussion questions",
    "Nabespreekvragen gemaakt.":"Discussion questions created.",
    "Preek aanleveren":"Provide a sermon","Andere preek verwerken":"Process another sermon",
    "Plak een link van een preek of een kanaal — of upload je preek als bestand.":"Paste a link to a sermon or a channel — or upload your sermon as a file.",
    "Verwerk":"Process","of":"or","Upload":"Upload","Preek aangeleverd":"Sermon provided",
    "Verwerken duurt even. Zet bij Instellingen „automatisch versturen” aan, dan staan de preken van afgelopen zondag al klaar als je inlogt.":"Processing takes a moment. Turn on automatic processing in Settings, and last Sunday's sermons are ready when you log in.",
    "Inschrijflink en QR-code":"Signup link and QR code",
    "Preken van afgelopen zondag":"Sermons from last Sunday","wordt verwerkt…":"processing…",
    "Kies wat je met een preek wilt. Nieuwe preken worden op de achtergrond verwerkt.":"Choose what to do with a sermon. New sermons are processed in the background.",
    "Nog geen dienst van afgelopen zondag gevonden. Verwerk er zelf een via „Andere preek verwerken”.":"No service from last Sunday found yet. Add one via \"Process another sermon\".",
    "Kies de dienst":"Choose the service","Geen diensten gevonden.":"No services found.",
    "Geen dienst van afgelopen zondag gevonden — kies er zelf een.":"No service from last Sunday found — choose one yourself.",
    "Kon de lijst niet laden.":"Couldn't load the list.","Kon de link niet lezen.":"Couldn't read the link.",
    "Link controleren…":"Checking the link…","Plak eerst een link.":"Paste a link first.",
    "Verwerken… (dit kan enkele minuten duren)":"Processing… (this can take a few minutes)",
    "Verwerken mislukt.":"Processing failed.","Kies eerst een bestand.":"Choose a file first.",
    "Wat wil je met deze preek?":"What do you want with this sermon?",
    "Er wordt pas AI gebruikt als je iets kiest.":"AI is only used once you choose something.",
    "Preektekst":"Sermon text","Samenvatting":"Summary","Vragen voor groepen…":"Group questions…","Dagstukjes":"Daily devotionals",
    "Bezig met genereren…":"Generating…","Genereren mislukt.":"Generating failed.",
    "Dagstukjes — naar wie?":"Daily devotionals — to whom?","Verstuur naar je lijst":"Send to your list",
    "Download PDF":"Download PDF","Beheer verzendlijst":"Manage recipient list","Versturen…":"Sending…",
    "Verzonden naar":"Sent to","Het weekboekje naar alle bevestigde inschrijvers versturen?":"Send the booklet to all confirmed subscribers?",
    "Vragen voor groepen":"Group questions","Leeftijd":"Age","Aantal vragen":"Number of questions",
    "Soorten vragen":"Types of questions","Genereer vragen":"Generate questions","Kies minstens één soort vragen.":"Choose at least one type of question.",
    "Vragen om de preek terug te halen":"Questions to recall the sermon","Verdiepende vragen over tekst en preek":"Deepening questions about text and sermon",
    "Vragen om tekst en preek te laten landen":"Questions to let the text and sermon land","Vragen/opdrachten om handen en voeten te geven":"Questions/tasks to put it into practice",
    "Preek automatisch op de achtergrond verwerken (dan staan de preken van afgelopen zondag klaar als je inlogt)":"Process sermons automatically in the background (last Sunday's sermons are ready when you log in)",
    "ochtend":"morning","avond":"evening",
    "Aanmelden":"Subscribe","E-mailadres *":"Email address *","Ontvang de wekelijkse overdenkingen bij de preek.":"Receive weekly sermon devotionals.",
    "Telefoonnummer (optioneel)":"Phone number (optional)","Hoe vaak wil je ontvangen?":"How often would you like to receive it?",
    "Eén keer per week (hele weekboekje ineens)":"Once a week (full devotional)",
    "Dagelijks (één overdenking per dag)":"Daily (one reflection per day)",
    "Vul je e-mailadres in.":"Enter your email address.","Kies je taal":"Choose your language"
    ,"Bekijk eerst de demo →":"View the demo first →"
    ,"AfterSermon maakt van je zondagse preek automatisch een weekboekje: een korte samenvatting en zeven dagoverdenkingen met vragen voor volwassenen en kinderen — en mailt die elke week naar je gemeenteleden.":"AfterSermon automatically turns Sunday’s sermon into a weekly devotional: a short summary and seven daily reflections with questions for adults and children — delivered to your members each week."
    ,"Koppel je YouTube- of Kerkdienstgemist-kanaal en het gaat vanzelf. Log in of maak een account om te beginnen.":"Connect your YouTube or Kerkdienstgemist channel and the rest runs automatically. Sign in or create an account to get started."
    ,"Plak een kanaal (YouTube-kanaal of Kerkdienstgemist-kerk) om alle diensten te zien, of een directe link naar één preek.":"Paste a channel (YouTube or Kerkdienstgemist) to retrieve all services, or paste a direct link to process one sermon."
    ,"Laden":"Load","Beschikbare diensten":"Available services","Vernieuwen":"Refresh"
    ,"Diensten & verzending":"Services & delivery","Scan nu op nieuwe diensten":"Scan for new services"
    ,"Gevonden op het kanaal":"Found on the channel","Verwerking & verzending":"Processing & delivery"
    ,"Verwerkt":"Processed","Wordt gecontroleerd":"Being checked"
    ,"Vul hierboven een kanaallink in. De diensten verschijnen hier automatisch.":"Enter a channel link above. Services will appear here automatically."
    ,"Kanaal wordt opgehaald…":"Retrieving channel…","Bezig met scannen…":"Scanning…"
    ,"Nieuwe diensten worden gecontroleerd en verwerkt…":"New services are being checked and processed…"
    ,"Bedankt voor je aanmelding!":"Thank you for subscribing!"
    ,"Je e-mailadres is bevestigd. Vanaf nu ontvang je de overdenkingen van deze kerk volgens de gekozen frequentie.":"Your email address has been confirmed. From now on, you will receive this church’s devotionals at your chosen frequency."
    ,"We hopen dat ze je helpen om de boodschap van zondag mee te nemen in de week.":"We hope they help you carry Sunday’s message into the week."
    ,"Basisinstellingen":"Basic settings","Verzendlijst":"Subscribers","Berichten":"Messages"
    ,"Overdenkingen beheren":"Manage devotionals","Te versturen":"To send","Reeds verstuurd":"Sent"
    ,"Kanaal nu vernieuwen":"Refresh channel","Geen openstaande diensten":"No pending services"
    ,"Nieuwe diensten uit de laatste vier weken verschijnen hier automatisch.":"New services from the past four weeks appear here automatically."
    ,"Nog niets verstuurd":"Nothing sent yet","Na de eerste verzending verschijnt hier de geschiedenis.":"Your delivery history will appear here after the first send."
    ,"Klaar voor verzending":"Ready to send","Klaar om te beoordelen":"Ready for review"
    ,"Nog te verwerken":"Not processed yet","Openen & bewerken":"Open & edit"
    ,"Verwerken & bewerken":"Process & edit","Bekijken":"View"
    ,"Stel stap 1 t/m 3 één keer in. Daarna staan ze bij elke volgende preek automatisch op groen — dan hoef je alleen nog te controleren en te versturen.":"Set up steps 1–3 once. After that they turn green automatically for every next sermon — you only need to review and send."
    ,"Preek aanleveren":"Provide sermon","Kies wat je wil maken":"Choose what to create","Automatiseer het proces":"Automate the process","Controleer en bewerk":"Review and edit","Verstuur":"Send"
    ,"Kies of lever eerst een preek aan bij stap 1.":"First choose or provide a sermon in step 1.","Beschikbaar zodra je de dagstukjes hebt gemaakt.":"Available once you have created the devotionals."
    ,"Plak de link van je kanaal (dan halen we elke week de preek van afgelopen zondag zélf op) of van één preek. Of upload een bestand.":"Paste your channel link (then we fetch last Sunday's sermon ourselves every week) or a single sermon link. Or upload a file."
    ,"Verwerk":"Process","of":"or","Upload":"Upload","Automatisch via kanaal":"Automatic via channel","Preek aangeleverd":"Sermon provided","Kanaal ingesteld":"Channel set"
    ,"Link controleren…":"Checking link…","Geen dienst van afgelopen zondag gevonden — kies er zelf een.":"No service from last Sunday found — pick one yourself.","Kon de link niet lezen.":"Could not read the link.","Plak eerst een link.":"Paste a link first."
    ,"Wil je dit voortaan automatisch?":"Want this automatically from now on?","Dan halen we elke week de preek van afgelopen zondag zelf op — jij hoeft niets meer aan te leveren.":"Then we fetch last Sunday's sermon ourselves every week — you no longer have to provide anything."
    ,"Ja, automatisch ophalen":"Yes, fetch automatically","Instellen…":"Setting up…","Kanaal gevonden.":"Channel found.","Automatisch ophalen staat aan. Volgende week staat de preek al klaar als je inlogt.":"Automatic fetching is on. Next week the sermon will be ready when you log in."
    ,"Plak je kanaal-link":"Paste your channel link","Automatiseer":"Automate"
    ,"Preek(en) van afgelopen zondag — kies er één om mee verder te gaan.":"Sermon(s) from last Sunday — pick one to continue.","Kon de lijst niet laden.":"Could not load the list.","Nog geen dienst van afgelopen zondag gevonden. Plak hierboven een preek- of kanaal-link.":"No service from last Sunday found yet. Paste a sermon or channel link above."
    ,"Kies deze preek":"Choose this sermon","Verwerken":"Process","Alle diensten tonen…":"Show all services…","Geen diensten gevonden.":"No services found."
    ,"Kies wat we van elke preek maken. Er wordt alleen AI gebruikt voor wat je aanvinkt.":"Choose what we create from each sermon. AI is only used for what you tick.","Een weekboekje met een stukje per dag — dit versturen we naar je gemeenteleden.":"A weekly booklet with a piece for each day — this is what we send to your members.","Een korte samenvatting van de preek.":"A short summary of the sermon.","Gespreksvragen voor kringen en gezinnen.":"Discussion questions for groups and families.","De volledige uitgeschreven preek.":"The full transcribed sermon."
    ,"Dagstukjes":"Devotionals","Samenvatting":"Summary","Vragen voor groepen":"Questions for groups","Preektekst":"Sermon text","Kies minstens één.":"Choose at least one."
    ,"Wanneer gaat het wekelijks de deur uit?":"When does it go out each week?","Elke week op":"Every week on","om":"at","Controle vóór verzenden?":"Review before sending?","Ik keur elke week eerst goed (ik krijg een mail)":"I approve first each week (I get an email)","Volledig automatisch versturen":"Send fully automatically","Preken vooraf op de achtergrond verwerken (dan staan ze klaar als je inlogt)":"Process sermons in advance in the background (then they are ready when you log in)"
    ,"Beheer verzendlijst / QR-code":"Manage recipients / QR code","automatisch":"automatic","met goedkeuring":"with approval","Meer opties (afzender, taal, bijbelvertaling, kleuren) vind je bij Instellingen.":"More options (sender, language, Bible translation, colours) are under Settings."
    ,"Maak en controleer het materiaal dat je bij stap 2 hebt gekozen.":"Create and review the material you chose in step 2.","Zet „Dagstukjes” aan bij stap 2 om te kunnen versturen.":"Enable \"Devotionals\" in step 2 to be able to send.","Download PDF":"Download PDF","Alleen beschikbaar bij audio/video-preken.":"Only available for audio/video sermons.","Maak samenvatting":"Create summary","Stel vragen samen…":"Compile questions…","Maak dagstukjes":"Create devotionals","Bezig met genereren…":"Generating…","Genereren mislukt.":"Generation failed.","Download weekboekje (PDF)":"Download booklet (PDF)"
    ,"Stuur het weekboekje naar je gemeenteleden.":"Send the booklet to your members.","Verstuur naar mijn lijst":"Send to my list","Het weekboekje naar alle bevestigde inschrijvers versturen?":"Send the booklet to all confirmed subscribers?","Versturen mislukt.":"Sending failed.","Verzonden naar":"Sent to","Verzonden":"Sent","Beheer verzendlijst / QR":"Manage recipients / QR"
    ,"Plak de link van je kanaal of van één preek — of upload een bestand. Hoe en naar wie het verstuurd wordt, stel je in bij stap 3.":"Paste your channel link or a single sermon link — or upload a file. How and to whom it's sent is configured in step 3.","Verwerken…":"Processing…","Opslaan en verder":"Save and continue"
    ,"Naar wie gaat het?":"Who does it go to?","De dagstukjes gaan naar je verzendlijst; jij krijgt zelf altijd een kopie ter controle op je eigen mailadres. Deel een inschrijflink of QR-code zodat gemeenteleden zich aanmelden.":"The devotionals go to your recipient list; you always get a copy for review at your own email address. Share a signup link or QR code so members can subscribe."
    ,"Kleur en logo (voor de e-mails en boekjes)":"Colour and logo (for the emails and booklets)","Accentkleur":"Accent colour","Logo":"Logo","Logo verwijderen":"Remove logo","Logo opgeslagen.":"Logo saved.","Verwijderen mislukt.":"Removal failed.","Uploaden mislukt.":"Upload failed."
    ,"Nog meer opties (afzender, taal, bijbelvertaling, toon) vind je bij Instellingen.":"More options (sender, language, Bible translation, tone) are under Settings.","Automatisch ophalen":"Fetch automatically","Preken komen automatisch van je kanaal. Volgende week staat de preek klaar als je inlogt.":"Sermons come automatically from your channel. Next week the sermon will be ready when you log in.","Wil je dit voortaan automatisch? Dan halen we elke week de preek van afgelopen zondag zelf op — jij hoeft niets meer aan te leveren.":"Want this automatically from now on? Then we fetch last Sunday's sermon ourselves every week — you no longer have to provide anything.","De preek wordt nog verwerkt — dit vult zich vanzelf zodra het klaar is.":"The sermon is still being processed — this fills in automatically once it's ready."
    ,"Maandag":"Monday","Dinsdag":"Tuesday","Woensdag":"Wednesday","Donderdag":"Thursday","Vrijdag":"Friday","Zaterdag":"Saturday","Zondag":"Sunday"
    ,"Bekijk de preektekst":"View the sermon text","Ruw transcript":"Raw transcript","Opgeschoonde preektekst":"Cleaned sermon text","Bewerk hieronder en sla op; de PDF gebruikt jouw versie.":"Edit below and save; the PDF uses your version.","Titel":"Title","Bijbelgedeelte":"Bible passage","Samenvatting":"Summary","Dag":"Day","Bijbeltekst":"Bible text","Gedachte":"Reflection","Vraag (volwassenen)":"Question (adults)","Vraag (kinderen)":"Question (children)","Wijzigingen opslaan":"Save changes","Opgeslagen ✓":"Saved ✓","Opnieuw genereren":"Regenerate","Weet je het zeker? Je bewerkingen gaan verloren.":"Are you sure? Your edits will be lost.","Laden…":"Loading…","Kon niet laden.":"Could not load.","Nog niet gemaakt.":"Not created yet."
    ,"Wat gebeurt er met elke uitvoer?":"What happens with each output?","Per onderdeel dat je in stap 2 koos: automatisch meesturen in de wekelijkse mail naar je verzendlijst, of alleen zelf maken en downloaden bij stap 4.":"For each item you chose in step 2: include it automatically in the weekly email to your recipient list, or just create and download it yourself in step 4.","Automatisch naar verzendlijst":"Automatically to recipient list","Alleen downloaden (stap 4)":"Download only (step 4)","Naar je verzendlijst: gemeenteleden schrijven zich in via een link/QR; jij krijgt zelf altijd een controle-kopie.":"To your recipient list: members subscribe via a link/QR; you always get a review copy yourself."
    ,"Wanneer krijgen de groepen de vragen?":"When do the groups get the questions?","Elke week, samen met de rest":"Every week, together with the rest","Op vaste datums":"On fixed dates","Voeg de datums toe waarop de groepsvragen worden verstuurd.":"Add the dates on which the group questions are sent.","Nog geen datums.":"No dates yet.","Datum toevoegen":"Add date"
  };
  const af = {
    "Welke dienst(en)?":"Watter diens(te)?",
    "Hoe wil je ontvangen?":"Hoe wil jy dit ontvang?",
    "Per e-mail":"Per e-pos","Als melding op mijn telefoon of computer":"As kennisgewing op my foon of rekenaar","Allebei":"Albei",
    "Meldingen op je iPhone":"Kennisgewings op jou iPhone",
    "Tik onderin op Deel en kies \"Zet op beginscherm\". Open AfterSermon daarna vanaf je beginscherm en zet meldingen aan.":"Tik onder op Deel en kies \"Voeg by tuisskerm\". Maak AfterSermon dan oop vanaf jou tuisskerm en skakel kennisgewings aan.",
    "Meldingen aanzetten":"Skakel kennisgewings aan",
    "Meldingen op dit apparaat aanzetten":"Skakel kennisgewings op hierdie toestel aan",
    "Dit apparaat/deze browser ondersteunt geen meldingen.":"Hierdie toestel/blaaier ondersteun nie kennisgewings nie.",
    "Meldingen aanzetten mislukte:":"Kennisgewings aanskakel het misluk:",
    "Ontvang de overdenkingen als melding op dit apparaat.":"Ontvang die oordenkings as kennisgewing op hierdie toestel.",
    "Dit apparaat of deze browser ondersteunt geen meldingen.":"Hierdie toestel of blaaier ondersteun nie kennisgewings nie.",
    "Meldingen zijn nog niet beschikbaar.":"Kennisgewings is nog nie beskikbaar nie.",
    "Je hebt meldingen niet toegestaan.":"Jy het kennisgewings nie toegelaat nie.",
    "Meldingen staan aan — je hebt een testmelding ontvangen.":"Kennisgewings is aan — jy het 'n toetskennisgewing ontvang.",
    "Meldingen aanzetten is mislukt. Probeer het later opnieuw.":"Kennisgewings aanskakel het misluk. Probeer later weer.",
    "Beheerders":"Administrateurs",
    "Nodig extra mensen uit om deze kerk mee te beheren. Zij krijgen een e-mail om een eigen wachtwoord in te stellen.":"Nooi ander mense uit om hierdie gemeente saam te bestuur. Hulle kry ’n e-pos om hul eie wagwoord op te stel.",
    "E-mailadres uitnodigen":"E-posadres om uit te nooi","Uitnodigen":"Nooi uit","Uitnodiging verstuurd.":"Uitnodiging gestuur.",
    "Goedgekeurd. De overdenkingen worden op de ingestelde tijden verstuurd.":"Goedgekeur. Die oordenkings word op die ingestelde tye gestuur.",
    "Deze link is ongeldig of verlopen.":"Hierdie skakel is ongeldig of het verval.","Geen geldige link.":"Geen geldige skakel nie.",
    "Dienst van":"Diens van","Optie 1 — via het kanaal":"Opsie 1 — via die kanaal",
    "Laat de preek automatisch ophalen en transcriberen, en maak er een weekboekje van. Dat kan een paar minuten duren.":"Laat die preek outomaties haal en transkribeer, en maak ’n oordenking daarvan. Dit kan ’n paar minute neem.",
    "Verwerk deze preek":"Verwerk hierdie preek","Bezig met verwerken…":"Besig om te verwerk…",
    "Optie 2 — je eigen preektekst of audio":"Opsie 2 — jou eie preekteks of klank",
    "Heb je je preek als document (PDF, DOCX, TXT) of als audio (MP3)? Upload hem hier; daar wordt direct een weekboekje van gemaakt. Bij een document hoeft er niets beluisterd te worden; audio wordt eerst getranscribeerd en het bestand daarna direct verwijderd.":"Het jy jou preek as ’n dokument (PDF, DOCX, TXT) of as klank (MP3)? Laai dit hier op; daar word dadelik ’n oordenking van gemaak. ’n Dokument hoef nie beluister te word nie; klank word eers getranskribeer en die lêer daarna dadelik verwyder.",
    "Verwerk geüploade tekst":"Verwerk opgelaaide lêer","Kies eerst een bestand.":"Kies eers ’n lêer.",
    "Wijzigingen opslaan":"Stoor veranderinge","Stuur test naar mezelf":"Stuur toets na myself",
    "Opnieuw versturen goedkeuren":"Keur herstuur goed","Goedkeuren & versturen":"Keur goed & stuur",
    "Versturen…":"Stuur…","Testmail verstuurd naar":"Toets-e-pos gestuur na","Terug naar concept":"Terug na konsep",
    "Welke dienst(en) wil je ontvangen?":"Watter diens(te) wil jy ontvang?",
    "Beide diensten":"Albei dienste","Alleen de ochtenddienst":"Slegs die oggenddiens","Alleen de avonddienst":"Slegs die aanddiens",
    "Download mijn gegevens":"Laai my inligting af","Opslaan":"Stoor","Afmelden":"Teken uit","Je voorkeuren zijn opgeslagen.":"Jou voorkeure is gestoor.",
    "Basisinstellingen":"Basiese instellings","Verzendlijst":"Ontvangers","Berichten":"Boodskappe","Analyse":"Analise",
    "Aan de slag":"Kom aan die gang",
    "Nog een paar stappen tot je eerste overdenkingen uitgaan:":"Nog ’n paar stappe voor jou eerste oordenkings uitgaan:",
    "Kanaal ingesteld":"Kanaal opgestel",
    "Zet je YouTube-, Kerkdienstgemist- of Kerkomroep-kanaal bij Basisinstellingen (of upload je preek bij Berichten).":"Stel jou YouTube-, Kerkdienstgemist- of Kerkomroep-kanaal op onder Basiese instellings (of laai jou preek op onder Boodskappe).",
    "bevestigde inschrijver(s)":"bevestigde intekenaar(s)",
    "Deel je inschrijflink of QR-code (tab Verzendlijst) zodat gemeenteleden zich aanmelden.":"Deel jou inteken-skakel of QR-kode (Ontvangers-oortjie) sodat lidmate kan inteken.",
    "Laden…":"Laai…","Kon de cijfers niet laden.":"Kon die syfers nie laai nie.",
    "Bevestigd":"Bevestig","Nieuw (30 dagen)":"Nuut (30 dae)","Verzonden e-mails":"E-posse gestuur",
    "Verwerkte diensten":"Verwerkte dienste","Laatste verzending:":"Laaste versending:","Nog niet bevestigd:":"Nog nie bevestig nie:",
    "Van zondagse preek naar een week vol verdieping.":"Van Sondag se preek na ’n week vol verdieping.",
    "Inloggen":"Meld aan","Account aanmaken":"Skep rekening","E-mailadres":"E-posadres",
    "Wachtwoord":"Wagwoord","Wachtwoord vergeten?":"Wagwoord vergeet?","Naam van de kerk":"Naam van die kerk",
    "Wachtwoord (min. 8 tekens)":"Wagwoord (min. 8 karakters)","Kanaal":"Preekbron",
    "Kanaal-URL":"Kanaal-URL","Instellingen opslaan":"Stoor instellings","Instellingen opgeslagen.":"Instellings gestoor.",
    "Diensten & verzending":"Dienste en versending","Scan nu op nieuwe diensten":"Soek nou vir nuwe dienste",
    "Inschrijvers":"Inskrywers","Handmatig toevoegen":"Voeg handmatig by","Naam":"Naam",
    "Telefoon (optioneel)":"Telefoon (opsioneel)","Frequentie":"Frekwensie","Wekelijks":"Weekliks",
    "Dagelijks":"Daagliks","Toevoegen":"Voeg by","Inschrijfpagina delen":"Deel inskrywingsblad",
    "Uitloggen":"Meld af","Nog geen verwerkte diensten.":"Nog geen verwerkte dienste nie.",
    "Nog geen inschrijvers.":"Nog geen inskrywers nie.","verwijderen":"verwyder",
    "Tijdzone (waar de diensten gehouden worden)":"Tydsone (waar dienste plaasvind)",
    "Automatisch versturen (uit = eerst zelf goedkeuren via de mail die je krijgt)":"Stuur outomaties (af = keur eers per e-pos goed)",
    "Tóch versturen als goedkeuring op tijd uitblijft":"Stuur tog as goedkeuring laat is",
    "Beheeromgeving":"Werkruimte","Overzicht":"Oorsig","Bron instellen":"Koppel bron",
    "Communicatie instellen":"Stel kommunikasie","Inschrijvers uitnodigen":"Nooi inskrywers",
    "Klaar voor automatische verwerking":"Gereed vir outomatiese verwerking",
    "Talen":"Tale","Taal beheeromgeving":"Taal van administrasie","Taal inschrijfpagina":"Taal van inskrywingsblad",
    "Taal communicatie":"Taal van kommunikasie","Automatisch (browsertaal)":"Outomaties (blaaiertaal)",
    "Bijbeltekst":"Bybelteks","Weergave van de Bijbeltekst":"Hoe die Bybelteks wys",
    "Volledige verstekst tonen":"Wys die volledige versteks","Alleen de verwijzing tonen":"Wys net die verwysing",
    "Vertaling":"Vertaling","Automatisch (publiek domein)":"Outomaties (publieke domein)",
    "Kies of het dagstukje de volledige verstekst toont of alleen de verwijzing, en uit welke vertaling. Er wordt altijd hoogstens één vers getoond, met bronvermelding.":"Kies of die dagstukkie die volledige versteks of net die verwysing wys, en uit watter vertaling. Daar word altyd hoogstens een vers gewys, met bronvermelding.",
    "Logo":"Logo","Logo opslaan":"Stoor logo","Logo verwijderen":"Verwyder logo","Logo opgeslagen.":"Logo gestoor.",
    "Logo verwijderd.":"Logo verwyder.","Kies eerst een afbeelding.":"Kies eers 'n prent.",
    "Uploaden mislukt.":"Oplaai het misluk.","Verwijderen mislukt.":"Verwydering het misluk.",
    "Upload het logo van je kerk. Het verschijnt bovenaan de mails en op de inschrijfpagina. PNG, JPG, WEBP, GIF of SVG, maximaal 500 kB.":"Laai jou kerk se logo op. Dit verskyn bo-aan die e-posse en op die inskrywingsblad. PNG, JPG, WEBP, GIF of SVG, hoogstens 500 kB.",
    "Kleur":"Kleur","Accentkleur":"Aksentkleur",
    "Kies de accentkleur voor je mails en de inschrijfpagina.":"Kies die aksentkleur vir jou e-posse en die inskrywingsblad.",
    "Stijl van de overdenkingen":"Styl van die oordenkings","Toon":"Toon","Lengte":"Lengte",
    "Bepaal de toon en de lengte van de overdenkingen die de AI schrijft.":"Bepaal die toon en lengte van die oordenkings wat die KI skryf.",
    "Warm en pastoraal":"Warm en pastoraal","Nuchter en bijbelgetrouw":"Nugter en Bybelgetrou",
    "Eigentijds en toegankelijk":"Eietyds en toeganklik","Theologisch verdiepend":"Teologies verdiepend",
    "Kort":"Kort","Gemiddeld":"Gemiddeld","Uitgebreid":"Uitgebreid",
    "Herschrijf deze dag":"Herskryf hierdie dag","Bezig…":"Besig…","Deze dag is opnieuw geschreven.":"Hierdie dag is oorgeskryf.",
    "Wat maakt AfterSermon van de preek?":"Wat moet AfterSermon van die preek maak?",
    "Kies één of meer uitvoeren. De standaard is dagstukjes.":"Kies een of meer uitsette. Die standaard is dagstukkies.",
    "Dagstukjes (weekboekje met 7 dagen)":"Dagstukkies (weekboekie met 7 dae)",
    "Preeksamenvatting":"Preekopsomming",
    "Preektranscript (volledige preektekst)":"Preektranskripsie (volledige teks)",
    "Vragen voor nabespreking (hoofd, hart, handen)":"Vrae vir nabespreking (kop, hart, hande)",
    "Genereer nabespreekvragen":"Genereer nabesprekingsvrae","Vernieuw nabespreekvragen":"Vernuwe nabesprekingsvrae",
    "Nabespreekvragen gemaakt.":"Nabesprekingsvrae gemaak.",
    "Preek aanleveren":"Preek verskaf","Andere preek verwerken":"Ander preek verwerk",
    "Plak een link van een preek of een kanaal — of upload je preek als bestand.":"Plak 'n skakel na 'n preek of 'n kanaal — of laai jou preek as lêer op.",
    "Verwerk":"Verwerk","of":"of","Upload":"Laai op","Preek aangeleverd":"Preek verskaf",
    "Verwerken duurt even. Zet bij Instellingen „automatisch versturen” aan, dan staan de preken van afgelopen zondag al klaar als je inlogt.":"Verwerking neem 'n oomblik. Skakel outomatiese verwerking in Instellings aan, dan is verlede Sondag se preke klaar wanneer jy inteken.",
    "Inschrijflink en QR-code":"Inskrywingskakel en QR-kode",
    "Preken van afgelopen zondag":"Preke van verlede Sondag","wordt verwerkt…":"word verwerk…",
    "Kies wat je met een preek wilt. Nieuwe preken worden op de achtergrond verwerkt.":"Kies wat jy met 'n preek wil doen. Nuwe preke word op die agtergrond verwerk.",
    "Nog geen dienst van afgelopen zondag gevonden. Verwerk er zelf een via „Andere preek verwerken”.":"Nog geen diens van verlede Sondag gevind nie. Voeg self een by via „Ander preek verwerk”.",
    "Kies de dienst":"Kies die diens","Geen diensten gevonden.":"Geen dienste gevind nie.",
    "Geen dienst van afgelopen zondag gevonden — kies er zelf een.":"Geen diens van verlede Sondag gevind nie — kies self een.",
    "Kon de lijst niet laden.":"Kon nie die lys laai nie.","Kon de link niet lezen.":"Kon nie die skakel lees nie.",
    "Link controleren…":"Skakel word gekontroleer…","Plak eerst een link.":"Plak eers 'n skakel.",
    "Verwerken… (dit kan enkele minuten duren)":"Verwerk… (dit kan 'n paar minute duur)",
    "Verwerken mislukt.":"Verwerking het misluk.","Kies eerst een bestand.":"Kies eers 'n lêer.",
    "Wat wil je met deze preek?":"Wat wil jy met hierdie preek doen?",
    "Er wordt pas AI gebruikt als je iets kiest.":"KI word eers gebruik wanneer jy iets kies.",
    "Preektekst":"Preekteks","Samenvatting":"Opsomming","Vragen voor groepen…":"Vrae vir groepe…","Dagstukjes":"Dagstukkies",
    "Bezig met genereren…":"Besig om te genereer…","Genereren mislukt.":"Genereer het misluk.",
    "Dagstukjes — naar wie?":"Dagstukkies — na wie?","Verstuur naar je lijst":"Stuur na jou lys",
    "Download PDF":"Laai PDF af","Beheer verzendlijst":"Bestuur versendlys","Versturen…":"Stuur…",
    "Verzonden naar":"Gestuur na","Het weekboekje naar alle bevestigde inschrijvers versturen?":"Stuur die boekie na alle bevestigde inskrywers?",
    "Vragen voor groepen":"Vrae vir groepe","Leeftijd":"Ouderdom","Aantal vragen":"Aantal vrae",
    "Soorten vragen":"Soorte vrae","Genereer vragen":"Genereer vrae","Kies minstens één soort vragen.":"Kies minstens een soort vraag.",
    "Vragen om de preek terug te halen":"Vrae om die preek te herroep","Verdiepende vragen over tekst en preek":"Verdiepende vrae oor teks en preek",
    "Vragen om tekst en preek te laten landen":"Vrae om teks en preek te laat land","Vragen/opdrachten om handen en voeten te geven":"Vrae/opdragte om dit in praktyk te bring",
    "Preek automatisch op de achtergrond verwerken (dan staan de preken van afgelopen zondag klaar als je inlogt)":"Verwerk preke outomaties op die agtergrond (verlede Sondag se preke is klaar wanneer jy inteken)",
    "ochtend":"oggend","avond":"aand",
    "Aanmelden":"Skryf in","E-mailadres *":"E-posadres *","Ontvang de wekelijkse overdenkingen bij de preek.":"Ontvang weeklikse oordenkings by die preek.",
    "Telefoonnummer (optioneel)":"Telefoonnommer (opsioneel)","Hoe vaak wil je ontvangen?":"Hoe gereeld wil jy dit ontvang?",
    "Eén keer per week (hele weekboekje ineens)":"Een keer per week (volledige boekie)",
    "Dagelijks (één overdenking per dag)":"Daagliks (een oordenking per dag)",
    "Vul je e-mailadres in.":"Vul jou e-posadres in.","Kies je taal":"Kies jou taal"
    ,"Bekijk eerst de demo →":"Bekyk eers die demo →"
    ,"AfterSermon maakt van je zondagse preek automatisch een weekboekje: een korte samenvatting en zeven dagoverdenkingen met vragen voor volwassenen en kinderen — en mailt die elke week naar je gemeenteleden.":"AfterSermon verander Sondag se preek outomaties in ’n weekboekie: ’n kort opsomming en sewe daaglikse oordenkings met vrae vir volwassenes en kinders — elke week aan jou gemeente gestuur."
    ,"Koppel je YouTube- of Kerkdienstgemist-kanaal en het gaat vanzelf. Log in of maak een account om te beginnen.":"Koppel jou YouTube- of Kerkdienstgemist-kanaal en die res gebeur outomaties. Meld aan of skep ’n rekening om te begin."
    ,"Plak een kanaal (YouTube-kanaal of Kerkdienstgemist-kerk) om alle diensten te zien, of een directe link naar één preek.":"Plak ’n kanaal (YouTube of Kerkdienstgemist) om alle dienste te laai, of plak ’n direkte skakel om een preek te verwerk."
    ,"Laden":"Laai","Beschikbare diensten":"Beskikbare dienste","Vernieuwen":"Verfris"
    ,"Diensten & verzending":"Dienste en versending","Scan nu op nieuwe diensten":"Soek vir nuwe dienste"
    ,"Gevonden op het kanaal":"Op die kanaal gevind","Verwerking & verzending":"Verwerking en versending"
    ,"Verwerkt":"Verwerk","Wordt gecontroleerd":"Word nagegaan"
    ,"Vul hierboven een kanaallink in. De diensten verschijnen hier automatisch.":"Vul ’n kanaalskakel hierbo in. Die dienste verskyn outomaties hier."
    ,"Kanaal wordt opgehaald…":"Kanaal word opgehaal…","Bezig met scannen…":"Besig om te soek…"
    ,"Nieuwe diensten worden gecontroleerd en verwerkt…":"Nuwe dienste word nagegaan en verwerk…"
    ,"Bedankt voor je aanmelding!":"Dankie vir jou inskrywing!"
    ,"Je e-mailadres is bevestigd. Vanaf nu ontvang je de overdenkingen van deze kerk volgens de gekozen frequentie.":"Jou e-posadres is bevestig. Van nou af ontvang jy hierdie kerk se oordenkings volgens jou gekose frekwensie."
    ,"We hopen dat ze je helpen om de boodschap van zondag mee te nemen in de week.":"Ons hoop dit help jou om Sondag se boodskap deur die week saam te dra."
    ,"Basisinstellingen":"Basiese instellings","Verzendlijst":"Inskrywers","Berichten":"Boodskappe"
    ,"Overdenkingen beheren":"Bestuur oordenkings","Te versturen":"Om te stuur","Reeds verstuurd":"Reeds gestuur"
    ,"Kanaal nu vernieuwen":"Verfris kanaal","Geen openstaande diensten":"Geen uitstaande dienste"
    ,"Nieuwe diensten uit de laatste vier weken verschijnen hier automatisch.":"Nuwe dienste van die afgelope vier weke verskyn outomaties hier."
    ,"Nog niets verstuurd":"Nog niks gestuur nie","Na de eerste verzending verschijnt hier de geschiedenis.":"Jou versendingsgeskiedenis verskyn hier ná die eerste versending."
    ,"Klaar voor verzending":"Gereed om te stuur","Klaar om te beoordelen":"Gereed vir beoordeling"
    ,"Nog te verwerken":"Nog nie verwerk nie","Openen & bewerken":"Maak oop en wysig"
    ,"Verwerken & bewerken":"Verwerk en wysig","Bekijken":"Bekyk"
    ,"Stel stap 1 t/m 3 één keer in. Daarna staan ze bij elke volgende preek automatisch op groen — dan hoef je alleen nog te controleren en te versturen.":"Stel stap 1–3 een keer op. Daarna word hulle outomaties groen vir elke volgende preek — jy hoef net na te gaan en te stuur."
    ,"Preek aanleveren":"Verskaf preek","Kies wat je wil maken":"Kies wat om te maak","Automatiseer het proces":"Outomatiseer die proses","Controleer en bewerk":"Gaan na en wysig","Verstuur":"Stuur"
    ,"Kies of lever eerst een preek aan bij stap 1.":"Kies of verskaf eers 'n preek by stap 1.","Beschikbaar zodra je de dagstukjes hebt gemaakt.":"Beskikbaar sodra jy die dagstukkies gemaak het."
    ,"Plak de link van je kanaal (dan halen we elke week de preek van afgelopen zondag zélf op) of van één preek. Of upload een bestand.":"Plak jou kanaal se skakel (dan haal ons elke week verlede Sondag se preek self op) of van een preek. Of laai 'n lêer op."
    ,"Verwerk":"Verwerk","of":"of","Upload":"Laai op","Automatisch via kanaal":"Outomaties via kanaal","Preek aangeleverd":"Preek verskaf","Kanaal ingesteld":"Kanaal opgestel"
    ,"Link controleren…":"Kontroleer skakel…","Geen dienst van afgelopen zondag gevonden — kies er zelf een.":"Geen diens van verlede Sondag gevind nie — kies self een.","Kon de link niet lezen.":"Kon nie die skakel lees nie.","Plak eerst een link.":"Plak eers 'n skakel."
    ,"Wil je dit voortaan automatisch?":"Wil jy dit voortaan outomaties hê?","Dan halen we elke week de preek van afgelopen zondag zelf op — jij hoeft niets meer aan te leveren.":"Dan haal ons elke week verlede Sondag se preek self op — jy hoef niks meer te verskaf nie."
    ,"Ja, automatisch ophalen":"Ja, haal outomaties op","Instellen…":"Stel op…","Kanaal gevonden.":"Kanaal gevind.","Automatisch ophalen staat aan. Volgende week staat de preek al klaar als je inlogt.":"Outomatiese ophaal is aan. Volgende week is die preek reeds gereed wanneer jy aanmeld."
    ,"Plak je kanaal-link":"Plak jou kanaal-skakel","Automatiseer":"Outomatiseer"
    ,"Preek(en) van afgelopen zondag — kies er één om mee verder te gaan.":"Preek(e) van verlede Sondag — kies een om mee voort te gaan.","Kon de lijst niet laden.":"Kon nie die lys laai nie.","Nog geen dienst van afgelopen zondag gevonden. Plak hierboven een preek- of kanaal-link.":"Nog geen diens van verlede Sondag gevind nie. Plak hierbo 'n preek- of kanaal-skakel."
    ,"Kies deze preek":"Kies hierdie preek","Verwerken":"Verwerk","Alle diensten tonen…":"Wys alle dienste…","Geen diensten gevonden.":"Geen dienste gevind nie."
    ,"Kies wat we van elke preek maken. Er wordt alleen AI gebruikt voor wat je aanvinkt.":"Kies wat ons van elke preek maak. KI word net gebruik vir wat jy merk.","Een weekboekje met een stukje per dag — dit versturen we naar je gemeenteleden.":"'n Weekboekie met 'n stukkie per dag — dít stuur ons aan jou gemeentelede.","Een korte samenvatting van de preek.":"'n Kort opsomming van die preek.","Gespreksvragen voor kringen en gezinnen.":"Gespreksvrae vir groepe en gesinne.","De volledige uitgeschreven preek.":"Die volledige uitgeskrewe preek."
    ,"Dagstukjes":"Dagstukkies","Samenvatting":"Opsomming","Vragen voor groepen":"Vrae vir groepe","Preektekst":"Preekteks","Kies minstens één.":"Kies ten minste een."
    ,"Wanneer gaat het wekelijks de deur uit?":"Wanneer gaan dit weekliks uit?","Elke week op":"Elke week op","om":"om","Controle vóór verzenden?":"Nagaan voor stuur?","Ik keur elke week eerst goed (ik krijg een mail)":"Ek keur elke week eers goed (ek kry 'n e-pos)","Volledig automatisch versturen":"Stuur heeltemal outomaties","Preken vooraf op de achtergrond verwerken (dan staan ze klaar als je inlogt)":"Verwerk preke vooraf op die agtergrond (dan is hulle gereed wanneer jy aanmeld)"
    ,"Beheer verzendlijst / QR-code":"Bestuur ontvangers / QR-kode","automatisch":"outomaties","met goedkeuring":"met goedkeuring","Meer opties (afzender, taal, bijbelvertaling, kleuren) vind je bij Instellingen.":"Meer opsies (sender, taal, Bybelvertaling, kleure) is by Instellings."
    ,"Maak en controleer het materiaal dat je bij stap 2 hebt gekozen.":"Maak en gaan die materiaal na wat jy by stap 2 gekies het.","Zet „Dagstukjes” aan bij stap 2 om te kunnen versturen.":"Skakel \"Dagstukkies\" aan by stap 2 om te kan stuur.","Download PDF":"Laai PDF af","Alleen beschikbaar bij audio/video-preken.":"Slegs beskikbaar by oudio/video-preke.","Maak samenvatting":"Maak opsomming","Stel vragen samen…":"Stel vrae saam…","Maak dagstukjes":"Maak dagstukkies","Bezig met genereren…":"Besig om te genereer…","Genereren mislukt.":"Genereer het misluk.","Download weekboekje (PDF)":"Laai weekboekie af (PDF)"
    ,"Stuur het weekboekje naar je gemeenteleden.":"Stuur die weekboekie aan jou gemeentelede.","Verstuur naar mijn lijst":"Stuur na my lys","Het weekboekje naar alle bevestigde inschrijvers versturen?":"Stuur die weekboekie aan alle bevestigde intekenaars?","Versturen mislukt.":"Stuur het misluk.","Verzonden naar":"Gestuur aan","Verzonden":"Gestuur","Beheer verzendlijst / QR":"Bestuur ontvangers / QR"
    ,"Plak de link van je kanaal of van één preek — of upload een bestand. Hoe en naar wie het verstuurd wordt, stel je in bij stap 3.":"Plak jou kanaal-skakel of van een preek — of laai 'n lêer op. Hoe en aan wie dit gestuur word, stel jy by stap 3.","Verwerken…":"Verwerk…","Opslaan en verder":"Stoor en gaan voort"
    ,"Naar wie gaat het?":"Aan wie gaan dit?","De dagstukjes gaan naar je verzendlijst; jij krijgt zelf altijd een kopie ter controle op je eigen mailadres. Deel een inschrijflink of QR-code zodat gemeenteleden zich aanmelden.":"Die dagstukkies gaan na jou ontvangerslys; jy kry altyd self 'n kopie ter kontrole op jou eie e-posadres. Deel 'n inskrywingskakel of QR-kode sodat lede kan inteken."
    ,"Kleur en logo (voor de e-mails en boekjes)":"Kleur en logo (vir die e-posse en boekies)","Accentkleur":"Aksentkleur","Logo":"Logo","Logo verwijderen":"Verwyder logo","Logo opgeslagen.":"Logo gestoor.","Verwijderen mislukt.":"Verwydering het misluk.","Uploaden mislukt.":"Oplaai het misluk."
    ,"Nog meer opties (afzender, taal, bijbelvertaling, toon) vind je bij Instellingen.":"Nog meer opsies (sender, taal, Bybelvertaling, toon) is by Instellings.","Automatisch ophalen":"Haal outomaties op","Preken komen automatisch van je kanaal. Volgende week staat de preek klaar als je inlogt.":"Preke kom outomaties van jou kanaal. Volgende week is die preek gereed wanneer jy aanmeld.","Wil je dit voortaan automatisch? Dan halen we elke week de preek van afgelopen zondag zelf op — jij hoeft niets meer aan te leveren.":"Wil jy dit voortaan outomaties hê? Dan haal ons elke week verlede Sondag se preek self op — jy hoef niks meer te verskaf nie.","De preek wordt nog verwerkt — dit vult zich vanzelf zodra het klaar is.":"Die preek word nog verwerk — dit vul self in sodra dit gereed is."
    ,"Maandag":"Maandag","Dinsdag":"Dinsdag","Woensdag":"Woensdag","Donderdag":"Donderdag","Vrijdag":"Vrydag","Zaterdag":"Saterdag","Zondag":"Sondag"
    ,"Bekijk de preektekst":"Bekyk die preekteks","Ruw transcript":"Rou transkripsie","Opgeschoonde preektekst":"Opgeskoonde preekteks","Bewerk hieronder en sla op; de PDF gebruikt jouw versie.":"Wysig hieronder en stoor; die PDF gebruik jou weergawe.","Titel":"Titel","Bijbelgedeelte":"Skrifgedeelte","Samenvatting":"Opsomming","Dag":"Dag","Bijbeltekst":"Bybelteks","Gedachte":"Oordenking","Vraag (volwassenen)":"Vraag (volwassenes)","Vraag (kinderen)":"Vraag (kinders)","Wijzigingen opslaan":"Stoor wysigings","Opgeslagen ✓":"Gestoor ✓","Opnieuw genereren":"Genereer weer","Weet je het zeker? Je bewerkingen gaan verloren.":"Is jy seker? Jou wysigings gaan verlore.","Laden…":"Laai…","Kon niet laden.":"Kon nie laai nie.","Nog niet gemaakt.":"Nog nie gemaak nie."
    ,"Wat gebeurt er met elke uitvoer?":"Wat gebeur met elke uitset?","Per onderdeel dat je in stap 2 koos: automatisch meesturen in de wekelijkse mail naar je verzendlijst, of alleen zelf maken en downloaden bij stap 4.":"Vir elke item wat jy in stap 2 gekies het: stuur dit outomaties saam in die weeklikse e-pos na jou ontvangerslys, of maak en laai dit net self af by stap 4.","Automatisch naar verzendlijst":"Outomaties na ontvangerslys","Alleen downloaden (stap 4)":"Net aflaai (stap 4)","Naar je verzendlijst: gemeenteleden schrijven zich in via een link/QR; jij krijgt zelf altijd een controle-kopie.":"Na jou ontvangerslys: lidmate teken in via 'n skakel/QR; jy kry self altyd 'n nasienkopie."
    ,"Wanneer krijgen de groepen de vragen?":"Wanneer kry die groepe die vrae?","Elke week, samen met de rest":"Elke week, saam met die res","Op vaste datums":"Op vaste datums","Voeg de datums toe waarop de groepsvragen worden verstuurd.":"Voeg die datums by waarop die groepsvrae gestuur word.","Nog geen datums.":"Nog geen datums nie.","Datum toevoegen":"Voeg datum by"
  };
  let current = "nl";
  const base = new WeakMap();
  function detected() {
    const v = (localStorage.getItem("afters_language") || navigator.language || "en").slice(0,2).toLowerCase();
    return languages[v] ? v : "en";
  }
  function translate(root=document.body) {
    if (!root) return;
    const walker=document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let n;
    while((n=walker.nextNode())) {
      if (!n.parentElement || ["SCRIPT","STYLE"].includes(n.parentElement.tagName)) continue;
      if (!base.has(n)) base.set(n,n.nodeValue);
      const raw=base.get(n), trimmed=raw.trim(), table=current==="en"?en:current==="af"?af:{};
      if(table[trimmed]) n.nodeValue=raw.replace(trimmed,table[trimmed]);
    }
    document.documentElement.lang=current;
    document.querySelectorAll(".language-switch button").forEach(b=>b.classList.toggle("active",b.dataset.lang===current));
  }
  function text(raw) {
    const table=current==="en"?en:current==="af"?af:{};
    return table[raw] || raw;
  }
  function set(code, remember=false) {
    current = code==="auto" ? detected() : (languages[code] ? code : detected());
    if(remember) localStorage.setItem("afters_language",current);
    translate();
  }
  function mount() {
    if(document.querySelector(".language-switch")) return;
    const box=document.createElement("div"); box.className="language-switch"; box.setAttribute("aria-label","Kies je taal");
    Object.entries(languages).forEach(([code,x])=>{
      const b=document.createElement("button"); b.type="button"; b.dataset.lang=code;
      b.title=x.name; b.setAttribute("aria-label",x.name); b.textContent=x.flag+" "+code.toUpperCase();
      b.onclick=()=>set(code,true); box.appendChild(b);
    });
    document.body.prepend(box); set("auto");
    new MutationObserver(()=>translate()).observe(document.body,{childList:true,subtree:true});
  }
  document.addEventListener("DOMContentLoaded",mount);
  return {languages,set,translate,detected,text,get current(){return current;}};
})();
