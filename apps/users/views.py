from django.http import HttpRequest, HttpResponse
from . import templates


def homepage(request: HttpRequest) -> HttpResponse:
    return templates.MyTemplate(
        name="George Washington",
        title="President",
        age=67,
        location="Virginia",
    ).render(request)
