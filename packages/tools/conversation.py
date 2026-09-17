from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.domain.models import TransactionType
from packages.domain.schemas import ConversationReply, PropertyRead, PropertySearch
from packages.domain.service import RealEstateService
from packages.domain.state_machine import ConversationSession, ConversationState


@dataclass
class SessionContext:
    machine: ConversationSession
    city: str | None = None
    transaction_type: TransactionType | None = None
    budget_max: int | None = None
    bedrooms_min: int | None = None
    last_property_ids: list[str] = field(default_factory=list)


class MockConversationAgent:
    """Deterministic text simulator used until a realtime model is configured."""

    def __init__(self) -> None:
        self.sessions: dict[str, SessionContext] = {}

    def reset(self) -> None:
        self.sessions.clear()

    def preferences_for(self, session_id: str) -> PropertySearch | None:
        context = self.sessions.get(session_id)
        if context is None:
            return None
        return PropertySearch(
            city=context.city,
            transaction_type=context.transaction_type,
            budget_max=context.budget_max,
            bedrooms_min=context.bedrooms_min,
        )

    def respond(self, session: Session, session_id: str, message: str) -> ConversationReply:
        context = self.sessions.setdefault(
            session_id, SessionContext(machine=ConversationSession(session_id=session_id))
        )
        normalized = message.lower().strip()

        if any(word in normalized for word in ("human", "agent", "person", "complaint")):
            if context.machine.state != ConversationState.HANDOFF:
                if ConversationState.HANDOFF in self._allowed(context):
                    context.machine.transition(ConversationState.HANDOFF)
            return self._reply(
                context,
                "I’ll arrange a human handoff. This local demo records the request "
                "but does not place a real call.",
            )

        if context.machine.state == ConversationState.GREETING:
            context.machine.transition(ConversationState.DISCOVERY)

        self._extract_preferences(context, normalized)
        missing = []
        if context.transaction_type is None:
            missing.append("whether you want to rent or buy")
        if context.city is None:
            missing.append("the city")
        if missing:
            return self._reply(
                context,
                f"Please tell me {' and '.join(missing)}. You can also include your "
                "maximum budget and minimum bedrooms.",
            )

        if context.machine.state == ConversationState.DISCOVERY:
            context.machine.transition(ConversationState.SEARCH)

        service = RealEstateService(session)
        results = service.search_properties(
            PropertySearch(
                city=context.city,
                transaction_type=context.transaction_type,
                budget_max=context.budget_max,
                bedrooms_min=context.bedrooms_min,
            )
        )
        context.last_property_ids = [item.id for item in results]
        if context.machine.state == ConversationState.SEARCH:
            if results:
                context.machine.transition(ConversationState.PRESENT_RESULTS)
            else:
                context.machine.transition(ConversationState.DISCOVERY)

        if not results:
            return self._reply(
                context,
                "I found no exact matches. Try a higher budget, fewer bedrooms, or another city.",
            )
        first = results[0]
        summary = (
            f"I found {len(results)} match{'es' if len(results) != 1 else ''}. "
            f"The first is {first.title}: {first.bedrooms} bedroom(s), {first.area_m2} m², "
            f"{first.price:.0f} {first.currency}. Select a listing below to view available slots."
        )
        return self._reply(context, summary, results)

    @staticmethod
    def _allowed(context: SessionContext) -> set[ConversationState]:
        from packages.domain.state_machine import ALLOWED_TRANSITIONS

        return ALLOWED_TRANSITIONS[context.machine.state]

    @staticmethod
    def _extract_preferences(context: SessionContext, text: str) -> None:
        cities = {
            "paris": "Paris",
            "lyon": "Lyon",
            "bordeaux": "Bordeaux",
            "nice": "Nice",
            "toulouse": "Toulouse",
            "lille": "Lille",
            "nantes": "Nantes",
            "montpellier": "Montpellier",
            "strasbourg": "Strasbourg",
        }
        for token, city in cities.items():
            if token in text:
                context.city = city
        if any(word in text for word in ("rent", "rental", "lease")):
            context.transaction_type = TransactionType.rent
        if any(word in text for word in ("buy", "purchase", "sale")):
            context.transaction_type = TransactionType.sale
        bedroom_words = {
            "studio": 0,
            "one": 1,
            "two": 2,
            "three": 3,
            "four": 4,
            "five": 5,
        }
        bedroom_match = re.search(
            r"(\d+|studio|one|two|three|four|five)[\s-]*(?:bed|bedroom)", text
        )
        if bedroom_match:
            bedroom_value = bedroom_match.group(1)
            context.bedrooms_min = (
                int(bedroom_value) if bedroom_value.isdigit() else bedroom_words[bedroom_value]
            )
        budget_match = re.search(r"(?:budget|max|under|up to)\D{0,12}([\d,.]+)\s*([km]?)", text)
        if budget_match:
            raw = budget_match.group(1).replace(",", "").replace(".", "")
            multiplier = {"k": 1_000, "m": 1_000_000}.get(budget_match.group(2), 1)
            context.budget_max = int(raw) * multiplier

    @staticmethod
    def _reply(
        context: SessionContext, text: str, properties: list | None = None
    ) -> ConversationReply:
        return ConversationReply(
            session_id=context.machine.session_id,
            state=context.machine.state,
            reply=text,
            properties=[PropertyRead.model_validate(item) for item in properties or []],
        )
