import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, validate_secret_key
from app.routers import auth as auth_router
from app.routers import classes as classes_router
from app.routers import courses as courses_router
from app.routers import tasks as tasks_router
from app.routers import files as files_router
from app.routers import submissions as submissions_router
from app.routers import grades as grades_router
from app.routers import users as users_router
from app.routers import ai as ai_router
from app.routers import prompts as prompts_router
from app.routers import dashboard as dashboard_router
from app.routers import venues as venues_router
from app.routers import equipment as equipment_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        validate_secret_key(settings)
    except ValueError:
        if os.environ.get("ENVIRONMENT") != "test":
            raise
    yield


app = FastAPI(
    title="数字实训教学管理平台",
    description="Digital Training Teaching Management Platform API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(classes_router.router)
app.include_router(courses_router.router)
app.include_router(tasks_router.router)
app.include_router(files_router.router)
app.include_router(submissions_router.router)
app.include_router(grades_router.router)
app.include_router(users_router.router)
app.include_router(ai_router.router)
app.include_router(prompts_router.router)
app.include_router(dashboard_router.router)
app.include_router(venues_router.router)
app.include_router(equipment_router.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
