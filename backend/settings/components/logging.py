"""Structured logging for Django, Gunicorn, and Django-Bolt (Cloud Logging–ready in prod)."""

from __future__ import annotations

import logging
import sys
from typing import Any, cast

import structlog

from backend.settings import DJANGO_ENV, env

GCP_PROJECT_ID = env.str("GCP_PROJECT_ID", default="")

type EventDict = dict[str, Any]

LOG_LEVEL = "DEBUG" if DJANGO_ENV == "local" else "INFO"


def drop_none_values(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Remove missing optional fields, including requests without a Cloud trace."""
    return {k: v for k, v in event_dict.items() if v is not None}


def simplify_logger_name(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Replace verbose logger names with shorter aliases."""

    name_map = {
        "django_structlog.middlewares.request": "http.request",
        "django.utils.autoreload": "autoreload",
        "django.server": "dj.server",
        "django.request": "dj.request",
    }

    if "logger" in event_dict:
        original = event_dict["logger"]
        event_dict["logger"] = name_map.get(original, original)

    return event_dict


def sanitize_exception(logger, method_name, event_dict):
    """Retain exception types without content, traceback source, or local variables."""
    exception = event_dict.pop("exc_info", None)
    event_dict.pop("stack_info", None)
    if exception:
        if exception is True:
            exception = sys.exc_info()
        event_dict.pop("positional_args", None)
        if isinstance(exception, tuple):
            exception = exception[1]
        if isinstance(exception, BaseException):
            event_dict["exception_type"] = type(exception).__name__
        event_dict["event"] = "request_exception"
    if event_dict.get("logger") == "gunicorn.error" and str(
        event_dict.get("event", "")
    ).startswith("Invalid request from ip="):
        event_dict["event"] = "invalid_http_request"
    return event_dict


_BASE_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    sanitize_exception,
    structlog.stdlib.PositionalArgumentsFormatter(),
    simplify_logger_name,
]

CONSOLE_PROCESSORS = _BASE_PROCESSORS + [drop_none_values]
JSON_PROCESSORS = _BASE_PROCESSORS + [drop_none_values]

CONSOLE_FORMATTER = "console" if DJANGO_ENV in ("local", "test") else "json"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.processors.JSONRenderer(),
            "foreign_pre_chain": JSON_PROCESSORS,
        },
        "console": {
            "()": structlog.stdlib.ProcessorFormatter,
            "processor": structlog.dev.ConsoleRenderer(
                colors=DJANGO_ENV not in ("prod", "test"),
                exception_formatter=structlog.dev.plain_traceback,
            ),
            "foreign_pre_chain": CONSOLE_PROCESSORS,
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": CONSOLE_FORMATTER,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "httpx": {"level": "WARNING"},
        "gunicorn.error": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "reactivated.fields": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django_structlog": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.utils.autoreload": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django_bolt.logging": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

_structlog_base = (
    CONSOLE_PROCESSORS if DJANGO_ENV in ("local", "test") else JSON_PROCESSORS
)
STRUCTLOG_PROCESSORS = _structlog_base.copy()
STRUCTLOG_PROCESSORS.insert(1, structlog.stdlib.filter_by_level)
STRUCTLOG_PROCESSORS.extend(
    [
        structlog.processors.UnicodeDecoder(),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ]
)

structlog.configure(
    processors=cast(
        list[structlog.types.Processor],
        STRUCTLOG_PROCESSORS,
    ),
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
