from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"


class LoginFailureReason(StrEnum):
    INVALID_CREDENTIALS = "invalid_credentials"
    INACTIVE_USER = "inactive_user"


class SimulationSessionStatus(StrEnum):
    CREATING = "creating"
    ACTIVE = "active"
    STOPPING = "stopping"
    COMPLETED = "completed"
    FAILED = "failed"


class SimulationCommandStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"
