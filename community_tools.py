"""Server-side ticket exchange for the central Community Tools login."""

import json
import os
import secrets
import urllib.error
import urllib.request


def is_ingeschakeld() -> bool:
    """De centrale login is opt-in en staat zonder expliciete vlag volledig uit."""
    return os.environ.get("COMMUNITY_TOOLS_SSO_ENABLED", "").lower() == "true"


def beheer_is_ingeschakeld() -> bool:
    """De beheer-API is een afzonderlijke, opt-in koppeling."""
    return os.environ.get("COMMUNITY_TOOLS_MANAGEMENT_ENABLED", "").lower() == "true"


def verifieer_beheer_token(authorization: str | None) -> bool:
    """Vergelijk het server-to-server token zonder timing-informatie te lekken."""
    verwacht = os.environ.get("COMMUNITY_TOOLS_MANAGEMENT_SECRET", "")
    prefix = "Bearer "
    if not beheer_is_ingeschakeld() or not verwacht or not authorization:
        return False
    if not authorization.startswith(prefix):
        return False
    return secrets.compare_digest(authorization[len(prefix):], verwacht)


def wissel_ticket(ticket: str) -> dict:
    if not is_ingeschakeld():
        raise ValueError("Community Tools-login is niet ingeschakeld.")
    if not ticket.startswith("ctt_") or len(ticket) > 200:
        raise ValueError("Ongeldig toegangsticket.")

    base_url = _vereist("COMMUNITY_TOOLS_URL").rstrip("/")
    request = urllib.request.Request(
        f"{base_url}/api/integrations/exchange",
        data=json.dumps({"ticket": ticket}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {_vereist('COMMUNITY_TOOLS_CLIENT_SECRET')}",
            "Content-Type": "application/json",
            "X-Community-Tools-Client": _vereist("COMMUNITY_TOOLS_CLIENT_ID"),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            context = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError("Community Tools heeft toegang geweigerd.") from error

    if (
        context.get("product", {}).get("code") != "sermon_processing"
        or not context.get("user", {}).get("id")
        or not context.get("user", {}).get("email")
        or not context.get("organization", {}).get("id")
    ):
        raise ValueError("Onvolledige Community Tools-context.")
    return context


def _vereist(naam: str) -> str:
    waarde = os.environ.get(naam)
    if not waarde:
        raise RuntimeError(f"{naam} ontbreekt.")
    return waarde
