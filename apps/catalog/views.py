from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.api_keys.models import APIKeyScope
from apps.api_keys.services import authenticate_api_key
from apps.catalog.importer import ImportRejected, import_package


@csrf_exempt
@require_POST
def catalog_import(request):
    """Receive a Catalog Import Package from an import-scoped client."""

    authorization = request.headers.get("Authorization", "")
    scheme, separator, raw_key = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not authenticate_api_key(
        raw_key, required_scope=APIKeyScope.CATALOG_IMPORT
    ):
        return JsonResponse({"error": "unauthorized"}, status=401)

    upload = request.FILES.get("package")
    package = upload.read() if upload else request.body
    try:
        result = import_package(package)
    except ImportRejected as exc:
        status = 409 if exc.code == "run_id_conflict" else 422
        return JsonResponse({"error": exc.code, "detail": exc.summary}, status=status)
    return JsonResponse(
        {"run_id": str(result.run.pk), "status": result.run.status},
        status=201 if result.created else 200,
    )
