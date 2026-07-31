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
