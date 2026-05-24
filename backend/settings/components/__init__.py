"""Shared bootstrap: project root path."""

from pathlib import Path

# backend/settings/components/__init__.py -> parents: settings, backend, repo root
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
