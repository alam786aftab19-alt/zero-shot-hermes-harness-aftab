"""Observability: structured logging and spans."""
from __future__ import annotations

import logging
import time
import structlog
from contextlib import contextmanager
from typing import Any, Dict, Iterator


def configure_logging(log_level: str = "INFO"):
    logging.basicConfig(level=log_level, format="%(message)s")
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.BoundLogger:
    return structlog.get_logger(name)


@contextmanager
def log_span(log: structlog.BoundLogger, name: str, **kwargs) -> Iterator[Dict[str, Any]]:
    span = dict(kwargs)
    start_time = time.time()
    try:
        yield span
    except Exception as exc:
        span["error"] = str(exc)
        raise
    finally:
        span["duration_ms"] = (time.time() - start_time) * 1000
        log.info(name, **span)
