"""Structured logging for Django, Gunicorn, and Django-Bolt (Cloud Logging–ready in prod)."""

from __future__ import annotations

import logging
from typing import Any, cast

import structlog
from environs import Env

type EventDict = dict[str, Any]

env = Env()

DJANGO_ENV = env.str("DJANGO_ENV", default="local")
LOG_LEVEL = "DEBUG" if DJANGO_ENV == "local" else "INFO"


def drop_none_values(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Remove keys with None values to reduce log noise (console only)."""
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
        "apps.schedules.inbound": "api.schedules",
        "apps.songs.inbound": "api.songs",
    }

    if "logger" in event_dict:
        original = event_dict["logger"]
        event_dict["logger"] = name_map.get(original, original)

    return event_dict


exc_processor = (
    structlog.processors.format_exc_info
    if DJANGO_ENV in ("local", "test")
    else structlog.processors.dict_tracebacks
)

_BASE_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.processors.StackInfoRenderer(),
    exc_processor,
    simplify_logger_name,
]

CONSOLE_PROCESSORS = _BASE_PROCESSORS + [drop_none_values]
JSON_PROCESSORS = _BASE_PROCESSORS.copy()

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
