# services/grading/routers/marking.py
import logging
import re
import time
from math import gcd
from typing import List

from fastapi import APIRouter
from sympy import Rational, nsimplify, sympify

from bank import QUESTIONS
from db import SessionLocal
from models import Attempt
from schemas.marking import (
    EvalRequest,
    MarkBatchItem,
    MarkBatchRequest,
    MarkBatchResponse,
    MarkBatchResult,
    MarkRequest,
    MarkResponse,
    QuestionOut,
)

logger = logging.getLogger("sumrise-grading")

router = APIRouter(prefix="", tags=["marking"])  # keep same paths as before

ALLOWED_RE = re.compile(r"[0-9\s+\-*/^().]{1,100}")
TOL = 1e-6

# ---------- Schemas live in schemas/marking.py ----------


# ---------- Helpers ----------
def _eval_numeric(expr_str: str) -> float:
    expr_norm = (expr_str or "").replace("^", "**")
    val = sympify(expr_norm).evalf()
    return float(val)


def _canonical_fraction_str(expr_str: str) -> tuple[str, list[str]]:
    expr_norm = (expr_str or "").replace("^", "**").strip()

    if "/" in expr_norm:
        num_str, den_str = expr_norm.split("/", 1)
        num_str, den_str = num_str.strip(), den_str.strip()
        if num_str.lstrip("+-").isdigit() and den_str.lstrip("+-").isdigit():
            n, d = int(num_str), int(den_str)
            if d == 0:
                raise ValueError("division by zero")
            g = gcd(abs(n), abs(d)) or 1
            steps = [
                f"Start: {n}/{d}",
                f"GCD({abs(n)},{abs(d)}) = {g}",
                f"Simplify: {n//g}/{d//g}",
            ]
            return f"{n//g}/{d//g}", steps

    val = nsimplify(sympify(expr_norm))
    if not isinstance(val, Rational):
        val = Rational(val).limit_denominator()
    n, d = int(val.p), int(val.q)
    return f"{n}/{d}", [f"Converted to fraction: {n}/{d}"]


def _mark_one(id_: str, answer: str) -> MarkResponse:
    q = next((qq for qq in QUESTIONS if qq["id"] == id_), None)
    if not q:
        return MarkResponse(ok=False, correct=False, score=0, feedback="Unknown question id.")

    expr = (answer or "").strip()

    if q["type"] == "numeric":
        if not expr:
            return MarkResponse(
                ok=False, correct=False, score=0, feedback="Please enter your answer (e.g., 25)."
            )
        if not ALLOWED_RE.fullmatch(expr):
            return MarkResponse(
                ok=False,
                correct=False,
                score=0,
                feedback="Only digits, + - * / ^ ( ) . and spaces allowed (max 100 chars).",
            )
        try:
            expected = _eval_numeric(q["answer_expr"])
            user_val = _eval_numeric(expr)
            correct = abs(user_val - expected) < TOL
            return MarkResponse(
                ok=True,
                correct=correct,
                score=1 if correct else 0,
                feedback="Correct ✅" if correct else "Not quite.",
                expected=expected,
            )
        except Exception:
            logger.exception("/mark numeric failed id=%r answer=%r", id_, answer)
            return MarkResponse(
                ok=False,
                correct=False,
                score=0,
                feedback="I couldn't parse that. Check brackets and operators.",
            )

    elif q["type"] == "simplify_fraction":
        if not expr:
            return MarkResponse(
                ok=False, correct=False, score=0, feedback="Please enter your answer (e.g., 3/4)."
            )
        if not ALLOWED_RE.fullmatch(expr):
            return MarkResponse(
                ok=False,
                correct=False,
                score=0,
                feedback="Only digits, + - * / ^ ( ) . and spaces allowed (max 100 chars).",
            )
        try:
            provided_fraction = False
            fully_reduced = True
            if "/" in expr:
                num_str, den_str = expr.split("/", 1)
                num_str, den_str = num_str.strip(), den_str.strip()
                if num_str.lstrip("+-").isdigit() and den_str.lstrip("+-").isdigit():
                    provided_fraction = True
                    n, d = int(num_str), int(den_str)
                    if d == 0:
                        return MarkResponse(
                            ok=False, correct=False, score=0, feedback="Denominator cannot be zero."
                        )
                    g = gcd(abs(n), abs(d)) or 1
                    fully_reduced = g == 1

            expected_str, expected_steps = _canonical_fraction_str(q["answer_expr"])
            user_str, _ = _canonical_fraction_str(expr)

            if user_str == expected_str:
                if provided_fraction and not fully_reduced:
                    return MarkResponse(
                        ok=True,
                        correct=False,
                        score=0,
                        feedback="Close — give your answer in simplest form.",
                        expected_str=expected_str,
                    )
                return MarkResponse(
                    ok=True,
                    correct=True,
                    score=1,
                    feedback="Correct ✅",
                    expected_str=expected_str,
                    steps=expected_steps,
                )

            return MarkResponse(
                ok=True,
                correct=False,
                score=0,
                feedback="Not quite. Try fully reducing the fraction.",
                expected_str=expected_str,
            )
        except Exception:
            logger.exception("/mark simplify_fraction failed id=%r answer=%r", id_, answer)
            return MarkResponse(
                ok=False,
                correct=False,
                score=0,
                feedback="I couldn't parse that. Try a form like 3/4 or 0.75.",
            )
    else:
        return MarkResponse(
            ok=False, correct=False, score=0, feedback="This question type isn't supported yet."
        )


# ---------- Routes ----------
@router.post("/evaluate")
def evaluate(req: EvalRequest):
    expr = (req.expr or "").strip()
    if not expr:
        return {"ok": False, "feedback": "Please enter an expression (e.g., 3^2 + 4^2)."}
    logger.info("expr raw=%r chars=%s", expr, [f"{c}:{ord(c)}" for c in expr])

    if not ALLOWED_RE.fullmatch(expr):
        return {
            "ok": False,
            "feedback": "Only digits, + - * / ^ ( ) . and spaces are allowed (max 100 chars).",
        }
    try:
        expr_norm = expr.replace("^", "**")
        value = sympify(expr_norm).evalf()
        result = float(value)
        logger.info("/evaluate ok expr=%r result=%s", expr, result)
        return {"ok": True, "value": result}
    except Exception:
        logger.exception("/evaluate failed expr=%r", expr)
        return {
            "ok": False,
            "error": "Sorry, I couldn't evaluate that. Check brackets and operators.",
        }


@router.get("/questions", response_model=List[QuestionOut])
def get_questions():
    return [
        {"id": q["id"], "topic": q["topic"], "prompt": q["prompt"], "type": q["type"]}
        for q in QUESTIONS
    ]


@router.post("/mark", response_model=MarkResponse)
def mark(req: MarkRequest):
    return _mark_one(req.id, req.answer)


@router.post("/mark-batch", response_model=MarkBatchResponse)
def mark_batch(req: MarkBatchRequest):
    start_ns = time.perf_counter_ns()
    results: List[MarkBatchResult] = []
    correct = 0
    for it in req.items:
        r = _mark_one(it.id, it.answer)
        if r.correct:
            correct += 1
        results.append(MarkBatchResult(id=it.id, response=r))
    end_ns = time.perf_counter_ns()
    duration_ms = (end_ns - start_ns) // 1_000_000

    attempt_id = None
    db = SessionLocal()
    try:
        attempt = Attempt(
            total=len(req.items),
            correct=correct,
            items=[{"id": r.id, "response": r.response.model_dump()} for r in results],
            duration_ms=duration_ms,
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)
        attempt_id = attempt.id
    finally:
        db.close()

    return MarkBatchResponse(
        ok=True, total=len(req.items), correct=correct, results=results, attempt_id=attempt_id
    )
