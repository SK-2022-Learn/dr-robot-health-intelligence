"""Conversation and message contracts without LLM behavior."""

from datetime import datetime

from app.database.enums import MessageRole
from app.schemas.common import IdentityTimestamps, SchemaModel


class ConversationCreate(SchemaModel):
    profile_id: str
    title: str | None = None


class ConversationUpdate(SchemaModel):
    title: str | None = None


class ConversationRead(IdentityTimestamps, ConversationCreate):
    pass


class MessageCreate(SchemaModel):
    conversation_id: str
    role: MessageRole
    content: str


class MessageRead(MessageCreate):
    id: str
    created_at: datetime
