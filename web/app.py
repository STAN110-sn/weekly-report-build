"""
Weekly Report Web Application - FastAPI メインエントリ
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db, run_migrations
from .routers import member, consultation
from .routers import auth_router, pages, report, weekly_report


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    run_migrations()
    yield


app = FastAPI(
    title="Weekly Report & Consultation API",
    description="週報・相談管理システム",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

app.include_router(auth_router.router)
app.include_router(pages.router)
app.include_router(member.router, prefix="/api")
app.include_router(consultation.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(weekly_report.router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
