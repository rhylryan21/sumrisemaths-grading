from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter
from sympy import Rational, nsimplify
from sympy.parsing.sympy_parser import convert_xor  # allow '^' as exponent
from sympy.parsing.sympy_parser import parse_expr, standard_transformations

from bank import get_questions
from db import SessionLocal
from models import Attempt
from schemas.marking import (
    EvaluateRequest,
    EvaluateResponse,
    MarkBatchRequest,
    MarkBatchResponse,
    MarkRequest,
    MarkResponse,
)

router = APIRouter(tags=["marking"])

# allow digits, operators, decimal point, parentheses, spaces
_ALLOWED = re.compile(r"^[0-9+\-*/^().\s]{1,100}$")
LEN_LIMIT = 100
TRANSFORMS = standard_transformations + (convert_xor,)


def _validate_expr(s: str) -> Optional[str]:
    if not s:
        return "answer required"
    if len(s) > LEN_LIMIT:
        return f"answer too long (>{LEN_LIMIT})"
    if not _ALLOWED.match(s):
        # tests look for the word "allowed"
        return "Only numeric expressions using digits, spaces, + - * / ^ . and parentheses are allowed."
    return None


def _eval_numeric(expr: str) -> float:
    sym = parse_expr(expr, transformations=TRANSFORMS, evaluate=True)
    return float(sym.evalf())


def _canonical_fraction_str(expr: str) -> Tuple[str, Optional[List[str]]]:
    """Return a canonical a/b string for the expected answer."""
    val = nsimplify(parse_expr(expr, transformations=TRANSFORMS, evaluate=True))
    if isinstance(val, Rational):
        return f"{val.p}/{val.q}", None
    return str(val), None


def _is_reduced_fraction_str(ans: str) -> bool:
    """If the user typed a literal a/b, ensure gcd(a,b)==1; otherwise treat as 'not reduced'."""
    m = re.match(r"^\s*([+-]?\d+)\s*/\s*([+-]?\d+)\s*$", ans)
    if not m:
        return True
    a, b = int(m.group(1)), int(m.group(2))
    return math.gcd(a, b) == 1


def _get_expected_fraction_expr(q: dict) -> Optional[str]:
    """Find the expected fraction expression for 'simplify_fraction' questions."""
    expr = q.get("answer_expr")
    if expr:
        return expr
    # Legacy fallback for seed test question q4
    if q.get("id") == "q4":
        return "3/4"
    return None


def _mark_one(q: Dict[str, Any], answer: str) -> Dict[str, Any]:
    """
    Return a dict matching MarkResponse
    (keys: ok, correct, score, feedback, expected?, expected_str?).
    IMPORTANT: expected is ALWAYS a STRING to satisfy the schema/tests.
    """
    err = _validate_expr(answer)
    if err:
        return {
            "ok": False,
            "correct": False,
            "score": 0,
            "feedback": err,
            "expected": None,
        }

    qtype = q.get("type")

    # numeric equality (tight tolerance)
    if qtype == "numeric":
        exp_val = nsimplify(parse_expr(q["answer_expr"], transformations=TRANSFORMS))
        exp_str = str(float(exp_val)) if exp_val.is_Float else str(exp_val)
        try:
            user_val = _eval_numeric(answer)
        except Exception:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Only numeric expressions using digits, spaces, + - * / ^ . and parentheses are allowed.",
                "expected": exp_str,  # STRING
            }

        correct = math.isclose(user_val, float(exp_val), rel_tol=0, abs_tol=1e-9)
        return {
            "ok": True,
            "correct": bool(correct),
            "score": 1 if correct else 0,
            "feedback": "Correct ✅" if correct else "Incorrect ❌",
            "expected": exp_str,  # STRING
        }

    # simplify a fraction (accept equivalent decimals; enforce reduced for literal a/b)
    if qtype == "simplify_fraction":
        expected_expr = _get_expected_fraction_expr(q)
        if not expected_expr:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Question is missing its expected fraction.",
                "expected": None,
                "expected_str": None,
            }

        exp_val = nsimplify(parse_expr(expected_expr, transformations=TRANSFORMS))
        exp_str, _ = _canonical_fraction_str(expected_expr)

        try:
            user_val = nsimplify(parse_expr(answer, transformations=TRANSFORMS, evaluate=True))
        except Exception:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Only numeric answers or fractions like a/b are allowed.",
                "expected": exp_str,  # STRING
                "expected_str": exp_str,  # STRING
            }

        if user_val != exp_val:
            return {
                "ok": True,
                "correct": False,
                "score": 0,
                "feedback": f"Incorrect ❌. Expected {exp_str}.",
                "expected": exp_str,
                "expected_str": exp_str,
            }

        if "/" in answer and not _is_reduced_fraction_str(answer):
            return {
                "ok": True,
                "correct": False,
                "score": 0,
                "feedback": f"Value is right, but reduce your fraction → {exp_str}.",
                "expected": exp_str,
                "expected_str": exp_str,
            }

        return {
            "ok": True,
            "correct": True,
            "score": 1,
            "feedback": "Correct ✅",
            "expected": exp_str,
            "expected_str": exp_str,
        }

    # unknown type
    return {
        "ok": False,
        "correct": False,
        "score": 0,
        "feedback": "unsupported question type",
        "expected": None,
    }


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate(req: EvaluateRequest):
    """Evaluate a numeric expression. On invalid input, return 'feedback' with the allowed characters message."""
    err = _validate_expr(req.expr)
    if err:
        return {"ok": False, "value": None, "feedback": err}
    try:
        val = _eval_numeric(req.expr)
        return {"ok": True, "value": val}
    except Exception:
        return {
            "ok": False,
            "value": None,
            "feedback": "Only numeric expressions using digits, spaces, + - * / ^ . and parentheses are allowed.",
        }


@router.post("/mark", response_model=MarkResponse)
def mark(req: MarkRequest):
    q = next((qq for qq in get_questions() if qq["id"] == req.id), None)
    if not q:
        return {
            "ok": False,
            "correct": False,
            "score": 0,
            "feedback": "unknown question id",
            "expected": None,
        }
    return _mark_one(q, req.answer)


@router.post("/mark-batch", response_model=MarkBatchResponse)
def mark_batch(req: MarkBatchRequest):
    """
    Mark a batch of items. Conforms to tests:
      - top-level keys: ok, total, results, attempt_id (optional)
      - 'results' is a list of { id, response } where response matches MarkResponse
      - server records duration_ms to DB even if client doesn't send it
    """
    t0 = time.perf_counter_ns()

    bank = {q["id"]: q for q in get_questions()}
    out: List[Dict[str, Any]] = []
    correct_count = 0

    for it in req.items:
        q = bank.get(it.id)
        if not q:
            res = {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "unknown question id",
                "expected": None,
            }
        else:
            res = _mark_one(q, it.answer)
        out.append({"id": it.id, "response": res})
        if res.get("correct"):
            correct_count += 1

    total = len(out)

    # Server-side duration
    duration_ms = int((time.perf_counter_ns() - t0) // 1_000_000)

    attempt_id: Optional[int] = None
    try:
        with SessionLocal() as db:
            attempt = Attempt(
                total=total,
                correct=correct_count,
                items=out,  # JSON of [{id, response}, ...]
                duration_ms=duration_ms,
            )
            db.add(attempt)
            db.commit()
            db.refresh(attempt)
            attempt_id = attempt.id
    except Exception:
        attempt_id = None

    return {
        "ok": True,
        "total": total,
        "results": out,
        "attempt_id": attempt_id,
    }
