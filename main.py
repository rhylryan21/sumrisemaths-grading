from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from sympy import sympify

app = FastAPI(title="Sumrise Maths – Grading API")

# Allow calls from the Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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
    try:
        # Parse and evaluate safely with SymPy
        value = sympify(req.expr).evalf()
        return {"ok": True, "value": float(value)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
