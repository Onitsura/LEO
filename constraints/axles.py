# constraints/axles.py
from __future__ import annotations

from typing import List, Tuple

from domain.types import AxleLoads, Candidate, PlacedItem, Vehicle
from catalogs.placed_item import placed_from_candidate


def compute_loads(placed: List[PlacedItem], vehicle: Vehicle) -> AxleLoads:
  total = 0.0
  for p in placed:
    total += float(p.item.weight)

  loads: AxleLoads = {"payload_kg": total}

  a_pos = vehicle.get("axleAPosFromHeadM")
  b_pos = vehicle.get("axleBPosFromHeadM")
  a_lim = vehicle.get("axleALimitKg")
  b_lim = vehicle.get("axleBLimitKg")

  # если нет осевой модели — просто payload
  if a_pos is None or b_pos is None or abs(float(b_pos) - float(a_pos)) < 1e-9:
    loads["axleA_kg"] = 0.0
    loads["axleB_kg"] = 0.0
    return loads

  L = float(vehicle["innerLength"])
  z0 = -L / 2.0
  span = float(b_pos) - float(a_pos)

  axleA = 0.0
  axleB = 0.0

  for p in placed:
    w = float(p.item.weight)
    x_from_head = float(p.z) - z0  # z0 = -L/2 => x_from_head = z + L/2

    rb = w * (x_from_head - float(a_pos)) / span
    ra = w - rb
    axleA += ra
    axleB += rb

  loads["axleA_kg"] = axleA
  loads["axleB_kg"] = axleB
  return loads


def check_loads(loads: AxleLoads, vehicle: Vehicle) -> Tuple[bool, List[str]]:
  reasons: List[str] = []

  payload_max = vehicle.get("payloadMaxKg")
  if payload_max is not None and float(loads.get("payload_kg", 0.0)) > float(payload_max) + 1e-9:
    reasons.append("payload_limit")

  a_lim = vehicle.get("axleALimitKg")
  b_lim = vehicle.get("axleBLimitKg")

  if a_lim is not None and float(loads.get("axleA_kg", 0.0)) > float(a_lim) + 1e-9:
    reasons.append("axleA_limit")
  if b_lim is not None and float(loads.get("axleB_kg", 0.0)) > float(b_lim) + 1e-9:
    reasons.append("axleB_limit")

  return (len(reasons) == 0, reasons)


def would_pass_with_candidate(
  placed: List[PlacedItem],
  candidate: Candidate,
  item,
  vehicle: Vehicle,
) -> Tuple[bool, List[str], AxleLoads]:
  tmp = placed + [placed_from_candidate(candidate, item=item)]
  loads = compute_loads(tmp, vehicle)
  ok, reasons = check_loads(loads, vehicle)
  return ok, reasons, loads
