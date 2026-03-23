from datetime import datetime, timezone
import uuid
from typing import Optional


class DateUtils:
    """
    Centralized date/time utilities.
    All times should be handled in UTC.
    """

    @staticmethod
    def now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def to_iso(dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        return dt.astimezone(timezone.utc).isoformat()

    @staticmethod
    def from_iso(date_str: str) -> datetime:
        return datetime.fromisoformat(date_str)

    @staticmethod
    def is_before(dt1: datetime, dt2: datetime) -> bool:
        return dt1 < dt2

    @staticmethod
    def is_after(dt1: datetime, dt2: datetime) -> bool:
        return dt1 > dt2


class IdGenerator:
    """
    Utility for generating unique identifiers (useful for idempotency keys, tracing, etc.)
    """

    @staticmethod
    def uuid() -> str:
        return str(uuid.uuid4())


class DictUtils:
    """
    Safe dictionary access helpers.
    """

    @staticmethod
    def get(data: dict, key: str, default=None):
        return data.get(key, default)

    @staticmethod
    def require(data: dict, key: str):
        if key not in data:
            raise KeyError(f"Missing required key: {key}")
        return data[key]


class ValidationUtils:
    """
    Generic validation helpers.
    """

    @staticmethod
    def not_none(value, field_name: str):
        if value is None:
            raise ValueError(f"{field_name} must not be None")

    @staticmethod
    def not_empty(value: str, field_name: str):
        if not value:
            raise ValueError(f"{field_name} must not be empty")

    @staticmethod
    def positive_int(value: int, field_name: str):
        if value is None or value <= 0:
            raise ValueError(f"{field_name} must be a positive integer")