from datetime import date
from typing import TypedDict

from django.http import HttpRequest
from django.urls import reverse

from apps.song_carts.services import read_active_cart


class SongCartHeader(TypedDict):
    url: str
    song_count: int


class SongCartContext(TypedDict):
    song_cart: SongCartHeader


def song_cart(request: HttpRequest) -> SongCartContext:
    """Expose the signed-in user's active draft without trusting a cookie count."""
    empty: SongCartContext = {
        "song_cart": {"url": reverse("song_carts:list"), "song_count": 0}
    }
    if not request.user.is_authenticated:
        return empty
    remembered_date = request.session.get("song_cart_service_date")
    try:
        service_date = date.fromisoformat(remembered_date) if remembered_date else None
    except (TypeError, ValueError):
        return empty
    cart = read_active_cart(user=request.user, service_date=service_date)
    if cart is None:
        return empty
    return {"song_cart": {
        "url": reverse("song_carts:detail", args=[cart.id]),
        "song_count": cart.song_count,
    }}
