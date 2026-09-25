from functools import lru_cache
from decimal import Decimal
import logging

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("ncof.config")


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "NCOF Platform API"
    secret_key: str = "CHANGE_ME"
    database_url: str = "postgresql+psycopg://ncof:ncof@localhost:5432/ncof"
    cors_origins: list[str] = ["http://localhost:3000"]
    payment_webhook_secret: str = "CHANGE_ME_WEBHOOK_SECRET"
    audit_hash_secret: str = "CHANGE_ME_AUDIT_SECRET"
    paystack_secret_key: str = ""
    flw_secret_hash: str = ""
    loan_max_amount: Decimal = Decimal("10000000.00")
    withdrawal_max_amount: Decimal = Decimal("5000000.00")
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    trusted_proxy: bool = False
    config_warnings: list[str] = []

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        for prefix in ("postgres://", "postgresql://", "postgresql+psycopg2://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_security(self):
        """Warn in production — do NOT raise (raising kills the Vercel function on import)."""
        warnings: list[str] = []
        if self.app_env.lower() in {"production", "prod"}:
            insecure = {"CHANGE_ME", "CHANGE_ME_WEBHOOK_SECRET", "CHANGE_ME_AUDIT_SECRET"}
            if self.secret_key in insecure or len(self.secret_key) < 32:
                warnings.append("SECRET_KEY must be a strong 32+ character production secret")
            if self.payment_webhook_secret in insecure or len(self.payment_webhook_secret) < 32:
                warnings.append("PAYMENT_WEBHOOK_SECRET must be a strong 32+ character production secret")
            if self.audit_hash_secret in insecure or len(self.audit_hash_secret) < 32:
                warnings.append("AUDIT_HASH_SECRET must be a strong 32+ character production secret")
            if len({self.secret_key, self.payment_webhook_secret, self.audit_hash_secret}) != 3:
                warnings.append("SECRET_KEY, PAYMENT_WEBHOOK_SECRET and AUDIT_HASH_SECRET must be different")
            if not self.cors_origins:
                warnings.append("CORS_ORIGINS is empty — using NCOF web defaults")
                object.__setattr__(
                    self,
                    "cors_origins",
                    [
                        "https://ncof.vercel.app",
                        "https://ncof-git-main-seyi-qing.vercel.app",
                    ],
                )
            for w in warnings:
                logger.warning("config: %s", w)
        object.__setattr__(self, "config_warnings", warnings)
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        logger.exception("Failed to load settings: %s", exc)
        return Settings(
            app_env="production",
            secret_key="TEMPORARY_FALLBACK_KEY_REPLACE_ME_32CHARS",
            payment_webhook_secret="TEMPORARY_FALLBACK_WEBHOOK_REPLACE_ME",
            audit_hash_secret="TEMPORARY_FALLBACK_AUDIT_REPLACE_ME_XX",
            cors_origins=[
                "https://ncof.vercel.app",
                "https://ncof-git-main-seyi-qing.vercel.app",
            ],
            config_warnings=[f"settings_load_error: {exc}"],
        )


settings = get_settings()
