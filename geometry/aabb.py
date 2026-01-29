# geometry/aabb.py
from __future__ import annotations

from typing import Iterable

from domain.types import AABB, PlacedItem, Vehicle


def aabb_from_center(x: float, y: float, z: float, dx: float, dy: float, dz: float) -> AABB:
  return {
    "minX": x - dx / 2.0, "maxX": x + dx / 2.0,
    "minY": y - dy / 2.0, "maxY": y + dy / 2.0,
    "minZ": z - dz / 2.0, "maxZ": z + dz / 2.0,
  }


def aabb_intersects(a: AABB, b: AABB, eps: float = 1e-9) -> bool:
  if a["maxX"] <= b["minX"] + eps or a["minX"] >= b["maxX"] - eps:
    return False
  if a["maxY"] <= b["minY"] + eps or a["minY"] >= b["maxY"] - eps:
    return False
  if a["maxZ"] <= b["minZ"] + eps or a["minZ"] >= b["maxZ"] - eps:
    return False
  return True


def oob_check(aabb: AABB, vehicle: Vehicle, eps: float = 1e-9) -> bool:
  half_w = float(vehicle["innerWidth"]) / 2.0
  half_l = float(vehicle["innerLength"]) / 2.0
  inner_h = float(vehicle["innerHeight"])

  if aabb["minX"] < -half_w - eps or aabb["maxX"] > half_w + eps:
    return True
  if aabb["minZ"] < -half_l - eps or aabb["maxZ"] > half_l + eps:
    return True
  if aabb["minY"] < 0.0 - eps or aabb["maxY"] > inner_h + eps:
    return True
  return False


def collides_with_any(aabb: AABB, placed: Iterable[PlacedItem], eps: float = 1e-9) -> bool:
  for p in placed:
    if aabb_intersects(aabb, p.aabb, eps=eps):
      return True
  return False
