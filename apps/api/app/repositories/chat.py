"""Persistence operations for conversations, messages, and pending health entries."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models import Conversation, Message, PendingHealthEntry


class ChatRepository:
    def create_conversation(self, db: Session, conversation: Conversation) -> Conversation:
        db.add(conversation)
        db.flush()
        return conversation

    def get_conversation(self, db: Session, conversation_id: str) -> Conversation | None:
        statement = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(
                selectinload(Conversation.messages),
                selectinload(Conversation.pending_entries),
            )
        )
        return db.scalar(statement)

    def list_conversations(self, db: Session, profile_id: str) -> list[Conversation]:
        statement = (
            select(Conversation)
            .where(Conversation.profile_id == profile_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id)
        )
        return list(db.scalars(statement))

    def create_message(self, db: Session, message: Message) -> Message:
        db.add(message)
        db.flush()
        return message

    def create_pending(self, db: Session, pending: PendingHealthEntry) -> PendingHealthEntry:
        db.add(pending)
        db.flush()
        return pending

    def get_pending(self, db: Session, pending_id: str) -> PendingHealthEntry | None:
        return db.get(PendingHealthEntry, pending_id)
