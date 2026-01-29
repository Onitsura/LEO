# candidates/generators.py
from __future__ import annotations

from typing import List, Tuple

from domain.types import Candidate, Item
from geometry.aabb import aabb_from_center
from geometry.free_rects import Rect, rect_area

from candidates.patterns import (
  gen_140plus80,
  gen_3across,
  gen_3plus2,
  gen_zigzag,
  is_140x120,
  is_std_80x120,
  PATTERN_140P80_Z,
  PATTERN_3ACROSS_Z,
  PATTERN_3P2_Z,
  PATTERN_ZIGZAG_Z,
)


def _anchors_for_rect(r: Rect, dx: float, dz: float) -> List[Tuple[float, float]]:
  minX, maxX, minZ, maxZ = r
  x0 = minX
  x1 = maxX - dx
  z0 = minZ
  z1 = maxZ - dz

  if x1 < x0 - 1e-9 or z1 < z0 - 1e-9:
    return []

  pts = [(x0, z0), (x1, z0), (x0, z1), (x1, z1)]
  uniq: List[Tuple[float, float]] = []
  seen = set()
  for x, z in pts:
    k = (round(x, 6), round(z, 6))
    if k in seen:
      continue
    seen.add(k)
    uniq.append((x, z))
  return uniq


def _z_anchors_for_len(rect: Rect, slot_len: float) -> List[float]:
  minX, maxX, minZ, maxZ = rect
  if (maxZ - minZ) + 1e-9 < slot_len:
    return []
  # два якоря: прижать к началу и к концу прямоугольника
  return [minZ, maxZ - slot_len]


def _assign_pattern_id(pack: List[Candidate], pid: str) -> None:
  """
  ВАЖНО: patternId должен быть уникальным на КАЖДЫЙ pack (группу),
  иначе _group_pattern_candidates() склеит альтернативные варианты в одну группу,
  и они начнут пересекаться между собой (pattern_internal_collision).
  """
  for c in pack:
    meta = c.get("meta")
    if meta is None:
      meta = {}
      c["meta"] = meta
    meta["patternId"] = pid


def generate_floor_candidates(state, items_subset: List[Item]) -> List[Candidate]:
  out: List[Candidate] = []

  rects = sorted(state.free_rects.list(), key=rect_area, reverse=True)[:250]

  std_items = [it for it in items_subset if is_std_80x120(it)]
  big_140 = [it for it in items_subset if is_140x120(it)]

  # -------------------------
  # PATTERNS (batched by patternId)
  # -------------------------
  pattern_seq = 0
  for r in rects:
    # 3across
    for z0 in _z_anchors_for_len(r, PATTERN_3ACROSS_Z):
      for pack in gen_3across(r, std_items, z_anchor=z0, pattern_id="scan"):
        pid = f"p{pattern_seq}"
        pattern_seq += 1
        _assign_pattern_id(pack, pid)
        out.extend(pack)

    # 140plus80
    for z0 in _z_anchors_for_len(r, PATTERN_140P80_Z):
      for pack in gen_140plus80(r, big_140, std_items, z_anchor=z0, pattern_id="scan"):
        pid = f"p{pattern_seq}"
        pattern_seq += 1
        _assign_pattern_id(pack, pid)
        out.extend(pack)

    # 3plus2
    for z0 in _z_anchors_for_len(r, PATTERN_3P2_Z):
      for pack in gen_3plus2(r, std_items, z_anchor=z0, pattern_id="scan"):
        pid = f"p{pattern_seq}"
        pattern_seq += 1
        _assign_pattern_id(pack, pid)
        out.extend(pack)

    # zigzag
    for z0 in _z_anchors_for_len(r, PATTERN_ZIGZAG_Z):
      for pack in gen_zigzag(r, std_items, z_anchor=z0, pattern_id="scan"):
        pid = f"p{pattern_seq}"
        pattern_seq += 1
        _assign_pattern_id(pack, pid)
        out.extend(pack)

  # -------------------------
  # SINGLE (anchor placements)
  # -------------------------
  for it in items_subset:
    for rot in (0, 90):
      dx, dz = (float(it.width), float(it.length)) if rot == 0 else (float(it.length), float(it.width))
      dy = float(it.height)

      for r in rects:
        minX, maxX, minZ, maxZ = r
        if (maxX - minX) + 1e-9 < dx:
          continue
        if (maxZ - minZ) + 1e-9 < dz:
          continue

        for (ax, az) in _anchors_for_rect(r, dx, dz):
          x = ax + dx / 2.0
          z = az + dz / 2.0
          y = 0.0
          aabb = aabb_from_center(x, y + dy / 2.0, z, dx, dy, dz)

          out.append({
            "itemId": it.id,
            "x": x, "y": y, "z": z,
            "rotationY": rot,
            "dx": dx, "dy": dy, "dz": dz,
            "aabb": aabb,
            "kind": "single",
            "meta": {"rect": r, "anchor": (ax, az)},
          })

  return out
