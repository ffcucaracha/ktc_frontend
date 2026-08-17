from app.core.config import Settings
from app.integrations.ai.base import AIGateway
from app.integrations.ai.http_gateway import HttpAIGateway
from app.integrations.ai.mock_gateway import MockAIGateway


def create_ai_gateway(settings: Settings) -> AIGateway:
    mode = settings.ai_gateway_mode.lower()
    if mode == "mock":
        return MockAIGateway()
    if mode == "http":
        return HttpAIGateway(
            base_url=settings.ai_service_base_url,
            connect_timeout_seconds=settings.ai_connect_timeout_seconds,
            read_timeout_seconds=settings.ai_read_timeout_seconds,
            prediction_timeout_seconds=settings.ai_prediction_timeout_seconds,
        )
    raise ValueError(f"Unsupported AI_GATEWAY_MODE: {settings.ai_gateway_mode}")
