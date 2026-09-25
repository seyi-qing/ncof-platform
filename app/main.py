from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db import engine
from app.core.config import settings
from app.api.v1.router import api_router

app = FastAPI(
    title="NCOF Platform API",
    version="1.7.0",
    description="Membership, attendance, dues, savings, governance, financial operations and member experience API.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins or ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Webhook-Signature", "X-Paystack-Signature", "verif-hash", "flutterwave-signature", "Idempotency-Key", "X-Bootstrap-Key"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ncof-api",
        "version": app.version,
        "config_warnings": settings.config_warnings,
        "cors_origins": settings.cors_origins,
    }


@app.get("/ready")
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok", "service": "ncof-api", "version": app.version}
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "database": "error", "service": "ncof-api", "version": app.version},
        )
