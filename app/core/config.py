from functools import lru_cache
from decimal import Decimal
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "NCOF Platform API"
    secret_key: str = "CHANGE_ME"
    database_url: str = "postgresql+psycopg://ncof:ncof@localhost:5432/ncof"
    cors_origins: list[str] = ["http://localhost:3000"]
    payment_webhook_secret: str = "CHANGE_ME_WEBHOOK_SECRET"
    audit_hash_secret: str = "CHANGE_ME_AUDIT_SECRET"
    loan_max_amount: Decimal = Decimal("10000000.00")
    withdrawal_max_amount: Decimal = Decimal("5000000.00")
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    login_max_attempts: int = 5
    login_lockout_minutes: int = 15
    trusted_proxy: bool = False

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if not isinstance(value, str):
            return value
        for prefix in ("postgres://", "postgresql://", "postgresql+psycopg2://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix):]
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.app_env.lower() in {"production", "prod"}:
            insecure = {"CHANGE_ME", "CHANGE_ME_WEBHOOK_SECRET", "CHANGE_ME_AUDIT_SECRET"}
            if self.secret_key in insecure or len(self.secret_key) < 32:
                raise ValueError("SECRET_KEY must be a strong 32+ character production secret")
            if self.payment_webhook_secret in insecure or len(self.payment_webhook_secret) < 32:
                raise ValueError("PAYMENT_WEBHOOK_SECRET must be a strong production secret")
            if self.audit_hash_secret in insecure or len(self.audit_hash_secret) < 32:
                raise ValueError("AUDIT_HASH_SECRET must be a strong production secret")
            if len({self.secret_key, self.payment_webhook_secret, self.audit_hash_secret}) != 3:
                raise ValueError("SECRET_KEY, PAYMENT_WEBHOOK_SECRET and AUDIT_HASH_SECRET must be different secrets")
            if not self.cors_origins:
                raise ValueError("CORS_ORIGINS must contain the production web origin")
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
