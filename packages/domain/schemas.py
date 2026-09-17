from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import SlotStatus, TransactionType


class PropertySearch(BaseModel):
    city: str | None = None
    transaction_type: TransactionType | None = None
    budget_min: Decimal | None = Field(None, ge=0)
    budget_max: Decimal | None = Field(None, ge=0)
    bedrooms_min: int | None = Field(None, ge=0, le=20)
    area_min_m2: int | None = Field(None, ge=0)
    amenities: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_budget(self) -> PropertySearch:
        if self.budget_min is not None and self.budget_max is not None:
            if self.budget_min > self.budget_max:
                raise ValueError("budget_min cannot exceed budget_max")
        return self


class PropertyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    external_ref: str
    transaction_type: TransactionType
    property_type: str
    title: str
    description: str
    address_display: str
    city: str
    postal_code: str
    price: Decimal
    currency: str
    bedrooms: int
    bathrooms: int
    area_m2: int
    amenities: str
    available_from: datetime


class LeadCreate(BaseModel):
    name: str | None = Field(None, max_length=120)
    phone_e164: str | None = Field(None, pattern=r"^\+[1-9]\d{7,14}$")
    email: str | None = Field(None, max_length=254)
    preferred_language: str = Field("en", max_length=16)
    contact_consent_status: str = Field("unknown", pattern="^(unknown|granted|declined)$")


class LeadRead(LeadCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    agency_id: str
    created_at: datetime


class LeadUpdate(BaseModel):
    name: str | None = Field(None, max_length=120)
    phone_e164: str | None = Field(None, pattern=r"^\+[1-9]\d{7,14}$")
    email: str | None = Field(None, max_length=254)
    contact_consent_status: str | None = Field(None, pattern="^(unknown|granted|declined)$")


class LeadPreferenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    city: str | None
    transaction_type: TransactionType | None
    budget_max: Decimal | None
    bedrooms_min: int | None
    updated_at: datetime


class ViewingSlotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    property_id: str
    starts_at: datetime
    ends_at: datetime
    status: SlotStatus


class BookingCreate(BaseModel):
    slot_id: str
    lead_id: str
    idempotency_key: str = Field(min_length=8, max_length=100)
    confirmed: bool
    call_id: str | None = None


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slot_id: str
    lead_id: str
    status: str
    confirmation_channel: str
    confirmation_email_status: str
    confirmation_email_sent_at: datetime | None
    idempotency_key: str
    created_at: datetime


class ConversationMessage(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=1000)
    call_id: str | None = None


class ConversationReply(BaseModel):
    session_id: str
    state: str
    reply: str
    properties: list[PropertyRead] = Field(default_factory=list)


class CallCreate(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    mode: str = Field(pattern="^(browser_text|browser_voice)$")


class CallTurnCreate(BaseModel):
    speaker: str = Field(pattern="^(caller|assistant)$")
    text: str = Field(min_length=1, max_length=10_000)
    interrupted: bool = False
    latency_ms: int | None = Field(None, ge=0, le=600_000)


class CallTurnRead(CallTurnCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sequence: int
    created_at: datetime


class ToolExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    tool_name: str
    arguments_redacted: str
    result_redacted: str
    status: str
    latency_ms: int
    created_at: datetime


class PropertyMatchRead(BaseModel):
    property: PropertyRead
    rank: int


class CallRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    lead_id: str
    booking_id: str | None
    mode: str
    status: str
    model_id: str | None
    summary: str | None
    disposition: str | None
    started_at: datetime
    ended_at: datetime | None


class CallDetail(CallRead):
    lead: LeadRead
    preferences: LeadPreferenceRead | None
    turns: list[CallTurnRead]
    tools: list[ToolExecutionRead]
    matches: list[PropertyMatchRead]
    booking: BookingRead | None
