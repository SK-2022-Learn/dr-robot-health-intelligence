"""Daily chat orchestration with persisted review and transactional confirmation."""

import logging
from datetime import UTC, date, datetime, time
from typing import Annotated

from fastapi import Depends
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chat.clarification import merge_clarification_answers, required_clarifications
from app.chat.parser import parse_daily_health_extraction, supplement_explicit_facts
from app.chat.prompts import build_daily_health_prompt
from app.chat.schemas import (
    BloodPressureEntry,
    ChatMessageResponse,
    ChatResponseStatus,
    ClarificationRequest,
    ConfirmationResponse,
    ConversationCreateRequest,
    ConversationDetail,
    ConversationSummary,
    DailyHealthExtraction,
    GlucoseEntry,
    MessageView,
    PendingCorrectionRequest,
    PendingHealthEntryView,
    SymptomSeverity,
    TrustedRecordView,
    WeightEntry,
)
from app.core.errors import ApiError
from app.database.base import utc_now
from app.database.enums import (
    MessageRole,
    PendingHealthEntryStatus,
    ProvenanceType,
    VerificationStatus,
)
from app.database.models import Conversation, Message, Observation, PendingHealthEntry, Symptom
from app.llm.base import LLMProvider
from app.llm.factory import get_llm_provider
from app.llm.types import LLMError, LLMResponseError, LLMUnavailableError
from app.repositories.chat import ChatRepository
from app.repositories.profile import ProfileRepository
from app.safety.enums import SafetyDecision
from app.safety.schemas import SafetyInput, SafetyResult
from app.safety.service import SafetyService
from app.services.audit import AuditService

logger = logging.getLogger("dr_robot.chat")


def _safe_extraction_summary(extraction: DailyHealthExtraction) -> dict[str, int]:
    return {
        "observation_count": len(extraction.observations),
        "symptom_count": len(extraction.symptoms),
        "activity_count": len(extraction.activities),
        "sleep_count": len(extraction.sleep_entries),
        "clarification_count": len(extraction.clarifications),
    }


def _changed_health_fields(
    before: DailyHealthExtraction, after: DailyHealthExtraction
) -> list[str]:
    """Describe corrected field paths without copying health values into the audit log."""

    changed: list[str] = []

    def compare(left, right, path: str) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                compare(left.get(key), right.get(key), f"{path}.{key}" if path else key)
        elif isinstance(left, list) and isinstance(right, list):
            for index in range(max(len(left), len(right))):
                left_value = left[index] if index < len(left) else None
                right_value = right[index] if index < len(right) else None
                compare(left_value, right_value, f"{path}.{index}")
        elif left != right:
            changed.append(path)

    before_payload = before.model_dump(mode="json")
    after_payload = after.model_dump(mode="json")
    for section in ("observations", "symptoms", "activities", "sleep_entries"):
        compare(before_payload[section], after_payload[section], section)
    return changed


def _date_as_datetime(value: date | None) -> datetime | None:
    return datetime.combine(value, time.min, tzinfo=UTC) if value else None


class ChatService:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        repository: ChatRepository | None = None,
        profiles: ProfileRepository | None = None,
        audit: AuditService | None = None,
        safety: SafetyService | None = None,
    ) -> None:
        self.provider = provider
        self.repository = repository or ChatRepository()
        self.profiles = profiles or ProfileRepository()
        self.audit = audit or AuditService()
        self.safety = safety or SafetyService(self.audit)

    def _require_profile(self, db: Session, profile_id: str):
        profile = self.profiles.get(db, profile_id)
        if profile is None:
            raise ApiError(
                status_code=404,
                code="PROFILE_NOT_FOUND",
                message="Health profile was not found.",
            )
        return profile

    def _require_conversation(self, db: Session, conversation_id: str) -> Conversation:
        conversation = self.repository.get_conversation(db, conversation_id)
        if conversation is None:
            raise ApiError(
                status_code=404,
                code="CONVERSATION_NOT_FOUND",
                message="Conversation was not found.",
            )
        return conversation

    def _require_pending(self, db: Session, pending_id: str) -> PendingHealthEntry:
        pending = self.repository.get_pending(db, pending_id)
        if pending is None:
            raise ApiError(
                status_code=404,
                code="PENDING_ENTRY_NOT_FOUND",
                message="Pending health entry was not found.",
            )
        return pending

    @staticmethod
    def _message_view(message: Message) -> MessageView:
        return MessageView.model_validate(message)

    @staticmethod
    def _pending_view(pending: PendingHealthEntry) -> PendingHealthEntryView:
        return PendingHealthEntryView(
            id=pending.id,
            conversation_id=pending.conversation_id,
            message_id=pending.message_id,
            profile_id=pending.profile_id,
            extraction=DailyHealthExtraction.model_validate(pending.structured_data),
            status=pending.status,
            was_corrected=pending.was_corrected,
            trusted_records=[
                TrustedRecordView.model_validate(item) for item in (pending.trusted_records or [])
            ],
            created_at=pending.created_at,
            updated_at=pending.updated_at,
        )

    @staticmethod
    def _conversation_summary(conversation: Conversation) -> ConversationSummary:
        return ConversationSummary.model_validate(conversation)

    def create_conversation(
        self,
        db: Session,
        profile_id: str,
        data: ConversationCreateRequest,
    ) -> ConversationSummary:
        profile = self._require_profile(db, profile_id)
        conversation = self.repository.create_conversation(
            db, Conversation(profile_id=profile_id, title=data.title)
        )
        self.audit.append(
            db,
            action="CONVERSATION_CREATED",
            entity_type="conversation",
            entity_id=conversation.id,
            actor_user_id=profile.owner_user_id,
            after_state={"profile_id": profile_id},
        )
        db.commit()
        db.refresh(conversation)
        return self._conversation_summary(conversation)

    def list_conversations(self, db: Session, profile_id: str) -> list[ConversationSummary]:
        self._require_profile(db, profile_id)
        return [
            self._conversation_summary(item)
            for item in self.repository.list_conversations(db, profile_id)
        ]

    def conversation_detail(self, db: Session, conversation_id: str) -> ConversationDetail:
        conversation = self._require_conversation(db, conversation_id)
        return ConversationDetail(
            **self._conversation_summary(conversation).model_dump(),
            messages=[
                self._message_view(item)
                for item in sorted(conversation.messages, key=lambda row: (row.created_at, row.id))
            ],
            pending_entries=[
                self._pending_view(item)
                for item in sorted(
                    conversation.pending_entries, key=lambda row: (row.created_at, row.id)
                )
            ],
        )

    def _assistant_message(self, db: Session, conversation: Conversation, content: str) -> Message:
        return self.repository.create_message(
            db,
            Message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=content,
            ),
        )

    def _audit_safety(
        self,
        db: Session,
        conversation: Conversation,
        message_id: str,
        result: SafetyResult,
    ) -> None:
        self.safety.audit_result(
            db,
            result,
            entity_id=message_id,
            profile_id=conversation.profile_id,
            actor_user_id=conversation.profile.owner_user_id,
        )

    @staticmethod
    def _informational_answer(db: Session, profile_id: str, content: str) -> str | None:
        normalized = " ".join(content.casefold().split())
        if "what does" in normalized and ("hba1c" in normalized or "a1c" in normalized):
            return (
                "HbA1c is a blood test that reflects average blood glucose over roughly the past "
                "two to three months. It is used for screening and monitoring; an individual "
                "result should be interpreted with a clinician in context."
            )
        if "latest" in normalized and ("hba1c" in normalized or "a1c" in normalized):
            observation = db.scalar(
                select(Observation)
                .where(
                    Observation.profile_id == profile_id,
                    func.lower(Observation.display_name).in_(("hba1c", "a1c")),
                    Observation.verification_status != VerificationStatus.REJECTED,
                )
                .order_by(Observation.observed_at.desc(), Observation.id.desc())
            )
            if observation is None:
                return "I couldn't find a recorded HbA1c result for this profile."
            value = (
                f"{observation.value_number:g}"
                if observation.value_number is not None
                else observation.value_text
            )
            unit = f" {observation.unit}" if observation.unit else ""
            return (
                f"The latest recorded HbA1c for this profile is {value}{unit}, dated "
                f"{observation.observed_at.date().isoformat()}. This summarizes the stored record; "
                "it is not a diagnosis."
            )
        if "how many times" in normalized and "constipation" in normalized:
            count = db.scalar(
                select(func.count())
                .select_from(Symptom)
                .where(
                    Symptom.profile_id == profile_id,
                    func.lower(Symptom.name) == "constipation",
                    Symptom.verification_status != VerificationStatus.REJECTED,
                )
            )
            return f"Constipation is recorded {count or 0} time(s) for this profile."
        if "what does my record say" in normalized and "glucose" in normalized:
            observation = db.scalar(
                select(Observation)
                .where(
                    Observation.profile_id == profile_id,
                    func.lower(Observation.display_name) == "glucose",
                    Observation.verification_status != VerificationStatus.REJECTED,
                )
                .order_by(Observation.observed_at.desc(), Observation.id.desc())
            )
            if observation is None:
                return "I couldn't find a recorded glucose result for this profile."
            value = (
                f"{observation.value_number:g}"
                if observation.value_number is not None
                else observation.value_text
            )
            unit = f" {observation.unit}" if observation.unit else ""
            return (
                f"The latest recorded glucose for this profile is {value}{unit}, dated "
                f"{observation.observed_at.date().isoformat()}."
            )
        if "show the source" in normalized:
            return (
                "Open the relevant Timeline item and choose WHY to view its profile-scoped source "
                "evidence. Select a specific condition or result so the source is unambiguous."
            )
        return None

    def add_message(self, db: Session, conversation_id: str, content: str) -> ChatMessageResponse:
        conversation = self._require_conversation(db, conversation_id)
        user_message = self.repository.create_message(
            db,
            Message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=content,
            ),
        )
        conversation.updated_at = utc_now()
        self.audit.append(
            db,
            action="CHAT_MESSAGE_CREATED",
            entity_type="message",
            entity_id=user_message.id,
            actor_user_id=conversation.profile.owner_user_id,
            after_state={"conversation_id": conversation.id, "profile_id": conversation.profile_id},
        )
        safety_input = SafetyInput(
            user_text=content,
            profile_id=conversation.profile_id,
            context_type="DAILY_CHAT",
            source="ASK_DR_ROBOT",
        )
        pre_result = self.safety.pre_check(safety_input)
        self._audit_safety(db, conversation, user_message.id, pre_result)
        db.commit()
        db.refresh(user_message)

        if pre_result.decision not in {
            SafetyDecision.ALLOW,
            SafetyDecision.ALLOW_WITH_NOTICE,
        }:
            safe_text = pre_result.safe_response_override or pre_result.message
            self._assistant_message(db, conversation, safe_text)
            conversation.updated_at = utc_now()
            db.commit()
            return ChatMessageResponse(
                message_id=user_message.id,
                pending_id=None,
                status=ChatResponseStatus.SAFETY_BOUNDARY,
                extraction=None,
                questions=[],
                assistant_message=safe_text,
                safety=pre_result,
            )

        informational = self._informational_answer(db, conversation.profile_id, content)
        if informational is not None:
            post_result = self.safety.post_check(
                safety_input.model_copy(update={"draft_response": informational})
            )
            self._audit_safety(db, conversation, user_message.id, post_result)
            final_text = post_result.safe_response_override or informational
            self._assistant_message(db, conversation, final_text)
            conversation.updated_at = utc_now()
            db.commit()
            return ChatMessageResponse(
                message_id=user_message.id,
                pending_id=None,
                status=(
                    ChatResponseStatus.INFORMATIONAL
                    if post_result.decision == SafetyDecision.ALLOW
                    else ChatResponseStatus.SAFETY_BOUNDARY
                ),
                extraction=None,
                questions=[],
                assistant_message=final_text,
                safety=post_result,
            )

        prompt = build_daily_health_prompt(content, datetime.now().astimezone())
        try:
            raw_response = self.provider.generate_structured(
                prompt, DailyHealthExtraction.model_json_schema()
            )
            extraction = parse_daily_health_extraction(raw_response)
            extraction = supplement_explicit_facts(extraction, content)
        except LLMUnavailableError as error:
            logger.warning(
                "Daily chat provider unavailable", extra={"conversation_id": conversation.id}
            )
            raise ApiError(
                status_code=503,
                code="LLM_UNAVAILABLE",
                message=(
                    "Daily health extraction is temporarily unavailable. Your message was saved."
                ),
            ) from error
        except (LLMResponseError, LLMError, ValidationError) as error:
            logger.warning("Daily chat output rejected", extra={"conversation_id": conversation.id})
            raise ApiError(
                status_code=502,
                code="CHAT_EXTRACTION_FAILED",
                message="The saved message could not be converted into a structured preview.",
            ) from error

        extraction.clarifications = required_clarifications(extraction)
        status = (
            PendingHealthEntryStatus.NEEDS_CLARIFICATION
            if extraction.clarifications
            else PendingHealthEntryStatus.PENDING_REVIEW
        )
        payload = extraction.model_dump(mode="json")
        pending = self.repository.create_pending(
            db,
            PendingHealthEntry(
                conversation_id=conversation.id,
                message_id=user_message.id,
                profile_id=conversation.profile_id,
                structured_data=payload,
                original_structured_data=payload,
                status=status,
                was_corrected=False,
            ),
        )
        self.audit.append(
            db,
            action="CHAT_EXTRACTION_CREATED",
            entity_type="pending_health_entry",
            entity_id=pending.id,
            actor_user_id=conversation.profile.owner_user_id,
            after_state={
                "profile_id": conversation.profile_id,
                **_safe_extraction_summary(extraction),
            },
        )
        if extraction.clarifications:
            self.audit.append(
                db,
                action="CHAT_CLARIFICATION_REQUESTED",
                entity_type="pending_health_entry",
                entity_id=pending.id,
                actor_user_id=conversation.profile.owner_user_id,
                after_state={
                    "profile_id": conversation.profile_id,
                    "fields": [item.field for item in extraction.clarifications],
                },
            )
            assistant_text = "I need one detail before saving this."
            response_status = ChatResponseStatus.NEEDS_CLARIFICATION
        else:
            assistant_text = "Here is what I understood. Review it before saving."
            response_status = ChatResponseStatus.STRUCTURED_PREVIEW
        post_result = self.safety.post_check(
            safety_input.model_copy(update={"draft_response": assistant_text})
        )
        self._audit_safety(db, conversation, user_message.id, post_result)
        if post_result.decision not in {
            SafetyDecision.ALLOW,
            SafetyDecision.ALLOW_WITH_NOTICE,
        }:
            assistant_text = post_result.safe_response_override or post_result.message
            response_status = ChatResponseStatus.SAFETY_BOUNDARY
        self._assistant_message(db, conversation, assistant_text)
        conversation.updated_at = utc_now()
        db.commit()
        db.refresh(pending)
        return ChatMessageResponse(
            message_id=user_message.id,
            pending_id=pending.id,
            status=response_status,
            extraction=extraction,
            questions=extraction.clarifications,
            assistant_message=assistant_text,
            safety=post_result,
        )

    def clarify(
        self, db: Session, pending_id: str, data: ClarificationRequest
    ) -> ChatMessageResponse:
        pending = self._require_pending(db, pending_id)
        if pending.status not in {
            PendingHealthEntryStatus.NEEDS_CLARIFICATION,
            PendingHealthEntryStatus.PENDING_REVIEW,
        }:
            raise ApiError(
                status_code=409,
                code="PENDING_ENTRY_NOT_EDITABLE",
                message="This entry can no longer be changed.",
            )
        extraction = DailyHealthExtraction.model_validate(pending.structured_data)
        extraction = merge_clarification_answers(extraction, data.answers)
        pending.structured_data = extraction.model_dump(mode="json")
        pending.status = (
            PendingHealthEntryStatus.NEEDS_CLARIFICATION
            if extraction.clarifications
            else PendingHealthEntryStatus.PENDING_REVIEW
        )
        db.commit()
        db.refresh(pending)
        status = (
            ChatResponseStatus.NEEDS_CLARIFICATION
            if extraction.clarifications
            else ChatResponseStatus.STRUCTURED_PREVIEW
        )
        return ChatMessageResponse(
            message_id=pending.message_id,
            pending_id=pending.id,
            status=status,
            extraction=extraction,
            questions=extraction.clarifications,
            assistant_message=(
                "I still need one detail before saving this."
                if extraction.clarifications
                else "Thanks. Here is the updated structured preview."
            ),
        )

    def correct(
        self, db: Session, pending_id: str, data: PendingCorrectionRequest
    ) -> PendingHealthEntryView:
        pending = self._require_pending(db, pending_id)
        if pending.status not in {
            PendingHealthEntryStatus.NEEDS_CLARIFICATION,
            PendingHealthEntryStatus.PENDING_REVIEW,
        }:
            raise ApiError(
                status_code=409,
                code="PENDING_ENTRY_NOT_EDITABLE",
                message="This entry can no longer be changed.",
            )
        before = DailyHealthExtraction.model_validate(pending.structured_data)
        corrected = data.extraction.model_copy(deep=True)
        corrected.clarifications = required_clarifications(corrected)
        changed_fields = _changed_health_fields(before, corrected)
        pending.structured_data = corrected.model_dump(mode="json")
        pending.status = (
            PendingHealthEntryStatus.NEEDS_CLARIFICATION
            if corrected.clarifications
            else PendingHealthEntryStatus.PENDING_REVIEW
        )
        if changed_fields:
            pending.was_corrected = True
            self.audit.append(
                db,
                action="CHAT_ENTRY_CORRECTED",
                entity_type="pending_health_entry",
                entity_id=pending.id,
                actor_user_id=pending.profile.owner_user_id,
                before_state={"profile_id": pending.profile_id, "was_corrected": False},
                after_state={
                    "profile_id": pending.profile_id,
                    "was_corrected": True,
                    "changed_fields": changed_fields,
                },
            )
        db.commit()
        db.refresh(pending)
        return self._pending_view(pending)

    @staticmethod
    def _observation(
        pending: PendingHealthEntry,
        *,
        display_name: str,
        value_number: float | None,
        value_text: str | None,
        unit: str | None,
        interpretation: str | None,
        observed_at: datetime,
        provenance: ProvenanceType,
    ) -> Observation:
        return Observation(
            profile_id=pending.profile_id,
            source_message_id=pending.message_id,
            display_name=display_name,
            value_number=value_number,
            value_text=value_text,
            unit=unit,
            interpretation=interpretation,
            observed_at=observed_at,
            provenance=provenance,
            verification_status=VerificationStatus.VERIFIED,
        )

    def _create_trusted_records(
        self, db: Session, pending: PendingHealthEntry, extraction: DailyHealthExtraction
    ) -> list[TrustedRecordView]:
        message_time = pending.message.created_at
        provenance = (
            ProvenanceType.USER_CORRECTED if pending.was_corrected else ProvenanceType.USER_REPORTED
        )
        rows: list[Observation | Symptom] = []
        for item in extraction.observations:
            observed_at = item.observed_at or message_time
            if isinstance(item, GlucoseEntry):
                rows.append(
                    self._observation(
                        pending,
                        display_name="Glucose",
                        value_number=item.value,
                        value_text=None,
                        unit=item.unit,
                        interpretation=item.context.value,
                        observed_at=observed_at,
                        provenance=provenance,
                    )
                )
            elif isinstance(item, BloodPressureEntry):
                rows.append(
                    self._observation(
                        pending,
                        display_name="Blood pressure",
                        value_number=None,
                        value_text=f"{item.systolic}/{item.diastolic}",
                        unit=item.unit,
                        interpretation=None,
                        observed_at=observed_at,
                        provenance=provenance,
                    )
                )
            elif isinstance(item, WeightEntry):
                rows.append(
                    self._observation(
                        pending,
                        display_name="Weight",
                        value_number=item.value,
                        value_text=None,
                        unit=item.unit,
                        interpretation=None,
                        observed_at=observed_at,
                        provenance=provenance,
                    )
                )
        for item in extraction.sleep_entries:
            rows.append(
                self._observation(
                    pending,
                    display_name="Sleep duration",
                    value_number=float(item.duration_minutes),
                    value_text=None,
                    unit="min",
                    interpretation=item.quality,
                    observed_at=_date_as_datetime(item.sleep_date) or message_time,
                    provenance=provenance,
                )
            )
        for item in extraction.activities:
            if item.duration_minutes is not None:
                value_number = float(item.duration_minutes)
                unit = "min"
                interpretation = (
                    f"Distance: {item.distance:g} {item.distance_unit}"
                    if item.distance is not None
                    else None
                )
            else:
                value_number = item.distance
                unit = item.distance_unit
                interpretation = None
            rows.append(
                self._observation(
                    pending,
                    display_name=f"Activity: {item.activity_type}",
                    value_number=value_number,
                    value_text=None,
                    unit=unit,
                    interpretation=interpretation,
                    observed_at=item.observed_at or message_time,
                    provenance=provenance,
                )
            )
        severity_values = {
            SymptomSeverity.MILD: 3,
            SymptomSeverity.MODERATE: 6,
            SymptomSeverity.SEVERE: 9,
            SymptomSeverity.UNKNOWN: None,
        }
        for item in extraction.symptoms:
            notes = ". ".join(part for part in (item.duration_text, item.notes) if part) or None
            rows.append(
                Symptom(
                    profile_id=pending.profile_id,
                    source_message_id=pending.message_id,
                    name=item.name,
                    severity=severity_values[item.severity],
                    started_at=item.started_at,
                    notes=notes,
                    provenance=provenance,
                    verification_status=VerificationStatus.VERIFIED,
                )
            )
        for row in rows:
            db.add(row)
        db.flush()
        return [TrustedRecordView(record_type=row.__tablename__, record_id=row.id) for row in rows]

    def confirm(self, db: Session, pending_id: str) -> ConfirmationResponse:
        pending = self._require_pending(db, pending_id)
        if pending.status == PendingHealthEntryStatus.CONFIRMED:
            trusted = [
                TrustedRecordView.model_validate(item) for item in (pending.trusted_records or [])
            ]
            return ConfirmationResponse(
                pending=self._pending_view(pending),
                trusted_records=trusted,
                already_confirmed=True,
            )
        if pending.status == PendingHealthEntryStatus.REJECTED:
            raise ApiError(
                status_code=409,
                code="PENDING_ENTRY_REJECTED",
                message="A rejected entry cannot be confirmed.",
            )
        extraction = DailyHealthExtraction.model_validate(pending.structured_data)
        if required_clarifications(extraction):
            raise ApiError(
                status_code=409,
                code="CLARIFICATION_REQUIRED",
                message="Resolve all required clarifications before confirming this entry.",
            )
        try:
            trusted = self._create_trusted_records(db, pending, extraction)
            pending.status = PendingHealthEntryStatus.CONFIRMED
            pending.confirmed_at = utc_now()
            pending.trusted_records = [item.model_dump() for item in trusted]
            self.audit.append(
                db,
                action="CHAT_ENTRY_CONFIRMED",
                entity_type="pending_health_entry",
                entity_id=pending.id,
                actor_user_id=pending.profile.owner_user_id,
                after_state={
                    "profile_id": pending.profile_id,
                    "record_count": len(trusted),
                    "provenance": (
                        ProvenanceType.USER_CORRECTED.value
                        if pending.was_corrected
                        else ProvenanceType.USER_REPORTED.value
                    ),
                },
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(pending)
        return ConfirmationResponse(
            pending=self._pending_view(pending),
            trusted_records=trusted,
            already_confirmed=False,
        )

    def reject(self, db: Session, pending_id: str) -> PendingHealthEntryView:
        pending = self._require_pending(db, pending_id)
        if pending.status == PendingHealthEntryStatus.CONFIRMED:
            raise ApiError(
                status_code=409,
                code="PENDING_ENTRY_CONFIRMED",
                message="A confirmed entry cannot be rejected.",
            )
        if pending.status != PendingHealthEntryStatus.REJECTED:
            pending.status = PendingHealthEntryStatus.REJECTED
            self.audit.append(
                db,
                action="CHAT_ENTRY_REJECTED",
                entity_type="pending_health_entry",
                entity_id=pending.id,
                actor_user_id=pending.profile.owner_user_id,
                after_state={"profile_id": pending.profile_id},
            )
            db.commit()
            db.refresh(pending)
        return self._pending_view(pending)


def get_chat_service(
    provider: Annotated[LLMProvider, Depends(get_llm_provider)],
) -> ChatService:
    return ChatService(provider)
