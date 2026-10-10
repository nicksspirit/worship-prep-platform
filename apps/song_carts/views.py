from typing import cast
from uuid import UUID

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from apps.catalog.services import (
    CatalogAccess,
    CatalogReadError,
    GetCatalogSong,
    get_catalog_song,
)
from apps.catalog.templates import RenderableTemplate
from apps.song_carts.forms import AddSongForm, CommentForm
from apps.song_carts.models import ServiceSection, SongCart, SongCartItem
from apps.song_carts.presentation import present_cart, present_carts
from apps.song_carts.services import (
    AddCartSong,
    add_cart_song,
    checkout_cart,
    get_cart,
    list_carts,
    remove_cart_song,
    add_comment,
    edit_comment,
)
from apps.song_carts.templates import AddSongPage, SectionChoiceProps


class CartListView(LoginRequiredMixin, View):
    """Render the current user's song carts."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the current user's song carts."""
        status_filter = request.GET.get("status", "")
        sort = request.GET.get("sort", "service_date_desc")
        try:
            carts = list_carts(user=request.user, status=status_filter, sort=sort)
        except ValidationError as exc:
            page = present_carts([], error=" ".join(exc.messages))
            response = cast(RenderableTemplate, page).render(request)
            response.status_code = 400
            return response
        page = present_carts(carts, status_filter=status_filter, sort=sort)
        return cast(RenderableTemplate, page).render(request)


class CartDetailView(LoginRequiredMixin, View):
    """Render the owner's draft or submitted selection."""

    def get(self, request: HttpRequest, cart_id: UUID) -> HttpResponse:
        """Render the owner's draft or submitted selection."""
        try:
            cart = get_cart(cart_id, user=request.user)
        except SongCart.DoesNotExist as exc:
            raise Http404("Song cart not found.") from exc
        if cart.status == "draft":
            request.session["song_cart_service_date"] = cart.service_date.isoformat()
        return cast(RenderableTemplate, present_cart(cart)).render(request)


class AddSongView(LoginRequiredMixin, View):
    """Bind a date and section, then add one catalog song."""

    def get(self, request: HttpRequest, song_uid: str) -> HttpResponse:
        return self._handle_form(request, song_uid)

    def post(self, request: HttpRequest, song_uid: str) -> HttpResponse:
        return self._handle_form(request, song_uid)

    def _handle_form(self, request: HttpRequest, song_uid: str) -> HttpResponse:
        """Bind the selected service date and section, then add one catalog song."""
        try:
            song = get_catalog_song(GetCatalogSong(song_uid, CatalogAccess(False, False)))
        except CatalogReadError as exc:
            raise Http404(exc.message) from exc
        form = AddSongForm(
            request.POST if request.method == "POST" else None,
            initial={
                "service_date": request.session.get("song_cart_service_date", ""),
                "section": request.session.get(
                    "song_cart_section", ServiceSection.CALL_TO_WORSHIP
                ),
            },
        )
        if request.method == "POST" and form.is_valid():
            try:
                cart_id = add_cart_song(
                    AddCartSong(
                        form.cleaned_data["service_date"],
                        form.cleaned_data["section"],
                        song_uid,
                    ),
                    user=request.user,
                )
            except (ValidationError, CatalogReadError) as exc:
                form.add_error(
                    None, exc.message if isinstance(exc, CatalogReadError) else exc
                )
            else:
                request.session["song_cart_service_date"] = form.cleaned_data[
                    "service_date"
                ].isoformat()
                request.session["song_cart_section"] = form.cleaned_data["section"]
                return redirect("song_carts:detail", cart_id=cart_id)
        page = AddSongPage(
            title="Add to song cart",
            song_title=song.title,
            action_url=reverse("song_carts:add", args=[song_uid]),
            song_url=reverse("catalog:detail", args=[song_uid]),
            service_date=str(form["service_date"].value() or ""),
            section=str(form["section"].value() or ServiceSection.CALL_TO_WORSHIP),
            sections=[
                SectionChoiceProps(value, label)
                for value, label in ServiceSection.choices
            ],
            errors=dict(form.errors),
        )
        response = cast(RenderableTemplate, page).render(request)
        response.status_code = 400 if form.is_bound and form.errors else 200
        return response


class RemoveSongView(LoginRequiredMixin, View):
    """Remove a song through the draft preparation service."""

    def post(self, request: HttpRequest, cart_id: UUID, song_id: int) -> HttpResponse:
        """Remove a song through the draft preparation service."""
        try:
            remove_cart_song(cart_id, song_id, user=request.user)
        except (SongCart.DoesNotExist, SongCartItem.DoesNotExist) as exc:
            raise Http404("Song cart item not found.") from exc
        except ValidationError as exc:
            page = present_cart(
                get_cart(cart_id, user=request.user), error=" ".join(exc.messages)
            )
            response = cast(RenderableTemplate, page).render(request)
            response.status_code = 400
            return response
        return redirect("song_carts:detail", cart_id=cart_id)


class CheckoutView(LoginRequiredMixin, View):
    """Submit a selection without duplicating submissions."""

    def post(self, request: HttpRequest, cart_id: UUID) -> HttpResponse:
        """Submit the current user's selection for team acknowledgement."""
        try:
            checkout_cart(cart_id, user=request.user)
        except SongCart.DoesNotExist as exc:
            raise Http404("Song cart not found.") from exc
        except ValidationError as exc:
            page = present_cart(
                get_cart(cart_id, user=request.user), error=" ".join(exc.messages)
            )
            response = cast(RenderableTemplate, page).render(request)
            response.status_code = 400
            return response
        return redirect("song_carts:detail", cart_id=cart_id)


class AddCommentView(LoginRequiredMixin, View):
    """Post one owner-authored submission comment."""

    def post(self, request: HttpRequest, cart_id: UUID) -> HttpResponse:
        form = CommentForm(request.POST)
        if form.is_valid():
            try:
                add_comment(cart_id, form.cleaned_data["body"], user=request.user)
            except SongCart.DoesNotExist as exc:
                raise Http404("Submission not found.") from exc
            except ValidationError as exc:
                form.add_error("body", exc)
            else:
                return redirect("song_carts:detail", cart_id=cart_id)
        try:
            cart = get_cart(cart_id, user=request.user)
        except SongCart.DoesNotExist as exc:
            raise Http404("Submission not found.") from exc
        page = present_cart(
            cart, comment_body=request.POST.get("body", ""),
            comment_errors=list(form.errors.get("body", [])),
        )
        response = cast(RenderableTemplate, page).render(request)
        response.status_code = 400
        return response


class EditCommentView(LoginRequiredMixin, View):
    """Edit one comment within its author edit window."""

    def post(self, request: HttpRequest, cart_id: UUID, comment_id: int) -> HttpResponse:
        form = CommentForm(request.POST)
        if form.is_valid():
            try:
                edit_comment(
                    cart_id, comment_id, form.cleaned_data["body"], user=request.user,
                )
            except SongCart.DoesNotExist as exc:
                raise Http404("Submission not found.") from exc
            except ValidationError as exc:
                form.add_error("body", exc)
            else:
                return redirect("song_carts:detail", cart_id=cart_id)
        try:
            cart = get_cart(cart_id, user=request.user)
        except SongCart.DoesNotExist as exc:
            raise Http404("Submission not found.") from exc
        page = present_cart(
            cart, comment_body=request.POST.get("body", ""),
            comment_errors=list(form.errors.get("body", [])),
        )
        response = cast(RenderableTemplate, page).render(request)
        response.status_code = 400
        return response
