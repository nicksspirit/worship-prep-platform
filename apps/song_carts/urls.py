from django.urls import path

from apps.song_carts import views
from apps.song_carts.unlisted_views import ReviewUnlistedSongView, UnlistedSongView

app_name = "song_carts"

urlpatterns = [
    path("song-carts/", views.CartListView.as_view(), name="list"),
    path("song-carts/empty/", views.EmptyCartView.as_view(), name="empty"),
    path("song-carts/unlisted/", UnlistedSongView.as_view(), name="add_unlisted"),
    path(
        "song-carts/<uuid:cart_id>/unlisted/<int:song_id>/",
        UnlistedSongView.as_view(), name="unlisted_detail",
    ),
    path(
        "song-carts/<uuid:cart_id>/unlisted/<int:song_id>/review/",
        ReviewUnlistedSongView.as_view(), name="review_unlisted",
    ),
    path("song-carts/add/<path:song_uid>/", views.AddSongView.as_view(), name="add"),
    path("song-carts/<uuid:cart_id>/", views.CartDetailView.as_view(), name="detail"),
    path(
        "song-carts/<uuid:cart_id>/comments/",
        views.AddCommentView.as_view(), name="add_comment",
    ),
    path(
        "song-carts/<uuid:cart_id>/comments/<int:comment_id>/edit/",
        views.EditCommentView.as_view(), name="edit_comment",
    ),
    path(
        "song-carts/<uuid:cart_id>/remove/<int:song_id>/",
        views.RemoveSongView.as_view(),
        name="remove",
    ),
    path(
        "song-carts/<uuid:cart_id>/checkout/",
        views.CheckoutView.as_view(),
        name="checkout",
    ),
]
