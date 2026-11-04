from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.database.models import Conversation, Message
from app.schemas.chat import ChatMessageInput
from app.services import inference


async def register(client, email="person@example.com"):
    response = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "a-very-long-test-password"},
    )
    assert response.status_code == 201
    return response.json()["user"]


@pytest.mark.asyncio
async def test_chat_validation_and_mocked_local_inference(client, database, monkeypatch):
    await register(client)
    invalid = await client.post(
        "/api/chat",
        json={"messages": [{"role": "system", "content": "not accepted"}]},
    )
    assert invalid.status_code == 422

    generator = AsyncMock(side_effect=["Hello from the local model.", "Second turn."])
    monkeypatch.setattr("app.api.chat.generate_reply", generator)
    first = await client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert first.status_code == 200
    assert first.json()["reply"] == "Hello from the local model."

    from uuid import UUID

    conversation_id = UUID(first.json()["conversation_id"])
    second = await client.post(
        "/api/chat",
        json={
            "conversation_id": str(conversation_id),
            "messages": [{"role": "user", "content": "Continue"}],
        },
    )
    assert second.status_code == 200
    assert second.json()["conversation_id"] == str(conversation_id)
    assert [message.content for message in generator.await_args_list[1].args[0]] == [
        "Hello",
        "Hello from the local model.",
        "Continue",
    ]

    detail = await client.get(f"/api/conversations/{conversation_id}")
    assert [message["role"] for message in detail.json()["messages"]] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    async with database() as session:
        conversation = await session.get(Conversation, conversation_id)
        messages = await session.scalars(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.position)
        )
        assert conversation.title == "Hello"
        assert len(list(messages)) == 4


@pytest.mark.asyncio
async def test_model_unavailable_saves_user_message_and_returns_safe_error(client, database, monkeypatch):
    await register(client)
    monkeypatch.setattr(
        "app.api.chat.generate_reply",
        AsyncMock(
            side_effect=HTTPException(
                status_code=503,
                detail="The local model server is unavailable.",
            )
        ),
    )

    response = await client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Please answer"}]},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "The local model server is unavailable."}
    conversations = (await client.get("/api/conversations")).json()
    assert len(conversations) == 1
    saved = await client.get(f"/api/conversations/{conversations[0]['id']}")
    assert saved.json()["messages"][0]["content"] == "Please answer"


@pytest.mark.asyncio
async def test_conversations_cannot_be_read_or_deleted_by_another_user(client, monkeypatch):
    await register(client, "first@example.com")
    monkeypatch.setattr(
        "app.api.chat.generate_reply",
        AsyncMock(return_value="Stored locally."),
    )
    created = await client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "My private chat"}]},
    )
    conversation_id = created.json()["conversation_id"]

    await client.post("/api/auth/logout")
    await register(client, "second@example.com")
    assert (await client.get(f"/api/conversations/{conversation_id}")).status_code == 404
    assert (
        await client.delete(f"/api/conversations/{conversation_id}")
    ).status_code == 404
    assert (await client.get("/api/conversations")).json() == []


@pytest.mark.asyncio
async def test_owner_can_delete_persisted_conversation(client, monkeypatch):
    await register(client)
    monkeypatch.setattr(
        "app.api.chat.generate_reply",
        AsyncMock(return_value="Stored locally."),
    )
    created = await client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Delete this later"}]},
    )
    conversation_id = created.json()["conversation_id"]

    deleted = await client.delete(f"/api/conversations/{conversation_id}")

    assert deleted.status_code == 204
    assert (await client.get(f"/api/conversations/{conversation_id}")).status_code == 404


@pytest.mark.asyncio
async def test_inference_uses_local_server_and_parses_openai_compatible_response(monkeypatch):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/v1/models"):
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["payload"] = request.read().decode()
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": " Local answer "}}]},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        inference.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    reply = await inference.generate_reply(
        [ChatMessageInput(role="user", content="Hello local model")]
    )

    assert reply == "Local answer"
    assert captured["url"].endswith("/v1/chat/completions")
    assert "authorization" not in captured["headers"]
    assert '"role":"system"' in captured["payload"]
    assert "Your application and assistant name is Max-AI." in captured["payload"]
    assert "A-maxcode, also known as Angelo Besas" in captured["payload"]
    assert "did not create the underlying SmolLM2 foundation model" in captured["payload"]
    assert "max_tokens" in captured["payload"]
    assert '"model":"test-model"' in captured["payload"]


@pytest.mark.asyncio
async def test_inference_unavailable_is_a_503(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("private model server unavailable", request=request)

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        inference.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=transport, **kwargs),
    )

    with pytest.raises(HTTPException) as caught:
        await inference.generate_reply(
            [ChatMessageInput(role="user", content="Hello local model")]
        )
    assert caught.value.status_code == 503
