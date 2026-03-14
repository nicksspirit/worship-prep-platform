class ScheduleNotFoundError(Exception):
    """Raised when a schedule update is requested for a missing service date."""


class DuplicateSubmissionError(Exception):
    """Raised when an idempotency key is reused with a different payload."""
