from fastapi import FastAPI
from bank import QUESTIONS
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from sympy import sympify
import logging
import re

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
        return MarkResponse(
            ok=False, correct=False, score=0, feedback="Unknown question id."
        )

    if q["type"] != "numeric":
        return MarkResponse(
            ok=False,
            correct=False,
            score=0,
            feedback="This question type isn't supported yet.",
        )

    # Validate characters like before
    expr = (req.answer or "").strip()
    if not expr:
        return MarkResponse(
            ok=False, correct=False, score=0, feedback="Please enter your answer."
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
        score = 1 if correct else 0
        feedback = (
            "Correct ✅" if correct else f"Not quite. Tip: check order of operations."
        )
        return MarkResponse(
            ok=True, correct=correct, score=score, feedback=feedback, expected=expected
        )
    except Exception:
        logger.exception("/mark failed id=%r answer=%r", req.id, req.answer)
        return MarkResponse(
            ok=False,
            correct=False,
            score=0,
            feedback="Sorry, I couldn't parse that. Try a simpler numeric answer.",
        )
