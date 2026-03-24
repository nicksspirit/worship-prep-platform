"""Common middleware for the Worship Prep Platform."""

from django.utils.deprecation import MiddlewareMixin


class ApiCsrfExemptMiddleware(MiddlewareMixin):
    """
    Exempts /api/v1/ from CSRF for machine-to-machine API key auth.

    django-bolt uses Bolt request.state["_csrf_exempt"] for CSRF bypass, so we set
    both Django request.csrf_exempt and Bolt request.state["_csrf_exempt"].
    """

    def process_request(self, request):
        if request.path.startswith("/api/v1/"):
            request.csrf_exempt = True
            bolt_req = getattr(request, "_bolt_request", None)
            if bolt_req is not None and hasattr(bolt_req, "state"):
                bolt_req.state["_csrf_exempt"] = True
        return None
