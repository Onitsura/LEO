# services/normalize.py
from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

from catalogs.packaging_catalog import TARA_CATALOG_CM
from domain.types import Item


def normalize_code_key(s: Optional[str]) -> str:
  if not s:
    return ""
  return s.strip().upper().replace("Х", "X")


def lookup_tara_by_code(code: Optional[str]) -> Optional[Dict[str, float]]:
  k = normalize_code_key(code)
  if not k:
    return None
  return TARA_CATALOG_CM.get(k)


def parse_pallet_type(pallet_type: str) -> Optional[Tuple[float, float, Optional[float]]]:
  if not pallet_type:
    return None
  s = pallet_type.strip().upper()

  m = re.search(r"PAL\s*(\d+)\s*[XХ]\s*(\d+)", s)
  if m:
    w_cm = int(m.group(1))
    l_cm = int(m.group(2))
    return (w_cm / 100.0, l_cm / 100.0, None)

  m = re.search(r"BOX\s*(\d+)\s*[XХ]\s*(\d+)\s*[XХ]\s*(\d+)", s)
  if m:
    w_cm = int(m.group(1))
    l_cm = int(m.group(2))
    h_cm = int(m.group(3))
    return (w_cm / 100.0, l_cm / 100.0, h_cm / 100.0)

  return None


def get_stack_flags(pallet_type: Optional[str]) -> Dict[str, bool]:
  key = normalize_code_key(pallet_type)
  RULES: Dict[str, Dict[str, bool]] = {}
  return RULES.get(key, {"can_be_base": True, "can_be_stacked": True})


def _safe_float(v: Any) -> Optional[float]:
  if v is None:
    return None
  try:
    return float(v)
  except Exception:
    return None


def _normalize_ratio(v: Any) -> Tuple[Optional[float], Optional[str]]:
  """
  ratio = floor demand: сколько стандартных паллетомест по полу потребляет груз.
  Если битый/нет — вернём None + reason, а fallback посчитаем по площади.
  """
  r = _safe_float(v)
  if r is None:
    return None, "ratio_missing"
  if r != r:  # NaN
    return None, "ratio_nan"
  if r <= 0:
    return None, "ratio_nonpositive"
  return r, None


def _normalize_height_cm(v: Any) -> Tuple[Optional[float], Optional[str]]:
  """
  height из БД — источник истины, но защищаемся от мусора.
  Возвращаем (height_cm, reason_if_bad).
  """
  h = _safe_float(v)
  if h is None:
    return None, "height_missing"
  if h != h:  # NaN
    return None, "height_nan"
  if h <= 0:
    return None, "height_nonpositive"
  # sanity-check: при необходимости можно ослабить/убрать
  if h > 400:
    return None, "height_too_large"
  return h, None


def normalize_pallet(row: Dict[str, Any]) -> Item:
  # drop_container_id == sscc (главный источник)
  sscc = row.get("drop_container_id") or row.get("sscc") or row.get("id")
  pallet_id = str(sscc) if sscc is not None else "UNKNOWN"

  pallet_type_raw = row.get("pallet_type") or ""
  pallet_type_key = normalize_code_key(pallet_type_raw)

  tara = lookup_tara_by_code(pallet_type_raw)

  status = "ok"
  h_from_type: Optional[float] = None

  # --- dims
  if tara:
    w_m = float(tara["width"]) / 100.0
    l_m = float(tara["length"]) / 100.0
    status = "dims_from_tara_catalog"
  else:
    parsed = parse_pallet_type(pallet_type_raw)
    if parsed:
      w_m, l_m, h_from_type = parsed
      status = "dims_from_pallet_type"
    else:
      w_m, l_m, h_from_type = 0.80, 1.20, None
      status = "unknown_pallet_type"

  # --- numeric inputs
  weight = _safe_float(row.get("weight"))
  volume = _safe_float(row.get("volume"))

  # --- height (priority: DB height -> volume -> type -> fallback)
  height_cm_raw = row.get("height")
  height_cm, height_reason = _normalize_height_cm(height_cm_raw)

  if height_cm is not None:
    h_m = float(height_cm) / 100.0
    if status in ("ok", "dims_from_tara_catalog", "dims_from_pallet_type"):
      status = "height_from_db"
    else:
      status = f"{status}|height_from_db"
  else:
    if height_reason:
      status = f"{status}|{height_reason}"

    if volume is not None:
      base_area = float(w_m) * float(l_m)
      if base_area > 0:
        h_m = float(volume) / base_area
        status = f"{status}|height_from_volume"
      else:
        h_m = 1.20
        status = f"{status}|no_base_area"
    elif h_from_type is not None:
      h_m = float(h_from_type)
      status = f"{status}|height_from_type"
    else:
      h_m = 1.20
      status = f"{status}|no_height_no_volume"

  # --- stack flags (fallback)
  flags = get_stack_flags(pallet_type_raw)

  # --- tare weight fallback
  tare_weight = _safe_float(tara.get("weight")) if tara else None
  if (weight is None) and (tare_weight is not None):
    weight = float(tare_weight)

  # --- ratio from DB (SEMANTICS: floor demand)
  ratio_raw = row.get("ratio")
  ratio, ratio_reason = _normalize_ratio(ratio_raw)

  if ratio is None:
    # fallback: считаем по площади паллеты / 1.0 (1 м² = 1 стандартное место)
    area = float(w_m) * float(l_m)
    ratio = area if area > 0 else 1.0
    status = f"{status}|{ratio_reason}|ratio_from_area"

  # --- provider (для будущего enrich стэкинга)
  provider_id = row.get("provider_id")
  provider_name = row.get("provider_name")

  return Item(
    id=pallet_id,

    width=float(w_m),
    length=float(l_m),
    height=float(h_m),

    # ВАЖНО: Item.weight должен быть float (solver), поэтому если None — ставим 0.0
    weight=float(weight) if weight is not None else 0.0,

    # ratio == floor demand (паллетомест по полу)
    ratio=float(ratio),

    palletType=row.get("pallet_type"),
    palletTypeNorm=pallet_type_key,

    providerId=(None if provider_id is None else str(provider_id)),
    providerName=(None if provider_name is None else str(provider_name)),

    taskId=str(row.get("_id") or row.get("task_id") or ""),
    routeId=str(row.get("route_id") or ""),
    transportType=str(row.get("transport_type") or ""),
    dropContainerId=str(row.get("drop_container_id") or pallet_id),

    status=status,
    canBeBase=bool(flags["can_be_base"]),
    canBeStacked=bool(flags["can_be_stacked"]),
  )
