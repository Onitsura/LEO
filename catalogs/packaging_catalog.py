# catalogs/packaging_catalog.py
from __future__ import annotations

from typing import Dict, Optional


# Единицы:
# - weight: кг
# - width / length / height: САНТИМЕТРЫ
TARA_CATALOG_CM: Dict[str, Dict[str, float]] = {
  "ADR 120X120": {"weight": 16.0, "width": 120.0, "height": 15.0, "length": 120.0},
  "ADR 80X120": {"weight": 16.0, "width": 80.0, "height": 15.0, "length": 120.0},
  "BIG": {"weight": 28.0, "width": 240.0, "height": 15.0, "length": 240.0},
  "BOX": {"weight": 25.0, "width": 80.0, "height": 40.0, "length": 120.0},
  "BOX 40X40X60": {"weight": 0.0, "width": 40.0, "height": 5.0, "length": 60.0},
  "CS": {"weight": 1.0, "width": 80.0, "height": 40.0, "length": 80.0},
  "DIV": {"weight": 25.0, "width": 170.0, "height": 15.0, "length": 120.0},
  "DVA": {"weight": 25.0, "width": 160.0, "height": 15.0, "length": 120.0},
  "FIN": {"weight": 25.0, "width": 120.0, "height": 15.0, "length": 120.0},
  "FLO 80X120": {"weight": 0.0, "width": 80.0, "height": 15.0, "length": 120.0},
  "GRS": {"weight": 25.0, "width": 140.0, "height": 15.0, "length": 120.0},
  "KBX": {"weight": 25.0, "width": 80.0, "height": 40.0, "length": 120.0},
  "LAM": {"weight": 25.0, "width": 80.0, "height": 40.0, "length": 120.0},
  "LAM 80X140": {"weight": 21.0, "width": 80.0, "height": 15.0, "length": 140.0},
  "MAX": {"weight": 27.0, "width": 320.0, "height": 15.0, "length": 120.0},
  "MBX": {"weight": 25.0, "width": 80.0, "height": 40.0, "length": 120.0},
  "MCS": {"weight": 25.0, "width": 80.0, "height": 14.4, "length": 120.0},
  "MIN": {"weight": 25.0, "width": 80.0, "height": 15.0, "length": 120.0},
  "NON": {"weight": 1.0, "width": 1.0, "height": 1.0, "length": 1.0},
  "PAL 100X120": {"weight": 19.0, "width": 100.0, "height": 15.0, "length": 120.0},
  "PAL 120X120": {"weight": 19.0, "width": 120.0, "height": 15.0, "length": 120.0},
  "PAL 120X170": {"weight": 30.0, "width": 120.0, "height": 15.0, "length": 170.0},
  "PAL 120X240": {"weight": 32.0, "width": 120.0, "height": 15.0, "length": 240.0},
  "PAL 140X120": {"weight": 0.0, "width": 140.0, "height": 15.0, "length": 120.0},
  "PAL 150X100": {"weight": 21.0, "width": 150.0, "height": 15.0, "length": 100.0},
  "PAL 155X155": {"weight": 20.0, "width": 155.0, "height": 15.0, "length": 155.0},
  "PAL 160X120": {"weight": 40.0, "width": 160.0, "height": 15.0, "length": 120.0},
  "PAL 170X120": {"weight": 24.0, "width": 170.0, "height": 15.0, "length": 120.0},
  "PAL 200X120": {"weight": 50.0, "width": 200.0, "height": 15.0, "length": 120.0},
  "PAL 200X250": {"weight": 0.0, "width": 200.0, "height": 15.0, "length": 250.0},
  "PAL 210X310": {"weight": 15.0, "width": 210.0, "height": 15.0, "length": 310.0},
  "PAL 240X120": {"weight": 32.0, "width": 240.0, "height": 15.0, "length": 120.0},
  "PAL 240X80": {"weight": 32.0, "width": 240.0, "height": 15.0, "length": 80.0},
  "PAL 250X120": {"weight": 35.0, "width": 250.0, "height": 15.0, "length": 120.0},
  "PAL 250X80": {"weight": 32.0, "width": 250.0, "height": 15.0, "length": 80.0},
  "PAL 300X100": {"weight": 32.0, "width": 300.0, "height": 15.0, "length": 100.0},
  "PAL 300X120": {"weight": 60.0, "width": 300.0, "height": 15.0, "length": 120.0},
  "PAL 300X164": {"weight": 0.0, "width": 300.0, "height": 15.0, "length": 164.0},
  "PAL 300X80": {"weight": 50.0, "width": 300.0, "height": 15.0, "length": 80.0},
  "PAL 320X120": {"weight": 32.0, "width": 320.0, "height": 15.0, "length": 120.0},
  "PAL 320X80": {"weight": 50.0, "width": 320.0, "height": 15.0, "length": 80.0},
  "PAL 370X80": {"weight": 32.0, "width": 370.0, "height": 15.0, "length": 80.0},
  "PAL 400X100": {"weight": 32.0, "width": 400.0, "height": 15.0, "length": 100.0},
  "PAL 400X80": {"weight": 45.0, "width": 80.0, "height": 15.0, "length": 400.0},
  "PAL 500X120": {"weight": 15.0, "width": 500.0, "height": 15.0, "length": 120.0},
  "PAL 50X120": {"weight": 0.0, "width": 500.0, "height": 15.0, "length": 120.0},
  "PAL 60X120": {"weight": 0.0, "width": 60.0, "height": 15.0, "length": 120.0},
  "PAL 80X120": {"weight": 16.0, "width": 80.0, "height": 15.0, "length": 120.0},
  "PAL 80X200": {"weight": 20.0, "width": 80.0, "height": 15.0, "length": 200.0},
  "PAL 80X300": {"weight": 30.0, "width": 80.0, "height": 15.0, "length": 300.0},
  "PAL 80X60": {"weight": 8.0, "width": 80.0, "height": 15.0, "length": 60.0},
  "PCN": {"weight": 25.0, "width": 80.0, "height": 14.4, "length": 120.0},
  "PLC": {"weight": 25.0, "width": 80.0, "height": 14.4, "length": 120.0},
  "ROL": {"weight": 25.0, "width": 80.0, "height": 15.0, "length": 120.0},
  "ROL 000-240": {"weight": 0.0, "width": 30.0, "height": 30.0, "length": 400.0},
  "ROL 241-360": {"weight": 0.0, "width": 30.0, "height": 30.0, "length": 400.0},
  "ROL 361-400": {"weight": 0.0, "width": 30.0, "height": 30.0, "length": 400.0},
  "ROL 361-480": {"weight": 0.0, "width": 30.0, "height": 30.0, "length": 400.0},
  "ROL 401-600": {"weight": 0.0, "width": 30.0, "height": 30.0, "length": 400.0},
  "ROL 481-600": {"weight": 0.0, "width": 30.0, "height": 30.0, "length": 400.0},
  "SPC 120X120": {"weight": 30.0, "width": 120.0, "height": 15.0, "length": 120.0},
  "SPC 80X120": {"weight": 15.0, "width": 80.0, "height": 15.0, "length": 120.0},
  "STD": {"weight": 25.0, "width": 80.0, "height": 14.4, "length": 120.0},
  "UKP": {"weight": 25.0, "width": 100.0, "height": 15.0, "length": 120.0},
  "USP": {"weight": 25.0, "width": 120.0, "height": 15.0, "length": 120.0},
}


# ----------------------------
# Хелперы
# ----------------------------

def normalize_tara_key(raw: Optional[str]) -> Optional[str]:
  if not raw:
    return None
  key = raw.strip().upper()
  return key if key in TARA_CATALOG_CM else None


def get_tara_cm(code: Optional[str]) -> Optional[Dict[str, float]]:
  if not code:
    return None
  return TARA_CATALOG_CM.get(code)
