from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.song_carts.services import submission_overview


def show_submissions(request, context):
    """Map the submissions overview into the existing Unfold dashboard."""
    status = request.GET.get("status", "pending")
    if status not in {"", "all", "draft", "pending", "confirmed", "rejected"}:
        status = "pending"
    sort = request.GET.get("sort", "submitted_desc")
    if sort not in {"submitted_desc", "service_date_desc", "service_date_asc"}:
        sort = "submitted_desc"
    query = request.GET.get("q", "").strip()[:200]
    overview = submission_overview(
        user=request.user, status=status, sort=sort, query=query,
    )
    rows = []
    for submission in overview.rows:
        detail_url = reverse(
            "admin:song_carts_songcart_change", args=[submission.id],
        )
        label = render_to_string("unfold/helpers/label.html", {
            "text": submission.status.capitalize(),
            "type": {
                "pending": "warning", "confirmed": "success", "rejected": "danger",
            }.get(submission.status, ""),
        })
        rows.append([
            format_html(
                '<a href="{}" class="font-medium text-primary-600 dark:text-primary-400 underline">{}</a>',
                detail_url, submission.service_date.strftime("%b %d, %Y"),
            ),
            format_html(
                '<div class="submission-owner">'
                '<div class="font-medium">{}</div>'
                '<div class="text-sm break-all">{}</div></div>',
                submission.owner_name or submission.owner_email,
                submission.owner_email,
            ),
            str(len(submission.songs)),
            submission.submitted_at.strftime("%b %d, %Y %H:%M")
            if submission.submitted_at else "Not submitted",
            mark_safe(label),
            format_html(
                '<a href="{}" class="underline">View details</a>', detail_url,
            ),
        ])
    context.update(
        title="Submissions",
        submission_counts=overview.counts,
        submission_total=overview.total,
        submissions_truncated=overview.truncated,
        submission_status=status,
        submission_sort=sort,
        submission_query=query,
        submission_table={
            "headers": [
                "Service date", "Submitted by", "Songs", "Submitted (UTC)",
                "Status", "Review",
            ],
            "rows": rows,
        },
    )
    return context
