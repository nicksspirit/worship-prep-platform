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


@dataclass(frozen=True, slots=True)
class IssueApiKey:
    """Request a new Integration Client credential."""

    name: str
    scopes: Iterable[str]
    created_by: object | None = None
    expires_on: object | None = None
    notes: str = ""
    rotated_from: IntegrationApiKey | None = None


@dataclass(frozen=True, slots=True)
class IssuedApiKey:
    """A persisted credential and its one-time plaintext value."""

    api_key: IntegrationApiKey
    plaintext_key: str


@dataclass(slots=True)
class _GeneratedAPIKeyMaterial:
    """One-time generated API key material used during issuance."""

    key_prefix: str
    plaintext_key: str
    hashed_key: str


@dataclass(frozen=True, slots=True)
class AuthorizationDenied:
    """A credential cannot authorize the requested resource."""

    code: str
    message: str


@dataclass(frozen=True, slots=True)
class AuthorizedAPIKey:
    """A credential authorized for the requested scopes."""

    api_key: IntegrationApiKey


@dataclass(frozen=True, slots=True)
class RateLimitOutcome:
    """Outcome of one per-key rate-limit check."""

    allowed: bool
    limit: int
    remaining: int
    reset_at: int
    retry_after: int


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
) -> AuthorizedAPIKey | AuthorizationDenied:
    """Authenticate a Bearer key and distinguish invalid credentials from scope denial."""

    scheme, separator, raw_key = str(authorization or "").partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not raw_key:
        return AuthorizationDenied(
            "invalid_api_key",
            "A valid Integration Client Bearer key is required.",
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
        return AuthorizationDenied(
            "invalid_api_key",
            "A valid Integration Client Bearer key is required.",
        )

    missing_scopes = sorted(set(required_scopes) - set(api_key.scopes))
    if missing_scopes:
        return AuthorizationDenied(
            "insufficient_scope",
            f"This resource requires scope: {', '.join(missing_scopes)}.",
        )

    api_key.last_used_on = timezone.now()
    api_key.save(update_fields=["last_used_on", "updated_on"])
    return AuthorizedAPIKey(api_key)


@transaction.atomic
def check_rate_limit(
    api_key: IntegrationApiKey,
    *,
    bucket: str,
    limit: int,
) -> RateLimitOutcome:
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
    return RateLimitOutcome(
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


def _generate_api_key_material() -> _GeneratedAPIKeyMaterial:
    """Generate a unique API key prefix and secret."""

    prefix = _next_key_prefix()
    secret = secrets.token_urlsafe(API_KEY_SECRET_BYTES)
    plaintext = build_api_key(prefix, secret)
    return _GeneratedAPIKeyMaterial(
        key_prefix=prefix,
        plaintext_key=plaintext,
        hashed_key=hash_api_key(plaintext),
    )


def issue_api_key(request: IssueApiKey) -> IssuedApiKey:
    """Create and persist a new API key, returning the plaintext once."""

    material = _generate_api_key_material()

    api_key = IntegrationApiKey(
        name=request.name,
        key_prefix=material.key_prefix,
        hashed_key=material.hashed_key,
        scopes=normalize_api_key_scopes(request.scopes),
        created_by=request.created_by,
        expires_on=request.expires_on,
        notes=request.notes,
        rotated_from=request.rotated_from,
    )
    api_key.save()
    return IssuedApiKey(api_key, material.plaintext_key)


@transaction.atomic
def rotate_api_key(
    api_key: IntegrationApiKey,
    *,
    rotated_by=None,
) -> IssuedApiKey:
    """Issue a replacement key and revoke the original."""

    replacement = issue_api_key(
        IssueApiKey(
            name=api_key.name,
            scopes=api_key.scopes,
            created_by=rotated_by,
            expires_on=api_key.expires_on,
            notes=api_key.notes,
            rotated_from=api_key,
        )
    )
    api_key.revoke()
    api_key.save(update_fields=["is_active", "revoked_on", "updated_on"])
    return replacement


def revoke_api_key(api_key: IntegrationApiKey) -> None:
    """Persistently revoke an API key."""

    api_key.revoke()
    api_key.save(update_fields=["is_active", "revoked_on", "updated_on"])
