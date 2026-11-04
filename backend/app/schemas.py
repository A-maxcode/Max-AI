"""Compatibility re-exports for the original starter's schema imports."""

from app.schemas.chat import ChatMessageInput as ChatMessage
from app.schemas.chat import ChatRequest, ChatResponse

__all__ = ["ChatMessage", "ChatRequest", "ChatResponse"]
