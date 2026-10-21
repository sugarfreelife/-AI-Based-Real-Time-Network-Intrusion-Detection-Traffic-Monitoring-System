"""Small JSON logging setup for capture lifecycle events."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    _context_fields = (
        "pcap_path",
        "interface",
        "packets_seen",
        "packets_processed",
        "packets_filtered",
        "parsing_failures",
        "read_failures",
        "elapsed_seconds",
        "status",
        "error",
    )

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        for name in self._context_fields:
            if hasattr(record, name):
                entry[name] = getattr(record, name)
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        return json.dumps(entry, separators=(",", ":"), default=str)


def configure_json_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
