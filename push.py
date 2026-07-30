"""Web-push (PWA-meldingen) via het Web Push Protocol.

VAPID-sleutels komen uit de omgeving:
- VAPID_PUBLIC_KEY  : base64url (applicationServerKey voor de browser)
- VAPID_PRIVATE_KEY : base64 van de PEM (één regel, veilig als env-var)
- VAPID_SUBJECT     : mailto:... (contact voor pushdiensten)

Genereer nieuwe sleutels met:  python -m push
"""

import base64
import json
import os

_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:info@aftersermon.online")


def _publiek():
    return os.environ.get("VAPID_PUBLIC_KEY", "")


def _prive_pem():
    b64 = os.environ.get("VAPID_PRIVATE_KEY", "")
    if not b64:
        return None
    try:
        pem = base64.b64decode(b64).decode()
        if "BEGIN" in pem:
            return pem
    except Exception:  # noqa: BLE001
        pass
    return b64  # misschien al een PEM


def beschikbaar():
    return bool(_publiek() and _prive_pem())


def publieke_sleutel():
    return _publiek()


def stuur(abonnement, titel, tekst, url="/"):
    """Stuur één melding. Werpt PushVerlopen als het abonnement dood is (404/410)."""
    from pywebpush import WebPushException, webpush

    if not beschikbaar():
        raise RuntimeError("Web-push is niet ingesteld (VAPID-sleutels ontbreken).")
    try:
        return webpush(
            subscription_info=abonnement,
            data=json.dumps({"title": titel, "body": tekst, "url": url}),
            vapid_private_key=_prive_pem(),
            vapid_claims={"sub": _SUBJECT},
        )
    except WebPushException as fout:
        code = getattr(getattr(fout, "response", None), "status_code", None)
        if code in (404, 410):
            raise PushVerlopen() from None
        raise


class PushVerlopen(Exception):
    """Het push-abonnement bestaat niet meer (browser/afmelding)."""


def _genereer_en_print():
    from cryptography.hazmat.primitives import serialization
    from py_vapid import Vapid01

    v = Vapid01()
    v.generate_keys()
    pem = v.private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = v.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    print("VAPID_PUBLIC_KEY=" + base64.urlsafe_b64encode(pub).rstrip(b"=").decode())
    print("VAPID_PRIVATE_KEY=" + base64.b64encode(pem.encode()).decode())


if __name__ == "__main__":
    _genereer_en_print()
