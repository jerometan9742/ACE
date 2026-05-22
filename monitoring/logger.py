"""Structured trade logging — writes every signal, decision, trade, and error to JSON logs with timestamps."""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

_LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
logger = logging.getLogger(__name__)


def _write(category: str, data: Dict[str, Any]) -> None:
    """Append one JSON entry to logs/<category>.jsonl. Silent on failure."""
    try:
        os.makedirs(_LOGS_DIR, exist_ok=True)
        path = os.path.join(_LOGS_DIR, f"{category}.jsonl")
        entry = {"ts": datetime.now(timezone.utc).isoformat(), **data}
        with open(path, "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception as exc:
        logger.error("logger._write(%s) failed: %s", category, exc)


def log_signal(pair: str, score: int, passed: bool, breakdown: dict) -> None:
    _write("signals", {"pair": pair, "score": score, "passed": passed, "breakdown": breakdown})


def log_decision(pair: str, action: str, confidence: float, reasoning: str) -> None:
    _write("decisions", {"pair": pair, "action": action, "confidence": confidence, "reasoning": reasoning})


def log_trade(order: dict) -> None:
    _write("trades", order)


def log_error(source: str, message: str) -> None:
    _write("errors", {"source": source, "message": message})
