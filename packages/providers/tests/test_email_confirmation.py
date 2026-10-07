from datetime import UTC, datetime, timedelta

from packages.providers import email_confirmation
from packages.providers.email_confirmation import (
    EmailConfirmationSender,
    ViewingConfirmation,
)


class SuccessfulResponse:
    def raise_for_status(self):
        return None


def test_brevo_delivery_uses_https_api(monkeypatch):
    request: dict = {}

    def fake_post(url, **kwargs):
        request["url"] = url
        request.update(kwargs)
        return SuccessfulResponse()

    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "brevo")
    monkeypatch.setenv("BREVO_API_KEY", "test-api-key")
    monkeypatch.setenv("BOOKING_FROM_EMAIL", "verified@example.com")
    monkeypatch.setenv("BOOKING_FROM_NAME", "Horizon Homes")
    monkeypatch.setattr(email_confirmation.httpx, "post", fake_post)
    starts_at = datetime(2026, 10, 8, 10, 0, tzinfo=UTC)

    status = EmailConfirmationSender().send(
        ViewingConfirmation(
            recipient="booker@example.com",
            booker_name="Alex Martin",
            property_title="Riverside Residence",
            property_address="10 River Road, Paris",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(minutes=30),
            booking_reference="VIEW-123",
        )
    )

    assert status == "sent"
    assert request["url"] == "https://api.brevo.com/v3/smtp/email"
    assert request["headers"]["api-key"] == "test-api-key"
    assert request["json"]["sender"]["email"] == "verified@example.com"
    assert request["json"]["to"][0]["email"] == "booker@example.com"
    assert "Riverside Residence" in request["json"]["htmlContent"]
