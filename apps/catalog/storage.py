from django.core.files.storage import storages


def catalog_import_storage():
    """Return the private storage reserved for import evidence and reports."""

    return storages["catalog_imports"]
