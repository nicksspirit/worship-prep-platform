from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.accounts.models import User
from apps.catalog.services import CatalogAccess, GetCatalogSong, get_catalog_song
from apps.song_carts.models import CartStatus, ServiceSection, SongCart, SongCartItem


@dataclass(frozen=True)
class AddCartSong:
    service_date: date
    section: str
    song_uid: str


@transaction.atomic
def add_cart_song(data: AddCartSong, *, user: User) -> UUID:
    """Add active catalog metadata to the user's draft for the selected date."""
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Sign in to prepare a song cart.")
    if data.section not in ServiceSection.values:
        raise ValidationError("Choose a valid service section.")
    song = get_catalog_song(GetCatalogSong(data.song_uid, CatalogAccess(False, False)))
    cart, _ = SongCart.objects.select_for_update().get_or_create(
        owner=user, service_date=data.service_date
    )
    if cart.status != CartStatus.DRAFT:
        raise ValidationError(
            "The song selection for this date has already been submitted."
        )
    SongCartItem.objects.get_or_create(
        cart=cart,
        section=data.section,
        song_uid=song.song_uid,
        defaults={"title": song.title, "authors": song.authors},
    )
    return cart.id


@transaction.atomic
def remove_cart_song(cart_id: UUID, song_id: int, *, user: User) -> UUID:
    """Remove one song from a draft owned by the active user."""
    if not user.is_authenticated or not user.is_active:
        raise PermissionDenied("Sign in to prepare a song cart.")
    cart = SongCart.objects.select_for_update().get(pk=cart_id, owner=user)
    if cart.status != CartStatus.DRAFT:
        raise ValidationError("Submitted song selections cannot be changed.")
    SongCartItem.objects.get(pk=song_id, cart=cart).delete()
    return cart.id
