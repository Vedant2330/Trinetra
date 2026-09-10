"""TRINETRA Hermes API Router (P-HERMES).

Exposes:
  - POST /api/hermes/ask: Grounded Q&A reasoning turn with honest error taxonomy
  - GET  /api/hermes/status: Cheap cached status check
  - GET  /api/hermes/context: Inspect assembled machine-verified context JSON
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from backend.core.errors import get_dao
from backend.services.hermes import (
    HermesService,
    HermesUnavailableError,
    build_hermes_context,
    generate_deterministic_answer,
)

log = logging.getLogger("trinetra.api.hermes")
router = APIRouter(prefix="/api/hermes", tags=["hermes"])

_hermes_svc = HermesService()


class HermesAskRequest(BaseModel):
    question: str
    event_id: Optional[str] = None
    session_id: Optional[str] = None
    model: Optional[str] = None
    allow_deterministic_fallback: bool = False


@router.get("/status")
def hermes_status(force_refresh: bool = Query(False)) -> dict[str, Any]:
    """Check Hermes LLM gateway connectivity and model status (cached 60s)."""
    return _hermes_svc.check_status(force_refresh=force_refresh)


@router.get("/context")
def hermes_context(
    event_id: Optional[str] = Query(None),
    session_id: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Inspect the machine-verified structured context assembled for an event/session."""
    dao = get_dao()
    return build_hermes_context(dao, question="Inspection", event_id=event_id, session_id=session_id)


@router.post("/ask")
def hermes_ask(req: HermesAskRequest) -> dict[str, Any]:
    """Perform a grounded Q&A reasoning turn with operator-selected context."""
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")

    dao = get_dao()
    try:
        res = _hermes_svc.ask(
            dao,
            question=req.question,
            event_id=req.event_id,
            session_id=req.session_id,
            model_override=req.model,
        )
        return res
    except HermesUnavailableError as e:
        if req.allow_deterministic_fallback:
            log.info("Hermes LLM offline; utilizing deterministic grounding fallback for query: %s", req.question)
            ctx = build_hermes_context(dao, question=req.question, event_id=req.event_id, session_id=req.session_id)
            answer = generate_deterministic_answer(ctx, req.question)
            return {
                "answer": answer,
                "model": "deterministic-sqlite-grounding",
                "elapsed_ms": 1.5,
                "grounded_event_id": req.event_id,
                "grounded_session_id": req.session_id,
                "context": ctx,
                "is_fallback": True,
                "fallback_reason": e.reason,
            }
        log.warning("Hermes unavailable: %s (reason: %s)", e.message, e.reason)
        raise HTTPException(
            status_code=503,
            detail=e.as_dict(),
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.exception("Unexpected error in hermes_ask")
        raise HTTPException(
            status_code=500,
            detail={"error": "internal_error", "message": str(e)},
        ) from e
