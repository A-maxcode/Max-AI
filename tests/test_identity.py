import pytest
from unittest.mock import AsyncMock
from uuid import uuid4


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "Who created you?",
            "I am Max-AI. I was created by A-maxcode, also known as Angelo Besas.",
        ),
        (
            "Who built you?",
            "I am Max-AI. I was built by A-maxcode, also known as Angelo Besas.",
        ),
        (
            "Who is your developer?",
            "I am Max-AI. My developer is A-maxcode, also known as Angelo Besas.",
        ),
        (
            "Who owns you?",
            "I am Max-AI. I was developed by A-maxcode, also known as Angelo Besas.",
        ),
        ("What is your name?", "My name is Max-AI."),
        (
            "Are you ChatGPT or Max-AI?",
            "I am Max-AI, an AI assistant developed by A-maxcode, also known as Angelo Besas.",
        ),
        (
            "Tell me about your creator.",
            "I am Max-AI, an AI assistant developed by A-maxcode, also known as "
            "Angelo Besas. A-maxcode developed the Max-AI assistant application "
            "and did not create the underlying SmolLM2 foundation model.",
        ),
        (
            "Who is Angelo Besas?",
            "A-maxcode, also known as Angelo Besas, developed the Max-AI "
            "assistant application. A-maxcode did not create the underlying SmolLM2 "
            "foundation model.",
        ),
    ],
)
async def test_identity_questions_return_official_facts(client, monkeypatch, question, expected):
    registration = await client.post(
        "/api/auth/register",
        json={
            "email": f"identity-{uuid4().hex}@example.com",
            "password": "a-very-long-test-password",
        },
    )
    assert registration.status_code == 201

    model = AsyncMock(side_effect=AssertionError("Identity FAQ should not invoke inference."))
    monkeypatch.setattr("app.api.chat.generate_reply", model)

    response = await client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": question}]},
    )

    assert response.status_code == 200
    assert expected in response.json()["reply"]
    model.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "question",
    [
        "Who is A maxcode?",
        "Who's your creator?",
        "Who made this assistant?",
        "Who is the person behind Max-AI?",
        "What AI are you?",
    ],
)
async def test_identity_understands_creator_and_name_variations(client, monkeypatch, question):
    registration = await client.post(
        "/api/auth/register",
        json={
            "email": f"identity-variation-{uuid4().hex}@example.com",
            "password": "a-very-long-test-password",
        },
    )
    assert registration.status_code == 201
    model = AsyncMock(side_effect=AssertionError("Identity FAQ should not invoke inference."))
    monkeypatch.setattr("app.api.chat.generate_reply", model)

    response = await client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": question}]},
    )

    assert response.status_code == 200
    assert "Max-AI" in response.json()["reply"]
    assert "A-maxcode" in response.json()["reply"]
    assert "Angelo Besas" in response.json()["reply"]
    model.assert_not_awaited()


def test_underlying_model_origin_question_is_not_misclassified_as_max_ai_origin():
    from app.services.identity import identity_reply

    assert identity_reply("Who created SmolLM2?") is None


@pytest.mark.asyncio
async def test_identity_faq_is_persisted_and_available_in_existing_conversation(
    client, monkeypatch
):
    registration = await client.post(
        "/api/auth/register",
        json={"email": "identity-followup@example.com", "password": "a-very-long-test-password"},
    )
    assert registration.status_code == 201

    model = AsyncMock(return_value="A normal local-model answer.")
    monkeypatch.setattr("app.api.chat.generate_reply", model)

    first = await client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert first.status_code == 200
    conversation_id = first.json()["conversation_id"]

    second = await client.post(
        "/api/chat",
        json={
            "conversation_id": conversation_id,
            "messages": [{"role": "user", "content": "Who created you?"}],
        },
    )

    assert second.status_code == 200
    assert second.json()["reply"] == (
        "I am Max-AI. I was created by A-maxcode, also known as Angelo Besas."
    )
    detail = await client.get(f"/api/conversations/{conversation_id}")
    assert [message["role"] for message in detail.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert detail.json()["messages"][-1]["content"] == second.json()["reply"]
    assert model.await_count == 1
