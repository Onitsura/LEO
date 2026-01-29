from typing import Dict, Optional
from domain.types import Vehicle

VEHICLE_PRESETS: Dict[str, Vehicle] = {
  "Тент (20т)": {"innerWidth": 2.45, "innerHeight": 2.70, "innerLength": 13.60},
  "Тент (10т)": {"innerWidth": 2.45, "innerHeight": 2.70, "innerLength": 6.80},
  "Контейнер 40'' HC": {"innerWidth": 2.35, "innerHeight": 2.39, "innerLength": 12.02},
}

DEFAULT_VEHICLE: Vehicle = {"innerWidth": 2.45, "innerHeight": 2.70, "innerLength": 13.60}


def get_vehicle(transport_type: Optional[str]) -> Vehicle:
  if not transport_type:
    return dict(DEFAULT_VEHICLE)
  v = VEHICLE_PRESETS.get(str(transport_type))
  if not v:
    return dict(DEFAULT_VEHICLE)
  return dict(v)