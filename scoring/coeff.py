# scoring/coeff.py
from __future__ import annotations

from typing import List

from domain.types import Item, ModeDecision, Vehicle
from settings import SETTINGS


def detect_mode(items: List[Item], vehicle: Vehicle) -> ModeDecision:
  eps = float(SETTINGS.EPS)

  if not items:
    return ModeDecision("mixed", 0.0, 0.0, 0.0, 0.5)

  total_weight = 0.0
  total_volume = 0.0
  total_floor_demand = 0.0  # в "стандартных паллетоместах"

  for i in items:
    w = max(0.0, float(i.width))
    l = max(0.0, float(i.length))
    h = max(0.0, float(i.height))

    total_weight += max(0.0, float(i.weight))
    total_volume += w * l * h

    # ratio = floor demand (паллетомест по полу), увеличивает давление на пол
    r = float(i.ratio) if i.ratio and float(i.ratio) > 0 else 1.0
    total_floor_demand += r

  payload_max = vehicle.get("payloadMaxKg")
  weight_capacity = float(payload_max) if payload_max is not None else max(total_weight, 1.0)

  fill_floor = float(vehicle.get("fillFactorFloor", SETTINGS.FILL_FACTOR_FLOOR_DEFAULT))
  fill_vol = float(vehicle.get("fillFactorVolume", SETTINGS.FILL_FACTOR_VOLUME_DEFAULT))

  # floor_capacity тут исторически считался в м², но теперь total_floor_demand в "паллетоместах".
  # Чтобы не ломать модель, считаем "ёмкость пола" тоже в паллетоместах:
  # 1 паллетоместо = 1.0 м² (как ты задал для fallback ratio).
  floor_capacity_m2 = (float(vehicle["innerWidth"]) * float(vehicle["innerLength"])) * fill_floor
  floor_capacity = floor_capacity_m2 / 1.0

  vol_capacity = (float(vehicle["innerWidth"]) * float(vehicle["innerLength"]) * float(vehicle["innerHeight"])) * fill_vol

  weight_pressure = total_weight / max(weight_capacity, eps)
  floor_pressure = total_floor_demand / max(floor_capacity, eps)
  volume_pressure = total_volume / max(vol_capacity, eps)

  thr = float(SETTINGS.MODE_PRESSURE_THRESHOLD)

  if weight_pressure >= thr and floor_pressure < thr:
    return ModeDecision("weight", weight_pressure, floor_pressure, volume_pressure, None)
  if floor_pressure >= thr and weight_pressure < thr:
    # исторически называлось "volume", но по факту это режим давления пола/объёма.
    return ModeDecision("volume", weight_pressure, floor_pressure, volume_pressure, None)

  raw = (weight_pressure - floor_pressure + 1.0) / 2.0
  alpha = min(0.8, max(0.2, raw))
  return ModeDecision("mixed", weight_pressure, floor_pressure, volume_pressure, alpha)


def compute_k(item: Item, mode: ModeDecision) -> float:
  # ratio = floor demand => повышает "ценность" (приоритет) груза
  r = float(item.ratio) if item.ratio and float(item.ratio) > 0 else 1.0

  w = max(0.0, float(item.weight))
  vol = max(0.0, float(item.width)) * max(0.0, float(item.length)) * max(0.0, float(item.height))

  if mode.mode == "weight":
    return w * r

  if mode.mode == "volume":
    return vol * r

  alpha = float(mode.alpha) if mode.alpha is not None else 0.5
  return alpha * (w * r) + (1.0 - alpha) * (vol * r)
