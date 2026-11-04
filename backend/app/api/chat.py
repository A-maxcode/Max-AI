from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.dependencies import CurrentUser
from app.core.rate_limit import rate_limiter
from app.database.connection import get_db_session
from app.database.models import Message, User
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
)
from app.services.conversation import (
    get_owned_conversation,
    list_user_conversations,
    prepare_chat_turn,
    save_assistant_reply,
)
from app.services.inference import generate_reply


router = APIRouter(tags=["chat"])
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    user: CurrentUser,
    session: DatabaseSession,
) -> ChatResponse:
    settings = get_settings()
    await rate_limiter.check(
        request,
        scope=f"chat:{user.id}",
        limit=settings.chat_rate_limit,
        window_seconds=60,
    )
    conversation, context = await prepare_chat_turn(session, user, payload)
    reply = await generate_reply(context)
    await save_assistant_reply(session, conversation, reply)
    return ChatResponse(reply=reply, conversation_id=conversation.id)


@router.get("/conversations", response_model=list[ConversationSummary])
async def conversations(
    user: CurrentUser,
    session: DatabaseSession,
) -> list[ConversationSummary]:
    items = await list_user_conversations(session, user)
    return [ConversationSummary.model_validate(item) for item in items]


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def conversation_detail(
    conversation_id: UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> ConversationDetail:
    conversation = await get_owned_conversation(session, user, conversation_id)
    stored_messages = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.position.desc())
        .limit(200)
    )
    return ConversationDetail(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "created_at": item.created_at,
            }
            for item in reversed(list(stored_messages))
        ],
    )


@router.delete(
    "/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_conversation(
    conversation_id: UUID,
    user: CurrentUser,
    session: DatabaseSession,
) -> Response:
    conversation = await get_owned_conversation(session, user, conversation_id)
    await session.delete(conversation)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
