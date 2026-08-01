from typing import Annotated

from django_bolt import BoltAPI, JSON, UploadFile
from django_bolt.param_functions import File, Header

from apps.api_keys.models import APIKeyScope
from apps.api_keys.services import authenticate_api_key
from apps.catalog.importer import MAX_PACKAGE_BYTES, ImportRejected, import_package

api = BoltAPI(prefix="/api/v1/catalog")


@api.post("/imports", tags=["catalog imports"], summary="Import a catalog package")
def catalog_import(
    package: Annotated[
        UploadFile,
        File(
            alias="package",
            max_size=MAX_PACKAGE_BYTES,
            allowed_types=["application/zip", "application/x-zip-compressed"],
        ),
    ],
    authorization: Annotated[str, Header(alias="Authorization")] = "",
):
    """Receive a Catalog Import Package from an import-scoped client."""

    scheme, separator, raw_key = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not authenticate_api_key(
        raw_key, required_scope=APIKeyScope.CATALOG_IMPORT
    ):
        return JSON({"error": "unauthorized"}, status_code=401)

    try:
        result = import_package(package.file.read())
    except ImportRejected as exc:
        status = 409 if exc.code == "run_id_conflict" else 422
        return JSON({"error": exc.code, "detail": exc.summary}, status_code=status)
    return JSON(
        {"run_id": str(result.run.pk), "status": result.run.status},
        status_code=201 if result.created else 200,
    )
