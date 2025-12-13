import logging
import os
import re
import time
from math import gcd
from typing import List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sympy import Rational, nsimplify, sympify

from bank import QUESTIONS, reload_bank  # replace old import of QUESTIONS if needed
from db import Base, SessionLocal, engine
from models import Attempt

logger = logging.getLogger("sumrise-grading")
logging.basicConfig(level=logging.INFO)

ALLOWED_RE = re.compile(r"[0-9\s+\-*/^().]{1,100}")

app = FastAPI(title="Sumrise Maths – Grading API")

# Allow calls from the Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://sumrise-maths.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    expected: Optional[float] = None  # numeric for now
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


class AttemptOut(BaseModel):
    id: int
    created_at: str
    total: int
    correct: int
    items: list

    @classmethod
    def from_orm_row(cls, a) -> "AttemptOut":
        # created_at -> ISO string for easy use on the web
        return cls(
            id=a.id,
            created_at=a.created_at.isoformat(),
            total=a.total,
            correct=a.correct,
            items=a.items,
        )


TOL = 1e-6


def _eval_numeric(expr_str: str) -> float:
    # user-friendly: treat ^ as power
    expr_norm = (expr_str or "").replace("^", "**")
    val = sympify(expr_norm).evalf()
    return float(val)


def _canonical_fraction_str(expr_str: str) -> tuple[str, list[str]]:
    """
    Return a simplified fraction "a/b" and short steps.
    Accepts inputs like "6/8", "0.75", "3^2/4^2", etc.
    """
    expr_norm = (expr_str or "").replace("^", "**").strip()

    # If it's a plain integer fraction a/b, show real GCD steps.
    if "/" in expr_norm:
        num_str, den_str = expr_norm.split("/", 1)
        num_str, den_str = num_str.strip(), den_str.strip()
        # allow +/-, digits only to avoid accidental floats here
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

    # Otherwise, let sympy evaluate and reduce
    val = nsimplify(sympify(expr_norm))  # exact rational if possible
    if not isinstance(val, Rational):
        val = Rational(val).limit_denominator()
    n, d = int(val.p), int(val.q)
    return f"{n}/{d}", [f"Converted to fraction: {n}/{d}"]


def _mark_one(id_: str, answer: str) -> MarkResponse:
    """Shared logic used by /mark and /mark-batch."""
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
            # detect plain a/b input to enforce simplest form
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


@app.get("/")
def health():
    return {"ok": True}


@app.post("/evaluate")
def evaluate(req: EvalRequest):
    expr = (req.expr or "").strip()
    # 1) Validate length and characters
    if not expr:
        return {
            "ok": False,
            "feedback": "Please enter an expression (e.g., 3^2 + 4^2).",
        }
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


@app.get("/questions", response_model=List[QuestionOut])
def get_questions():
    return [
        {"id": q["id"], "topic": q["topic"], "prompt": q["prompt"], "type": q["type"]}
        for q in QUESTIONS
    ]


@app.post("/mark", response_model=MarkResponse)
def mark(req: MarkRequest):
    return _mark_one(req.id, req.answer)


@app.post("/mark-batch", response_model=MarkBatchResponse)
def mark_batch(req: MarkBatchRequest):
    start_ns = time.perf_counter_ns()
    results: List[MarkBatchResult] = []
    correct = 0
    for it in req.items:
        r = _mark_one(it.id, it.answer)
        if r.correct:
            correct += 1
        results.append(MarkBatchResult(id=it.id, response=r))
    # measure duration up to here (marking work only)
    end_ns = time.perf_counter_ns()
    duration_ms = (end_ns - start_ns) // 1_000_000
    # persist the summary
    attempt_id = None
    try:
        db = SessionLocal()
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

    # include attempt_id in response (optional)
    return MarkBatchResponse(
        ok=True, total=len(req.items), correct=correct, results=results, attempt_id=attempt_id
    )


@app.post("/admin/reload")
def admin_reload(x_admin_token: str | None = Header(default=None)):
    token = os.getenv("ADMIN_TOKEN", "")  # <-- read at request time
    if not token:
        return {"ok": False, "error": "ADMIN_TOKEN not configured on server."}
    if x_admin_token != token:
        return {"ok": False, "error": "Unauthorized."}
    n = reload_bank()
    logger.info("/admin/reload: reloaded %s questions", n)
    return {"ok": True, "count": n}


@app.get("/attempts/{attempt_id}", response_model=AttemptOut)
def get_attempt(attempt_id: int):
    db = SessionLocal()
    try:
        a = db.query(Attempt).filter(Attempt.id == attempt_id).first()
        if not a:
            # FastAPI will make this a 404 if you prefer:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Attempt not found")
        return AttemptOut.from_orm_row(a)
    finally:
        db.close()


@app.get("/health/db")
def health_db():
    # Use engine.connect() and a SQLAlchemy textual SQL object
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"db_error: {type(e).__name__}: {e}")


@app.get("/health/migrations")
def health_migrations():
    try:
        with engine.connect() as conn:
            row = conn.execute(text("select version_num from alembic_version")).first()
        return {"ok": True, "version": row[0] if row else None}
    except Exception as e:
        return {"ok": False, "error": str(e)}
