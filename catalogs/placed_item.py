# catalogs/placed_item.py
from __future__ import annotations

from typing import Dict

from domain.types import Candidate, Item, PlacedItem
from geometry.aabb import aabb_from_center


def from_item_at_pose(item: Item, x: float, y: float, z: float, rotationY: int) -> PlacedItem:
  if rotationY % 180 == 90:
    dx, dz = float(item.length), float(item.width)
  else:
    dx, dz = float(item.width), float(item.length)
  dy = float(item.height)

  aabb = aabb_from_center(x, y + dy / 2.0, z, dx, dy, dz)
  corner: Dict[str, float] = {"x": aabb["minX"], "z": aabb["minZ"]}

  return PlacedItem(
    item=item,
    x=x, y=y, z=z,
    rotationY=rotationY,
    dims=(dx, dy, dz),
    aabb=aabb,
    corner=corner,
    status=item.status,
  )


def placed_from_candidate(candidate: Candidate, item: Item) -> PlacedItem:
  aabb = candidate["aabb"]
  corner: Dict[str, float] = {"x": aabb["minX"], "z": aabb["minZ"]}
  return PlacedItem(
    item=item,
    x=float(candidate["x"]), y=float(candidate["y"]), z=float(candidate["z"]),
    rotationY=int(candidate["rotationY"]),
    dims=(float(candidate["dx"]), float(candidate["dy"]), float(candidate["dz"])),
    aabb=aabb,
    corner=corner,
    status=item.status,
  )
