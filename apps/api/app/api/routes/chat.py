"""Daily chat endpoints with persisted review before trusted writes."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.chat.schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ClarificationRequest,
    ConfirmationResponse,
    ConversationCreateRequest,
    ConversationDetail,
    ConversationSummary,
    PendingCorrectionRequest,
    PendingHealthEntryView,
)
from app.chat.service import ChatService, get_chat_service
from app.database.session import get_db

router = APIRouter(tags=["daily chat"])


@router.post(
    "/profiles/{profile_id}/conversations",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    profile_id: str,
    data: ConversationCreateRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ConversationSummary:
    return service.create_conversation(db, profile_id, data)


@router.get("/profiles/{profile_id}/conversations", response_model=list[ConversationSummary])
def list_conversations(
    profile_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> list[ConversationSummary]:
    return service.list_conversations(db, profile_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ConversationDetail:
    return service.conversation_detail(db, conversation_id)


@router.post("/conversations/{conversation_id}/messages", response_model=ChatMessageResponse)
def create_message(
    conversation_id: str,
    data: ChatMessageRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatMessageResponse:
    return service.add_message(db, conversation_id, data.content)


@router.post("/chat/pending/{pending_id}/clarify", response_model=ChatMessageResponse)
def clarify_pending(
    pending_id: str,
    data: ClarificationRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ChatMessageResponse:
    return service.clarify(db, pending_id, data)


@router.patch("/chat/pending/{pending_id}", response_model=PendingHealthEntryView)
def correct_pending(
    pending_id: str,
    data: PendingCorrectionRequest,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> PendingHealthEntryView:
    return service.correct(db, pending_id, data)


@router.post("/chat/pending/{pending_id}/confirm", response_model=ConfirmationResponse)
def confirm_pending(
    pending_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> ConfirmationResponse:
    return service.confirm(db, pending_id)


@router.post("/chat/pending/{pending_id}/reject", response_model=PendingHealthEntryView)
def reject_pending(
    pending_id: str,
    db: Annotated[Session, Depends(get_db)],
    service: Annotated[ChatService, Depends(get_chat_service)],
) -> PendingHealthEntryView:
    return service.reject(db, pending_id)
