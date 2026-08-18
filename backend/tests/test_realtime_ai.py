from app.models import OperatorErrorType
from app.services.realtime_ai import _error_type_value


def test_realtime_ai_error_type_value_accepts_enum_and_persisted_string() -> None:
    assert _error_type_value(OperatorErrorType.WRONG_ACTION) == "WRONG_ACTION"
    assert _error_type_value("WRONG_SEQUENCE") == "WRONG_SEQUENCE"
