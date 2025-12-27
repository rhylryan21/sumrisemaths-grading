from __future__ import annotations

import random as _rnd
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from bank import get_questions
from schemas.questions import QuestionOut

router = APIRouter(tags=["questions"])


@router.get("/questions", response_model=List[QuestionOut])
def list_questions(
    topic: Optional[str] = None,
    limit: Optional[int] = Query(default=None, ge=1, le=100),
    random: bool = Query(default=False, description="If true, shuffle before limiting"),
):
    # materialize once so we can filter/shuffle/limit deterministically
    qs = list(get_questions())

    if topic:
        qs = [q for q in qs if q.get("topic") == topic]

    if random:
        _rnd.shuffle(qs)

    if limit is not None:
        qs = qs[:limit]

    return qs


@router.get("/questions/{qid}", response_model=QuestionOut)
def get_question_detail(qid: str):
    q = next((qq for qq in get_questions() if qq["id"] == qid), None)
    if not q:
        raise HTTPException(status_code=404, detail="question not found")
    return q
