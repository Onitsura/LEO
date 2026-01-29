# catalogs/item.py
from __future__ import annotations

from typing import Optional, Tuple

from domain.types import Item


# ----------------------------
# Размерные хелперы
# ----------------------------

def dims_xy(item: Item, rotationY: int = 0) -> Tuple[float, float]:
  """
  Возвращает (dx, dz) для пола (x,z) в метрах.
  rotationY: 0 или 90.
  """
  if rotationY % 180 == 90:
    return (float(item.length), float(item.width))
  return (float(item.width), float(item.length))


def footprint_m2(item: Item) -> float:
  return float(item.width) * float(item.length)


def volume_m3(item: Item) -> float:
  return float(item.width) * float(item.length) * float(item.height)


# ----------------------------
# Классификаторы типов груза
# ----------------------------

def is_box_like(item: Item) -> bool:
  """
  Короб/тарное место: ориентируемся по palletType/palletTypeNorm и габаритам.
  Это эвристика для MVP.
  """
  pt = (item.palletType or "").upper()
  ptn = (item.palletTypeNorm or "").upper()

  # Явные BOX
  if "BOX" in pt or "BOX" in ptn:
    return True

  # Очень маленькая площадь — скорее короб/нестандарт
  if footprint_m2(item) <= 0.40 * 0.40:
    return True

  # Высокое и узкое (условно): часто короб/упаковка на поддоне неясного типа
  if item.height >= 1.6 and min(item.width, item.length) <= 0.6:
    return True

  return False


def is_standard_80x120(item: Item, tol_m: float = 0.03) -> bool:
  """
  Стандарт EUR-паллета 0.80 x 1.20 (с допуском).
  Проверяем обе ориентации.
  """
  w, l = float(item.width), float(item.length)
  a, b = (0.80, 1.20)

  def _close(x: float, y: float) -> bool:
    return abs(x - y) <= tol_m

  return (_close(w, a) and _close(l, b)) or (_close(w, b) and _close(l, a))


def is_fin_100x120(item: Item, tol_m: float = 0.03) -> bool:
  w, l = float(item.width), float(item.length)
  a, b = (1.00, 1.20)

  def _close(x: float, y: float) -> bool:
    return abs(x - y) <= tol_m

  return (_close(w, a) and _close(l, b)) or (_close(w, b) and _close(l, a))


def is_square_120(item: Item, tol_m: float = 0.03) -> bool:
  w, l = float(item.width), float(item.length)
  return abs(w - 1.20) <= tol_m and abs(l - 1.20) <= tol_m


def is_oversize(item: Item, vehicle_inner_width: Optional[float] = None, tol_m: float = 0.01) -> bool:
  """
  Негабарит по полу:
  - либо ширина/длина существенно больше типовых,
  - либо ширина близка/больше ширины кузова (если задано).
  """
  w, l = float(item.width), float(item.length)

  # Явный сверх-типовой размер (эвристика)
  if max(w, l) >= 1.60 + tol_m:
    return True

  # Очень длинный (роллы/плашки)
  if max(w, l) >= 2.40 + tol_m:
    return True

  # Почти в ширину кузова
  if vehicle_inner_width is not None:
    if w >= vehicle_inner_width - 0.02 or l >= vehicle_inner_width - 0.02:
      return True

  return False


# ----------------------------
# Приоритетные группы (для policies/packer)
# ----------------------------

def item_class(item: Item, vehicle_inner_width: Optional[float] = None) -> str:
  """
  Возвращает класс для очереди:
  - oversize
  - standard
  - box
  - other
  """
  if is_oversize(item, vehicle_inner_width=vehicle_inner_width):
    return "oversize"
  if is_standard_80x120(item) or is_fin_100x120(item) or is_square_120(item):
    return "standard"
  if is_box_like(item):
    return "box"
  return "other"
