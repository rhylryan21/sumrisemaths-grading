# services/grading/bank.py

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, ValidationError

_BASE = Path(__file__).resolve().parent
_DATA_DIR = _BASE / "data" / "questions"  # preferred sharded dir
_FALLBACK_JSON = _BASE / "questions.json"  # legacy single file


class QuestionModel(BaseModel):
    id: str
    topic: str
    prompt: str
    type: str
    answer_expr: Optional[str] = None


def _iter_jsonl(p: Path) -> Iterable[Dict[str, Any]]:
    with p.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("//"):
                continue
            try:
                yield json.loads(s)
            except json.JSONDecodeError:
                # Skip malformed rows instead of crashing the whole endpoint
                continue


def _iter_json(p: Path) -> Iterable[Dict[str, Any]]:
    with p.open("r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            # Treat a broken JSON file as empty
            data = []
    if isinstance(data, list):
        for obj in data:
            yield obj
    else:
        # Non-list root -> ignore
        return


class QuestionBank:
    _questions: List[Dict[str, Any]] = []

    @classmethod
    def load(cls) -> List[Dict[str, Any]]:
        if not cls._questions:
            cls.reload()
        return cls._questions

    @classmethod
    def reload(cls) -> int:
        questions: List[Dict[str, Any]] = []

        # Prefer sharded directory if present
        if _DATA_DIR.exists():
            for p in sorted(_DATA_DIR.rglob("*")):
                if not p.is_file():
                    continue
                suf = p.suffix.lower()
                if suf == ".jsonl":
                    source = _iter_jsonl(p)
                elif suf == ".json":
                    source = _iter_json(p)
                else:
                    continue

                for raw in source:
                    try:
                        q = QuestionModel(**raw).model_dump()
                        questions.append(q)
                    except ValidationError:
                        # Skip invalid records
                        continue

        # Fallback to legacy single file if nothing valid loaded
        if not questions and _FALLBACK_JSON.exists():
            for raw in _iter_json(_FALLBACK_JSON):
                try:
                    q = QuestionModel(**raw).model_dump()
                    questions.append(q)
                except ValidationError:
                    continue

        cls._questions = questions
        return len(cls._questions)


# Public API
def get_questions() -> List[Dict[str, Any]]:
    return QuestionBank.load()


def reload_bank() -> int:
    return QuestionBank.reload()  # <- fix the earlier typo
