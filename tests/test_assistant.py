from app.models.conversation import AssistantConversation, AssistantMessage


INSUFFICIENT_ANSWER = (
    "I couldn't find sufficient verified information in the available knowledge base to answer this accurately."
)


def test_assistant_returns_exact_no_evidence_fallback(client):
    response = client.post(
        "/api/assistant/chat",
        json={"message": "Can I recycle greasy pizza cardboard boxes?"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == INSUFFICIENT_ANSWER
    assert data["status"] == "insufficient_evidence"
    assert data["confidence"] == "Insufficient evidence"
    assert data["sources"] == []
    assert data["session_id"] is None


def test_assistant_rejects_empty_question(client):
    response = client.post("/api/assistant/chat", json={"message": ""})
    assert response.status_code == 422


def test_assistant_rejects_impossible_metadata_dates(client):
    response = client.post(
        "/api/assistant/chat",
        json={
            "question": "What are the local rules?",
            "metadata_filters": {"effective_on": "2026-99-42"},
        },
    )
    assert response.status_code == 422


def test_authenticated_assistant_turns_are_persisted_and_user_scoped(
    client, db_session, auth_headers
):
    first = client.post(
        "/api/assistant/chat",
        json={"question": "How should I handle wet waste?"},
        headers=auth_headers,
    )
    assert first.status_code == 200
    session_id = first.json()["session_id"]
    assert session_id

    second = client.post(
        "/api/assistant/chat",
        json={"message": "What about composting it?", "session_id": session_id},
        headers=auth_headers,
    )
    assert second.status_code == 200
    conversation = (
        db_session.query(AssistantConversation)
        .filter_by(conversation_id=session_id)
        .one()
    )
    messages = (
        db_session.query(AssistantMessage)
        .filter_by(conversation_id=session_id)
        .order_by(AssistantMessage.id)
        .all()
    )
    assert conversation.user_id is not None
    assert [message.role for message in messages] == ["user", "assistant", "user", "assistant"]

    client.post(
        "/api/auth/register",
        json={
            "email": "assistant.other@example.com",
            "password": "Password123!",
            "full_name": "Other Citizen",
        },
    )
    other_token = client.post(
        "/api/auth/login",
        json={"email": "assistant.other@example.com", "password": "Password123!"},
    ).json()["access_token"]
    other_response = client.post(
        "/api/assistant/chat",
        json={"question": "Continue", "session_id": session_id},
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_response.status_code == 404


def test_anonymous_user_cannot_resume_saved_conversation(client):
    response = client.post(
        "/api/assistant/chat",
        json={"question": "Continue", "session_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert response.status_code == 401
