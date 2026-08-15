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


class TrainingSessionMode(StrEnum):
    TRAINING = "training"
    EXAM = "exam"


class TrainingScenarioDifficulty(StrEnum):
    BASIC = "basic"
    MEDIUM = "medium"
    ADVANCED = "advanced"


class SimulationCommandStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"


class SimulationTimelineEventType(StrEnum):
    SESSION_STARTED = "session.started"
    SESSION_READY = "session.ready"
    STATE_SNAPSHOT = "state.snapshot"
    STATE_PATCH = "state.patch"
    OPERATOR_COMMAND = "operator.command"
    COMMAND_ACCEPTED = "command.accepted"
    COMMAND_REJECTED = "command.rejected"
    COMMAND_FAILED = "command.failed"
    ALARM_RAISED = "alarm.raised"
    ALARM_CLEARED = "alarm.cleared"
    INTEGRATION_ERROR = "integration.error"
    SESSION_COMPLETED = "session.completed"
    SESSION_FAILED = "session.failed"


class SimulationEventSource(StrEnum):
    OPERATOR = "operator"
    SIMULATION = "simulation"
    SYSTEM = "system"
    ASSESSMENT = "assessment"
    AI = "ai"
