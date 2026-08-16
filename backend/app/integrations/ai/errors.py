from enum import StrEnum


class AIIntegrationErrorCode(StrEnum):
    AI_TIMEOUT = "AI_TIMEOUT"
    AI_SERVICE_UNAVAILABLE = "AI_SERVICE_UNAVAILABLE"
    AI_PROTOCOL_ERROR = "AI_PROTOCOL_ERROR"


class AIIntegrationError(Exception):
    def __init__(self, code: AIIntegrationErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
