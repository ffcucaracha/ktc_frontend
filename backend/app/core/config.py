from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="local", validation_alias="APP_ENV")
    app_name: str = Field(default="ktc_frontend", validation_alias="APP_NAME")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+asyncpg://trainer:trainer@localhost:5432/trainer",
        validation_alias="DATABASE_URL",
    )
    cors_origins: str = Field(
        default="http://localhost:5173",
        validation_alias="CORS_ORIGINS",
    )
    jwt_secret: str = Field(
        default="change-me-in-local-development-only-32-bytes",
        validation_alias="JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", validation_alias="JWT_ALGORITHM")
    access_token_ttl_minutes: int = Field(
        default=15,
        validation_alias="ACCESS_TOKEN_TTL_MINUTES",
    )
    refresh_token_ttl_days: int = Field(default=14, validation_alias="REFRESH_TOKEN_TTL_DAYS")
    cookie_secure: bool = Field(default=False, validation_alias="COOKIE_SECURE")
    simulation_gateway_mode: str = Field(default="mock", validation_alias="SIMULATION_GATEWAY_MODE")
    simulation_api_base_url: str = Field(
        default="http://simulation-service:8080",
        validation_alias="SIMULATION_API_BASE_URL",
    )
    simulation_ws_base_url: str = Field(
        default="ws://simulation-service:8080",
        validation_alias="SIMULATION_WS_BASE_URL",
    )
    simulation_api_key: str = Field(default="change-me", validation_alias="SIMULATION_API_KEY")
    ktc_api_base_url: str = Field(
        default="http://localhost:8001",
        validation_alias="KTC_API_BASE_URL",
    )
    simulation_connect_timeout_seconds: float = Field(
        default=3.0,
        validation_alias="SIMULATION_CONNECT_TIMEOUT_SECONDS",
    )
    simulation_read_timeout_seconds: float = Field(
        default=10.0,
        validation_alias="SIMULATION_READ_TIMEOUT_SECONDS",
    )
    simulation_telemetry_enabled: bool = Field(
        default=True,
        validation_alias="SIMULATION_TELEMETRY_ENABLED",
    )
    simulation_telemetry_interval_seconds: float = Field(
        default=2.0,
        gt=0,
        validation_alias="SIMULATION_TELEMETRY_INTERVAL_SECONDS",
    )
    simulation_telemetry_discovery_interval_seconds: float = Field(
        default=1.0,
        gt=0,
        validation_alias="SIMULATION_TELEMETRY_DISCOVERY_INTERVAL_SECONDS",
    )
    training_completion_events_enabled: bool = Field(
        default=True,
        validation_alias="TRAINING_COMPLETION_EVENTS_ENABLED",
    )
    training_completion_events_interval_seconds: float = Field(
        default=2.0,
        gt=0,
        validation_alias="TRAINING_COMPLETION_EVENTS_INTERVAL_SECONDS",
    )
    training_completion_events_max_attempts: int = Field(
        default=5,
        ge=1,
        validation_alias="TRAINING_COMPLETION_EVENTS_MAX_ATTEMPTS",
    )
    ai_gateway_mode: str = Field(default="mock", validation_alias="AI_GATEWAY_MODE")
    ai_service_base_url: str = Field(
        default="http://ai-service:8090",
        validation_alias="AI_SERVICE_BASE_URL",
    )
    ai_connect_timeout_seconds: float = Field(
        default=3.0,
        gt=0,
        validation_alias="AI_CONNECT_TIMEOUT_SECONDS",
    )
    ai_read_timeout_seconds: float = Field(
        default=15.0,
        gt=0,
        validation_alias="AI_READ_TIMEOUT_SECONDS",
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
