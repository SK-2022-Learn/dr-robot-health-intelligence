"""Optional semantic evidence retrieval with graceful structured-data fallback."""

from sqlalchemy.orm import Session

from app.agents.state import DrRobotState
from app.core.errors import ApiError
from app.retrieval.service import RetrievalService


def retrieval_node(db: Session, service: RetrievalService):
    def run(state: DrRobotState) -> dict:
        query = state["user_query"].casefold()
        useful = any(term in query for term in ("report", "document", "source", "record"))
        if not useful or state.get("structured_context", {}).get("items"):
            return {"nodes_run": ["retrieval"]}
        try:
            result = service.search(db, state["profile_id"], state["user_query"], 3)
        except ApiError:
            db.rollback()
            return {
                "warnings": [
                    "Semantic evidence search is unavailable; trusted SQLite results remain usable."
                ],
                "nodes_run": ["retrieval"],
            }
        return {
            "retrieval_context": result.model_dump(mode="json"),
            "sources": [
                {
                    "source_type": "DOCUMENT",
                    "label": item.filename,
                    "document_id": item.document_id,
                    "page_number": item.page_number,
                    "evidence_path": f"/api/v1/documents/{item.document_id}",
                }
                for item in result.results
            ],
            "actions_taken": ["semantic_retrieval"],
            "nodes_run": ["retrieval"],
        }

    return run
