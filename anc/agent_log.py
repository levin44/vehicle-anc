"""NDJSON debug logging for Cursor debug sessions (dev + Pi paths)."""

from __future__ import annotations

import json
import time
from pathlib import Path

# #region agent log
_DEBUG_SESSION = "f2b82f"
_DEBUG_LOG_PATHS = (
    Path("/home/ubuntu/Dev/pi/.cursor") / f"debug-{_DEBUG_SESSION}.log",
    Path(__file__).resolve().parent / ".cursor" / f"debug-{_DEBUG_SESSION}.log",
)


def agent_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: dict,
    run_id: str = "pre-fix",
) -> None:
    payload = {
        "sessionId": _DEBUG_SESSION,
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload) + "\n"
    for path in _DEBUG_LOG_PATHS:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(line)
            break
        except OSError:
            continue


# #endregion