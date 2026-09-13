from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import Agency, Lead, Property, SlotStatus, Viewing, ViewingSlot
from .schemas import BookingCreate, LeadCreate, PropertySearch


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
        return viewing
