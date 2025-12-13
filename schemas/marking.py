# services/grading/schemas/marking.py
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel

# ---------- Evaluate ----------


class EvaluateRequest(BaseModel):
    expr: str


class EvaluateResponse(BaseModel):
    ok: bool
    value: Optional[float] = None
    feedback: Optional[str] = None


# ---------- Mark single ----------


class MarkRequest(BaseModel):
    id: str
    answer: str


class MarkResponse(BaseModel):
    ok: bool
    correct: bool
    score: int
    feedback: str
    # present for fraction questions; harmless to leave optional otherwise
    expected: Optional[str] = None
    expected_str: Optional[str] = None


# ---------- Mark batch ----------


class MarkBatchItem(BaseModel):
    id: str
    response: MarkResponse


class MarkBatchRequest(BaseModel):
    items: List[MarkRequest]
    # Client may send it, but server computes its own duration anyway.
    duration_ms: Optional[int] = None


class MarkBatchResponse(BaseModel):
    ok: bool
    total: int
    results: List[MarkBatchItem]
    attempt_id: Optional[int] = None
