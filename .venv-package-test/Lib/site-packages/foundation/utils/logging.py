"""
SH-3 Complete Edition v1.0
Foundation Layer
Utils Subsystem
logging.py
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from typing import Any

from .hash import short_id
from .json import dumps
from .time import iso

_LOGGERS: dict[str, logging.Logger] = {}


def get_logger(name: str = "sh3", level: int = logging.INFO) -> logging.Logger:
    logger = _LOGGERS.get(name)
    if logger is not None:
        return logger

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _LOGGERS[name] = logger
    return logger


def _format_structured(
    message: str,
    data: dict[str, Any] | None,
) -> str:
    if not data:
        return message

    try:
        payload = dumps(data, ensure_ascii=False)
    except Exception:
        payload = str(data)

    return f"{message} | data={payload}"


def info(
    message: str,
    data: dict[str, Any] | None = None,
    logger: str = "sh3",
) -> None:
    log = get_logger(logger)
    log.info(_format_structured(message, data))


def debug(
    message: str,
    data: dict[str, Any] | None = None,
    logger: str = "sh3",
) -> None:
    log = get_logger(logger, level=logging.DEBUG)
    log.debug(_format_structured(message, data))


def warn(
    message: str,
    data: dict[str, Any] | None = None,
    logger: str = "sh3",
) -> None:
    log = get_logger(logger)
    log.warning(_format_structured(message, data))


def error(
    message: str,
    data: dict[str, Any] | None = None,
    logger: str = "sh3",
) -> None:
    log = get_logger(logger)
    log.error(_format_structured(message, data))


def event(
    name: str,
    payload: dict[str, Any] | None = None,
    logger: str = "sh3",
) -> None:
    log = get_logger(logger)
    data: dict[str, Any] = dict(payload) if payload is not None else {}
    data["event_id"] = short_id(name)
    data["timestamp"] = iso(datetime.now(UTC))
    log.info(f"[EVENT] {name} | {dumps(data, ensure_ascii=False)}")


def exception(
    message: str,
    exc: Exception,
    data: dict[str, Any] | None = None,
    logger: str = "sh3",
) -> None:
    log = get_logger(logger)
    payload: dict[str, Any] = dict(data) if data is not None else {}
    payload["exception_type"] = type(exc).__name__
    payload["exception_message"] = str(exc)
    log.error(_format_structured(message, payload), exc_info=True)


def set_level(
    level: int,
    logger: str = "sh3",
) -> None:
    get_logger(logger).setLevel(level)


def disable(logger: str = "sh3") -> None:
    logging.getLogger(logger).disabled = True


def enable(logger: str = "sh3") -> None:
    logging.getLogger(logger).disabled = False
