from __future__ import annotations

import secrets
from collections.abc import Iterable
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.api_keys.models import IntegrationApiKey, normalize_api_key_scopes

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


def authenticate_api_key(
    raw_key: str | None, *, required_scope: str
) -> IntegrationApiKey | None:
    """Authenticate an active API key carrying the required scope."""

    prefix = parse_api_key_prefix(raw_key)
    if prefix is None:
        return None
    api_key = IntegrationApiKey.objects.filter(key_prefix=prefix).first()
    if (
        api_key is None
        or api_key.status != "active"
        or required_scope not in api_key.scopes
        or not constant_time_compare(api_key.hashed_key, hash_api_key(str(raw_key)))
    ):
        return None
    api_key.last_used_on = timezone.now()
    api_key.save(update_fields=["last_used_on", "updated_on"])
    return api_key


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
