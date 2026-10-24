from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description="Backend API for the AI Quant Terminal prototype.",
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
