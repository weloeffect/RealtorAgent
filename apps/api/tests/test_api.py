def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["mode"] == "local-mock"


def test_property_search_is_deterministic(client):
    response = client.get(
        "/api/properties",
        params={"city": "Paris", "transaction_type": "rent", "bedrooms_min": 2},
    )
    assert response.status_code == 200
    assert [item["external_ref"] for item in response.json()] == ["PAR-001"]


def test_booking_requires_confirmation_and_is_idempotent(client):
    property_record = client.get("/api/properties", params={"city": "Lyon"}).json()[0]
    slot = client.get(f"/api/properties/{property_record['id']}/slots").json()[0]
    lead = client.post(
        "/api/leads",
        json={"name": "Alex Martin", "contact_consent_status": "declined"},
    ).json()
    payload = {
        "slot_id": slot["id"],
        "lead_id": lead["id"],
        "idempotency_key": "browser-test-001",
        "confirmed": False,
    }
    assert client.post("/api/viewings", json=payload).status_code == 422
    payload["confirmed"] = True
    first = client.post("/api/viewings", json=payload)
    second = client.post("/api/viewings", json=payload)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    another_lead = client.post(
        "/api/leads",
        json={"name": "Sam Dupont", "contact_consent_status": "declined"},
    ).json()
    payload["lead_id"] = another_lead["id"]
    assert client.post("/api/viewings", json=payload).status_code == 409


def test_text_conversation_collects_then_searches(client):
    first = client.post(
        "/api/conversations/message",
        json={"session_id": "test", "message": "Hello"},
    )
    assert first.json()["state"] == "discovery"
    second = client.post(
        "/api/conversations/message",
        json={"session_id": "test", "message": "I want to rent in Paris under 3000"},
    )
    assert second.json()["state"] == "present_results"
    assert second.json()["properties"][0]["external_ref"] == "PAR-001"
