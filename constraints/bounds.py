# constraints/bounds.py
from __future__ import annotations

from typing import List, Tuple

from domain.types import Candidate, PlacedItem, Vehicle
from geometry.aabb import collides_with_any, oob_check


def check_oob(candidate: Candidate, vehicle: Vehicle) -> Tuple[bool, List[str]]:
  if oob_check(candidate["aabb"], vehicle):
    return (False, ["oob"])
  return (True, [])


def check_collision(candidate: Candidate, placed: List[PlacedItem]) -> Tuple[bool, List[str]]:
  if collides_with_any(candidate["aabb"], placed):
    return (False, ["collision"])
  return (True, [])
