from django.core.exceptions import PermissionDenied

from apps.accounts.models import User

TECHNICAL_TEAM = "Technical Team"


def is_technical_team(user: User) -> bool:
    """Check team membership independently of general staff access."""
    return bool(
        user.is_authenticated and user.is_active and user.is_staff
        and user.groups.filter(name=TECHNICAL_TEAM).exists()
    )


def _require_active(user: User) -> None:
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Sign in to access song submissions.")


def _require_staff(user: User) -> None:
    _require_active(user)
    if not user.is_staff:
        raise PermissionDenied("Administrator access is required.")


def _require_team(user: User) -> None:
    if not is_technical_team(user):
        raise PermissionDenied("Technical Team membership is required.")
