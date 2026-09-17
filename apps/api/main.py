from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.domain.database import Base, SessionLocal, engine, get_session
from packages.domain.models import (
    CallSession,
    CallTurn,
    LeadPreference,
    Property,
    PropertyMatch,
    ToolExecution,
    Viewing,
    ViewingSlot,
)
from packages.domain.schemas import (
    BookingCreate,
    BookingRead,
    CallCreate,
    CallDetail,
    CallRead,
    CallTurnCreate,
    CallTurnRead,
    ConversationMessage,
    ConversationReply,
    LeadCreate,
    LeadRead,
    LeadUpdate,
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
from packages.providers.email_confirmation import (
    EmailConfirmationSender,
    ViewingConfirmation,
)
from packages.providers.qwen_realtime import (
    QwenConfigurationError,
    QwenRealtimeProvider,
    configure_real_estate_session,
)
from packages.tools.conversation import MockConversationAgent

conversation_agent = MockConversationAgent()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        seed_database(session)
    yield


app = FastAPI(
    title="Real Estate Voice Agent API",
    version="0.1.0",
    description="Local browser MVP using synthetic data and optional Qwen realtime voice.",
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


@app.patch("/api/leads/{lead_id}", response_model=LeadRead)
def update_lead(
    lead_id: str, payload: LeadUpdate, app_service: RealEstateService = Depends(service)
):
    try:
        return app_service.update_lead(lead_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.get("/api/properties/{property_id}/slots", response_model=list[ViewingSlotRead])
def list_slots(property_id: str, app_service: RealEstateService = Depends(service)):
    try:
        return app_service.get_slots(property_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.post("/api/viewings", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_viewing(payload: BookingCreate, session: Session = Depends(get_session)):
    app_service = RealEstateService(session)
    try:
        viewing = app_service.book_viewing(payload)
        return deliver_booking_confirmation(session, viewing)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except ConfirmationRequiredError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    except ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


def deliver_booking_confirmation(session: Session, viewing: Viewing) -> Viewing:
    if viewing.confirmation_email_status == "sent":
        return viewing
    app_service = RealEstateService(session)
    lead = app_service.get_lead(viewing.lead_id)
    slot = session.get(ViewingSlot, viewing.slot_id)
    property_record = session.get(Property, slot.property_id) if slot else None
    if not lead.email or slot is None or property_record is None:
        viewing.confirmation_email_status = "skipped"
        session.commit()
        return viewing
    try:
        delivery_status = EmailConfirmationSender().send(
            ViewingConfirmation(
                recipient=lead.email,
                booker_name=lead.name or "Guest",
                property_title=property_record.title,
                property_address=property_record.address_display,
                starts_at=slot.starts_at,
                ends_at=slot.ends_at,
                booking_reference=viewing.id,
            )
        )
        viewing.confirmation_email_status = delivery_status
        if delivery_status == "sent":
            viewing.confirmation_email_sent_at = datetime.now(UTC)
    except Exception:
        logger.exception("Viewing confirmation email delivery failed")
        viewing.confirmation_email_status = "failed"
    session.commit()
    session.refresh(viewing)
    return viewing


@app.post("/api/conversations/message", response_model=ConversationReply)
def conversation_message(
    payload: ConversationMessage, session: Session = Depends(get_session)
) -> ConversationReply:
    started = perf_counter()
    reply = conversation_agent.respond(session, payload.session_id, payload.message)
    if payload.call_id:
        app_service = RealEstateService(session)
        try:
            call = app_service.get_call(payload.call_id)
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        filters = conversation_agent.preferences_for(payload.session_id)
        if filters is not None:
            app_service.update_preferences(call, filters)
        matched_properties = [
            property_record
            for item in reply.properties
            if (property_record := session.get(Property, item.id)) is not None
        ]
        app_service.record_matches(call.id, matched_properties)
        if filters is not None and filters.city and filters.transaction_type:
            session.add(
                ToolExecution(
                    call_id=call.id,
                    tool_name="search_properties",
                    arguments_redacted=filters.model_dump_json(exclude_none=True),
                    result_redacted=json.dumps(
                        [item.model_dump(mode="json") for item in reply.properties]
                    ),
                    status="success",
                    latency_ms=int((perf_counter() - started) * 1000),
                )
            )
        session.commit()
    return reply


@app.post("/api/calls", response_model=CallRead, status_code=status.HTTP_201_CREATED)
def create_call(payload: CallCreate, app_service: RealEstateService = Depends(service)):
    model_id = (
        QwenRealtimeProvider().config.model if payload.mode == "browser_voice" else "local-mock"
    )
    return app_service.create_call(payload, model_id=model_id)


@app.get("/api/calls", response_model=list[CallRead])
def list_calls(limit: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)):
    query = select(CallSession).order_by(CallSession.started_at.desc()).limit(limit)
    return list(session.scalars(query).all())


@app.post("/api/calls/{call_id}/turns", response_model=CallTurnRead)
def add_call_turn(
    call_id: str,
    payload: CallTurnCreate,
    app_service: RealEstateService = Depends(service),
):
    try:
        return app_service.add_turn(call_id, payload)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.post("/api/calls/{call_id}/complete", response_model=CallRead)
def complete_call(call_id: str, app_service: RealEstateService = Depends(service)):
    try:
        return app_service.complete_call(call_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@app.get("/api/calls/{call_id}", response_model=CallDetail)
def get_call_detail(call_id: str, session: Session = Depends(get_session)):
    app_service = RealEstateService(session)
    try:
        call = app_service.get_call(call_id)
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    lead = app_service.get_lead(call.lead_id)
    preferences = session.get(LeadPreference, call.lead_id)
    turns = list(
        session.scalars(
            select(CallTurn).where(CallTurn.call_id == call.id).order_by(CallTurn.sequence)
        ).all()
    )
    tools = list(
        session.scalars(
            select(ToolExecution)
            .where(ToolExecution.call_id == call.id)
            .order_by(ToolExecution.created_at)
        ).all()
    )
    match_rows = session.execute(
        select(PropertyMatch, Property)
        .join(Property, Property.id == PropertyMatch.property_id)
        .where(PropertyMatch.call_id == call.id)
        .order_by(PropertyMatch.rank)
    ).all()
    booking = session.get(Viewing, call.booking_id) if call.booking_id else None
    return {
        **CallRead.model_validate(call).model_dump(),
        "lead": lead,
        "preferences": preferences,
        "turns": turns,
        "tools": tools,
        "matches": [
            {"rank": match.rank, "property": property_record}
            for match, property_record in match_rows
        ],
        "booking": booking,
    }


@app.websocket("/ws/qwen-realtime")
async def qwen_realtime(websocket: WebSocket) -> None:
    allowed_origins = {"http://localhost:3000", "http://127.0.0.1:3000"}
    if websocket.headers.get("origin") not in allowed_origins:
        await websocket.close(code=1008, reason="Origin not allowed")
        return
    await websocket.accept()
    call_id = websocket.query_params.get("call_id")
    try:
        provider = QwenRealtimeProvider()
        async with provider.connect() as upstream:
            initial_event = await upstream.recv()
            await websocket.send_text(initial_event)
            await configure_real_estate_session(upstream)

            async def forward_client_events() -> None:
                while True:
                    raw = await websocket.receive_text()
                    if len(raw) > 2 * 1024 * 1024:
                        await websocket.close(code=1009, reason="Event too large")
                        return
                    event = json.loads(raw)
                    allowed = {
                        "input_audio_buffer.append",
                        "input_audio_buffer.commit",
                        "input_audio_buffer.clear",
                        "response.create",
                        "response.cancel",
                    }
                    if event.get("type") not in allowed:
                        await websocket.send_json(
                            {"type": "proxy.error", "message": "Unsupported client event"}
                        )
                        continue
                    await upstream.send(raw)

            async def forward_qwen_events() -> None:
                async for raw in upstream:
                    await websocket.send_text(raw)
                    event = json.loads(raw)
                    if event.get("type") == "response.function_call_arguments.done":
                        result = execute_qwen_tool(
                            event.get("name", ""), event.get("arguments", "{}"), call_id
                        )
                        await websocket.send_json(
                            {
                                "type": "proxy.tool_result",
                                "name": event.get("name", ""),
                                "output": json.loads(result),
                            }
                        )
                        await upstream.send(
                            json.dumps(
                                {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "function_call_output",
                                        "call_id": event.get("call_id"),
                                        "output": result,
                                    },
                                }
                            )
                        )
                        await upstream.send(json.dumps({"type": "response.create"}))

            tasks = {
                asyncio.create_task(forward_client_events()),
                asyncio.create_task(forward_qwen_events()),
            }
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
    except WebSocketDisconnect:
        return
    except QwenConfigurationError as exc:
        await websocket.send_json({"type": "proxy.error", "message": str(exc)})
        await websocket.close(code=1011)
    except Exception:
        logger.exception("Qwen realtime proxy failed")
        await websocket.send_json(
            {"type": "proxy.error", "message": "Unable to connect to Qwen Realtime"}
        )
        await websocket.close(code=1011)


def execute_qwen_tool(name: str, raw_arguments: str, call_id: str | None = None) -> str:
    started = perf_counter()
    status_value = "success"
    payload: list | dict
    try:
        arguments = json.loads(raw_arguments)
    except (ValueError, TypeError) as exc:
        return json.dumps({"error": f"Invalid tool arguments: {exc}"})

    with SessionLocal() as session:
        app_service = RealEstateService(session)
        try:
            call = app_service.get_call(call_id) if call_id else None
            if name == "search_properties":
                filters = PropertySearch.model_validate(arguments)
                matches = app_service.search_properties(filters)[:5]
                if call:
                    app_service.update_preferences(call, filters)
                    app_service.record_matches(call.id, matches)
                payload = [
                    PropertyRead.model_validate(item).model_dump(mode="json") for item in matches
                ]
            elif name == "get_viewing_slots":
                slots = app_service.get_slots(arguments["property_id"])
                payload = [
                    ViewingSlotRead.model_validate(item).model_dump(mode="json") for item in slots
                ]
            elif name == "book_viewing":
                if call is None:
                    raise ValueError("A persisted call is required for voice booking")
                booking = app_service.book_viewing(
                    BookingCreate(
                        slot_id=arguments["slot_id"],
                        lead_id=call.lead_id,
                        call_id=call.id,
                        idempotency_key=f"voice:{call.id}:{arguments['slot_id']}",
                        confirmed=arguments.get("confirmed", False),
                    )
                )
                app_service.update_lead(
                    call.lead_id,
                    LeadUpdate(
                        name=arguments.get("caller_name"),
                        email=arguments.get("caller_email"),
                    ),
                )
                booking = deliver_booking_confirmation(session, booking)
                payload = BookingRead.model_validate(booking).model_dump(mode="json")
            else:
                payload = {"error": "Unknown tool"}
                status_value = "error"
        except (
            ValueError,
            KeyError,
            NotFoundError,
            ConflictError,
            ConfirmationRequiredError,
        ) as exc:
            payload = {"error": str(exc)}
            status_value = "error"

        if call_id:
            try:
                call = app_service.get_call(call_id)
            except NotFoundError:
                call = None
            if call is not None:
                safe_arguments = {
                    key: "[redacted]" if key in {"caller_name", "caller_email"} else value
                    for key, value in arguments.items()
                }
                execution = ToolExecution(
                    call_id=call.id,
                    tool_name=name,
                    arguments_redacted=json.dumps(safe_arguments),
                    result_redacted=json.dumps(payload),
                    status=status_value,
                    latency_ms=int((perf_counter() - started) * 1000),
                )
                session.add(execution)
                session.commit()
    return json.dumps(payload)
