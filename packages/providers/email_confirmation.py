from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path

import httpx
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class EmailConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class EmailConfig:
    mode: str
    host: str
    port: int
    username: str
    password: str
    from_email: str
    use_ssl: bool
    start_tls: bool
    from_name: str
    brevo_api_key: str
    brevo_api_url: str

    @classmethod
    def from_env(cls) -> EmailConfig:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        username = os.getenv("SMTP_USERNAME", "").strip()
        return cls(
            mode=os.getenv("EMAIL_DELIVERY_MODE", "console").strip().lower(),
            host=os.getenv("SMTP_HOST", "").strip(),
            port=int(os.getenv("SMTP_PORT", "587")),
            username=username,
            password=os.getenv("SMTP_PASSWORD", "").strip(),
            from_email=os.getenv("BOOKING_FROM_EMAIL", "").strip() or username,
            use_ssl=os.getenv("SMTP_USE_SSL", "false").strip().lower() == "true",
            start_tls=os.getenv("SMTP_START_TLS", "true").strip().lower() == "true",
            from_name=os.getenv("BOOKING_FROM_NAME", "Horizon Homes").strip(),
            brevo_api_key=os.getenv("BREVO_API_KEY", "").strip(),
            brevo_api_url=os.getenv(
                "BREVO_API_URL", "https://api.brevo.com/v3/smtp/email"
            ).strip(),
        )


@dataclass(frozen=True)
class ViewingConfirmation:
    recipient: str
    booker_name: str
    property_title: str
    property_address: str
    starts_at: datetime
    ends_at: datetime
    booking_reference: str


class EmailConfirmationSender:
    def __init__(self, config: EmailConfig | None = None):
        self.config = config or EmailConfig.from_env()

    def send(self, confirmation: ViewingConfirmation) -> str:
        message = self._build_message(confirmation)
        if self.config.mode == "console":
            logger.info(
                "Simulated viewing confirmation email for booking %s",
                confirmation.booking_reference,
            )
            return "simulated"
        if self.config.mode == "brevo":
            return self._send_with_brevo(message, confirmation)
        if self.config.mode != "smtp":
            raise EmailConfigurationError(
                "EMAIL_DELIVERY_MODE must be console, smtp, or brevo"
            )
        if not self.config.host or not self.config.from_email:
            raise EmailConfigurationError("SMTP_HOST and BOOKING_FROM_EMAIL are required")

        smtp_class = smtplib.SMTP_SSL if self.config.use_ssl else smtplib.SMTP
        with smtp_class(self.config.host, self.config.port, timeout=15) as smtp:
            if not self.config.use_ssl and self.config.start_tls:
                smtp.starttls()
            if self.config.username:
                smtp.login(self.config.username, self.config.password)
            smtp.send_message(message)
        return "sent"

    def _send_with_brevo(
        self, message: EmailMessage, confirmation: ViewingConfirmation
    ) -> str:
        if not self.config.brevo_api_key or not self.config.from_email:
            raise EmailConfigurationError(
                "BREVO_API_KEY and BOOKING_FROM_EMAIL are required"
            )
        html_body = message.get_body(preferencelist=("html",))
        response = httpx.post(
            self.config.brevo_api_url,
            headers={
                "accept": "application/json",
                "api-key": self.config.brevo_api_key,
                "content-type": "application/json",
            },
            json={
                "sender": {
                    "name": self.config.from_name or "Horizon Homes",
                    "email": self.config.from_email,
                },
                "to": [
                    {
                        "name": confirmation.booker_name,
                        "email": confirmation.recipient,
                    }
                ],
                "subject": str(message["Subject"]),
                "htmlContent": html_body.get_content() if html_body else "",
                "tags": ["viewing-confirmation"],
            },
            timeout=15,
        )
        response.raise_for_status()
        return "sent"

    def _build_message(self, confirmation: ViewingConfirmation) -> EmailMessage:
        date_text = confirmation.starts_at.strftime("%A, %d %B %Y")
        time_text = confirmation.starts_at.strftime("%H:%M")
        end_time_text = confirmation.ends_at.strftime("%H:%M")
        message = EmailMessage()
        message["Subject"] = f"Viewing confirmed: {confirmation.property_title}"
        message["From"] = self.config.from_email or "Horizon Homes <demo@localhost>"
        message["To"] = confirmation.recipient
        message.set_content(
            f"Hello {confirmation.booker_name},\n\n"
            "Your property viewing is confirmed.\n\n"
            f"Property: {confirmation.property_title}\n"
            f"Address: {confirmation.property_address}\n"
            f"Date: {date_text}\n"
            f"Time: {time_text}–{end_time_text}\n"
            f"Booking reference: {confirmation.booking_reference}\n\n"
            "If you need to change the appointment, please contact Horizon Homes.\n"
        )
        html = (
            '<html><body style="margin:0;background:#f3efe6;color:#18201d;'
            'font-family:Arial,sans-serif">'
            '<div style="max-width:620px;margin:32px auto;background:#fffefa;'
            'border-radius:18px;overflow:hidden">'
            '<div style="background:#102b22;color:#fffefa;padding:30px 36px">'
            '<div style="color:#e7d4b4;font-size:12px;letter-spacing:2px">'
            "HORIZON HOMES</div>"
            '<h1 style="font-family:Georgia,serif;font-weight:400;margin:14px 0 0">'
            "Your viewing is confirmed.</h1></div>"
            '<div style="padding:34px 36px">'
            f"<p>Hello {escape(confirmation.booker_name)},</p>"
            "<p>We look forward to showing you this home.</p>"
            '<div style="margin:28px 0;padding:22px;border:1px solid #dedbd1;'
            'border-radius:12px">'
            '<strong style="font-family:Georgia,serif;font-size:20px">'
            f"{escape(confirmation.property_title)}</strong>"
            f'<p style="color:#68716d">{escape(confirmation.property_address)}</p>'
            f"<p><strong>{escape(date_text)}</strong><br>"
            f"{escape(time_text)}–{escape(end_time_text)}</p></div>"
            '<p style="color:#68716d;font-size:13px">Booking reference: '
            f"{escape(confirmation.booking_reference)}</p>"
            "</div></div></body></html>"
        )
        message.add_alternative(html, subtype="html")
        return message
