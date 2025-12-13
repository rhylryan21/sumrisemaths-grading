from typing import List, Optional

from pydantic import BaseModel


class EvalRequest(BaseModel):
    expr: str


class QuestionOut(BaseModel):
    id: str
    topic: str
    prompt: str
    type: str


class MarkRequest(BaseModel):
    id: str
    answer: str


class MarkResponse(BaseModel):
    ok: bool
    correct: bool
    score: int
    feedback: str
    expected: Optional[float] = None
    expected_str: Optional[str] = None
    steps: Optional[List[str]] = None


class MarkBatchItem(BaseModel):
    id: str
    answer: str


class MarkBatchRequest(BaseModel):
    items: List[MarkBatchItem]


class MarkBatchResult(BaseModel):
    id: str
    response: MarkResponse


class MarkBatchResponse(BaseModel):
    ok: bool
    total: int
    correct: int
    results: List[MarkBatchResult]
    attempt_id: Optional[int] = None
