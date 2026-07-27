"""Uitbreidbare vaste teksten; preekinhoud volgt los hiervan de preektaal."""

LANGUAGES = {
    "nl": {
        "verify_subject": "Bevestig je AfterSermon-account", "welcome": "Welkom",
        "verify_account": "Bevestig je account via deze link:",
        "reset_subject": "Wachtwoord opnieuw instellen",
        "reset_body": "Stel via deze link een nieuw wachtwoord in (2 uur geldig):",
        "subscribe_subject": "Bevestig je aanmelding bij {church}",
        "subscribe_body": "Bevestig via deze link je aanmelding voor de overdenkingen:",
        "ignore": "Heb je je niet aangemeld? Dan kun je deze mail negeren.",
        "church": "de kerk", "receiving": "Je ontvangt dit van {church}.",
        "preferences": "Voorkeuren wijzigen", "unsubscribe": "Afmelden",
        "approval_subject": "Overdenking klaar om goed te keuren: {title}",
        "approval_ready": "Er staat een nieuwe overdenking klaar voor de dienst van {date}: {title}.",
        "review": "Bekijk en bewerk", "approve": "Goedkeuren en versturen",
    },
    "en": {
        "verify_subject": "Confirm your AfterSermon account", "welcome": "Welcome",
        "verify_account": "Confirm your account using this link:",
        "reset_subject": "Reset your password",
        "reset_body": "Set a new password using this link (valid for 2 hours):",
        "subscribe_subject": "Confirm your subscription to {church}",
        "subscribe_body": "Confirm your devotional subscription using this link:",
        "ignore": "If you did not subscribe, you can ignore this email.",
        "church": "the church", "receiving": "You receive this from {church}.",
        "preferences": "Change preferences", "unsubscribe": "Unsubscribe",
        "approval_subject": "Devotional ready for approval: {title}",
        "approval_ready": "A new devotional is ready for the service on {date}: {title}.",
        "review": "Review and edit", "approve": "Approve and send",
    },
    "af": {
        "verify_subject": "Bevestig jou AfterSermon-rekening", "welcome": "Welkom",
        "verify_account": "Bevestig jou rekening met hierdie skakel:",
        "reset_subject": "Stel jou wagwoord terug",
        "reset_body": "Stel met hierdie skakel ’n nuwe wagwoord in (2 uur geldig):",
        "subscribe_subject": "Bevestig jou inskrywing by {church}",
        "subscribe_body": "Bevestig jou inskrywing vir die oordenkings met hierdie skakel:",
        "ignore": "As jy nie ingeskryf het nie, kan jy hierdie e-pos ignoreer.",
        "church": "die kerk", "receiving": "Jy ontvang dit van {church}.",
        "preferences": "Verander voorkeure", "unsubscribe": "Teken uit",
        "approval_subject": "Oordenking gereed vir goedkeuring: {title}",
        "approval_ready": "’n Nuwe oordenking is gereed vir die diens van {date}: {title}.",
        "review": "Bekyk en wysig", "approve": "Keur goed en stuur",
    },
}

def valid(code, fallback="nl", allow_auto=True):
    code = (code or "").lower().split("-")[0]
    if allow_auto and code == "auto":
        return "auto"
    return code if code in LANGUAGES else fallback

def messages(code):
    return LANGUAGES[valid(code, "nl", allow_auto=False)]
