import community_tools


def test_management_api_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("COMMUNITY_TOOLS_MANAGEMENT_ENABLED", raising=False)
    monkeypatch.setenv("COMMUNITY_TOOLS_MANAGEMENT_SECRET", "test-secret")

    assert not community_tools.verifieer_beheer_token("Bearer test-secret")


def test_management_api_requires_exact_bearer_secret(monkeypatch):
    monkeypatch.setenv("COMMUNITY_TOOLS_MANAGEMENT_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_TOOLS_MANAGEMENT_SECRET", "test-secret")

    assert community_tools.verifieer_beheer_token("Bearer test-secret")
    assert not community_tools.verifieer_beheer_token("Bearer wrong")
    assert not community_tools.verifieer_beheer_token(None)


def test_management_endpoint_lists_only_product_admin_accounts(
    client, db, uniek_email, monkeypatch
):
    from db import Church, Medebeheerder, Subscriber
    import auth

    monkeypatch.setenv("COMMUNITY_TOOLS_MANAGEMENT_ENABLED", "true")
    monkeypatch.setenv("COMMUNITY_TOOLS_MANAGEMENT_SECRET", "test-secret")
    kerk = Church(
        naam="Testkerk",
        email=uniek_email("hoofd"),
        wachtwoord_hash=auth.hash_wachtwoord("wachtwoord12"),
        email_geverifieerd=True,
        community_tools_organization_id="central-org",
        community_tools_user_id="central-owner",
    )
    db.add(kerk)
    db.flush()
    db.add(
        Medebeheerder(
            kerk_id=kerk.id,
            naam="Redacteur",
            email=uniek_email("redacteur"),
            email_geverifieerd=True,
            community_tools_user_id="central-editor",
        )
    )
    db.add(
        Subscriber(
            kerk_id=kerk.id,
            naam="Privé abonnee",
            email=uniek_email("abonnee"),
        )
    )
    db.commit()

    unauthorized = client.get(
        "/api/community-tools/v1/organizations/central-org/users"
    )
    assert unauthorized.status_code == 401

    response = client.get(
        "/api/community-tools/v1/organizations/central-org/users",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "sermon_processing"
    assert [user["role"] for user in payload["users"]] == ["owner", "editor"]
    assert all(user["name"] != "Privé abonnee" for user in payload["users"])
