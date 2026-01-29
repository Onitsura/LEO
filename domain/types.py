# domain/types.py
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, TypedDict


# ----------------------------
# Core enums / aliases
# ----------------------------

ItemStatus = Literal["ok", "unplaced", "box_loose", "stacked"]
ModeName = Literal["weight", "volume", "mixed"]

DebugLogFn = Callable[[str, Dict[str, Any]], None]


# ----------------------------
# Vehicle (TypedDict, как у тебя было)
# ----------------------------

class Vehicle(TypedDict, total=False):
  id: str

  innerWidth: float
  innerLength: float
  innerHeight: float

  # режим/эвристики
  fillFactorFloor: float
  fillFactorVolume: float

  # общий лимит массы (если есть)
  payloadMaxKg: Optional[float]

  # оси (опционально, для constraints/axles.py)
  axleALimitKg: Optional[float]
  axleBLimitKg: Optional[float]
  axleAPosFromHeadM: Optional[float]
  axleBPosFromHeadM: Optional[float]


# ----------------------------
# Domain модели
# ----------------------------

@dataclass
class Item:
  # идентификаторы / служебные
  id: str  # sscc (drop_container_id)
  taskId: Optional[str] = None
  routeId: Optional[str] = None
  transportType: Optional[str] = None
  dropContainerId: Optional[str] = None

  providerId: Optional[str] = None
  providerName: Optional[str] = None

  palletType: Optional[str] = None
  palletTypeNorm: Optional[str] = None

  # геометрия / вес (метры, кг)
  width: float = 0.0
  length: float = 0.0
  height: float = 0.0
  weight: float = 0.0
  ratio: float = 1.0

  # флаги
  canBeBase: bool = True
  canBeStacked: bool = False

  status: ItemStatus = "ok"

  def volume(self) -> float:
    return max(self.width, 0.0) * max(self.length, 0.0) * max(self.height, 0.0)

  def footprint(self) -> float:
    return max(self.width, 0.0) * max(self.length, 0.0)


class AABB(TypedDict):
  minX: float
  maxX: float
  minY: float
  maxY: float
  minZ: float
  maxZ: float


@dataclass
class PlacedItem:
  item: Item
  x: float
  y: float
  z: float
  rotationY: int  # 0 / 90

  dims: Tuple[float, float, float]  # (dx, dy, dz)
  aabb: AABB
  corner: Dict[str, float]
  status: ItemStatus = "ok"


class Candidate(TypedDict):
  itemId: str
  x: float
  y: float
  z: float
  rotationY: int

  dx: float
  dy: float
  dz: float

  aabb: AABB
  kind: str
  meta: Dict[str, Any]


class AxleLoads(TypedDict, total=False):
  axleA_kg: float
  axleB_kg: float
  payload_kg: float


@dataclass(frozen=True)
class ModeDecision:
  mode: ModeName
  weight_pressure: float
  floor_pressure: float
  volume_pressure: float
  alpha: Optional[float] = None


@dataclass
class DebugEvent:
  evt: str
  payload: Dict[str, Any]


@dataclass
class PlanResult:
  taskId: str
  transportType: str
  vehicle: Vehicle
  mode: ModeDecision
  placed: List[PlacedItem]
  unplaced: List[Item]
  loads: Optional[AxleLoads] = None
  debug: List[DebugEvent] = None

  def to_dict(self) -> Dict[str, Any]:
    placed_out: List[Dict[str, Any]] = []
    for p in self.placed:
      placed_out.append({
        "id": p.item.id,
        "sscc": p.item.dropContainerId or p.item.id,
        "x": p.x, "y": p.y, "z": p.z,
        "rotationY": p.rotationY,
        "dims": {"dx": p.dims[0], "dy": p.dims[1], "dz": p.dims[2]},
        "aabb": dict(p.aabb),
        "corner": dict(p.corner),
        "status": p.status,
        "weight": p.item.weight,
        "ratio": p.item.ratio,
        "palletType": p.item.palletType,
        "palletTypeNorm": p.item.palletTypeNorm,
      })

    unplaced_out: List[Dict[str, Any]] = []
    for it in self.unplaced:
      unplaced_out.append({
        "id": it.id,
        "sscc": it.dropContainerId or it.id,
        "dims": {"w": it.width, "l": it.length, "h": it.height},
        "weight": it.weight,
        "ratio": it.ratio,
        "status": "unplaced",
      })

    return {
      "taskId": self.taskId,
      "transportType": self.transportType,
      "vehicle": dict(self.vehicle),
      "mode": asdict(self.mode),
      "placed": placed_out,
      "unplaced": unplaced_out,
      "loads": (dict(self.loads) if self.loads else None),
      "debug": ([asdict(e) for e in (self.debug or [])]),
    }
