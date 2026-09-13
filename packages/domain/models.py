from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def uuid4_str() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class TransactionType(StrEnum):
    sale = "sale"
    rent = "rent"


class SlotStatus(StrEnum):
    available = "available"
    booked = "booked"


class Agency(Base):
    __tablename__ = "agencies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    name: Mapped[str] = mapped_column(String(120))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Paris")
    default_language: Mapped[str] = mapped_column(String(16), default="en")


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    external_ref: Mapped[str] = mapped_column(String(40), unique=True)
    transaction_type: Mapped[TransactionType] = mapped_column(Enum(TransactionType))
    property_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    address_display: Mapped[str] = mapped_column(String(180))
    city: Mapped[str] = mapped_column(String(80), index=True)
    postal_code: Mapped[str] = mapped_column(String(16))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    bedrooms: Mapped[int] = mapped_column(Integer)
    bathrooms: Mapped[int] = mapped_column(Integer)
    area_m2: Mapped[int] = mapped_column(Integer)
    amenities: Mapped[str] = mapped_column(Text, default="")
    available_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    slots: Mapped[list[ViewingSlot]] = relationship(back_populates="property")


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    agency_id: Mapped[str] = mapped_column(ForeignKey("agencies.id"), index=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone_e164: Mapped[str | None] = mapped_column(String(24), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(16), default="en")
    contact_consent_status: Mapped[str] = mapped_column(String(20), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ViewingSlot(Base):
    __tablename__ = "viewing_slots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    property_id: Mapped[str] = mapped_column(ForeignKey("properties.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[SlotStatus] = mapped_column(Enum(SlotStatus), default=SlotStatus.available)

    property: Mapped[Property] = relationship(back_populates="slots")


class Viewing(Base):
    __tablename__ = "viewings"
    __table_args__ = (
        UniqueConstraint("slot_id", name="uq_viewings_slot_id"),
        UniqueConstraint("idempotency_key", name="uq_viewings_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    slot_id: Mapped[str] = mapped_column(ForeignKey("viewing_slots.id"), index=True)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    confirmation_channel: Mapped[str] = mapped_column(String(20), default="browser")
    idempotency_key: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
