from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Agency, Property, TransactionType, ViewingSlot


def synthetic_expansion(agency_id: str) -> list[Property]:
    expansion_cities = ["Nice", "Toulouse", "Lille", "Nantes", "Montpellier", "Strasbourg"]
    property_types = ["apartment", "house", "townhouse"]
    amenities = [
        "balcony,lift",
        "garden,parking",
        "furnished,bike storage",
        "workspace,cellar",
    ]
    listings = []
    for index in range(28):
        city = expansion_cities[index % len(expansion_cities)]
        transaction = TransactionType.rent if index % 2 == 0 else TransactionType.sale
        bedrooms = 1 + (index % 4)
        price = (
            Decimal(1500 + index * 75)
            if transaction == TransactionType.rent
            else Decimal(320000 + index * 18500)
        )
        listings.append(
            Property(
                agency_id=agency_id,
                external_ref=f"SYN-{index + 1:03d}",
                transaction_type=transaction,
                property_type=property_types[index % len(property_types)],
                title=f"Synthetic {bedrooms}-bedroom home in {city}",
                description=(
                    "Synthetic demonstration listing with verified structured attributes."
                ),
                address_display=f"Demo district {1 + index % 5}, {city}",
                city=city,
                postal_code=f"{10000 + index:05d}",
                price=price,
                currency="EUR",
                bedrooms=bedrooms,
                bathrooms=1 + (index % 2),
                area_m2=38 + bedrooms * 18 + index % 12,
                amenities=amenities[index % len(amenities)],
                available_from=datetime.now(UTC) + timedelta(days=index % 21),
            )
        )
    return listings


def add_slots(session: Session, listings: list[Property]) -> None:
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


def seed_database(session: Session) -> None:
    existing_agency = session.scalar(select(Agency).order_by(Agency.name))
    if existing_agency:
        existing_refs = set(session.scalars(select(Property.external_ref)).all())
        additions = [
            item
            for item in synthetic_expansion(existing_agency.id)
            if item.external_ref not in existing_refs
        ]
        add_slots(session, additions)
        session.commit()
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

    listings.extend(synthetic_expansion(agency.id))
    add_slots(session, listings)
    session.commit()
