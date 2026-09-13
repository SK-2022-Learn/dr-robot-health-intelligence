"""Daily logging delegates to the existing pending-review chat workflow."""

from sqlalchemy.orm import Session

from app.agents.state import DrRobotState
from app.chat.schemas import ConversationCreateRequest
from app.chat.service import ChatService
from app.core.errors import ApiError


def daily_log_node(db: Session, service: ChatService):
    def run(state: DrRobotState) -> dict:
        conversation_id = state.get("conversation_id")
        if conversation_id:
            detail = service.conversation_detail(db, conversation_id)
            if detail.profile_id != state["profile_id"]:
                raise ApiError(
                    status_code=404,
                    code="CONVERSATION_NOT_FOUND",
                    message="Conversation was not found for this profile.",
                )
        else:
            conversation = service.create_conversation(
                db,
                state["profile_id"],
                ConversationCreateRequest(title="Ask Dr. Robot"),
            )
            conversation_id = conversation.id
        response = service.add_message(db, conversation_id, state["user_query"])
        warnings = response.extraction.warnings if response.extraction else []
        return {
            "conversation_id": conversation_id,
            "pending_id": response.pending_id,
            "clarification_required": bool(response.questions),
            "structured_context": {
                "kind": "daily_log",
                "response": response.model_dump(mode="json"),
            },
            "draft_response": response.assistant_message,
            "warnings": warnings,
            "actions_taken": ["daily_log_pending_review"],
            "nodes_run": ["daily_log"],
        }

    return run
