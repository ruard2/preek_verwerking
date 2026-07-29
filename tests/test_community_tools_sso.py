"""Regressietests voor identiteitsscheiding bij Community Tools SSO."""


def test_mislukte_sso_wist_bestaande_lokale_sessie(
    client,
    db,
    uniek_email,
    monkeypatch,
):
    from db import Church
    import auth
    import community_tools

    email = uniek_email("lokaal")
    kerk = Church(
        naam="Lokale kerk",
        email=email,
        wachtwoord_hash=auth.hash_wachtwoord("wachtwoord12"),
        email_geverifieerd=True,
    )
    db.add(kerk)
    db.commit()

    login = client.post(
        "/api/admin/login",
        json={"email": email, "wachtwoord": "wachtwoord12"},
    )
    assert login.status_code == 200
    assert client.get("/api/admin/analytics").status_code == 200

    def weiger_ticket(_ticket):
        raise ValueError("Ticket geweigerd")

    monkeypatch.setattr(community_tools, "wissel_ticket", weiger_ticket)
    response = client.get(
        "/api/community-tools/sso?ct_ticket=ctt_mislukt",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin?error=community-tools"
    assert client.get("/api/admin/analytics").status_code == 401
