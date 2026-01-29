# candidates/patterns.py
from __future__ import annotations

from typing import Dict, List, Tuple

from domain.types import Candidate, Item
from geometry.aabb import aabb_from_center
from geometry.free_rects import Rect


# =============================================================================
# ВАЖНО: selection policy (inside pattern)
# =============================================================================
# Цель:
# - ПАТТЕРН выбирается СНАРУЖИ packer-ом по антифрагментации (quality), а не по K.
# - ВНУТРИ паттерна мы хотим брать "самые жирные" паллеты.
#
# Ограничение: здесь нет compute_k(mode), поэтому "жирность" мы берем из ПОРЯДКА std_items/big_items,
# который приходит из generate_floor_candidates(state, window).
# window формируется из remaining, который уже отсортирован по K (ваша очередь).
#
# Поэтому:
# - НЕ сортируем тут по полям Item (не вводим ложный K)
# - Берем TOP-N первых элементов и строим несколько вариантов (fallback),
#   чтобы при коллизиях/осях/допусках дать шанс соседним по жирности.
#
# Настройки (простые, без завязок на settings):
MAX_PREFIX_STD = 14      # сколько верхних "жирных" std мы рассматриваем для вариативности
MAX_PREFIX_BIG = 10      # сколько верхних "жирных" big 140x120
MAX_VARIANTS_3 = 6       # максимум вариантов под 3across
MAX_VARIANTS_5 = 8       # максимум вариантов под 3plus2/zigzag
MAX_VARIANTS_140P80 = 20 # максимум вариантов под 140+80 на один rect+anchor


def _top(items: List[Item], n: int) -> List[Item]:
  if n <= 0:
    return []
  return items[: min(len(items), n)]


# =============================================================================
# Classification helpers
# =============================================================================

def is_std_80x120(it: Item, tol: float = 0.03) -> bool:
  w, l = float(it.width), float(it.length)
  a, b = 0.80, 1.20

  def close(x: float, y: float) -> bool:
    return abs(x - y) <= tol

  return (close(w, a) and close(l, b)) or (close(w, b) and close(l, a))


def is_140x120(it: Item, tol: float = 0.03) -> bool:
  w, l = float(it.width), float(it.length)
  a, b = 1.40, 1.20

  def close(x: float, y: float) -> bool:
    return abs(x - y) <= tol

  return (close(w, a) and close(l, b)) or (close(w, b) and close(l, a))


def _rot_for(it: Item, want_w: float, want_l: float) -> int:
  # rotationY так, чтобы dx≈want_w, dz≈want_l
  if abs(float(it.width) - want_w) <= 0.03 and abs(float(it.length) - want_l) <= 0.03:
    return 0
  return 90


# =============================================================================
# Candidate builder
# =============================================================================

def _build_candidate(it: Item, x: float, y: float, z: float, rot: int, kind: str, meta: Dict) -> Candidate:
  dx, dz = (float(it.width), float(it.length)) if rot == 0 else (float(it.length), float(it.width))
  dy = float(it.height)
  aabb = aabb_from_center(x, y + dy / 2.0, z, dx, dy, dz)

  meta2 = dict(meta or {})
  # Дебаг: позиция паллеты в "жирной" очереди окна (меньше = жирнее).
  # packer сможет это залогировать, если нужно.
  # (Если meta2 уже содержит kRank — не трогаем.)
  meta2.setdefault("kRank", None)

  return {
    "itemId": it.id,
    "x": x, "y": y, "z": z,
    "rotationY": rot,
    "dx": dx, "dy": dy, "dz": dz,
    "aabb": aabb,
    "kind": kind,
    "meta": meta2,
  }


# =============================================================================
# Варианты наборов "по жирности" без комбинаторики
# =============================================================================

def _variants_take3(items: List[Item]) -> List[Tuple[Item, Item, Item]]:
  """
  Возвращает несколько трио, начиная с самых "жирных" (по порядку списка).
  Без комбинаторного взрыва.
  """
  n = len(items)
  if n < 3:
    return []

  # базовый: 0,1,2
  idx_sets = [(0, 1, 2)]

  # запасные: обязательно держим 0 (самый жирный), меняем 3-ю позицию
  if n >= 4:
    idx_sets.append((0, 1, 3))
    idx_sets.append((0, 2, 3))
    idx_sets.append((1, 2, 3))

  if n >= 5:
    idx_sets.append((0, 1, 4))
    idx_sets.append((0, 2, 4))

  out: List[Tuple[Item, Item, Item]] = []
  seen = set()
  for a, b, c in idx_sets:
    if a < n and b < n and c < n:
      key = tuple(sorted((a, b, c)))
      if key in seen:
        continue
      seen.add(key)
      out.append((items[a], items[b], items[c]))
    if len(out) >= MAX_VARIANTS_3:
      break
  return out


def _variants_take5(items: List[Item]) -> List[Tuple[Item, Item, Item, Item, Item]]:
  """
  Несколько пятёрок, начиная с самых "жирных".
  Идея: базово берём топ-5, далее меняем 5-ю позицию и/или одну из середины.
  """
  n = len(items)
  if n < 5:
    return []

  idx_sets = [
    (0, 1, 2, 3, 4),
  ]

  # заменить "хвост" на более слабый, чтобы дать шанс пройти фильтры/геометрию
  if n >= 6:
    idx_sets.append((0, 1, 2, 3, 5))
    idx_sets.append((0, 1, 2, 4, 5))
    idx_sets.append((0, 1, 3, 4, 5))

  if n >= 7:
    idx_sets.append((0, 2, 3, 4, 5))
    idx_sets.append((1, 2, 3, 4, 5))
    idx_sets.append((0, 1, 2, 3, 6))
    idx_sets.append((0, 1, 2, 4, 6))

  out: List[Tuple[Item, Item, Item, Item, Item]] = []
  seen = set()
  for idxs in idx_sets:
    if all(i < n for i in idxs):
      key = tuple(sorted(idxs))
      if key in seen:
        continue
      seen.add(key)
      out.append(tuple(items[i] for i in idxs))  # type: ignore
    if len(out) >= MAX_VARIANTS_5:
      break
  return out


# -------------------------------------------------------------------------
# PATTERN: 3across (3*0.80 across X, Z slot = 1.20)
# -------------------------------------------------------------------------

PATTERN_3ACROSS_W = 2.40
PATTERN_3ACROSS_Z = 1.20


def gen_3across(rect: Rect, std_items: List[Item], *, z_anchor: float, pattern_id: str) -> List[List[Candidate]]:
  minX, maxX, minZ, maxZ = rect
  rect_w = maxX - minX
  rect_l = maxZ - minZ

  if rect_w + 1e-9 < PATTERN_3ACROSS_W or rect_l + 1e-9 < PATTERN_3ACROSS_Z:
    return []

  # std_items уже отсортирован по "жирности" через очередь -> window
  pool = _top(list(std_items), MAX_PREFIX_STD)
  if len(pool) < 3:
    return []

  z0 = z_anchor
  zc = z0 + PATTERN_3ACROSS_Z / 2.0
  y = 0.0

  out: List[List[Candidate]] = []

  for trio in _variants_take3(pool):
    pack: List[Candidate] = []
    ok = True

    for j, it in enumerate(trio):
      rot = _rot_for(it, 0.80, 1.20)
      dx, dz = (float(it.width), float(it.length)) if rot == 0 else (float(it.length), float(it.width))
      if dx > 0.86 or dz > 1.26:
        ok = False
        break

      x = minX + (j * 0.80) + dx / 2.0
      meta = {"pattern": "3across", "patternId": pattern_id, "rect": rect, "slotZ0": z0, "idx": j, "kRank": j}
      pack.append(_build_candidate(it, x, y, zc, rot, "pattern_3across", meta))

    if ok:
      out.append(pack)

  return out


# -------------------------------------------------------------------------
# PATTERN: 140plus80 (1.40x1.20 + 0.80x1.20 across X, Z slot = 1.20)
# ОРИЕНТАЦИЯ НЕ МЕНЯЕТСЯ: X = 2.20 (фикс)
# -------------------------------------------------------------------------

PATTERN_140P80_W = 2.20
PATTERN_140P80_Z = 1.20


def gen_140plus80(
  rect: Rect,
  big_items: List[Item],
  std_items: List[Item],
  *,
  z_anchor: float,
  pattern_id: str
) -> List[List[Candidate]]:
  minX, maxX, minZ, maxZ = rect
  rect_w = maxX - minX
  rect_l = maxZ - minZ

  if rect_w + 1e-9 < PATTERN_140P80_W or rect_l + 1e-9 < PATTERN_140P80_Z:
    return []

  big_pool = _top(list(big_items), MAX_PREFIX_BIG)
  std_pool = _top(list(std_items), MAX_PREFIX_STD)
  if not big_pool or not std_pool:
    return []

  z0 = z_anchor
  zc = z0 + PATTERN_140P80_Z / 2.0
  y = 0.0

  out: List[List[Candidate]] = []
  produced = 0

  # Внутри паттерна: пробуем самые жирные первые, но даём небольшой fallback.
  # 1) фиксируем биг как можно жирнее
  for bi_idx, bi in enumerate(big_pool):
    rot_b = _rot_for(bi, 1.40, 1.20)
    dx_b, dz_b = (float(bi.width), float(bi.length)) if rot_b == 0 else (float(bi.length), float(bi.width))
    if dx_b > 1.46 or dz_b > 1.26:
      continue

    # 2) к нему подбираем std как можно жирнее
    for si_idx, si in enumerate(std_pool):
      rot_s = _rot_for(si, 0.80, 1.20)
      dx_s, dz_s = (float(si.width), float(si.length)) if rot_s == 0 else (float(si.length), float(si.width))
      if dx_s > 0.86 or dz_s > 1.26:
        continue

      if (dx_b + dx_s) > rect_w + 1e-9:
        continue

      xb = minX + dx_b / 2.0
      xs = minX + dx_b + dx_s / 2.0

      meta_b = {"pattern": "140plus80", "patternId": pattern_id, "rect": rect, "slotZ0": z0, "role": "big", "kRank": bi_idx}
      meta_s = {"pattern": "140plus80", "patternId": pattern_id, "rect": rect, "slotZ0": z0, "role": "std", "kRank": si_idx}

      out.append([
        _build_candidate(bi, xb, y, zc, rot_b, "pattern_140plus80", meta_b),
        _build_candidate(si, xs, y, zc, rot_s, "pattern_140plus80", meta_s),
      ])

      produced += 1
      if produced >= MAX_VARIANTS_140P80:
        return out

  return out


# -------------------------------------------------------------------------
# PATTERN: 3plus2 (исходная ориентация, НЕ повернутая)
#  - Ряд 1: 3 по 0.80x1.20, Z = 1.20
#  - Ряд 2: 2 по 1.20x0.80 (поворот), Z = 0.80
#  Итого: W = 2.40, Z = 2.00
# -------------------------------------------------------------------------

PATTERN_3P2_W = 2.40
PATTERN_3P2_Z = 2.00


def gen_3plus2(rect: Rect, std_items: List[Item], *, z_anchor: float, pattern_id: str) -> List[List[Candidate]]:
  minX, maxX, minZ, maxZ = rect
  rect_w = maxX - minX
  rect_l = maxZ - minZ

  if rect_w + 1e-9 < PATTERN_3P2_W or rect_l + 1e-9 < PATTERN_3P2_Z:
    return []

  pool = _top(list(std_items), MAX_PREFIX_STD)
  if len(pool) < 5:
    return []

  z0 = z_anchor
  zc1 = z0 + 1.20 / 2.0

  z1 = z0 + 1.20
  zc2 = z1 + 0.80 / 2.0

  y = 0.0
  out: List[List[Candidate]] = []

  for five in _variants_take5(pool):
    row1 = five[:3]
    row2 = five[3:]

    pack: List[Candidate] = []
    ok = True

    # Row1: 3 across (0.80x1.20)
    for j, it in enumerate(row1):
      rot = _rot_for(it, 0.80, 1.20)
      dx, dz = (float(it.width), float(it.length)) if rot == 0 else (float(it.length), float(it.width))
      if dx > 0.86 or dz > 1.26:
        ok = False
        break
      x = minX + (j * 0.80) + dx / 2.0
      meta = {"pattern": "3plus2", "patternId": pattern_id, "rect": rect, "slotZ0": z0, "row": 1, "idx": j, "kRank": j}
      pack.append(_build_candidate(it, x, y, zc1, rot, "pattern_3plus2", meta))
    if not ok:
      continue

    # Row2: 2 across rotated (1.20x0.80)
    for j, it in enumerate(row2):
      rot = _rot_for(it, 1.20, 0.80)
      dx, dz = (float(it.width), float(it.length)) if rot == 0 else (float(it.length), float(it.width))
      if dx > 1.26 or dz > 0.86:
        ok = False
        break
      x = minX + (j * 1.20) + dx / 2.0
      meta = {"pattern": "3plus2", "patternId": pattern_id, "rect": rect, "slotZ0": z0, "row": 2, "idx": j, "kRank": 3 + j}
      pack.append(_build_candidate(it, x, y, zc2, rot, "pattern_3plus2", meta))

    if ok:
      out.append(pack)

  return out


# -------------------------------------------------------------------------
# PATTERN: zigzag (исходная ориентация, НЕ повернутая)
#  - Ряд 1: 2 по 1.20x0.80 (rot), Z=0.80
#  - Ряд 2: 3 по 0.80x1.20, Z=1.20
#  Итого: W=2.40, Z=2.00
# -------------------------------------------------------------------------

PATTERN_ZIGZAG_W = 2.40
PATTERN_ZIGZAG_Z = 2.00


def gen_zigzag(rect: Rect, std_items: List[Item], *, z_anchor: float, pattern_id: str) -> List[List[Candidate]]:
  minX, maxX, minZ, maxZ = rect
  rect_w = maxX - minX
  rect_l = maxZ - minZ

  if rect_w + 1e-9 < PATTERN_ZIGZAG_W or rect_l + 1e-9 < PATTERN_ZIGZAG_Z:
    return []

  pool = _top(list(std_items), MAX_PREFIX_STD)
  if len(pool) < 5:
    return []

  z0 = z_anchor
  zc1 = z0 + 0.80 / 2.0

  z1 = z0 + 0.80
  zc2 = z1 + 1.20 / 2.0

  y = 0.0
  out: List[List[Candidate]] = []

  for five in _variants_take5(pool):
    row1 = five[:2]
    row2 = five[2:]

    pack: List[Candidate] = []
    ok = True

    # Row1: 2 across rotated (1.20x0.80)
    for j, it in enumerate(row1):
      rot = _rot_for(it, 1.20, 0.80)
      dx, dz = (float(it.width), float(it.length)) if rot == 0 else (float(it.length), float(it.width))
      if dx > 1.26 or dz > 0.86:
        ok = False
        break
      x = minX + (j * 1.20) + dx / 2.0
      meta = {"pattern": "zigzag", "patternId": pattern_id, "rect": rect, "slotZ0": z0, "row": 1, "idx": j, "kRank": j}
      pack.append(_build_candidate(it, x, y, zc1, rot, "pattern_zigzag", meta))
    if not ok:
      continue

    # Row2: 3 across normal (0.80x1.20)
    for j, it in enumerate(row2):
      rot = _rot_for(it, 0.80, 1.20)
      dx, dz = (float(it.width), float(it.length)) if rot == 0 else (float(it.length), float(it.width))
      if dx > 0.86 or dz > 1.26:
        ok = False
        break
      x = minX + (j * 0.80) + dx / 2.0
      meta = {"pattern": "zigzag", "patternId": pattern_id, "rect": rect, "slotZ0": z0, "row": 2, "idx": j, "kRank": 2 + j}
      pack.append(_build_candidate(it, x, y, zc2, rot, "pattern_zigzag", meta))

    if ok:
      out.append(pack)

  return out
