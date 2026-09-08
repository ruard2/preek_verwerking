"""Transactionele e-mail via Brevo (verificatie, wachtwoord-reset).

Zonder BREVO_API_KEY wordt niets verzonden maar de inhoud (incl. link) naar de
console gelogd — handig voor lokale ontwikkeling en testen.
"""

import json
import os
import urllib.error
import urllib.request

API = "https://api.brevo.com/v3/smtp/email"


def _afzender(van_naam=None):
    # Eén geverifieerd afzenderadres (van jouw domein) voor alle kerken; de
    # weergavenaam is per kerk anders. BREVO_SENDER_NAAM is alleen een fallback
    # voor systeemmails (verificatie/reset).
    return {
        "name": van_naam or os.environ.get("BREVO_SENDER_NAAM", "Preekverwerker"),
        "email": os.environ.get("BREVO_SENDER_EMAIL", "no-reply@example.com"),
    }


def verzend(naar_email, onderwerp, html, tekst=None, van_naam=None, antwoord_naar=None):
    """Verstuur één e-mail. Geeft True bij verzonden, False bij (dev-)fallback.

    van_naam: weergavenaam van de afzender (meestal de kerknaam).
    antwoord_naar: Reply-To-adres (meestal het e-mailadres van de kerk).
    """
    sleutel = os.environ.get("BREVO_API_KEY")
    if not sleutel:
        print(
            f"\n[BREVO dev-fallback] Geen BREVO_API_KEY.\n"
            f"  Van:        {van_naam or '(standaard)'}\n"
            f"  Aan:        {naar_email}\n"
            f"  Antwoord:   {antwoord_naar or '-'}\n"
            f"  Onderwerp:  {onderwerp}\n"
            f"  Tekst:      {tekst or _plat(html)}\n"
        )
        return False

    payload = {
        "sender": _afzender(van_naam),
        "to": [{"email": naar_email}],
        "subject": onderwerp,
        "htmlContent": html,
    }
    if antwoord_naar:
        payload["replyTo"] = {"email": antwoord_naar}
    if tekst:
        payload["textContent"] = tekst
    import logging
    _log = logging.getLogger("aftersermon.brevo")

    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": sleutel,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
            body = r.read().decode("utf-8", errors="replace")
        _log.info(f"Brevo HTTP {status} → aan={naar_email} onderwerp={onderwerp!r} body={body[:200]}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        _log.error(f"Brevo HTTP {exc.code} FOUT → aan={naar_email} body={body[:400]}")
        raise
    return True


def _plat(html):
    import re

    return re.sub(r"<[^>]+>", "", html or "").strip()
