from __future__ import annotations

import math
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter
from sympy import Rational, nan, nsimplify, oo, zoo
from sympy.core.power import Pow
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

# --- Grading policy toggles ------------------------------------------------------
# If True: non-reduced correct fractions are marked incorrect with "Reduce..." feedback.
# If False: non-reduced correct fractions are marked correct with a gentle nudge.
STRICT_SIMPLIFICATION = False

# If True: give partial credit to non-reduced fractions (e.g., 0.5). If False: full credit.
PARTIAL_CREDIT_FOR_NON_REDUCED = False
NOT_REDUCED_SCORE_VALUE = 0.5  # used only when PARTIAL_CREDIT_FOR_NON_REDUCED = True

# --- Parsing / validation helpers ------------------------------------------------
LEN_LIMIT = 100
_INVALID_CHARS_MSG = (
    "Only numeric expressions using digits, spaces, + - * / ^ . and parentheses are allowed."
)
_NON_FINITE_MSG = "Expression is not finite (e.g., division by zero)."
_TOO_COMPLEX_MSG = "Expression is too complex."
_ALLOWED_RE = re.compile(r"^[0-9+\-*/^().\s]{1,100}$")

TRANSFORMS = standard_transformations + (
    convert_xor,
    implicit_multiplication_application,
)

# Reasonable hard-stops that won’t affect normal use
_MAX_OPS = 200
_MAX_INT_DIGITS = 200
_MAX_EXPONENT_ABS = 2000


def _validate_answer_text(s: str) -> Optional[str]:
    if s is None or not isinstance(s, str) or not s.strip():
        return "Answer required."
    if len(s) > LEN_LIMIT:
        return "Answer too long (> 100)."
    if _ALLOWED_RE.fullmatch(s) is None:
        return _INVALID_CHARS_MSG
    return None


def _validate_expr(s: str) -> Optional[str]:
    return _validate_answer_text(s)


def _get_raw_expected(q: Dict[str, Any]) -> Optional[str]:
    """
    Be tolerant to different bank shapes: accept answer_expr, expected, answer, expected_expr, expected_str.
    Also accept numeric literals (int/float) and stringify them.
    Return a non-empty trimmed string if found, else None.
    """
    for key in ("answer_expr", "expected", "answer", "expected_expr", "expected_str"):
        if key in q:
            v = q.get(key)
            if isinstance(v, (int, float)):
                return str(v)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _ensure_questions_have_answer_expr() -> None:
    """
    Keep the guard, but accept multiple expected keys.
    Raise with a clear list if truly missing.
    """
    missing = []
    for q in get_questions():
        if not _get_raw_expected(q):
            missing.append(q.get("id"))
    if missing:
        raise RuntimeError(
            f"Questions missing expected value (answer_expr/expected/answer): {missing}"
        )


router = APIRouter(tags=["marking"])
_ensure_questions_have_answer_expr()

# --- Finite & Complexity guards ---------------------------------------------------


def _assert_finite_sym(val: Any) -> None:
    finite = getattr(val, "is_finite", None)
    if finite is False:
        raise ValueError(_NON_FINITE_MSG)
    if val in (oo, -oo, zoo, nan):
        raise ValueError(_NON_FINITE_MSG)


def _assert_expr_complexity(sym: Any) -> None:
    """
    Treat plain scalars as trivial; only inspect SymPy expressions for complexity.
    """
    # Plain Python scalars
    if isinstance(sym, (int, float)):
        if not math.isfinite(float(sym)):
            raise ValueError(_NON_FINITE_MSG)
        return

    # SymPy numbers
    try:
        is_number = bool(getattr(sym, "is_number", False) or getattr(sym, "is_Number", False))
    except Exception:
        is_number = False
    if is_number:
        try:
            f = float(sym)
            if not math.isfinite(f):
                raise ValueError(_NON_FINITE_MSG)
        except Exception:
            pass
        return

    # SymPy expression
    try:
        if hasattr(sym, "count_ops") and sym.count_ops() > _MAX_OPS:
            raise ValueError(_TOO_COMPLEX_MSG)
    except Exception:
        raise ValueError(_TOO_COMPLEX_MSG)

    try:
        if hasattr(sym, "preorder_traversal"):
            for node in sym.preorder_traversal():
                if getattr(node, "is_Integer", False):
                    try:
                        n = int(node)
                        if len(str(abs(n))) > _MAX_INT_DIGITS:
                            raise ValueError(_TOO_COMPLEX_MSG)
                    except Exception:
                        raise ValueError(_TOO_COMPLEX_MSG)
                if isinstance(node, Pow):
                    exp = node.exp
                    if getattr(exp, "is_number", False):
                        try:
                            e = int(exp)
                            if abs(e) > _MAX_EXPONENT_ABS:
                                raise ValueError(_TOO_COMPLEX_MSG)
                        except Exception:
                            try:
                                f = float(exp)
                                if not math.isfinite(f) or abs(f) > _MAX_EXPONENT_ABS:
                                    raise ValueError(_TOO_COMPLEX_MSG)
                            except Exception:
                                raise ValueError(_TOO_COMPLEX_MSG)
    except ValueError:
        raise
    except Exception:
        raise ValueError(_TOO_COMPLEX_MSG)


# --- Low-level helpers ------------------------------------------------------------


def _eval_numeric(expr: str) -> float:
    sym = parse_expr(expr, transformations=TRANSFORMS, evaluate=True)
    _assert_expr_complexity(sym)
    _assert_finite_sym(sym)
    val = float(sym.evalf())
    if not math.isfinite(val):
        raise ValueError(_NON_FINITE_MSG)
    return val


def _canonical_fraction_str(expr: str) -> Tuple[str, Optional[List[str]]]:
    sym = parse_expr(expr, transformations=TRANSFORMS, evaluate=True)
    _assert_expr_complexity(sym)
    val = nsimplify(sym)
    _assert_finite_sym(val)
    if isinstance(val, Rational):
        return f"{val.p}/{val.q}", None
    return str(val), None


def _is_reduced_fraction_str(ans: str) -> bool:
    m = re.match(r"^\s*([+-]?\d+)\s*/\s*([+-]?\d+)\s*$", ans)
    if not m:
        return True
    a, b = int(m.group(1)), int(m.group(2))
    return math.gcd(a, b) == 1


def _num_to_clean_str(x: float) -> str:
    if math.isfinite(x) and abs(x - round(x)) < 1e-12:
        return str(int(round(x)))
    return str(x)


def _prepare_expected(q: Dict[str, Any]) -> Tuple[bool, Optional[str], Optional[Any], str]:
    """
    Returns: (is_fraction, expected_str, expected_value, error_feedback_if_missing)
      - expected_str: human display ("3/4" or "25")
      - expected_value: Rational | float used for equality checks
      - error_feedback_if_missing: message if we cannot compute expected_value
    """
    raw = _get_raw_expected(q)
    qtype = q.get("type")

    # Detect fraction either by explicit type or clean a/b pattern.
    frac_pat = re.compile(r"^[+-]?\s*\d+\s*/\s*[+-]?\s*\d+\s*$")
    is_fraction = (qtype == "simplify_fraction") or (bool(raw) and frac_pat.match(raw) is not None)

    if not (isinstance(raw, str) and raw.strip()):
        return (
            is_fraction,
            None,
            None,
            (
                "Question is missing its expected fraction (answer_expr)."
                if is_fraction
                else "Question is missing its expected answer."
            ),
        )

    raw_str = raw.strip()

    if is_fraction:
        # First try a fast path using integers to avoid parser quirks
        try:
            num_str, den_str = raw_str.split("/", 1)
            a = int(num_str.strip())
            b = int(den_str.strip())
            if b == 0:
                return (
                    True,
                    raw_str,
                    None,
                    "Question is missing its expected fraction (answer_expr).",
                )
            r = Rational(a, b)  # auto-reduced canonical
            exp_str = f"{r.p}/{r.q}"
            exp_val = r
            _assert_finite_sym(exp_val)
            return True, exp_str, exp_val, ""
        except Exception:
            # Fallback to sympy for anything non-standard
            try:
                exp_str, _ = _canonical_fraction_str(raw_str)
                exp_sym = parse_expr(raw_str, transformations=TRANSFORMS, evaluate=True)
                _assert_expr_complexity(exp_sym)
                exp_val = nsimplify(exp_sym)
                _assert_finite_sym(exp_val)
                return True, exp_str, exp_val, ""
            except Exception:
                return (
                    True,
                    raw_str,
                    None,
                    "Question is missing its expected fraction (answer_expr).",
                )

    # Numeric expected (non-fraction)
    # Fast path: plain number without going through sympy.
    try:
        val = float(raw_str)
        exp_str = _num_to_clean_str(val)
        return False, exp_str, val, ""
    except Exception:
        # Fallback to sympy to allow expressions like "3^2 + 4^2" as the stored expected.
        try:
            expected_sym = parse_expr(raw_str, transformations=TRANSFORMS, evaluate=True)
            _assert_expr_complexity(expected_sym)
            expected_val_sym = nsimplify(expected_sym)
            _assert_finite_sym(expected_val_sym)
            val = float(expected_val_sym)
            exp_str = _num_to_clean_str(val)
            return False, exp_str, val, ""
        except Exception:
            return False, raw_str, None, "Question is missing its expected answer."


# --- Core marking -----------------------------------------------------------------


def _mark_one(q: Dict[str, Any], answer: str) -> Dict[str, Any]:
    # Compute expected FIRST so every path can include it
    is_fraction, exp_str, exp_value, exp_err_msg = _prepare_expected(q)

    # Input validation
    msg = _validate_answer_text(answer)
    if msg:
        return {
            "ok": False,
            "correct": False,
            "score": 0,
            "feedback": msg,
            "expected": exp_str,
            "expected_str": exp_str,
        }

    # If expected couldn't be computed, bail with appropriate message
    if exp_value is None:
        return {
            "ok": False,
            "correct": False,
            "score": 0,
            "feedback": exp_err_msg
            or (
                "Question is missing its expected fraction (answer_expr)."
                if is_fraction
                else "Question is missing its expected answer."
            ),
            "expected": exp_str,
            "expected_str": exp_str,
        }

    # Optional per-question override
    require_simplified = bool(q.get("require_simplified")) if isinstance(q, dict) else False
    enforce_simplify = STRICT_SIMPLIFICATION or require_simplified

    if is_fraction:
        # Parse user
        try:
            user_sym = parse_expr(answer, transformations=TRANSFORMS, evaluate=True)
            _assert_expr_complexity(user_sym)
            user_val = nsimplify(user_sym)
            _assert_finite_sym(user_val)
        except ValueError as e:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": str(e),
                "expected": exp_str,
                "expected_str": exp_str,
            }
        except Exception:
            return {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": _INVALID_CHARS_MSG,
                "expected": exp_str,
                "expected_str": exp_str,
            }

        # Equality (tolerant)
        try:
            values_equal = bool(exp_value.equals(user_val)) or float(exp_value) == float(user_val)
        except Exception:
            values_equal = bool(exp_value.equals(user_val))

        if not values_equal:
            return {
                "ok": True,
                "correct": False,
                "score": 0,
                "feedback": "",
                "expected": exp_str,
                "expected_str": exp_str,
            }

        # Non-reduced?
        if "/" in answer and not _is_reduced_fraction_str(answer):
            if enforce_simplify:
                # STRICT: mark incorrect with reduce message
                return {
                    "ok": True,
                    "correct": False,
                    "score": 0,
                    "feedback": f"Reduce your fraction to {exp_str}.",
                    "expected": exp_str,
                    "expected_str": exp_str,
                }
            else:
                # LENIENT: mark correct, optionally partial credit, with nudge
                score_val = NOT_REDUCED_SCORE_VALUE if PARTIAL_CREDIT_FOR_NON_REDUCED else 1
                return {
                    "ok": True,
                    "correct": True,
                    "score": score_val,
                    "feedback": f"Correct, but reduce your fraction to {exp_str}.",
                    "expected": exp_str,
                    "expected_str": exp_str,
                }

        # Correct & reduced (or not typed as a/b)
        return {
            "ok": True,
            "correct": True,
            "score": 1,
            "feedback": "",
            "expected": exp_str,
            "expected_str": exp_str,
        }

    # Numeric
    try:
        user_val = _eval_numeric(answer)
    except ValueError as e:
        return {
            "ok": False,
            "correct": False,
            "score": 0,
            "feedback": str(e),
            "expected": exp_str,
            "expected_str": exp_str,
        }
    except Exception:
        return {
            "ok": False,
            "correct": False,
            "score": 0,
            "feedback": _INVALID_CHARS_MSG,
            "expected": exp_str,
            "expected_str": exp_str,
        }

    correct = math.isclose(user_val, float(exp_value), rel_tol=0, abs_tol=1e-9)

    # Gentle suggestion if they typed an expression but simplest form differs
    feedback = ""
    if correct:
        raw = answer.strip()
        if exp_str and raw != exp_str and any(op in raw for op in ("+", "-", "*", "/", "^", " ")):
            feedback = f"Correct; simplest form is {exp_str}."

    return {
        "ok": True,
        "correct": bool(correct),
        "score": 1 if correct else 0,
        "feedback": feedback if correct else "",
        "expected": exp_str,
        "expected_str": exp_str,
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
    except ValueError as e:
        return {"ok": False, "value": None, "feedback": str(e)}
    except Exception:
        return {"ok": False, "value": None, "feedback": _INVALID_CHARS_MSG}


@router.post("/mark", response_model=MarkResponse)
def mark(req: MarkRequest):
    q = next((qq for qq in get_questions() if qq.get("id") == req.id), None)
    if not q:
        return {"ok": False, "correct": False, "score": 0, "feedback": "unknown question id"}
    # Always compute expected so we can include it on validation failures
    _, exp_str, _, exp_err = _prepare_expected(q)
    msg = _validate_answer_text(req.answer)
    if msg:
        return {
            "ok": False,
            "correct": False,
            "score": 0,
            "feedback": msg,
            "expected": exp_str,
            "expected_str": exp_str,
        }
    return _mark_one(q, req.answer)


@router.post("/mark-batch", response_model=MarkBatchResponse)
def mark_batch(req: MarkBatchRequest):
    t0 = time.perf_counter()

    questions_by_id = {q["id"]: q for q in get_questions()}
    results: List[Dict[str, Any]] = []
    correct_count = 0

    for it in req.items:
        q = questions_by_id.get(it.id)
        if not q:
            res = {
                "ok": False,
                "correct": False,
                "score": 0,
                "feedback": "unknown question id",
                "expected": None,
                "expected_str": None,
            }
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
                total=total, correct=correct_count, items=results, duration_ms=duration_ms
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
        "duration_ms": duration_ms,
    }
