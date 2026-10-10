import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.song_carts.models import CartStatus, ServiceSection, SongCart, SongCartItem
from .access import _require_active
from .prepare_lyrics import (
    PreparedSection, _format_sections, _read_sections, _store_sections, prepare_lyrics,
)


@dataclass(frozen=True)
class UnlistedSongInput:
    service_date: date
    section: str
    title: str
    lyrics: str
    song_id: int | None = None


@dataclass(frozen=True)
class UnlistedSongDetails:
    id: int
    cart_id: UUID
    service_date: date
    section: str
    title: str
    lyrics: str
    sections: tuple[PreparedSection, ...]
    formatted_text: str
    reviewed_at: datetime | None
    can_edit: bool
    fingerprint: str


def _fingerprint(song: SongCartItem) -> str:
    content = json.dumps({
        "id": song.id, "title": song.title, "lyrics": song.original_lyrics,
        "section": song.section, "sections": song.prepared_sections,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _describe_unlisted(song: SongCartItem, cart: SongCart) -> UnlistedSongDetails:
    sections = _read_sections(song.prepared_sections)
    return UnlistedSongDetails(
        song.id, cart.id, cart.service_date, song.section, song.title,
        song.original_lyrics, sections, _format_sections(sections),
        song.reviewed_at, cart.status == CartStatus.DRAFT, _fingerprint(song),
    )


def save_unlisted_song(data: UnlistedSongInput, *, user: User) -> UnlistedSongDetails:
    """Save owner-supplied content to a draft after deterministic local preparation."""
    _require_active(user)
    if not isinstance(data.service_date, date) or isinstance(data.service_date, datetime):
        raise ValidationError("Choose a valid service date.")
    if data.section not in ServiceSection.values:
        raise ValidationError("Choose a valid service section.")
    if not isinstance(data.title, str) or not data.title.strip():
        raise ValidationError("Enter the song title.")
    title = data.title.strip()
    if len(title) > 512:
        raise ValidationError("Song titles cannot exceed 512 characters.")
    if any((ord(char) < 32 and char not in "\t\r\n") or ord(char) == 127
           for char in title):
        raise ValidationError("The title contains unsupported control characters.")
    prepared = _store_sections(prepare_lyrics(data.lyrics))
    with transaction.atomic():
        if data.song_id is None:
            cart, _ = SongCart.objects.select_for_update().get_or_create(
                owner=user, service_date=data.service_date,
            )
            song = None
        else:
            cart_id = SongCartItem.objects.values_list("cart_id", flat=True).get(
                pk=data.song_id, cart__owner=user,
            )
            cart = SongCart.objects.select_for_update().get(pk=cart_id, owner=user)
            song = SongCartItem.objects.get(pk=data.song_id, cart=cart)
            if song.song_uid is not None:
                raise ValidationError("Only unlisted songs can be edited here.")
            if cart.service_date != data.service_date:
                raise ValidationError("The service date must match the existing cart.")
        if cart.status != CartStatus.DRAFT:
            raise ValidationError("Submitted song selections cannot be changed.")
        if song is None:
            song = SongCartItem.objects.create(
                cart=cart, section=data.section, song_uid=None, title=title,
                original_lyrics=data.lyrics, prepared_sections=prepared,
            )
        elif (song.title, song.section, song.original_lyrics, song.prepared_sections) != (
            title, data.section, data.lyrics, prepared,
        ):
            song.title = title
            song.section = data.section
            song.original_lyrics = data.lyrics
            song.prepared_sections = prepared
            song.reviewed_at = None
            song.save(update_fields=[
                "title", "section", "original_lyrics", "prepared_sections", "reviewed_at",
            ])
        return _describe_unlisted(song, cart)


def get_unlisted_song(cart_id: UUID, song_id: int, *, user: User) -> UnlistedSongDetails:
    """Read saved owner-supplied lyrics even after the selection is locked."""
    _require_active(user)
    cart = SongCart.objects.get(pk=cart_id, owner=user)
    song = SongCartItem.objects.get(pk=song_id, cart=cart, song_uid__isnull=True)
    return _describe_unlisted(song, cart)


@transaction.atomic
def review_unlisted_song(
    cart_id: UUID, song_id: int, fingerprint: str, *, user: User,
) -> UUID:
    """Record explicit review of the current saved projection content once."""
    _require_active(user)
    cart = SongCart.objects.select_for_update().get(pk=cart_id, owner=user)
    if cart.status != CartStatus.DRAFT:
        raise ValidationError("Submitted song selections cannot be changed.")
    song = SongCartItem.objects.get(pk=song_id, cart=cart, song_uid__isnull=True)
    if fingerprint != _fingerprint(song):
        raise ValidationError(
            "This preview is out of date. Review the latest saved lyrics.",
        )
    if song.reviewed_at is None:
        song.reviewed_at = timezone.now()
        song.save(update_fields=["reviewed_at"])
    return cart.id
