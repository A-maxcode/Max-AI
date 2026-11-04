from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import Conversation, Message, User
from app.schemas.chat import ChatMessageInput, ChatRequest


def _conversation_title(messages: list[ChatMessageInput]) -> str:
    first_user_message = next((message.content for message in messages if message.role == "user"), None)
    if first_user_message is None:
        return "New conversation"
    title = " ".join(first_user_message.split())
    return title[:117] + "..." if len(title) > 120 else title


async def get_owned_conversation(
    session: AsyncSession,
    user: User,
    conversation_id: UUID,
) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")
    return conversation


async def list_user_conversations(session: AsyncSession, user: User) -> list[Conversation]:
    result = await session.scalars(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(100)
    )
    return list(result)


async def prepare_chat_turn(
    session: AsyncSession,
    user: User,
    request: ChatRequest,
) -> tuple[Conversation, list[ChatMessageInput]]:
    if request.messages[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The last chat message must be from the user.",
        )

    if request.conversation_id is None:
        conversation = Conversation(
            user_id=user.id,
            title=_conversation_title(request.messages),
        )
        session.add(conversation)
        await session.flush()
        for position, item in enumerate(request.messages, start=1):
            session.add(
                Message(
                    conversation_id=conversation.id,
                    position=position,
                    role=item.role,
                    content=item.content,
                )
            )
    else:
        conversation = await session.scalar(
            select(Conversation)
            .where(
                Conversation.id == request.conversation_id,
                Conversation.user_id == user.id,
            )
            .with_for_update()
        )
        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found.",
            )
        last_message = request.messages[-1]
        last_position = await session.scalar(
            select(func.max(Message.position)).where(
                Message.conversation_id == conversation.id
            )
        )
        session.add(
            Message(
                conversation_id=conversation.id,
                position=(last_position or 0) + 1,
                role=last_message.role,
                content=last_message.content,
            )
        )
        conversation.updated_at = datetime.now(timezone.utc)

    await session.commit()
    result = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.position.desc())
        .limit(200)
    )
    context = [
        ChatMessageInput(role=message.role, content=message.content)
        for message in reversed(list(result))
    ]
    available_characters = max(
        1,
        (get_settings().model_context_length - get_settings().model_max_tokens) * 3,
    )
    limited_context: list[ChatMessageInput] = []
    characters_used = 0
    for item in reversed(context):
        remaining = available_characters - characters_used
        if remaining <= 0:
            break
        content = item.content[:remaining]
        limited_context.append(item.model_copy(update={"content": content}))
        characters_used += len(content)
    return conversation, list(reversed(limited_context))


async def save_assistant_reply(
    session: AsyncSession,
    conversation: Conversation,
    reply: str,
) -> None:
    last_position = await session.scalar(
        select(func.max(Message.position)).where(
            Message.conversation_id == conversation.id
        )
    )
    session.add(
        Message(
            conversation_id=conversation.id,
            position=(last_position or 0) + 1,
            role="assistant",
            content=reply,
        )
    )
    conversation.updated_at = datetime.now(timezone.utc)
    await session.commit()
