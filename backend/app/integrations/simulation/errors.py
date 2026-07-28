from enum import StrEnum


class IntegrationErrorCode(StrEnum):
    SIMULATION_SERVICE_UNAVAILABLE = "SIMULATION_SERVICE_UNAVAILABLE"
    SIMULATION_TIMEOUT = "SIMULATION_TIMEOUT"
    SIMULATION_PROTOCOL_ERROR = "SIMULATION_PROTOCOL_ERROR"
    SIMULATION_SESSION_NOT_FOUND = "SIMULATION_SESSION_NOT_FOUND"
    COMMAND_REJECTED = "COMMAND_REJECTED"
    STALE_STATE_REVISION = "STALE_STATE_REVISION"
    INVALID_EXTERNAL_PAYLOAD = "INVALID_EXTERNAL_PAYLOAD"


class SimulationIntegrationError(Exception):
    def __init__(self, code: IntegrationErrorCode, message: str) -> None:
        self.code = code
        super().__init__(message)


class SimulationUnavailableError(SimulationIntegrationError):
    def __init__(self) -> None:
        super().__init__(
            IntegrationErrorCode.SIMULATION_SERVICE_UNAVAILABLE,
            "Simulation service is unavailable.",
        )


class SimulationTimeoutError(SimulationIntegrationError):
    def __init__(self) -> None:
        super().__init__(
            IntegrationErrorCode.SIMULATION_TIMEOUT,
            "Simulation service request timed out.",
        )


class SimulationProtocolError(SimulationIntegrationError):
    def __init__(self) -> None:
        super().__init__(
            IntegrationErrorCode.SIMULATION_PROTOCOL_ERROR,
            "Simulation service returned an unexpected response.",
        )


class SimulationSessionNotFoundError(SimulationIntegrationError):
    def __init__(self) -> None:
        super().__init__(
            IntegrationErrorCode.SIMULATION_SESSION_NOT_FOUND,
            "Simulation session was not found.",
        )


class CommandRejectedError(SimulationIntegrationError):
    def __init__(self) -> None:
        super().__init__(
            IntegrationErrorCode.COMMAND_REJECTED,
            "Simulation service rejected the command.",
        )


class InvalidExternalPayloadError(SimulationIntegrationError):
    def __init__(self) -> None:
        super().__init__(
            IntegrationErrorCode.INVALID_EXTERNAL_PAYLOAD,
            "Simulation service payload is invalid.",
        )
