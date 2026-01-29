# solver/entrypoint.py
from __future__ import annotations

from typing import Callable, List, Optional

from domain.types import Item, PlanResult, Vehicle
from solver.packer import pack
from solver.reopt import ReoptConfig, reopt

DebugLogFn = Optional[Callable[[str, dict], None]]


def solve(items: List[Item], vehicle: Vehicle, task_id: str, transport_type: str, debug_log: DebugLogFn = None) -> PlanResult:
  plan = pack(items, vehicle, task_id=task_id, transport_type=transport_type, debug_log=debug_log)
  # по умолчанию reopt выключен, но интерфейс готов
  return reopt(plan, debug_log=debug_log, cfg=ReoptConfig(enabled=False))

