from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db.models import Count, F, Q, QuerySet

from apps.accounts.models import User
from apps.song_carts.models import CartStatus, SongCart
from .access import _require_active, _require_staff
from .comments import _can_edit, _edit_deadline

SORTS = {
    "service_date_desc": ("-service_date", "-created_at"),
    "service_date_asc": ("service_date", "created_at"),
    "submitted_desc": (F("submitted_at").desc(nulls_last=True), "-created_at"),
    "submitted_asc": (F("submitted_at").asc(nulls_last=True), "created_at"),
    "created_desc": ("-created_at",),
    "created_asc": ("created_at",),
}


@dataclass(frozen=True)
class ActiveCart:
    id: UUID
    song_count: int


def read_active_cart(
    *, user: User, service_date: date | None = None,
) -> ActiveCart | None:
    """Read the remembered draft, or the newest draft when none is selected."""
    if not user.is_authenticated or not user.is_active:
        return None
    carts = SongCart.objects.filter(owner=user, status=CartStatus.DRAFT)
    if service_date is not None:
        carts = carts.filter(service_date=service_date)
    cart = carts.annotate(song_count=Count("songs")).order_by("-created_at").first()
    return ActiveCart(cart.id, cart.song_count) if cart is not None else None


@dataclass(frozen=True)
class CartSong:
    id: int
    section: str
    song_uid: str
    title: str
    authors: tuple[str, ...]


@dataclass(frozen=True)
class CartComment:
    id: int
    body: str
    created_at: datetime
    updated_at: datetime | None
    can_edit: bool
    edit_deadline: datetime | None


@dataclass(frozen=True)
class CartEmail:
    id: int
    kind: str
    label: str
    status: str
    error: str
    sent_at: datetime | None


@dataclass(frozen=True)
class CartDetails:
    id: UUID
    service_date: date
    status: str
    notification_status: str
    songs: tuple[CartSong, ...]
    owner_name: str
    owner_email: str
    submitted_at: datetime | None
    confirmed_at: datetime | None
    confirmed_by: str | None
    rejected_at: datetime | None
    rejected_by: str | None
    rejection_reason: str
    comments: tuple[CartComment, ...]
    emails: tuple[CartEmail, ...]


@dataclass(frozen=True)
class SubmissionOverview:
    counts: dict[str, int]
    rows: tuple[CartDetails, ...]
    total: int
    truncated: bool


def _display_user(user: User | None) -> str | None:
    return (user.get_full_name() or user.email) if user else None


def _describe(cart: SongCart, *, user: User) -> CartDetails:
    return CartDetails(
        id=cart.id, service_date=cart.service_date, status=cart.status,
        notification_status=cart.notification_status,
        songs=tuple(CartSong(
            song.id, song.section, song.song_uid, song.title, tuple(song.authors),
        ) for song in cart.songs.all()),
        owner_name=cart.owner.get_full_name() or cart.owner.email,
        owner_email=cart.owner.email, submitted_at=cart.submitted_at,
        confirmed_at=cart.confirmed_at, confirmed_by=_display_user(cart.confirmed_by),
        rejected_at=cart.rejected_at, rejected_by=_display_user(cart.rejected_by),
        rejection_reason=cart.rejection_reason,
        comments=tuple(CartComment(
            comment.id, comment.body, comment.created_at, comment.updated_at,
            cart.owner_id == user.pk and _can_edit(comment, cart, user),
            _edit_deadline(comment, cart),
        ) for comment in cart.comments.all()),
        emails=tuple(CartEmail(
            email.id, email.kind, email.get_kind_display(),
            email.status, email.error, email.sent_at,
        ) for email in cart.emails.all()),
    )


def _rows() -> QuerySet[SongCart]:
    return SongCart.objects.select_related(
        "owner", "confirmed_by", "rejected_by",
    ).prefetch_related("songs", "comments", "emails")


def _filter(carts: QuerySet[SongCart], *, status: str, sort: str) -> QuerySet[SongCart]:
    if status not in ("", "all", *CartStatus.values):
        raise ValidationError("Choose a valid submission state.")
    if sort not in SORTS:
        raise ValidationError("Choose a valid submission sort order.")
    if status not in ("", "all"):
        carts = carts.filter(status=status)
    return carts.order_by(*SORTS[sort], "id")


def get_cart(cart_id: UUID, *, user: User) -> CartDetails:
    """Read a cart belonging to the active signed-in user."""
    _require_active(user)
    return _describe(_rows().get(pk=cart_id, owner=user), user=user)


def list_carts(
    *, user: User, status: str = "", sort: str = "service_date_desc",
) -> list[CartDetails]:
    """Read only the owner's drafts and submissions with validated state and sorting."""
    _require_active(user)
    return [_describe(cart, user=user) for cart in _filter(
        _rows().filter(owner=user), status=status, sort=sort,
    )]


def read_submission_for_admin(cart_id: UUID, *, user: User) -> CartDetails:
    """Read all selected songs, comments, and delivery outcomes for staff review."""
    _require_staff(user)
    return _describe(_rows().get(pk=cart_id), user=user)


def submission_overview(
    *, user: User, status: str = "pending", sort: str = "submitted_desc", query: str = "",
) -> SubmissionOverview:
    """Summarize submitted states and disclose when a filtered table exceeds 100 rows."""
    _require_staff(user)
    if len(query) > 200:
        raise ValidationError("Search terms cannot exceed 200 characters.")
    counts = SongCart.objects.aggregate(**{
        state: Count("id", filter=Q(status=state))
        for state in (CartStatus.PENDING, CartStatus.CONFIRMED, CartStatus.REJECTED)
    })
    counts["total"] = sum(counts.values())
    carts = _filter(_rows(), status=status, sort=sort)
    if status == "":
        carts = carts.exclude(status=CartStatus.DRAFT)
    if query.strip():
        carts = carts.filter(
            Q(owner__email__icontains=query.strip())
            | Q(owner__first_name__icontains=query.strip())
            | Q(owner__last_name__icontains=query.strip())
            | Q(songs__title__icontains=query.strip())
        ).distinct()
    total = carts.count()
    return SubmissionOverview(
        counts, tuple(_describe(cart, user=user) for cart in carts[:100]),
        total, total > 100,
    )
