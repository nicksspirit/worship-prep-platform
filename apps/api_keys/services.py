from __future__ import annotations

import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.api_keys.models import (
    IntegrationApiKey,
    IntegrationApiKeyRateWindow,
    normalize_api_key_scopes,
)

API_KEY_PREFIX_NAMESPACE = "wpp_live"
API_KEY_PUBLIC_ID_BYTES = 6
API_KEY_SECRET_BYTES = 32
API_KEY_HASH_SALT = "worship_prep_platform.api_keys"


@dataclass(slots=True)
class GeneratedAPIKeyMaterial:
    """One-time generated API key material used during issuance."""

    key_prefix: str
    plaintext_key: str
    hashed_key: str


class APIKeyAccessError(ValueError):
    """An Integration Client credential cannot authorize the requested resource."""

    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Outcome and response metadata for one per-key rate-limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: int

    @property
    def headers(self) -> dict[str, str]:
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_at),
        }
        if not self.allowed:
            headers["Retry-After"] = str(self.retry_after)
        return headers


def hash_api_key(raw_key: str) -> str:
    """Return the stored digest for an API key."""

    return salted_hmac(API_KEY_HASH_SALT, raw_key).hexdigest()


def parse_api_key_prefix(raw_key: str | None) -> str | None:
    """Extract the public lookup prefix from a presented API key."""

    normalized = str(raw_key or "").strip()
    if not normalized:
        return None

    prefix, separator, _secret = normalized.partition(".")
    if separator != "." or not prefix.startswith(f"{API_KEY_PREFIX_NAMESPACE}_"):
        return None
    return prefix


def authorize_api_key(
    authorization: str | None,
    *,
    required_scopes: Iterable[str],
) -> IntegrationApiKey:
    """Authenticate a Bearer key and distinguish invalid credentials from scope denial."""

    scheme, separator, raw_key = str(authorization or "").partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not raw_key:
        raise APIKeyAccessError(
            "invalid_api_key",
            "A valid Integration Client Bearer key is required.",
            401,
        )

    prefix = parse_api_key_prefix(raw_key)
    api_key = (
        IntegrationApiKey.objects.filter(key_prefix=prefix).first()
        if prefix is not None
        else None
    )
    if (
        api_key is None
        or not constant_time_compare(api_key.hashed_key, hash_api_key(raw_key))
        or api_key.status != "active"
    ):
        raise APIKeyAccessError(
            "invalid_api_key",
            "A valid Integration Client Bearer key is required.",
            401,
        )

    missing_scopes = sorted(set(required_scopes) - set(api_key.scopes))
    if missing_scopes:
        raise APIKeyAccessError(
            "insufficient_scope",
            f"This resource requires scope: {', '.join(missing_scopes)}.",
            403,
        )

    api_key.last_used_on = timezone.now()
    api_key.save(update_fields=["last_used_on", "updated_on"])
    return api_key


@transaction.atomic
def check_rate_limit(
    api_key: IntegrationApiKey,
    *,
    bucket: str,
    limit: int,
) -> RateLimitResult:
    """Consume one request from a database-coordinated one-minute key window."""

    now = timezone.now()
    window_started_at = now.replace(second=0, microsecond=0)
    reset_at = window_started_at + timedelta(minutes=1)
    window, _created = (
        IntegrationApiKeyRateWindow.objects.select_for_update().get_or_create(
            api_key=api_key,
            bucket=bucket,
            defaults={
                "window_started_at": window_started_at,
                "request_count": 0,
            },
        )
    )
    if window.window_started_at != window_started_at:
        window.window_started_at = window_started_at
        window.request_count = 0

    allowed = window.request_count < limit
    if allowed:
        window.request_count += 1
    window.save(update_fields=["window_started_at", "request_count"])

    retry_after = max(1, int((reset_at - now).total_seconds()))
    return RateLimitResult(
        allowed=allowed,
        limit=limit,
        remaining=max(0, limit - window.request_count),
        reset_at=int(reset_at.timestamp()),
        retry_after=retry_after,
    )


def build_api_key(prefix: str, secret: str) -> str:
    """Build a plaintext API key from its public prefix and secret portion."""

    return f"{prefix}.{secret}"


def _next_key_prefix() -> str:
    """Generate a unique public key prefix."""

    while True:
        candidate = (
            f"{API_KEY_PREFIX_NAMESPACE}_{secrets.token_hex(API_KEY_PUBLIC_ID_BYTES)}"
        )
        if not IntegrationApiKey.objects.filter(key_prefix=candidate).exists():
            return candidate


def generate_api_key_material() -> GeneratedAPIKeyMaterial:
    """Generate a unique API key prefix and secret."""

    prefix = _next_key_prefix()
    secret = secrets.token_urlsafe(API_KEY_SECRET_BYTES)
    plaintext = build_api_key(prefix, secret)
    return GeneratedAPIKeyMaterial(
        key_prefix=prefix,
        plaintext_key=plaintext,
        hashed_key=hash_api_key(plaintext),
    )


def issue_api_key(
    *,
    name: str,
    scopes: Iterable[str],
    created_by=None,
    expires_on=None,
    notes: str = "",
    rotated_from: IntegrationApiKey | None = None,
) -> tuple[IntegrationApiKey, str]:
    """Create and persist a new API key, returning the plaintext once."""

    material = generate_api_key_material()

    api_key = IntegrationApiKey(
        name=name,
        key_prefix=material.key_prefix,
        hashed_key=material.hashed_key,
        scopes=normalize_api_key_scopes(scopes),
        created_by=created_by,
        expires_on=expires_on,
        notes=notes,
        rotated_from=rotated_from,
    )
    api_key.save()
    return api_key, material.plaintext_key


@transaction.atomic
def rotate_api_key(
    api_key: IntegrationApiKey,
    *,
    rotated_by=None,
) -> tuple[IntegrationApiKey, str]:
    """Issue a replacement key and revoke the original."""

    replacement, plaintext = issue_api_key(
        name=api_key.name,
        scopes=api_key.scopes,
        created_by=rotated_by,
        expires_on=api_key.expires_on,
        notes=api_key.notes,
        rotated_from=api_key,
    )
    api_key.revoke()
    api_key.save(update_fields=["is_active", "revoked_on", "updated_on"])
    return replacement, plaintext


def revoke_api_key(api_key: IntegrationApiKey) -> None:
    """Persistently revoke an API key."""

    api_key.revoke()
    api_key.save(update_fields=["is_active", "revoked_on", "updated_on"])
