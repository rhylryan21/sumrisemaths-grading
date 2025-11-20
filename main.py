from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sympy import sympify
import logging
import re

logger = logging.getLogger('sumrise-grading')
logging.basicConfig(level=logging.INFO)

ALLOWED_RE = re.compile(r"[0-9\s+\-*/^().]{1,100}")
app = FastAPI(title="Sumrise Maths – Grading API")

# Allow calls from the Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "https://sumrise-maths.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class EvalRequest(BaseModel):
    expr: str

@app.get("/")
def health():
    return {"ok": True}

@app.post("/evaluate")
def evaluate(req: EvalRequest):
    expr = (req.expr or "").strip()
    # 1) Validate length and characters
    if not expr:
        return {"ok": False, "error": "Please enter an expression (e.g., 3^2 + 4^2)."}
    logger.info("expr raw=%r chars=%s", expr, [f"{c}:{ord(c)}" for c in expr])

    if not ALLOWED_RE.fullmatch(expr):
        return {
            "ok": False,
            "error": "Only digits, + - * / ^ ( ) . and spaces are allowed (max 100 chars).",
        }
    try:
        expr_norm = expr.replace("^", "**")
        value = sympify(expr_norm).evalf()
        result = float(value)
        logger.info("/evaluate ok expr=%r result=%s", expr, result)
        return {"ok": True, "value": result}
    except Exception:
        logger.exception("/evaluate failed expr=%r", expr)
        return {"ok": False, "error": "Sorry, I couldn't evaluate that. Check brackets and operators."}
