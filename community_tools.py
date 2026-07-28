"""Server-side ticket exchange for the central Community Tools login."""

import json
import os
import urllib.error
import urllib.request


def wissel_ticket(ticket: str) -> dict:
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
