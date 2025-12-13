from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException

from bank import get_questions
from schemas.questions import QuestionOut

router = APIRouter(tags=["questions"])


@router.get("/questions", response_model=List[QuestionOut])
def list_questions():
    return list(get_questions())


@router.get("/questions/{qid}", response_model=QuestionOut)
def get_question_detail(qid: str):
    q = next((qq for qq in get_questions() if qq["id"] == qid), None)
    if not q:
        raise HTTPException(status_code=404, detail="question not found")
    return q
