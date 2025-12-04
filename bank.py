from __future__ import annotations
import json, pathlib
from typing import List
from pydantic import BaseModel


class Question(BaseModel):
    id: str
    topic: str
    prompt: str
    answer_expr: str
    type: str


_bank_path = pathlib.Path(__file__).with_name("questions.json")


def _read() -> list[dict]:
    return json.loads(_bank_path.read_text(encoding="utf-8"))


def _validate(raw: list[dict]) -> list[dict]:
    return [Question(**q).model_dump() for q in raw]


# in-memory cache
QUESTIONS: list[dict] = _validate(_read())


def reload_bank() -> int:
    """Reload questions.json into the in-memory QUESTIONS list."""
    global QUESTIONS
    QUESTIONS = _validate(_read())
    return len(QUESTIONS)
