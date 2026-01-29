# catalogs/plan_state.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from domain.types import AxleLoads, Candidate, DebugEvent, Item, ModeDecision, PlanResult, PlacedItem, Vehicle
from geometry.free_rects import FreeRects, Rect
from catalogs.placed_item import placed_from_candidate
from constraints.bounds import check_collision, check_oob
from constraints.axles import compute_loads, check_loads


@dataclass
class PlanState:
  task_id: str
  transport_type: str
  vehicle: Vehicle
  mode: ModeDecision
  debug: List[DebugEvent] = field(default_factory=list)

  items_by_id: Dict[str, Item] = field(default_factory=dict)
  placed: List[PlacedItem] = field(default_factory=list)
  unplaced: List[Item] = field(default_factory=list)

  free_rects: FreeRects = field(default_factory=lambda: FreeRects(rects=[]))
  loads: Optional[AxleLoads] = None

  def init_free_rects(self) -> None:
    self.free_rects = FreeRects.init_for_vehicle(self.vehicle)

  def emit(self, evt: str, payload: dict) -> None:
    self.debug.append(DebugEvent(evt=evt, payload=payload))

  def can_place(self, cand: Candidate) -> Tuple[bool, List[str]]:
    reasons: List[str] = []

    ok, r = check_oob(cand, self.vehicle)
    if not ok:
      reasons.extend(r)
      return (False, reasons)

    ok, r = check_collision(cand, self.placed)
    if not ok:
      reasons.extend(r)
      return (False, reasons)

    # Axles hard-filter
    item = self.items_by_id[cand["itemId"]]
    tmp_placed = self.placed + [placed_from_candidate(cand, item=item)]
    loads = compute_loads(tmp_placed, self.vehicle)
    ok, r = check_loads(loads, self.vehicle)
    if not ok:
      reasons.extend(r)
      return (False, reasons)

    return (True, [])

  def commit(self, cand: Candidate) -> None:
    item = self.items_by_id[cand["itemId"]]
    p = placed_from_candidate(cand, item=item)
    self.placed.append(p)

    used: Rect = (cand["aabb"]["minX"], cand["aabb"]["maxX"], cand["aabb"]["minZ"], cand["aabb"]["maxZ"])
    self.free_rects.reserve(used)

    self.loads = compute_loads(self.placed, self.vehicle)

  def snapshot(self) -> PlanResult:
    return PlanResult(
      taskId=self.task_id,
      transportType=self.transport_type,
      vehicle=self.vehicle,
      mode=self.mode,
      placed=self.placed,
      unplaced=self.unplaced,
      loads=self.loads,
      debug=self.debug,
    )
