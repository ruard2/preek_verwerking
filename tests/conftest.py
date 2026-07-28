"""Gedeelde testopzet: wegwerp-database en externe diensten afgeknepen.

BELANGRIJK: de omgevingsvariabelen worden hier gezet vóór het importeren van de
app-modules, want db.py/store.py lezen DATA_DIR en DATABASE_URL bij import.
"""

import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="aftersermon-test-")
os.environ["SECRET_KEY"] = "test-secret"
os.environ["OPENAI_API_KEY"] = "test-key"
os.environ["AUTOMATISERING"] = "uit"  # geen achtergrond-lus tijdens tests
for weg in ("DATABASE_URL", "SUPADATA_API_KEY", "BREVO_API_KEY", "RAILWAY_PUBLIC_DOMAIN"):
    os.environ.pop(weg, None)

import itertools

import pytest

_teller = itertools.count(1)


@pytest.fixture(autouse=True)
def _knijp_extern_af(monkeypatch):
    """Voorkom dat tests echte mail/OpenAI/transcriptie/netwerk raken."""
    import brevo
    import ratelimit

    ratelimit._hits.clear()  # schone rate-limit-teller per test
    verzonden = []
    monkeypatch.setattr(
        brevo, "verzend",
        lambda naar, onderwerp, html, **k: verzonden.append((naar, onderwerp)) or {"ok": True},
    )
    return verzonden


@pytest.fixture(scope="session")
def app():
    import main  # importeren draait init_db() met de test-DATA_DIR

    return main.app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    from db import SessionLocal

    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def uniek_email():
    """Uniek e-mailadres per aanroep (de test-DB wordt gedeeld)."""
    return lambda prefix="kerk": f"{prefix}{next(_teller)}@test.example"
