import json

from apps.api import main
from packages.domain.database import get_session


def test_qwen_search_tool_uses_verified_inventory(client, monkeypatch):
    call = client.post(
        "/api/calls", json={"session_id": "qwen-tool-test", "mode": "browser_voice"}
    ).json()
    override = main.app.dependency_overrides[get_session]
    session_iterator = override()
    test_session = next(session_iterator)
    monkeypatch.setattr(main, "SessionLocal", lambda: test_session)
    try:
        result = json.loads(
            main.execute_qwen_tool(
                "search_properties",
                json.dumps(
                    {
                        "city": "Paris",
                        "transaction_type": "rent",
                        "budget_max": 3000,
                    }
                ),
                call["id"],
            )
        )
    finally:
        session_iterator.close()
    assert result[0]["external_ref"] == "PAR-001"
    detail = client.get(f"/api/calls/{call['id']}").json()
    assert detail["preferences"]["city"] == "Paris"
    assert detail["preferences"]["budget_max"] == "3000.00"
    assert detail["matches"][0]["property"]["external_ref"] == "PAR-001"
    assert detail["tools"][0]["tool_name"] == "search_properties"


def test_qwen_tool_rejects_unknown_tools():
    assert json.loads(main.execute_qwen_tool("delete_everything", "{}")) == {
        "error": "Unknown tool"
    }


def test_qwen_booking_requires_explicit_confirmation(client, monkeypatch):
    call = client.post(
        "/api/calls", json={"session_id": "voice-booking-test", "mode": "browser_voice"}
    ).json()
    property_record = client.get("/api/properties", params={"city": "Paris"}).json()[0]
    slot = client.get(f"/api/properties/{property_record['id']}/slots").json()[0]
    override = main.app.dependency_overrides[get_session]
    session_iterator = override()
    test_session = next(session_iterator)
    monkeypatch.setattr(main, "SessionLocal", lambda: test_session)
    try:
        result = json.loads(
            main.execute_qwen_tool(
                "book_viewing",
                json.dumps(
                    {
                        "slot_id": slot["id"],
                        "caller_name": "Private Name",
                        "caller_email": "private@example.com",
                        "confirmed": False,
                    }
                ),
                call["id"],
            )
        )
    finally:
        session_iterator.close()
    assert "confirmation" in result["error"].lower()
    detail = client.get(f"/api/calls/{call['id']}").json()
    assert detail["lead"]["name"] is None
    assert detail["tools"][0]["status"] == "error"
    assert "Private Name" not in detail["tools"][0]["arguments_redacted"]
    assert "private@example.com" not in detail["tools"][0]["arguments_redacted"]
