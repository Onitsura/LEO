# server.py
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine

from settings import DATABASE_URL
from services.packing import pack_task_to_viewer_json

load_dotenv()

# -------------------------
# App / DB
# -------------------------

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

app = FastAPI(title="Packman Load Plan API", version="0.3.0")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=False,
  allow_methods=["GET"],
  allow_headers=["*"],
)

# -------------------------
# Debug (per-request file)
# -------------------------

DEBUG_ENABLED = os.getenv("DEBUG_ENABLED", "1") == "1"
DEBUG_DIR = os.getenv("DEBUG_DIR", "debug_runs")
DEBUG_RETURN_PATH = os.getenv("DEBUG_RETURN_PATH", "0") == "1"

DebugLogFn = Callable[[str, Dict[str, Any]], None]


def _ts_name_utc() -> str:
  return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _safe_fs_name(s: str) -> str:
  s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s)
  return s[:120] if len(s) > 120 else s


def _make_file_logger(run_id: str, task_id: str) -> tuple[DebugLogFn, str]:
  os.makedirs(DEBUG_DIR, exist_ok=True)
  fname = f"{_ts_name_utc()}__{_safe_fs_name(task_id)}__{run_id}.jsonl"
  path = os.path.join(DEBUG_DIR, fname)

  def log(evt: str, payload: Dict[str, Any]) -> None:
    rec = {
      "ts": datetime.now(timezone.utc).isoformat(),
      "evt": evt,
      "payload": payload,
    }
    with open(path, "a", encoding="utf-8") as f:
      f.write(json.dumps(rec, ensure_ascii=False) + "\n")

  return log, path


# -------------------------
# Health
# -------------------------

@app.get("/health")
def health() -> Dict[str, Any]:
  return {"ok": True}


# -------------------------
# Main endpoint
# -------------------------

@app.get("/plan/{task_id}")
def get_plan(task_id: str) -> Dict[str, Any]:
  run_id = uuid.uuid4().hex[:10]

  debug_log: Optional[DebugLogFn] = None
  debug_path: Optional[str] = None
  if DEBUG_ENABLED:
    debug_log, debug_path = _make_file_logger(run_id, task_id)

  try:
    payload = pack_task_to_viewer_json(engine=engine, task_id=task_id, debug_log=debug_log)
  except Exception as exc:
    if debug_log:
      debug_log("server_error", {"taskId": task_id, "error": f"{type(exc).__name__}: {exc}"})
    raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")

  if DEBUG_RETURN_PATH and debug_path:
    payload["_debug"] = {"runId": run_id, "path": debug_path}

  return payload


@app.get("/api/load-plan/by-task/{task_id}")
def get_plan_compat(task_id: str) -> Dict[str, Any]:
  # полностью тот же обработчик, что и /plan/{task_id}, было лень искать где viewer ходит не в ту апи
  run_id = uuid.uuid4().hex[:10]

  debug_log: Optional[DebugLogFn] = None
  debug_path: Optional[str] = None
  if DEBUG_ENABLED:
    debug_log, debug_path = _make_file_logger(run_id, task_id)

  try:
    payload = pack_task_to_viewer_json(engine=engine, task_id=task_id, debug_log=debug_log)
  except Exception as exc:
    if debug_log:
      debug_log("server_error", {"taskId": task_id, "error": f"{type(exc).__name__}: {exc}"})
    raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")

  if DEBUG_RETURN_PATH and debug_path:
    payload["_debug"] = {"runId": run_id, "path": debug_path}

  return payload
