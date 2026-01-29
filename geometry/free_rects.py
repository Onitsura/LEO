# geometry/free_rects.py
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from domain.types import Vehicle

Rect = Tuple[float, float, float, float]  # (minX, maxX, minZ, maxZ)


# ----------------------------
# Basic rect ops
# ----------------------------
def rect_area(r: Rect) -> float:
  return max(0.0, r[1] - r[0]) * max(0.0, r[3] - r[2])


def rect_contains(big: Rect, small: Rect, eps: float = 1e-9) -> bool:
  return (
    small[0] >= big[0] - eps and small[1] <= big[1] + eps and
    small[2] >= big[2] - eps and small[3] <= big[3] + eps
  )


def rect_intersects(a: Rect, b: Rect, eps: float = 1e-9) -> bool:
  if a[1] <= b[0] + eps or a[0] >= b[1] - eps:
    return False
  if a[3] <= b[2] + eps or a[2] >= b[3] - eps:
    return False
  return True


def split_rect(free: Rect, used: Rect, eps: float = 1e-9) -> List[Rect]:
  """
  Split a free rect by removing the intersecting area with `used`.
  NOTE: used is assumed axis-aligned in the same XZ plane.
  """
  fx0, fx1, fz0, fz1 = free
  ux0, ux1, uz0, uz1 = used

  out: List[Rect] = []

  # left strip
  if ux0 > fx0 + eps:
    out.append((fx0, min(ux0, fx1), fz0, fz1))
  # right strip
  if ux1 < fx1 - eps:
    out.append((max(ux1, fx0), fx1, fz0, fz1))
  # bottom strip (within intersection x-range)
  if uz0 > fz0 + eps:
    out.append((max(fx0, ux0), min(fx1, ux1), fz0, min(uz0, fz1)))
  # top strip (within intersection x-range)
  if uz1 < fz1 - eps:
    out.append((max(fx0, ux0), min(fx1, ux1), max(uz1, fz0), fz1))

  return [r for r in out if rect_area(r) > 1e-9]


def prune_contained(rects: List[Rect], eps: float = 1e-9) -> List[Rect]:
  """
  Remove rectangles that are fully contained in other rectangles.
  """
  out: List[Rect] = []
  for i, r in enumerate(rects):
    contained = False
    for j, other in enumerate(rects):
      if i == j:
        continue
      if rect_contains(other, r, eps=eps):
        contained = True
        break
    if not contained:
      out.append(r)
  return out


# ----------------------------
# Merging (snap / "схлопывание")
# ----------------------------
def _almost_equal(a: float, b: float, eps: float) -> bool:
  return abs(a - b) <= eps


def _normalize_rect(r: Rect, eps: float) -> Rect:
  """
  Normalize tiny negative zeros / tiny eps drift.
  """
  x0, x1, z0, z1 = r
  if x1 < x0:
    x0, x1 = x1, x0
  if z1 < z0:
    z0, z1 = z1, z0
  # clamp tiny widths/heights
  if abs(x0) < eps:
    x0 = 0.0
  if abs(x1) < eps:
    x1 = 0.0
  if abs(z0) < eps:
    z0 = 0.0
  if abs(z1) < eps:
    z1 = 0.0
  return (x0, x1, z0, z1)


def merge_adjacent(rects: List[Rect], eps: float = 1e-6, max_iters: int = 50) -> List[Rect]:
  """
  Merge rectangles that are adjacent (share a full edge) to reduce fragmentation.

  Two merge rules:
  1) Merge along X if (z0,z1) are equal (within eps) and x edges touch/overlap:
     (x0,x1,z0,z1) + (x1,x2,z0,z1) -> (x0,x2,z0,z1)
  2) Merge along Z if (x0,x1) are equal (within eps) and z edges touch/overlap:
     (x0,x1,z0,z1) + (x0,x1,z1,z2) -> (x0,x1,z0,z2)

  We also allow tiny overlaps/gaps within eps.
  """
  if not rects:
    return []

  cur = [_normalize_rect(r, eps) for r in rects if rect_area(r) > 1e-9]

  # Small helper: attempt to merge two rects, return merged or None
  def try_merge(a: Rect, b: Rect) -> Rect | None:
    ax0, ax1, az0, az1 = a
    bx0, bx1, bz0, bz1 = b

    # Merge along X: same Z-span
    if _almost_equal(az0, bz0, eps) and _almost_equal(az1, bz1, eps):
      # If they touch/overlap in X
      if (ax1 >= bx0 - eps and bx1 >= ax0 - eps):
        nx0 = min(ax0, bx0)
        nx1 = max(ax1, bx1)
        return (nx0, nx1, az0, az1)

    # Merge along Z: same X-span
    if _almost_equal(ax0, bx0, eps) and _almost_equal(ax1, bx1, eps):
      # If they touch/overlap in Z
      if (az1 >= bz0 - eps and bz1 >= az0 - eps):
        nz0 = min(az0, bz0)
        nz1 = max(az1, bz1)
        return (ax0, ax1, nz0, nz1)

    return None

  # Iterate until no merges occur (fixpoint), with safety cap
  for _ in range(max_iters):
    merged_any = False
    used = [False] * len(cur)
    nxt: List[Rect] = []

    for i in range(len(cur)):
      if used[i]:
        continue
      a = cur[i]
      merged = a
      changed = True

      # Greedy: keep merging `merged` with any compatible rect
      while changed:
        changed = False
        for j in range(len(cur)):
          if i == j or used[j]:
            continue
          b = cur[j]
          m = try_merge(merged, b)
          if m is not None:
            merged = _normalize_rect(m, eps)
            used[j] = True
            merged_any = True
            changed = True

      used[i] = True
      nxt.append(merged)

    # Remove contained after merge and normalize
    nxt = prune_contained(nxt, eps=eps)
    nxt = [_normalize_rect(r, eps) for r in nxt if rect_area(r) > 1e-9]

    cur = nxt
    if not merged_any:
      break

  return cur


# ----------------------------
# FreeRects container
# ----------------------------
@dataclass
class FreeRects:
  rects: List[Rect]

  @classmethod
  def init_for_vehicle(cls, vehicle: Vehicle) -> "FreeRects":
    half_w = float(vehicle["innerWidth"]) / 2.0
    half_l = float(vehicle["innerLength"]) / 2.0
    return cls(rects=[(-half_w, half_w, -half_l, half_l)])

  def list(self) -> List[Rect]:
    return list(self.rects)

  def reserve(self, used: Rect) -> None:
    """
    Remove `used` area from the free rectangles set.
    IMPORTANT: `used` must be in the same XZ coordinate system (centered vehicle).
    """
    new_rects: List[Rect] = []
    for r in self.rects:
      if not rect_intersects(r, used):
        new_rects.append(r)
      else:
        new_rects.extend(split_rect(r, used))

    # 1) drop contained
    new_rects = prune_contained(new_rects)

    # 2) merge adjacent to reduce fragmentation ("схлопывание")
    new_rects = merge_adjacent(new_rects, eps=1e-6)

    self.rects = new_rects
