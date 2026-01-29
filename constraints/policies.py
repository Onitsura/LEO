# constraints/policies.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from domain.types import Candidate, Item, ModeDecision, Vehicle
from catalogs.item import item_class
from settings import SETTINGS


# -----------------------------------------------------------------------------
# Helpers: settings access
# -----------------------------------------------------------------------------

def _get_setting(settings, name: str, default):
  """
  Унифицированный доступ к настройкам, чтобы поддержать и объект SETTINGS, и dict.
  """
  if settings is None:
    return default
  if isinstance(settings, dict):
    return settings.get(name, default)
  return getattr(settings, name, default)


# -----------------------------------------------------------------------------
# Зонирование по длине (A/B/C/D)
# -----------------------------------------------------------------------------
# Координаты solver/viewer:
# - Z: вдоль кузова, центр в 0, диапазон [-L/2 .. L/2]
# - "голова" = -L/2, "хвост" = +L/2
#
# Для zoning используем x_from_head = z_center + L/2 => [0 .. L]
# -----------------------------------------------------------------------------

ZoneName = str  # "A" | "B" | "C" | "D"


@dataclass(frozen=True)
class ZoneConfig:
  # доли длины кузова (сумма = 1.0)
  a: float = 0.25
  b: float = 0.25
  c: float = 0.25
  d: float = 0.25


DEFAULT_ZONES = ZoneConfig()


def x_from_head(z_center: float, vehicle: Vehicle) -> float:
  L = float(vehicle["innerLength"])
  return float(z_center) + (L / 2.0)


def zone_for_z(z_center: float, vehicle: Vehicle, cfg: ZoneConfig = DEFAULT_ZONES) -> ZoneName:
  L = float(vehicle["innerLength"])
  x = x_from_head(z_center, vehicle)
  if x < 0.0:
    x = 0.0
  if x > L:
    x = L

  a_end = L * cfg.a
  b_end = a_end + L * cfg.b
  c_end = b_end + L * cfg.c

  if x <= a_end:
    return "A"
  if x <= b_end:
    return "B"
  if x <= c_end:
    return "C"
  return "D"


# -----------------------------------------------------------------------------
# Policy: очередность + предпочтения зон (soft) + hard-запреты (минимально)
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyDecision:
  # Список reasons для hard reject (если не пустой => запрещено)
  hard_reject_reasons: List[str]

  # Штраф (>=0): добавляется в objective как минус/penalty
  zone_penalty: float

  # Бонус (>=0): добавляется в objective как плюс
  zone_bonus: float

  # Теги (для debug)
  tags: Dict[str, str]


def _zones_from_settings(settings) -> ZoneConfig:
  """
  SETTINGS.POLICY_ZONES может быть:
  - ZoneConfig
  - dict {"a":..,"b":..,"c":..,"d":..}
  - None (тогда DEFAULT_ZONES)
  """
  z = _get_setting(settings, "POLICY_ZONES", None)
  if z is None:
    return DEFAULT_ZONES
  if isinstance(z, ZoneConfig):
    return z
  if isinstance(z, dict):
    return ZoneConfig(
      a=float(z.get("a", DEFAULT_ZONES.a)),
      b=float(z.get("b", DEFAULT_ZONES.b)),
      c=float(z.get("c", DEFAULT_ZONES.c)),
      d=float(z.get("d", DEFAULT_ZONES.d)),
    )
  return DEFAULT_ZONES


def _is_high_value(item: Item, mode: ModeDecision, settings=SETTINGS) -> bool:
  """
  ВАЖНО: ratio = floor demand (паллетомест по полу), его нельзя использовать как делитель.
  High-value здесь — простая эвристика "тяжёлое/объёмное".

  Настройки:
  - POLICY_HI_WEIGHT_ABS: кг для mode=weight
  - POLICY_HI_VOL_ABS: м3 для mode=volume
  - POLICY_HI_WEIGHT_ABS_MIXED: кг для mode=mixed
  """
  thr_w = float(_get_setting(settings, "POLICY_HI_WEIGHT_ABS", 700.0))
  thr_vol = float(_get_setting(settings, "POLICY_HI_VOL_ABS", 1.0))
  thr_mixed_w = float(_get_setting(settings, "POLICY_HI_WEIGHT_ABS_MIXED", thr_w))

  w = max(0.0, float(item.weight))
  vol = max(0.0, float(item.width)) * max(0.0, float(item.length)) * max(0.0, float(item.height))

  if mode.mode == "weight":
    return w >= thr_w

  if mode.mode == "volume":
    return vol >= thr_vol

  # mixed
  return w >= thr_mixed_w


def evaluate_candidate_policy(
  item: Item,
  candidate: Candidate,
  vehicle: Vehicle,
  mode: ModeDecision,
  *,
  settings=SETTINGS,
  allow_hard_rules: bool = False,
) -> PolicyDecision:
  """
  Возвращает soft penalties/bonuses + (опционально) hard reject.
  """
  z = float(candidate["z"])
  zone_cfg = _zones_from_settings(settings)
  zone = zone_for_z(z, vehicle, cfg=zone_cfg)

  cls = item_class(item, vehicle_inner_width=float(vehicle["innerWidth"]))
  hi = _is_high_value(item, mode, settings=settings)

  hard: List[str] = []
  penalty = 0.0
  bonus = 0.0

  # -------------------------
  # Коэффициенты (settings)
  # -------------------------
  # Weight mode
  W_HI_AB_BONUS = float(_get_setting(settings, "POLICY_W_HI_AB_BONUS", 2.0))
  W_HI_CD_PENALTY = float(_get_setting(settings, "POLICY_W_HI_CD_PENALTY", 3.0))
  W_LO_CD_BONUS = float(_get_setting(settings, "POLICY_W_LO_CD_BONUS", 0.5))
  W_LO_AB_PENALTY = float(_get_setting(settings, "POLICY_W_LO_AB_PENALTY", 0.5))

  # Volume mode
  V_BIG_ABC_BONUS = float(_get_setting(settings, "POLICY_V_BIG_ABC_BONUS", 1.0))
  V_BIG_D_PENALTY = float(_get_setting(settings, "POLICY_V_BIG_D_PENALTY", 2.0))
  V_SMALL_CD_BONUS = float(_get_setting(settings, "POLICY_V_SMALL_CD_BONUS", 0.5))

  BIG_FOOTPRINT_M2 = float(_get_setting(settings, "POLICY_BIG_FOOTPRINT_M2", 1.6))

  # Mixed mode
  M_HI_AB_BONUS = float(_get_setting(settings, "POLICY_M_HI_AB_BONUS", 1.5))
  M_LO_AB_PENALTY = float(_get_setting(settings, "POLICY_M_LO_AB_PENALTY", 0.5))

  # Class guidance
  OVERSIZE_BONUS = float(_get_setting(settings, "POLICY_OVERSIZE_BONUS", 0.8))
  BOX_AB_PENALTY = float(_get_setting(settings, "POLICY_BOX_AB_PENALTY", 0.7))
  BOX_CD_BONUS = float(_get_setting(settings, "POLICY_BOX_CD_BONUS", 1.5))

  # Hard rules toggles / specifics
  HARD_OVERSIZE_IN_D = bool(_get_setting(settings, "POLICY_HARD_OVERSIZE_IN_D", False))

  # -------------------------
  # Guidance по зонам
  # -------------------------
  if mode.mode == "weight":
    if hi:
      if zone in ("A", "B"):
        bonus += W_HI_AB_BONUS
      else:
        penalty += W_HI_CD_PENALTY
    else:
      if zone in ("C", "D"):
        bonus += W_LO_CD_BONUS
      else:
        penalty += W_LO_AB_PENALTY

  elif mode.mode == "volume":
    big_footprint = (float(item.width) * float(item.length)) >= BIG_FOOTPRINT_M2
    if big_footprint:
      if zone in ("A", "B", "C"):
        bonus += V_BIG_ABC_BONUS
      else:
        penalty += V_BIG_D_PENALTY
    else:
      if zone in ("C", "D"):
        bonus += V_SMALL_CD_BONUS

  else:
    if hi and zone in ("A", "B"):
      bonus += M_HI_AB_BONUS
    if (not hi) and zone in ("A", "B"):
      penalty += M_LO_AB_PENALTY

  # -------------------------
  # Очередность типов (как предпочтение, не запрет)
  # -------------------------
  if cls == "oversize":
    bonus += OVERSIZE_BONUS

  if cls == "box":
    if zone in ("A", "B"):
      penalty += BOX_AB_PENALTY
    else:
      bonus += BOX_CD_BONUS


  # -------------------------
  # Hard rules (по умолчанию выключены)
  # -------------------------
  if allow_hard_rules:
    if HARD_OVERSIZE_IN_D and cls == "oversize" and zone == "D":
      hard.append("oversize_in_D")

  return PolicyDecision(
    hard_reject_reasons=hard,
    zone_penalty=penalty,
    zone_bonus=bonus,
    tags={
      "zone": zone,
      "class": cls,
      "hi": "1" if hi else "0",
      "mode": mode.mode,
    },
  )


# -----------------------------------------------------------------------------
# Policy: порядок очереди (до генерации кандидатов)
# -----------------------------------------------------------------------------

# Чем меньше число — тем раньше в очереди
CLASS_PRIORITY_DEFAULT: Dict[str, int] = {
  "oversize": 0,
  "standard": 1,
  "other": 2,
  "box": 3,
}


def sort_key_for_queue(item: Item, vehicle: Vehicle, mode: ModeDecision, settings=SETTINGS) -> Tuple[int, float]:
  """
  Возвращает ключ сортировки:
  1) класс (oversize раньше)
  2) K (по режиму) по убыванию => в ключе берём -K

  ВАЖНО: ratio = floor demand, поэтому оно ДОЛЖНО увеличивать приоритет,
  а не уменьшать. Никаких делений на ratio.
  """
  cls = item_class(item, vehicle_inner_width=float(vehicle["innerWidth"]))

  class_priority = _get_setting(settings, "POLICY_CLASS_PRIORITY", None)
  if isinstance(class_priority, dict):
    pr = int(class_priority.get(cls, 99))
  else:
    pr = CLASS_PRIORITY_DEFAULT.get(cls, 99)

  r = float(item.ratio) if item.ratio and float(item.ratio) > 0 else 1.0

  w = max(0.0, float(item.weight))
  vol = max(0.0, float(item.width)) * max(0.0, float(item.length)) * max(0.0, float(item.height))

  if mode.mode == "weight":
    k = w * r
  elif mode.mode == "volume":
    k = vol * r
  else:
    alpha = float(mode.alpha) if mode.alpha is not None else 0.5
    k = alpha * (w * r) + (1.0 - alpha) * (vol * r)

  return (pr, -k)
