# services/packing.py
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from sqlalchemy.engine import Engine

from catalogs.vehicles import get_vehicle
from domain.types import Item, PlanResult
from services.fetch import fetch_task_rows
from services.normalize import normalize_pallet
from solver.entrypoint import solve
from settings import SETTINGS


DebugLogFn = Optional[Callable[[str, Dict[str, Any]], None]]


# -----------------------------------------------------------------------------
# Viewer JSON adapter
# -----------------------------------------------------------------------------

def _placed_item_to_viewer(p) -> Dict[str, Any]:
  it = p.item
  return {
    "id": it.id,
    "dropContainerId": it.dropContainerId,
    "sscc": it.dropContainerId,  # alias for viewer/debug

    "palletType": it.palletType,
    "palletTypeNorm": it.palletTypeNorm,
    "providerId": it.providerId,
    "providerName": it.providerName,

    "weight": it.weight,
    "height": it.height,
    "width": it.width,
    "length": it.length,
    "ratio": it.ratio,
    "volume": it.volume(),

    "status": p.status,

    "x": p.x,
    "y": p.y,
    "z": p.z,
    "rotationY": p.rotationY,

    "dims": {"dx": p.dims[0], "dy": p.dims[1], "dz": p.dims[2]},
    "aabb": p.aabb,
    "corner": p.corner,
  }


def _unplaced_item_to_viewer(it: Item) -> Dict[str, Any]:
  return {
    "id": it.id,
    "dropContainerId": it.dropContainerId,
    "sscc": it.dropContainerId,

    "palletType": it.palletType,
    "palletTypeNorm": it.palletTypeNorm,
    "providerId": it.providerId,
    "providerName": it.providerName,

    "weight": it.weight,
    "height": it.height,
    "width": it.width,
    "length": it.length,
    "ratio": it.ratio,
    "volume": it.volume(),

    "status": it.status if it.status else "unplaced",
  }


def _compute_utilization(plan: PlanResult) -> Dict[str, Any]:
  v = plan.vehicle

  # геометрическая площадь/объём кузова
  floor_total_m2 = float(v["innerWidth"]) * float(v["innerLength"])
  vol_total_m3 = floor_total_m2 * float(v["innerHeight"])

  used_floor_m2 = 0.0
  used_vol_m3 = 0.0

  # спрос пола (ratio): паллетоместа по полу
  # стандарт: 1 паллетоместо = 1.0 м² (как у тебя в fallback ratio)
  fill_floor = float(v.get("fillFactorFloor", SETTINGS.FILL_FACTOR_FLOOR_DEFAULT))
  floor_capacity_demand = (floor_total_m2 * fill_floor) / 1.0

  used_floor_demand = 0.0
  for p in plan.placed:
    dx, dy, dz = p.dims
    used_floor_m2 += float(dx) * float(dz)
    used_vol_m3 += float(dx) * float(dy) * float(dz)

    it = p.item
    r = float(it.ratio) if getattr(it, "ratio", None) and float(it.ratio) > 0 else 1.0
    used_floor_demand += r

  return {
    "floor": {
      "usedM2": used_floor_m2,
      "totalM2": floor_total_m2,
      "util": (used_floor_m2 / floor_total_m2) if floor_total_m2 > 0 else None,
    },
    "volume": {
      "usedM3": used_vol_m3,
      "totalM3": vol_total_m3,
      "util": (used_vol_m3 / vol_total_m3) if vol_total_m3 > 0 else None,
    },
    "floorDemand": {
      "used": used_floor_demand,
      "capacity": floor_capacity_demand,
      "util": (used_floor_demand / floor_capacity_demand) if floor_capacity_demand > 0 else None,
      "unit": "pallet_places_by_floor",
      "standardM2": 1.0,
      "fillFactorFloor": fill_floor,
    },
  }


def plan_to_viewer_json(plan: PlanResult) -> Dict[str, Any]:
  placed = [_placed_item_to_viewer(p) for p in plan.placed]
  unplaced = [_unplaced_item_to_viewer(it) for it in plan.unplaced]

  debug_events = [{"evt": e.evt, "payload": e.payload} for e in plan.debug] if plan.debug else []

  util = _compute_utilization(plan)

  loads = plan.loads or {}
  aggregates = {
    "counts": {
      "placed": len(plan.placed),
      "unplaced": len(plan.unplaced),
    },
    "loads": loads,
    "utilization": util,
    "mode": {
      "mode": plan.mode.mode,
      "weightPressure": plan.mode.weight_pressure,
      "floorPressure": plan.mode.floor_pressure,
      "volumePressure": plan.mode.volume_pressure,
      "alpha": plan.mode.alpha,
    },
  }

  # ВАЖНО: viewer ждёт "pallets"
  pallets = placed + unplaced

  return {
    "taskId": plan.taskId,
    "transportType": plan.transportType,
    "vehicle": dict(plan.vehicle),

    # новый формат (оставляем)
    "placed": placed,
    "unplacedZone": unplaced,

    # совместимость со старым viewer
    "pallets": pallets,

    "debug": debug_events,
    "aggregates": aggregates,
  }



# -----------------------------------------------------------------------------
# Main service: fetch -> normalize -> solve -> viewer json
# -----------------------------------------------------------------------------

def pack_task_to_viewer_json(
  engine: Engine,
  task_id: str,
  debug_log: DebugLogFn = None,
) -> Dict[str, Any]:
  # 1) fetch
  rows = fetch_task_rows(engine, task_id)
  if debug_log:
    debug_log("fetch_rows", {"taskId": task_id, "rows": len(rows)})

  if not rows:
    # без строк вообще — считаем пустым планом
    vehicle = get_vehicle(None)
    empty_plan = solve([], vehicle, task_id=task_id, transport_type="UNKNOWN", debug_log=debug_log)
    return plan_to_viewer_json(empty_plan)

  # 2) transport type + vehicle
  transport_type = str(rows[0].get("transport_type") or "UNKNOWN")
  vehicle = get_vehicle(transport_type)

  # 3) normalize
  items: List[Item] = []
  bad = 0
  for r in rows:
    try:
      it = normalize_pallet(r)
      items.append(it)
    except Exception as exc:
      bad += 1
      if debug_log:
        debug_log("normalize_failed", {"taskId": task_id, "row": r, "error": f"{type(exc).__name__}: {exc}"})

  if debug_log:
    debug_log("normalize_done", {"taskId": task_id, "items": len(items), "bad": bad})

  # 4) solve (packer + optional reopt)
  plan = solve(items, vehicle, task_id=task_id, transport_type=transport_type, debug_log=debug_log)

  # 5) viewer json
  payload = plan_to_viewer_json(plan)
  if debug_log:
    debug_log("plan_ready", {
      "taskId": task_id,
      "placed": len(plan.placed),
      "unplaced": len(plan.unplaced),
      "mode": plan.mode.mode,
    })

  return payload
