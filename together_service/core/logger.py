"""Structured JSON logging via logging.config.dictConfig."""
import json
import logging
import logging.config
from datetime import datetime, timezone


SERVICE_NAME = "together-service"

# Зафиксированный набор стандартных полей LogRecord — берём из реального
# экземпляра, чтобы не отстать от изменений в stdlib при обновлении Python.
# Плюс "message" (его кладёт сам Formatter после record.getMessage()) — это
# поле мы уже добавили вручную, повторно сериализовать не надо.
_RESERVED_LOG_FIELDS = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "service": SERVICE_NAME,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_FIELDS:
                continue
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "core.logger.JsonFormatter"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}


def setup_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
