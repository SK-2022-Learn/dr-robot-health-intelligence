"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

import { AgentResponse } from "@/components/chat/agent-response";
import { StructuredPreview } from "@/components/chat/structured-preview";
import { useProfile } from "@/components/health/profile-context";
import { Card, EmptyState, ErrorState, LoadingState, PageHeading } from "@/components/ui";
import {
  createConversation,
  getConversation,
  getConversations,
} from "@/lib/api/chat";
import { askDrRobot } from "@/lib/api/agents";
import { readableApiError } from "@/lib/api/client";
import type {
  AskResponse,
  ChatMessageResponse,
  ConversationDetail,
  ConversationSummary,
} from "@/lib/types/api";
import { formatDate } from "@/lib/utils/format";

type ReviewState = Pick<ChatMessageResponse, "questions"> & {
  pendingId: string;
  extraction: NonNullable<ChatMessageResponse["extraction"]>;
};

export default function ChatPage() {
  const { activeProfile, loading: profilesLoading, error: profileError } = useProfile();
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversation, setConversation] = useState<ConversationDetail | null>(null);
  const [review, setReview] = useState<ReviewState | null>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadedProfileId, setLoadedProfileId] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentResponse, setAgentResponse] = useState<AskResponse | null>(null);

  const openConversation = useCallback(async (conversationId: string) => {
    const detail = await getConversation(conversationId);
    setConversation(detail);
    const pending = [...detail.pending_entries]
      .reverse()
      .find((item) => item.status === "PENDING_REVIEW" || item.status === "NEEDS_CLARIFICATION");
    setReview(
      pending
        ? {
            pendingId: pending.id,
            extraction: pending.extraction,
            questions: pending.extraction.clarifications,
          }
        : null,
    );
  }, []);

  useEffect(() => {
    if (!activeProfile) return;
    let cancelled = false;
    (async () => {
      try {
        let rows = await getConversations(activeProfile.id);
        if (!rows.length) {
          const created = await createConversation(activeProfile.id);
          rows = [created];
        }
        if (cancelled) return;
        setLoading(true);
        setError(null);
        setAgentResponse(null);
        setReview(null);
        setConversations(rows);
        await openConversation(rows[0].id);
        setLoadedProfileId(activeProfile.id);
      } catch (reason: unknown) {
        if (!cancelled) setError(readableApiError(reason));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [activeProfile, openConversation]);

  async function startConversation() {
    if (!activeProfile) return;
    setLoading(true);
    setError(null);
    try {
      const created = await createConversation(activeProfile.id);
      setConversations((current) => [created, ...current]);
      await openConversation(created.id);
    } catch (reason: unknown) {
      setError(readableApiError(reason));
    } finally {
      setLoading(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!activeProfile || !conversation || !content.trim()) return;
    setSending(true);
    setError(null);
    setAgentResponse(null);
    try {
      const response = await askDrRobot(activeProfile.id, content.trim(), conversation.id);
      setContent("");
      setAgentResponse(response);
      const daily = response.structured_result?.response;
      if (
        response.intent === "DAILY_LOG" &&
        response.pending_id &&
        daily &&
        typeof daily === "object" &&
        "extraction" in daily &&
        daily.extraction &&
        typeof daily.extraction === "object" &&
        "questions" in daily &&
        Array.isArray(daily.questions)
      ) {
        setReview({
          pendingId: response.pending_id,
          extraction: daily.extraction as ReviewState["extraction"],
          questions: daily.questions as ReviewState["questions"],
        });
      } else {
        setReview(null);
      }
      if (response.conversation_id) {
        const detail = await getConversation(response.conversation_id);
        setConversation(detail);
      }
    } catch (reason: unknown) {
      setError(readableApiError(reason));
    } finally {
      setSending(false);
    }
  }

  async function pendingChanged() {
    if (conversation) setConversation(await getConversation(conversation.id));
  }

  if (profilesLoading) return <LoadingState label="Loading profile..." />;
  if (profileError) return <ErrorState message={profileError} />;
  if (!activeProfile) {
    return <EmptyState title="No profile selected" message="Choose a profile before logging health updates." />;
  }

  return (
    <>
      <PageHeading
        eyebrow="Daily health logging"
        title="Ask Dr. Robot"
        description={`For: ${activeProfile.display_name}. One safe route for daily logs, records, evidence, trends, family patterns, and visit preparation.`}
      />
      <div className="chat-layout">
        <Card className="conversation-panel">
          <div className="conversation-toolbar">
            <label htmlFor="conversation-selector">Conversation</label>
            <select
              id="conversation-selector"
              value={conversation?.id ?? ""}
              onChange={(event) => openConversation(event.target.value)}
              disabled={loading}
            >
              {conversations.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.title ?? "Daily health log"} - {formatDate(item.updated_at)}
                </option>
              ))}
            </select>
            <button className="secondary-button" onClick={startConversation} disabled={loading}>
              New conversation
            </button>
          </div>

          {loading || loadedProfileId !== activeProfile.id ? (
            <LoadingState label="Loading conversation..." />
          ) : !conversation?.messages.length ? (
            <EmptyState
              title="Start a daily update"
              message="Your original message will be preserved. Nothing enters health memory until you confirm the structured preview."
            />
          ) : (
            <div className="message-history" aria-label="Conversation messages">
              {conversation.messages.map((message) => (
                <article className={`chat-message ${message.role.toLowerCase()}`} key={message.id}>
                  <span>{message.role === "USER" ? activeProfile.display_name : "Dr. Robot"}</span>
                  <p>{message.content}</p>
                </article>
              ))}
            </div>
          )}

          <form className="chat-composer" onSubmit={submit}>
            <label htmlFor="daily-health-message">Ask or share a daily health update</label>
            <textarea
              id="daily-health-message"
              value={content}
              maxLength={2000}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Morning sugar 118 before food — or ask: What does HbA1c measure?"
              disabled={sending || !conversation}
            />
            <div>
              <span>{content.length}/2000</span>
              <button className="primary-button" disabled={sending || !content.trim()}>
                {sending ? "Routing safely..." : "Ask Dr. Robot"}
              </button>
            </div>
          </form>
        </Card>

        <aside className="review-column">
          {agentResponse && <AgentResponse response={agentResponse} />}
          {review ? (
            <StructuredPreview
              key={review.pendingId}
              pendingId={review.pendingId}
              initial={review.extraction}
              questions={review.questions}
              onChanged={pendingChanged}
            />
          ) : (
            !agentResponse && <Card><EmptyState title="Ready to help" message="Ask about records, evidence, changes, family patterns, or log a health update for confirmation." /></Card>
          )}
          {error && <ErrorState message={error} />}
        </aside>
      </div>
    </>
  );
}
