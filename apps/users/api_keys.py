from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from typing import Iterable

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django_bolt import JSON, Request

from apps.users.models import IntegrationApiKey, normalize_api_key_scopes

API_KEY_HEADER = "X-API-Key"
API_KEY_PREFIX_NAMESPACE = "wpp_live"
API_KEY_PUBLIC_ID_BYTES = 6
API_KEY_SECRET_BYTES = 32
API_KEY_HASH_SALT = "worship_prep_platform.api_keys"

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AuthenticatedAPIKey:
    """Authenticated API key details attached to a request."""

    api_key: IntegrationApiKey
    scopes: tuple[str, ...]

    def to_context(self) -> dict[str, object]:
        return {
            "auth_backend": "api_key",
            "api_key_id": str(self.api_key.pk),
            "api_key_name": self.api_key.name,
            "api_key_prefix": self.api_key.key_prefix,
            "api_key_scopes": list(self.scopes),
        }


@dataclass(slots=True)
class GeneratedAPIKeyMaterial:
    """One-time generated API key material used during issuance."""

    key_prefix: str
    plaintext_key: str
    hashed_key: str


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


def build_api_key(prefix: str, secret: str) -> str:
    """Build a plaintext API key from its public prefix and secret portion."""

    return f"{prefix}.{secret}"


def _next_key_prefix() -> str:
    """Generate a unique public key prefix."""

    while True:
        candidate = f"{API_KEY_PREFIX_NAMESPACE}_{secrets.token_hex(API_KEY_PUBLIC_ID_BYTES)}"
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


def _bind_api_key_context(
    request: Request | None,
    authenticated_key: AuthenticatedAPIKey,
) -> None:
    if request is None:
        return

    context = authenticated_key.to_context()

    request_context = getattr(request, "context", None)
    if isinstance(request_context, dict):
        request_context.update(context)

    request_state = getattr(request, "state", None)
    if isinstance(request_state, dict):
        request_state.update(context)


async def authorize_api_key(
    api_key: str | None,
    *,
    request: Request | None = None,
    required_scopes: Iterable[str] = (),
) -> AuthenticatedAPIKey | JSON:
    """Authorize a request using a database-backed API key."""

    normalized = str(api_key or "").strip()
    if not normalized:
        logger.warning(
            "API key auth failed: missing or empty X-API-Key",
            extra={"reason": "missing_header"},
        )
        return JSON({"detail": "Missing X-API-Key header."}, status_code=401)

    prefix = parse_api_key_prefix(normalized)
    if prefix is None:
        logger.warning(
            "API key auth failed: invalid key format (expected wpp_live_<hex>.<secret>)",
            extra={
                "reason": "invalid_format",
                "present_length": len(normalized),
                "has_separator": "." in normalized,
            },
        )
        return JSON({"detail": "Invalid API key."}, status_code=401)

    stored_key = await IntegrationApiKey.objects.filter(key_prefix=prefix).afirst()
    if stored_key is None:
        logger.warning(
            "API key auth failed: no key registered for prefix",
            extra={"reason": "unknown_prefix", "key_prefix": prefix},
        )
        return JSON({"detail": "Invalid API key."}, status_code=401)

    if not constant_time_compare(hash_api_key(normalized), stored_key.hashed_key):
        logger.warning(
            "API key auth failed: secret does not match stored hash",
            extra={
                "reason": "hash_mismatch",
                "key_prefix": prefix,
                "integration_api_key_id": stored_key.pk,
            },
        )
        return JSON({"detail": "Invalid API key."}, status_code=401)

    if stored_key.is_revoked or not stored_key.is_active:
        logger.warning(
            "API key auth failed: key revoked or inactive",
            extra={
                "reason": "revoked_or_inactive",
                "key_prefix": prefix,
                "integration_api_key_id": stored_key.pk,
                "is_active": stored_key.is_active,
                "revoked_on": stored_key.revoked_on.isoformat()
                if stored_key.revoked_on
                else None,
            },
        )
        return JSON({"detail": "API key has been revoked."}, status_code=401)

    if stored_key.is_expired:
        logger.warning(
            "API key auth failed: key past expiration",
            extra={
                "reason": "expired",
                "key_prefix": prefix,
                "integration_api_key_id": stored_key.pk,
                "expires_on": stored_key.expires_on.isoformat()
                if stored_key.expires_on
                else None,
            },
        )
        return JSON({"detail": "API key has expired."}, status_code=401)

    required = set(normalize_api_key_scopes(required_scopes))
    granted = set(stored_key.scopes)
    if not required.issubset(granted):
        missing = sorted(required - granted)
        logger.warning(
            "API key auth failed: insufficient scope",
            extra={
                "reason": "insufficient_scope",
                "key_prefix": prefix,
                "integration_api_key_id": stored_key.pk,
                "required_scopes": sorted(required),
                "granted_scopes": sorted(granted),
                "missing_scopes": missing,
            },
        )
        return JSON({"detail": "API key does not have the required scope."}, status_code=403)

    now = timezone.now()
    await IntegrationApiKey.objects.filter(pk=stored_key.pk).aupdate(last_used_on=now)
    stored_key.last_used_on = now

    authenticated_key = AuthenticatedAPIKey(
        api_key=stored_key,
        scopes=tuple(stored_key.scopes),
    )
    _bind_api_key_context(request, authenticated_key)
    return authenticated_key
