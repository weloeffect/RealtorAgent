from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from dotenv import load_dotenv
from websockets.asyncio.client import ClientConnection, connect

QWEN_REALTIME_ENDPOINT = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"


class QwenConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class QwenRealtimeConfig:
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> QwenRealtimeConfig:
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
        model = os.getenv("QWEN_REALTIME_MODEL", "").strip()
        if not api_key or api_key == "replace-with-your-api-key":
            raise QwenConfigurationError("DASHSCOPE_API_KEY is not configured")
        if not model:
            raise QwenConfigurationError("QWEN_REALTIME_MODEL is not configured")
        return cls(api_key=api_key, model=model)

    @property
    def websocket_url(self) -> str:
        return f"{QWEN_REALTIME_ENDPOINT}?{urlencode({'model': self.model})}"


class QwenRealtimeProvider:
    def __init__(self, config: QwenRealtimeConfig | None = None):
        self.config = config or QwenRealtimeConfig.from_env()

    def connect(self):
        return connect(
            self.config.websocket_url,
            additional_headers={"Authorization": f"Bearer {self.config.api_key}"},
            open_timeout=15,
            close_timeout=5,
            max_size=16 * 1024 * 1024,
        )

    async def probe(self) -> dict:
        async with self.connect() as websocket:
            message = await asyncio.wait_for(websocket.recv(), timeout=15)
            event = json.loads(message)
            if event.get("type") == "error":
                error = event.get("error", {})
                raise ConnectionError(error.get("message", "Qwen returned an error"))
            if event.get("type") != "session.created":
                raise ConnectionError(f"Unexpected Qwen event: {event.get('type', 'unknown')}")
            await configure_real_estate_session(websocket)
            while True:
                configured = json.loads(await asyncio.wait_for(websocket.recv(), timeout=15))
                if configured.get("type") == "error":
                    error = configured.get("error", {})
                    raise ConnectionError(error.get("message", "Qwen rejected the session"))
                if configured.get("type") == "session.updated":
                    break
            return {
                "connected": True,
                "model": self.config.model,
                "event": configured["type"],
            }


async def configure_real_estate_session(websocket: ClientConnection) -> None:
    await websocket.send(
        json.dumps(
            {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "voice": "Tina",
                    "input_audio_format": "pcm",
                    "input_audio_transcription": {"model": "qwen3-asr-flash-realtime"},
                    "output_audio_format": "pcm",
                    "turn_detection": {"type": "server_vad", "silence_duration_ms": 600},
                    "tools": [
                        {
                            "type": "function",
                            "name": "search_properties",
                            "description": (
                                "Search the verified synthetic property inventory. Use this "
                                "before making any claim that a property matches a request."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "city": {"type": "string"},
                                    "transaction_type": {
                                        "type": "string",
                                        "enum": ["rent", "sale"],
                                    },
                                    "budget_max": {"type": "number", "minimum": 0},
                                    "bedrooms_min": {"type": "integer", "minimum": 0},
                                },
                                "required": ["city", "transaction_type"],
                            },
                        },
                        {
                            "type": "function",
                            "name": "book_viewing",
                            "description": (
                                "Book a verified viewing slot only after the caller explicitly "
                                "confirms the exact property, date, and time."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "slot_id": {"type": "string"},
                                    "caller_name": {"type": "string"},
                                    "caller_email": {"type": "string"},
                                    "confirmed": {"type": "boolean"},
                                },
                                "required": [
                                    "slot_id",
                                    "caller_name",
                                    "caller_email",
                                    "confirmed",
                                ],
                            },
                        },
                        {
                            "type": "function",
                            "name": "get_viewing_slots",
                            "description": (
                                "Return currently available viewing times for a property. "
                                "This does not create a booking."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {"property_id": {"type": "string"}},
                                "required": ["property_id"],
                            },
                        },
                    ],
                    "instructions": (
                        "You are the Horizon Homes real-estate voice concierge. "
                        "Tell callers this is an AI assistant. Ask whether they want to rent "
                        "or buy, their city, budget, and bedroom needs. Never invent listings, "
                        "prices, availability, legal advice, or completed bookings. Always call "
                        "search_properties for matching homes and get_viewing_slots for times. "
                        "This is a synthetic-data demo. Before book_viewing, repeat the exact "
                        "property, date, and time, collect and repeat the caller's email address, "
                        "and ask for an explicit yes. Never set confirmed to true without that "
                        "reply. Offer a human handoff on request."
                    ),
                },
            }
        )
    )
