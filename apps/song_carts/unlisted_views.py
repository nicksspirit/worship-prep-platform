from typing import cast
from uuid import UUID

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views import View

from apps.catalog.templates import RenderableTemplate
from apps.song_carts.forms import UnlistedSongForm
from apps.song_carts.models import ServiceSection, SongCart, SongCartItem
from apps.song_carts.presentation import present_unlisted_song
from apps.song_carts.services import (
    UnlistedSongInput, get_unlisted_song, review_unlisted_song, save_unlisted_song,
)


class UnlistedSongView(LoginRequiredMixin, View):
    """Save pasted lyrics in an owned draft, then show their prepared preview."""

    def get(
        self, request: HttpRequest, cart_id: UUID | None = None,
        song_id: int | None = None,
    ) -> HttpResponse:
        song = None
        if cart_id is not None and song_id is not None:
            try:
                song = get_unlisted_song(cart_id, song_id, user=request.user)
            except (SongCart.DoesNotExist, SongCartItem.DoesNotExist) as exc:
                raise Http404("Unlisted song not found.") from exc
        form = UnlistedSongForm(initial={
            "title": song.title if song else request.GET.get("title", "")[:512],
            "lyrics": song.lyrics if song else "",
            "service_date": song.service_date.isoformat() if song else request.GET.get(
                "service_date", request.session.get("song_cart_service_date", ""),
            ),
            "section": song.section if song else request.session.get(
                "song_cart_section", ServiceSection.CALL_TO_WORSHIP,
            ),
        })
        page = present_unlisted_song(
            song, song_title=str(form["title"].value() or ""),
            lyrics=str(form["lyrics"].value() or ""),
            service_date=str(form["service_date"].value() or ""),
            section=str(form["section"].value() or ServiceSection.CALL_TO_WORSHIP),
        )
        return cast(RenderableTemplate, page).render(request)

    def post(
        self, request: HttpRequest, cart_id: UUID | None = None,
        song_id: int | None = None,
    ) -> HttpResponse:
        song = None
        if cart_id is not None and song_id is not None:
            try:
                song = get_unlisted_song(cart_id, song_id, user=request.user)
            except (SongCart.DoesNotExist, SongCartItem.DoesNotExist) as exc:
                raise Http404("Unlisted song not found.") from exc
        form = UnlistedSongForm(request.POST)
        if form.is_valid():
            try:
                saved = save_unlisted_song(UnlistedSongInput(
                    service_date=form.cleaned_data["service_date"],
                    section=form.cleaned_data["section"],
                    title=form.cleaned_data["title"], lyrics=form.cleaned_data["lyrics"],
                    song_id=song_id,
                ), user=request.user)
            except (SongCart.DoesNotExist, SongCartItem.DoesNotExist) as exc:
                raise Http404("Unlisted song not found.") from exc
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                request.session["song_cart_service_date"] = saved.service_date.isoformat()
                request.session["song_cart_section"] = saved.section
                return redirect(
                    "song_carts:unlisted_detail", cart_id=saved.cart_id, song_id=saved.id,
                )
        page = present_unlisted_song(
            song, song_title=str(form["title"].value() or ""),
            lyrics=str(form["lyrics"].value() or ""),
            service_date=str(form["service_date"].value() or ""),
            section=str(form["section"].value() or ServiceSection.CALL_TO_WORSHIP),
            errors=dict(form.errors),
        )
        response = cast(RenderableTemplate, page).render(request)
        response.status_code = 400
        return response


class ReviewUnlistedSongView(LoginRequiredMixin, View):
    """Record review of the saved preview without accepting stale lyric content."""

    def post(self, request: HttpRequest, cart_id: UUID, song_id: int) -> HttpResponse:
        try:
            review_unlisted_song(
                cart_id, song_id, request.POST.get("fingerprint", ""), user=request.user,
            )
        except (SongCart.DoesNotExist, SongCartItem.DoesNotExist) as exc:
            raise Http404("Unlisted song not found.") from exc
        except ValidationError as exc:
            song = get_unlisted_song(cart_id, song_id, user=request.user)
            page = present_unlisted_song(
                song, song_title=song.title, lyrics=song.lyrics,
                service_date=song.service_date.isoformat(), section=song.section,
                errors={"__all__": exc.messages},
            )
            response = cast(RenderableTemplate, page).render(request)
            response.status_code = 400
            return response
        return redirect("song_carts:detail", cart_id=cart_id)
