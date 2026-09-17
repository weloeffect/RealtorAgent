from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import (
    Agency,
    CallSession,
    CallTurn,
    Lead,
    LeadPreference,
    Property,
    PropertyMatch,
    SlotStatus,
    Viewing,
    ViewingSlot,
)
from .schemas import (
    BookingCreate,
    CallCreate,
    CallTurnCreate,
    LeadCreate,
    LeadUpdate,
    PropertySearch,
)


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    pass


class ConfirmationRequiredError(Exception):
    pass


class RealEstateService:
    def __init__(self, session: Session):
        self.session = session

    def default_agency(self) -> Agency:
        agency = self.session.scalar(select(Agency).order_by(Agency.name))
        if agency is None:
            raise NotFoundError("No agency is configured")
        return agency

    def search_properties(self, filters: PropertySearch) -> list[Property]:
        query: Select[tuple[Property]] = select(Property)
        if filters.city:
            query = query.where(func.lower(Property.city) == filters.city.strip().lower())
        if filters.transaction_type:
            query = query.where(Property.transaction_type == filters.transaction_type)
        if filters.budget_min is not None:
            query = query.where(Property.price >= filters.budget_min)
        if filters.budget_max is not None:
            query = query.where(Property.price <= filters.budget_max)
        if filters.bedrooms_min is not None:
            query = query.where(Property.bedrooms >= filters.bedrooms_min)
        if filters.area_min_m2 is not None:
            query = query.where(Property.area_m2 >= filters.area_min_m2)
        for amenity in filters.amenities:
            query = query.where(func.lower(Property.amenities).contains(amenity.lower()))
        return list(self.session.scalars(query.order_by(Property.price, Property.id)).all())

    def get_property(self, property_id: str) -> Property:
        property_record = self.session.get(Property, property_id)
        if property_record is None:
            raise NotFoundError("Property not found")
        return property_record

    def create_lead(self, payload: LeadCreate) -> Lead:
        lead = Lead(agency_id=self.default_agency().id, **payload.model_dump())
        self.session.add(lead)
        self.session.commit()
        self.session.refresh(lead)
        return lead

    def get_lead(self, lead_id: str) -> Lead:
        lead = self.session.get(Lead, lead_id)
        if lead is None:
            raise NotFoundError("Lead not found")
        return lead

    def update_lead(self, lead_id: str, payload: LeadUpdate) -> Lead:
        lead = self.get_lead(lead_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(lead, field, value)
        self.session.commit()
        self.session.refresh(lead)
        return lead

    def create_call(self, payload: CallCreate, model_id: str | None = None) -> CallSession:
        existing = self.session.scalar(
            select(CallSession).where(CallSession.session_id == payload.session_id)
        )
        if existing is not None:
            return existing
        lead = Lead(agency_id=self.default_agency().id, contact_consent_status="unknown")
        self.session.add(lead)
        self.session.flush()
        call = CallSession(
            session_id=payload.session_id,
            agency_id=lead.agency_id,
            lead_id=lead.id,
            mode=payload.mode,
            model_id=model_id,
        )
        self.session.add(call)
        self.session.commit()
        self.session.refresh(call)
        return call

    def get_call(self, call_id: str) -> CallSession:
        call = self.session.get(CallSession, call_id)
        if call is None:
            raise NotFoundError("Call not found")
        return call

    def add_turn(self, call_id: str, payload: CallTurnCreate) -> CallTurn:
        self.get_call(call_id)
        sequence = self.session.scalar(
            select(func.coalesce(func.max(CallTurn.sequence), 0)).where(CallTurn.call_id == call_id)
        )
        turn = CallTurn(call_id=call_id, sequence=int(sequence) + 1, **payload.model_dump())
        self.session.add(turn)
        self.session.commit()
        self.session.refresh(turn)
        return turn

    def update_preferences(self, call: CallSession, filters: PropertySearch) -> LeadPreference:
        preference = self.session.get(LeadPreference, call.lead_id)
        if preference is None:
            preference = LeadPreference(lead_id=call.lead_id)
            self.session.add(preference)
        for field in ("city", "transaction_type", "budget_max", "bedrooms_min"):
            value = getattr(filters, field)
            if value is not None:
                setattr(preference, field, value)
        self.session.flush()
        return preference

    def record_matches(self, call_id: str, properties: list[Property]) -> None:
        existing = set(
            self.session.scalars(
                select(PropertyMatch.property_id).where(PropertyMatch.call_id == call_id)
            ).all()
        )
        for rank, property_record in enumerate(properties, start=1):
            if property_record.id not in existing:
                self.session.add(
                    PropertyMatch(call_id=call_id, property_id=property_record.id, rank=rank)
                )

    def complete_call(self, call_id: str) -> CallSession:
        call = self.get_call(call_id)
        turns = list(
            self.session.scalars(
                select(CallTurn).where(CallTurn.call_id == call_id).order_by(CallTurn.sequence)
            ).all()
        )
        caller_text = " ".join(turn.text for turn in turns if turn.speaker == "caller")
        call.summary = caller_text[:700] if caller_text else "No caller transcript was captured."
        call.status = "completed"
        call.ended_at = datetime.now(UTC)
        call.disposition = "viewing_booked" if call.booking_id else "enquiry"
        self.session.commit()
        self.session.refresh(call)
        return call

    def get_slots(self, property_id: str) -> list[ViewingSlot]:
        self.get_property(property_id)
        query = (
            select(ViewingSlot)
            .where(ViewingSlot.property_id == property_id)
            .where(ViewingSlot.status == SlotStatus.available)
            .order_by(ViewingSlot.starts_at)
        )
        return list(self.session.scalars(query).all())

    def book_viewing(self, payload: BookingCreate) -> Viewing:
        call = None
        if payload.call_id:
            call = self.get_call(payload.call_id)
            if call.lead_id != payload.lead_id:
                raise ConflictError("Booking lead does not belong to this call")
        existing = self.session.scalar(
            select(Viewing).where(Viewing.idempotency_key == payload.idempotency_key)
        )
        if existing is not None:
            if existing.slot_id != payload.slot_id or existing.lead_id != payload.lead_id:
                raise ConflictError("Idempotency key was already used for another booking")
            return existing
        if not payload.confirmed:
            raise ConfirmationRequiredError("Explicit confirmation is required")
        self.get_lead(payload.lead_id)
        slot = self.session.get(ViewingSlot, payload.slot_id)
        if slot is None:
            raise NotFoundError("Viewing slot not found")
        if slot.status != SlotStatus.available:
            raise ConflictError("Viewing slot is no longer available")

        slot.status = SlotStatus.booked
        viewing = Viewing(
            slot_id=slot.id,
            lead_id=payload.lead_id,
            idempotency_key=payload.idempotency_key,
        )
        self.session.add(viewing)
        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            repeated = self.session.scalar(
                select(Viewing).where(Viewing.idempotency_key == payload.idempotency_key)
            )
            if repeated is not None:
                return repeated
            raise ConflictError("Viewing slot is no longer available") from exc
        self.session.refresh(viewing)
        if call:
            call.booking_id = viewing.id
            self.session.commit()
        return viewing
