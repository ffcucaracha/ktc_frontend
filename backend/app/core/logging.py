import json
import logging
from datetime import UTC, datetime
from typing import override


class HealthcheckAccessFilter(logging.Filter):
    """Hide successful healthcheck access-log noise while keeping other requests visible."""

    HEALTH_PATHS = ("/health", "/health/ready")

    @override
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(f'GET {path} ' in message for path in self.HEALTH_PATHS)


class JsonFormatter(logging.Formatter):
    @override
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    logging.getLogger("uvicorn.access").addFilter(HealthcheckAccessFilter())
