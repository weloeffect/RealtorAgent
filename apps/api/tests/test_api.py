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
        json={
            "name": "Alex Martin",
            "email": "alex@example.com",
            "contact_consent_status": "declined",
        },
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
    assert first.json()["confirmation_email_status"] == "simulated"

    another_lead = client.post(
        "/api/leads",
        json={"name": "Sam Dupont", "contact_consent_status": "declined"},
    ).json()
    payload["lead_id"] = another_lead["id"]
    assert client.post("/api/viewings", json=payload).status_code == 409


def test_text_conversation_collects_then_searches(client):
    call = client.post(
        "/api/calls", json={"session_id": "text-search", "mode": "browser_text"}
    ).json()
    first = client.post(
        "/api/conversations/message",
        json={"session_id": "test", "call_id": call["id"], "message": "Hello"},
    )
    assert first.json()["state"] == "discovery"
    second = client.post(
        "/api/conversations/message",
        json={
            "session_id": "test",
            "call_id": call["id"],
            "message": "I want to rent in Paris under 3000",
        },
    )
    assert second.json()["state"] == "present_results"
    assert second.json()["properties"][0]["external_ref"] == "PAR-001"
    detail = client.get(f"/api/calls/{call['id']}").json()
    assert detail["preferences"]["city"] == "Paris"
    assert detail["matches"][0]["property"]["external_ref"] == "PAR-001"
    assert detail["tools"][0]["tool_name"] == "search_properties"


def test_text_conversation_understands_expanded_cities_and_word_bedrooms(client):
    response = client.post(
        "/api/conversations/message",
        json={
            "session_id": "nice-word-bedroom",
            "message": "I want to rent a two-bedroom in Nice under 4000",
        },
    )
    assert response.status_code == 200
    assert response.json()["state"] == "present_results"
    assert all(item["city"] == "Nice" for item in response.json()["properties"])
    assert all(item["bedrooms"] >= 2 for item in response.json()["properties"])


def test_call_lifecycle_persists_review_data(client):
    call = client.post(
        "/api/calls", json={"session_id": "review-test", "mode": "browser_text"}
    ).json()
    assert call["status"] == "active"

    lead = client.patch(
        f"/api/leads/{call['lead_id']}",
        json={"name": "Review Caller", "contact_consent_status": "declined"},
    )
    assert lead.status_code == 200
    for speaker, text in (
        ("caller", "I want to rent in Paris."),
        ("assistant", "I can help with verified listings."),
    ):
        response = client.post(
            f"/api/calls/{call['id']}/turns", json={"speaker": speaker, "text": text}
        )
        assert response.status_code == 200

    completed = client.post(f"/api/calls/{call['id']}/complete")
    assert completed.json()["status"] == "completed"
    detail = client.get(f"/api/calls/{call['id']}").json()
    assert detail["lead"]["name"] == "Review Caller"
    assert len(detail["turns"]) == 2
    assert "rent in Paris" in detail["summary"]
