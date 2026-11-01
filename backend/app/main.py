from fastapi import FastAPI

from .config import settings
from .api.auth import router as auth_router
from .api.health import router as health_router
from .api.labels import router as labels_router
from app.api.emails import router as emails_router
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(emails_router)
app.include_router(labels_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "AI Mail Backend is running",
    }
