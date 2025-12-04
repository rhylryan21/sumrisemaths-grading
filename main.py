import os
from fastapi import FastAPI, Header
from bank import QUESTIONS, reload_bank  # replace old import of QUESTIONS if needed
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from sympy import sympify
import logging
import re
from sympy import sympify, nsimplify, Rational
from math import gcd

def _canonical_fraction_str(expr_str: str) -> tuple[str, list[str]]:
    """Return simplified fraction 'a/b' and optional steps."""
    expr_norm = (expr_str or "").replace("^", "**").strip()

    # If it's a pure a/b with integers, show proper GCD steps
    if "/" in expr_norm and all(p.strip().lstrip("+-").isdigit() for p in expr_norm.split("/", 1)):
        n_str, d_str = expr_norm.split("/", 1)
        n, d = int(n_str), int(d_str)
        if d == 0:
            raise ValueError("division by zero")
        g = gcd(abs(n), abs(d)) or 1
        steps = [f"Start: {n}/{d}", f"GCD({abs(n)},{abs(d)}) = {g}", f"Simplify: {n//g}/{d//g}"]
        return f"{n//g}/{d//g}", steps

    # Otherwise, let sympy find a rational and simplify
    val = nsimplify(sympify(expr_norm))
    if not isinstance(val, Rational):
        val = Rational(val).limit_denominator()
    return f"{int(val.p)}/{int(val.q)}", [f"Converted to fraction: {int(val.p)}/{int(val.q)}"]

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


TOL = 1e-6


def _eval_numeric(expr_str: str) -> float:
    # user-friendly: treat ^ as power
    expr_norm = (expr_str or "").replace("^", "**")
    val = sympify(expr_norm).evalf()
    return float(val)


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
    # Return questions without the answer field
    return [
        QuestionOut(id=q["id"], topic=q["topic"], prompt=q["prompt"], type=q["type"])
        for q in QUESTIONS
    ]


@app.post("/mark", response_model=MarkResponse)
def mark(req: MarkRequest):
    q = next((qq for qq in QUESTIONS if qq["id"] == req.id), None)
    if not q:
        return MarkResponse(ok=False, correct=False, score=0, feedback="Unknown question id.")

    if q["type"] == "numeric":
        # ... your existing numeric logic ...
        ...

    elif q["type"] == "simplify_fraction":
        expr = (req.answer or "").strip()
        if not expr:
            return MarkResponse(ok=False, correct=False, score=0, feedback="Please enter your answer (e.g., 3/4).")
        if not ALLOWED_RE.fullmatch(expr):
            return MarkResponse(ok=False, correct=False, score=0,
                                feedback="Only digits, + - * / ^ ( ) . and spaces allowed (max 100 chars).")
        try:
            expected_str, expected_steps = _canonical_fraction_str(q["answer_expr"])
            user_str, _ = _canonical_fraction_str(expr)
            correct = (user_str == expected_str)
            return MarkResponse(
                ok=True,
                correct=correct,
                score=1 if correct else 0,
                feedback="Correct ✅" if correct else "Not quite. Try fully reducing the fraction.",
                expected_str=expected_str,
                steps=expected_steps if correct else None,
            )
        except Exception:
            logger.exception("/mark simplify_fraction failed id=%r answer=%r", req.id, req.answer)
            return MarkResponse(ok=False, correct=False, score=0,
                                feedback="I couldn't parse that. Try a form like 3/4 or 0.75.")
    else:
        return MarkResponse(ok=False, correct=False, score=0, feedback="This question type isn't supported yet.")


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
