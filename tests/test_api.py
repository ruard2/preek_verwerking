"""API-flows via TestClient: auth, inschrijven/bevestigen, rate-limiting, analytics."""

from sqlalchemy import select


def _registreer_en_verifieer(client, db, email):
    from db import Church, EmailToken

    r = client.post("/api/admin/register", json={
        "naam": "Kerk", "email": email, "wachtwoord": "wachtwoord12", "taal": "nl",
    })
    assert r.status_code == 200, r.text
    kerk = db.scalar(select(Church).where(Church.email == email))
    token = db.scalar(select(EmailToken).where(
        EmailToken.kerk_id == kerk.id, EmailToken.soort == "verify"
    ))
    assert client.get(f"/api/admin/verify?token={token.token}").status_code in (200, 303)
    return kerk.id


def _login(client, email):
    return client.post("/api/admin/login", json={"email": email, "wachtwoord": "wachtwoord12"})


def test_register_verify_login(client, db, uniek_email):
    email = uniek_email()
    _registreer_en_verifieer(client, db, email)
    assert _login(client, email).status_code == 200


def test_login_fout_wachtwoord(client, db, uniek_email):
    email = uniek_email()
    _registreer_en_verifieer(client, db, email)
    r = client.post("/api/admin/login", json={"email": email, "wachtwoord": "fout"})
    assert r.status_code == 400


def test_analytics_vereist_login(client):
    assert client.get("/api/admin/analytics").status_code == 401


def test_analytics_na_login(client, db, uniek_email):
    email = uniek_email()
    _registreer_en_verifieer(client, db, email)
    _login(client, email)
    r = client.get("/api/admin/analytics")
    assert r.status_code == 200
    data = r.json()
    assert data["inschrijvers_totaal"] == 0
    assert "verzonden_totaal" in data


def test_inschrijven_en_bevestigen(client, db, uniek_email):
    from db import Subscriber

    kerk_id = _registreer_en_verifieer(client, db, uniek_email())
    sub_email = uniek_email("lid")
    r = client.post("/api/inschrijven", json={
        "kerk_id": kerk_id, "email": sub_email, "frequentie": "wekelijks",
    })
    assert r.status_code == 200
    sub = db.scalar(select(Subscriber).where(Subscriber.email == sub_email))
    assert sub is not None and not sub.bevestigd
    client.get(f"/api/inschrijven/bevestig?token={sub.bevestig_token}", follow_redirects=False)
    db.refresh(sub)
    assert sub.bevestigd is True


def test_rate_limit_login(client):
    # loginlimiet is 20/uur per IP; het 21e verzoek moet 429 geven
    codes = [
        client.post("/api/admin/login", json={"email": "x@x.nl", "wachtwoord": "y"}).status_code
        for _ in range(22)
    ]
    assert 429 in codes
