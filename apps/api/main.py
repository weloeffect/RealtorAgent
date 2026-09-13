from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from packages.domain.database import Base, SessionLocal, engine, get_session
from packages.domain.schemas import (
    BookingCreate,
    BookingRead,
    ConversationMessage,
    ConversationReply,
    LeadCreate,
    LeadRead,
    PropertyRead,
    PropertySearch,
    ViewingSlotRead,
)
from packages.domain.seed import seed_database
from packages.domain.service import (
    ConfirmationRequiredError,
    ConflictError,
    NotFoundError,
    RealEstateService,
)
from packages.tools.conversation import MockConversationAgent

conversation_agent = MockConversationAgent()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_database(session)
    yield


app = FastAPI(
    title="Real Estate Voice Agent API",
    version="0.1.0",
    description="Provider-free local MVP using synthetic data.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def service(session: Session = Depends(get_session)) -> RealEstateService:
    return RealEstateService(session)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "local-mock"}


@app.get("/api/properties", response_model=list[PropertyRead])
def list_properties(
    city: str | None = None,
    transaction_type: str | None = None,
    budget_min: float | None = Query(None, ge=0),
    budget_max: float | None = Query(None, ge=0),
    bedrooms_min: int | None = Query(None, ge=0, le=20),
    area_min_m2: int | None = Query(None, ge=0),
    amenities: list[str] = Query(default=[]),
    app_service: RealEstateService = Depends(service),
):
    try:
        filters = PropertySearch(
            city=city,
            transaction_type=transaction_type,
            budget_min=budget_min,
            budget_max=budget_max,
            bedrooms_min=bedrooms_min,
            area_min_m2=area_min_m2,
            amenities=amenities,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    return app_service.search_properties(filters)


@app.get("/api/properties/{property_id}", response_model=PropertyRead)
def get_property(property_id: str, app_service: RealEstateService = Depends(service)):
    try:
        return app_service.get_property(property_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.post("/api/leads", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(payload: LeadCreate, app_service: RealEstateService = Depends(service)):
    return app_service.create_lead(payload)


@app.get("/api/properties/{property_id}/slots", response_model=list[ViewingSlotRead])
def list_slots(property_id: str, app_service: RealEstateService = Depends(service)):
    try:
        return app_service.get_slots(property_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.post("/api/viewings", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_viewing(payload: BookingCreate, app_service: RealEstateService = Depends(service)):
    try:
        return app_service.book_viewing(payload)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ConfirmationRequiredError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@app.post("/api/conversations/message", response_model=ConversationReply)
def conversation_message(
    payload: ConversationMessage, session: Session = Depends(get_session)
) -> ConversationReply:
    return conversation_agent.respond(session, payload.session_id, payload.message)
