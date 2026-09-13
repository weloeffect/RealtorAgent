import pytest

from packages.domain.state_machine import ConversationSession, ConversationState


def test_state_machine_rejects_skipped_steps():
    session = ConversationSession("test")
    with pytest.raises(ValueError, match="Invalid transition"):
        session.transition(ConversationState.BOOKING)


def test_state_machine_accepts_search_flow():
    session = ConversationSession("test")
    for target in (
        ConversationState.DISCOVERY,
        ConversationState.SEARCH,
        ConversationState.PRESENT_RESULTS,
        ConversationState.COMPLETE,
    ):
        session.transition(target)
    assert session.state == ConversationState.COMPLETE
