class ScheduleNotFoundError(Exception):
    """Raised when a schedule update is requested for a missing service date."""


class DuplicateSubmissionError(Exception):
    """Raised when an idempotency key is reused with a different payload."""


class DuplicateScheduleItemTypeError(Exception):
    """Raised when a schedule would contain more than one item of the same type."""
