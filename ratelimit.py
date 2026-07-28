"""Eenvoudige in-memory rate-limiting tegen misbruik van publieke endpoints.

Volstaat voor één container. Beschermt vooral de inschrijf- en login-endpoints
tegen bots en brute force. Bij overschrijding: HTTP 429.
"""

import threading
import time

_hits = {}
_lock = threading.Lock()


def toegestaan(sleutel, max_per_uur):
    """True als deze sleutel nog binnen de limiet zit (en telt dit verzoek mee)."""
    nu = time.time()
    with _lock:
        tijden = [t for t in _hits.get(sleutel, []) if nu - t < 3600]
        if len(tijden) >= max_per_uur:
            _hits[sleutel] = tijden
            return False
        tijden.append(nu)
        _hits[sleutel] = tijden
        # Af en toe oude sleutels opruimen zodat het geheugen niet groeit.
        if len(_hits) > 5000:
            for k in [k for k, v in _hits.items() if not v or nu - v[-1] > 3600]:
                _hits.pop(k, None)
        return True


def ip_van(request):
    """Best-effort client-IP (achter een proxy: X-Forwarded-For)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "onbekend"
