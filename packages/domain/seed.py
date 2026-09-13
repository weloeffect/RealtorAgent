from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Agency, Property, TransactionType, ViewingSlot


def seed_database(session: Session) -> None:
    if session.scalar(select(func.count()).select_from(Agency)):
        return

    agency = Agency(name="Horizon Homes", timezone="Europe/Paris", default_language="en")
    session.add(agency)
    session.flush()

    listings = [
        Property(
            agency_id=agency.id,
            external_ref="PAR-001",
            transaction_type=TransactionType.rent,
            property_type="apartment",
            title="Bright two-bedroom near Canal Saint-Martin",
            description="Quiet renovated apartment with balcony and lift.",
            address_display="Rue des Récollets, Paris 10e",
            city="Paris",
            postal_code="75010",
            price=Decimal("2350"),
            currency="EUR",
            bedrooms=2,
            bathrooms=1,
            area_m2=68,
            amenities="balcony,lift,bike storage",
            available_from=datetime.now(UTC) + timedelta(days=14),
        ),
        Property(
            agency_id=agency.id,
            external_ref="PAR-002",
            transaction_type=TransactionType.sale,
            property_type="apartment",
            title="Family apartment in Batignolles",
            description="Three-bedroom home with a courtyard-facing living room.",
            address_display="Rue des Moines, Paris 17e",
            city="Paris",
            postal_code="75017",
            price=Decimal("895000"),
            currency="EUR",
            bedrooms=3,
            bathrooms=2,
            area_m2=94,
            amenities="lift,cellar,courtyard",
            available_from=datetime.now(UTC),
        ),
        Property(
            agency_id=agency.id,
            external_ref="LYO-001",
            transaction_type=TransactionType.rent,
            property_type="apartment",
            title="Modern one-bedroom in Part-Dieu",
            description="Furnished apartment close to rail and tram connections.",
            address_display="Rue de la Villette, Lyon 3e",
            city="Lyon",
            postal_code="69003",
            price=Decimal("1250"),
            currency="EUR",
            bedrooms=1,
            bathrooms=1,
            area_m2=45,
            amenities="furnished,lift,concierge",
            available_from=datetime.now(UTC) + timedelta(days=7),
        ),
        Property(
            agency_id=agency.id,
            external_ref="BDX-001",
            transaction_type=TransactionType.sale,
            property_type="house",
            title="Three-bedroom house with garden",
            description="Renovated stone house with a private garden and workspace.",
            address_display="Caudéran, Bordeaux",
            city="Bordeaux",
            postal_code="33200",
            price=Decimal("585000"),
            currency="EUR",
            bedrooms=3,
            bathrooms=2,
            area_m2=122,
            amenities="garden,parking,workspace",
            available_from=datetime.now(UTC),
        ),
    ]
    session.add_all(listings)
    session.flush()

    base = datetime.now(UTC).replace(hour=10, minute=0, second=0, microsecond=0)
    for property_record in listings:
        for days, hour in ((2, 10), (3, 14), (5, 11)):
            starts_at = (base + timedelta(days=days)).replace(hour=hour)
            session.add(
                ViewingSlot(
                    property_id=property_record.id,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(minutes=30),
                )
            )
    session.commit()
