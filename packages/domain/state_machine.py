from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ConversationState(StrEnum):
    GREETING = "greeting"
    DISCOVERY = "discovery"
    SEARCH = "search"
    PRESENT_RESULTS = "present_results"
    BOOKING = "booking"
    HANDOFF = "handoff"
    COMPLETE = "complete"


ALLOWED_TRANSITIONS = {
    ConversationState.GREETING: {ConversationState.DISCOVERY, ConversationState.HANDOFF},
    ConversationState.DISCOVERY: {ConversationState.SEARCH, ConversationState.HANDOFF},
    ConversationState.SEARCH: {ConversationState.PRESENT_RESULTS, ConversationState.DISCOVERY},
    ConversationState.PRESENT_RESULTS: {
        ConversationState.DISCOVERY,
        ConversationState.BOOKING,
        ConversationState.HANDOFF,
        ConversationState.COMPLETE,
    },
    ConversationState.BOOKING: {ConversationState.COMPLETE, ConversationState.HANDOFF},
    ConversationState.HANDOFF: {ConversationState.COMPLETE},
    ConversationState.COMPLETE: set(),
}


@dataclass
class ConversationSession:
    session_id: str
    state: ConversationState = ConversationState.GREETING

    def transition(self, target: ConversationState) -> None:
        if target not in ALLOWED_TRANSITIONS[self.state]:
            raise ValueError(f"Invalid transition: {self.state} -> {target}")
        self.state = target
