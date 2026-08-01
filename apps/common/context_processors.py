from typing import TypedDict

from django.http import HttpRequest

from apps.accounts.models import User


class ReactivatedUserData(TypedDict):
    is_authenticated: bool
    is_staff: bool
    full_name: str | None
    avatar_url: str | None
    email: str | None


class AuthContext(TypedDict):
    user: ReactivatedUserData | None


def auth(request: HttpRequest) -> AuthContext:
    if hasattr(request, "user") and request.user.is_authenticated:
        # The Reactivated context exposes only presentation-safe account fields.
        user: User = request.user  # type: ignore
        return {
            "user": {
                "is_authenticated": True,
                "is_staff": user.is_staff,
                "full_name": user.full_name,
                "avatar_url": user.avatar_url,
                "email": user.email,
            }
        }

    return {
        "user": {
            "is_authenticated": False,
            "is_staff": False,
            "full_name": None,
            "avatar_url": None,
            "email": None,
        }
    }
