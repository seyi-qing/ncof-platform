"""Vercel Python entrypoint for NCOF Platform API."""
try:
    from app.main import app
except Exception as exc:  # pragma: no cover
    import traceback
    from fastapi import FastAPI

    _err = f"{type(exc).__name__}: {exc}"
    _tb = traceback.format_exc()
    app = FastAPI(title="NCOF API boot failure")

    @app.get("/health")
    @app.get("/api/v1/health")
    @app.get("/ready")
    @app.get("/api/v1/ready")
    @app.api_route("/{full_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
    def _boot_failed(full_path: str = ""):
        return {
            "status": "boot_failed",
            "error": _err,
            "hint": "Check Vercel env: DATABASE_URL, SECRET_KEY, CORS_ORIGINS, APP_ENV. See Runtime Logs.",
            "traceback_tail": _tb[-1500:],
        }
