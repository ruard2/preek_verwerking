"""Transactionele e-mail via Brevo (verificatie, wachtwoord-reset).

Zonder BREVO_API_KEY wordt niets verzonden maar de inhoud (incl. link) naar de
console gelogd — handig voor lokale ontwikkeling en testen.
"""

import json
import os
import urllib.request

API = "https://api.brevo.com/v3/smtp/email"


def _afzender():
    return {
        "name": os.environ.get("BREVO_SENDER_NAAM", "Preekverwerker"),
        "email": os.environ.get("BREVO_SENDER_EMAIL", "no-reply@example.com"),
    }


def verzend(naar_email, onderwerp, html, tekst=None):
    """Verstuur één e-mail. Geeft True bij verzonden, False bij (dev-)fallback."""
    sleutel = os.environ.get("BREVO_API_KEY")
    if not sleutel:
        print(
            f"\n[BREVO dev-fallback] Geen BREVO_API_KEY.\n"
            f"  Aan:        {naar_email}\n"
            f"  Onderwerp:  {onderwerp}\n"
            f"  Tekst:      {tekst or _plat(html)}\n"
        )
        return False

    payload = {
        "sender": _afzender(),
        "to": [{"email": naar_email}],
        "subject": onderwerp,
        "htmlContent": html,
    }
    if tekst:
        payload["textContent"] = tekst
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": sleutel,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    return True


def _plat(html):
    import re

    return re.sub(r"<[^>]+>", "", html or "").strip()
