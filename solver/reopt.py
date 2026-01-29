# solver/reopt.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from domain.types import PlanResult

DebugLogFn = Optional[Callable[[str, dict], None]]


@dataclass(frozen=True)
class ReoptConfig:
  enabled: bool = False
  max_iters: int = 20
  # позже:
  # - neighbourhood size
  # - swap/move operators
  # - time budget


def reopt(plan: PlanResult, debug_log: DebugLogFn = None, cfg: ReoptConfig = ReoptConfig()) -> PlanResult:
  """
  MVP: заглушка.
  Держит интерфейс и debug события, чтобы пайплайн был цельным:
  packer -> (reopt?) -> result
  """
  if not cfg.enabled:
    if debug_log:
      debug_log("reopt_skipped", {"enabled": False})
    return plan

  # Здесь позже будет локальный поиск:
  # - попытка перестановок для уплотнения (free_rects rebuild)
  # - попытка заменить 2-3 item на другие по K, сохраняя оси
  # - попытка "почти влезает": выкинуть 1 низкоценный и вставить 2 высокоценных
  if debug_log:
    debug_log("reopt_started", {"max_iters": cfg.max_iters, "placed": len(plan.placed), "unplaced": len(plan.unplaced)})

  # Сейчас — без изменений
  if debug_log:
    debug_log("reopt_done", {"changed": False})

  return plan
