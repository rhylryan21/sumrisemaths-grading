from __future__ import annotations
import json, pathlib
from typing import List
from pydantic import BaseModel


class Question(BaseModel):
    id: str
    topic: str
    prompt: str
    answer_expr: str
    type: str  # e.g., "numeric"


def load_questions(path: str | None = None) -> List[dict]:
    p = (
        pathlib.Path(path)
        if path
        else pathlib.Path(__file__).with_name("questions.json")
    )
    data = json.loads(p.read_text(encoding="utf-8"))
    # validate and return as plain dicts
    return [Question(**q).model_dump() for q in data]


# Eager load at import time (simple for now)
QUESTIONS = load_questions()
