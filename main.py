import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.admin import router as admin_router

# Routers
from routers.attempts import router as attempts_router
from routers.health import router as health_router
from routers.marking import router as marking_router
from routers.questions import router as questions_router

logger = logging.getLogger("sumrise-grading")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Sumrise Maths – Grading API")

# Allow calls from the Next.js dev server and production site
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://sumrise-maths.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "x-api-key", "x-admin-token"],
)


@app.get("/")
def health_root():
    return {"ok": True}


# Register routers (paths preserved)
app.include_router(marking_router)  # /evaluate, /questions, /mark, /mark-batch
app.include_router(attempts_router)  # /attempts/...
app.include_router(admin_router)  # /admin/...
app.include_router(health_router)  # /health/...
app.include_router(questions_router)  # /questions/...
