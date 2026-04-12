class ScheduleNotFoundError(Exception):
    """Raised when a schedule update is requested for a missing service date."""


class DuplicateSubmissionError(Exception):
    """Raised when an idempotency key is reused with a different payload."""


class DuplicateScheduleItemTypeError(Exception):
    """Raised when a schedule would contain more than one item of the same type."""


class SchedulePayloadValidationError(Exception):
    """Raised when an inbound schedule payload fails validation."""

    def __init__(self, detail: str, errors: list[str]) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors
