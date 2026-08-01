from __future__ import annotations

import logging
import sys

import structlog

from app.config import settings


def configure_logging() -> None:
    """JSON logs in every environment, so production and local read the same."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=settings.log_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.log_level.upper()]
        ),
        cache_logger_on_first_use=True,
    )
