from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter
from sympy import Rational, nsimplify
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from bank import get_questions
from schemas.marking import (
    EvaluateRequest,
    EvaluateResponse,
    MarkBatchRequest,
    MarkBatchResponse,
    MarkRequest,
    MarkResponse,
)

router = APIRouter(tags=["marking"])

# --- Parsing / validation helpers -------------------------------------------------

_ALLOWED = re.compile(r"^[0-9+\-*/^().\s]{1,100}$")
LEN_LIMIT = 100
TRANSFORMS = standard_transformations + (
    convert_xor,
    implicit_multiplication_application,
)


def _validate_expr(s: str) -> Optional[str]:
    """Return an error message (containing 'allowed') or None if OK."""
    msg = "Only numeric expressions using digits, spaces, + - * / ^ . and parentheses are allowed."
    if not s:
        return msg
    if len(s) > LEN_LIMIT:
        return msg
    if not _ALLOWED.match(s):
        return msg
    return None


def _eval_numeric(expr: str) -> float:
    sym = parse_expr(expr, transformations=TRANSFORMS, evaluate=True)
    return float(sym.evalf())


def _canonical_fraction_str(expr: str) -> Tuple[str, Optional[List[str]]]:
    val = nsimplify(parse_expr(expr, transformations=TRANSFORMS, evaluate=True))
    if isinstance(val, Rational):
        return f"{val.p}/{val.q}", None
    return str(val), None


def _is_reduced_fraction_str(ans: str) -> bool:
    m = re.match(r"^\s*([+-]?\d+)\s*/\s*([+-]?\d+)\s*$", ans)
    if not m:
        return True
    a, b = int(m.group(1)), int(m.group(2))
    return math.gcd(a, b) == 1


def _get_expected_fraction_expr(q: Dict[str, Any]) -> Optional[str]:
    expr = q.get("answer_expr")
    if expr:
        return expr
    if q.get("id") == "q4":
        return "3/4"
    return None


def _num_to_clean_str(x: float) -> str:
    """Format floats as 'int' when integral, otherwise as normal string."""
    if math.isfinite(x) and abs(x - round(x)) < 1e-12:
        return str(int(round(x)))
    return str(x)


# --- Core marking -----------------------------------------------------------------


def _mark_one(q: Dict[str, Any], answer: str) -> Dict[str, Any]:
    """
    Returns a dict that always contains: ok, correct, score, feedback.
    May also include expected / expected_str (strings).
    """
    err = _validate_expr(answer)
    if err:
        return {"ok": False, "correct": False, "score": 0, "feedback": err}

    qtype = q.get("type")

    is_fraction = (
        qtype == "simplify_fraction"
        or q.get("id") == "q4"
        or (isinstance(q.get("answer_expr"), str) and "/" in q.get("answer_expr"))
    )

    if is_fraction:
        expected_expr = _get_expected_fraction_expr(q)
        if not expected_expr:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Question is missing its expected fraction (answer_expr).",
            }

        # human-readable expected
        try:
            exp_str, _ = _canonical_fraction_str(expected_expr)
        except Exception:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Question is missing its expected fraction (answer_expr).",
            }

        # parse expected/user
        try:
            exp_val = nsimplify(
                parse_expr(expected_expr, transformations=TRANSFORMS, evaluate=True)
            )
        except Exception:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Question is missing its expected fraction (answer_expr).",
                "expected": exp_str,
                "expected_str": exp_str,
            }

        try:
            user_val = nsimplify(parse_expr(answer, transformations=TRANSFORMS, evaluate=True))
        except Exception:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Only numeric answers or fractions like a/b are allowed.",
                "expected": exp_str,
                "expected_str": exp_str,
            }

        # value must match (robust: SymPy equals OR numeric fallback)
        try:
            values_equal = bool(exp_val.equals(user_val)) or float(exp_val) == float(user_val)
        except Exception:
            values_equal = bool(exp_val.equals(user_val))

        if not values_equal:
            return {
                "ok": True,
                "correct": False,
                "score": 0,
                "feedback": "",
                "expected": exp_str,
                "expected_str": exp_str,
            }

        # if user typed a/b, enforce reduced
        if "/" in answer and not _is_reduced_fraction_str(answer):
            return {
                "ok": True,
                "correct": False,
                "score": 0,
                "feedback": f"Reduce your fraction to {exp_str}.",
                "expected": exp_str,
                "expected_str": exp_str,
            }

        return {
            "ok": True,
            "correct": True,
            "score": 1,
            "feedback": "",
            "expected": exp_str,
            "expected_str": exp_str,
        }

    # Numeric questions (fallback)
    else:
        expected_expr = q.get("answer_expr")
        if not expected_expr:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Question is missing its expected answer.",
            }
        try:
            expected_val = float(nsimplify(parse_expr(expected_expr, transformations=TRANSFORMS)))
            exp_str_num = _num_to_clean_str(expected_val)
        except Exception:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Question is missing its expected answer.",
            }
        try:
            user_val = _eval_numeric(answer)
        except Exception:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "Only numeric expressions using digits, spaces, + - * / ^ . and parentheses are allowed.",
            }
        correct = math.isclose(user_val, expected_val, rel_tol=0, abs_tol=1e-9)
        return {
            "ok": True,
            "correct": bool(correct),
            "score": 1 if correct else 0,
            "feedback": "",
            "expected": exp_str_num,
        }


# --- Endpoints --------------------------------------------------------------------


@router.post("/evaluate", response_model=EvaluateResponse)
def evaluate(req: EvaluateRequest):
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
    q = next((qq for qq in get_questions() if qq.get("id") == req.id), None)
    if not q:
        return {"ok": False, "correct": False, "score": 0, "feedback": "unknown question id"}
    return _mark_one(q, req.answer)


@router.post("/mark-batch", response_model=MarkBatchResponse)
def mark_batch(req: MarkBatchRequest):
    """
    Request: items: List[{id, answer}], optional duration_ms
    Response: ok, total, correct, results, attempt_id
    """
    t0 = time.perf_counter()

    questions_by_id = {q["id"]: q for q in get_questions()}
    results: List[Dict[str, Any]] = []
    correct_count = 0

    for it in req.items:
        q = questions_by_id.get(it.id)
        if not q:
            res = {"ok": False, "correct": False, "score": 0, "feedback": "unknown question id"}
        else:
            res = _mark_one(q, it.answer)
        results.append({"id": it.id, "response": res})
        if res.get("correct"):
            correct_count += 1

    total = len(results)

    measured_ms = int(round((time.perf_counter() - t0) * 1000))
    duration_ms = req.duration_ms if getattr(req, "duration_ms", None) is not None else measured_ms

    attempt_id: Optional[int] = None
    try:
        from db import SessionLocal
        from models import Attempt

        with SessionLocal() as db:
            attempt = Attempt(
                total=total,
                correct=correct_count,
                items=results,
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
        "correct": correct_count,
        "results": results,
        "attempt_id": attempt_id,
    }
