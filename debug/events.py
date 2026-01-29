# debug/events.py
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

DebugLogFn = Callable[[str, Dict[str, Any]], None]


def emit(log: Optional[DebugLogFn], evt: str, payload: Dict[str, Any]) -> None:
  if not log:
    return
  try:
    log(evt, payload)
  except Exception:
    # debug лог не должен валить solver
    pass


def emit_error(log: Optional[DebugLogFn], evt: str, payload: Dict[str, Any], exc: Exception) -> None:
  p = dict(payload)
  p["error"] = f"{type(exc).__name__}: {exc}"
  emit(log, evt, p)
