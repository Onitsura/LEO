# solver/packer.py
from __future__ import annotations

from typing import Callable, Dict, List, Optional, Tuple

from catalogs.plan_state import PlanState
from candidates.generators import generate_floor_candidates
from domain.types import Candidate, Item, PlanResult, Vehicle
from scoring.coeff import detect_mode
from scoring.objective import score_candidate
from settings import SETTINGS
from constraints.policies import sort_key_for_queue, evaluate_candidate_policy
from constraints.bounds import check_collision, check_oob
from constraints.axles import compute_loads, check_loads
from catalogs.placed_item import placed_from_candidate
from geometry.aabb import aabb_intersects


DebugLogFn = Optional[Callable[[str, dict], None]]


def _group_pattern_candidates(cands: List[Candidate]) -> Dict[str, List[Candidate]]:
  groups: Dict[str, List[Candidate]] = {}
  for c in cands:
    pid = (c.get("meta") or {}).get("patternId")
    if not pid:
      continue
    groups.setdefault(pid, []).append(c)
  return groups


def _can_commit_group(state: PlanState, group: List[Candidate]) -> Tuple[bool, List[str]]:
  reasons: List[str] = []

  # 1) внутренняя коллизия группы
  for i in range(len(group)):
    for j in range(i):
      if aabb_intersects(group[i]["aabb"], group[j]["aabb"]):
        return (False, ["pattern_internal_collision"])

  # 2) OOB + коллизии с уже placed
  for c in group:
    ok, r = check_oob(c, state.vehicle)
    if not ok:
      return (False, r)
    ok, r = check_collision(c, state.placed)
    if not ok:
      return (False, r)

  # 3) Оси как жёсткий фильтр на итоговой постановке
  tmp_placed = state.placed[:]
  for c in group:
    it = state.items_by_id[c["itemId"]]
    tmp_placed.append(placed_from_candidate(c, item=it))

  loads = compute_loads(tmp_placed, state.vehicle)
  ok, r = check_loads(loads, state.vehicle)
  if not ok:
    reasons.extend(r)
    return (False, reasons)

  return (True, [])


def _apply_policy_to_score(sc, pol) -> Tuple[int, float, float, float]:
  """
  Политику добавляем в последнюю компоненту.
  sc ожидается как (int, float, float, float)
  """
  if sc is None or pol is None:
    return sc
  w = float(getattr(SETTINGS, "POLICY_SCORE_WEIGHT", 1.0))
  term = w * (float(pol.zone_bonus) - float(pol.zone_penalty))
  return (int(sc[0]), float(sc[1]), float(sc[2]), float(sc[3]) + term)


def _pat_reason_bucket(reasons: List[str]) -> str:
  if not reasons:
    return "unknown"
  s = "|".join(str(x) for x in reasons).lower()
  if "pattern_internal_collision" in s:
    return "internal_collision"
  if "oob" in s or "out" in s:
    return "oob"
  if "collision" in s or "intersect" in s:
    return "collision"
  if "axle" in s or "load" in s or "support" in s:
    return "axles"
  return "other"


def _packing_quality(group: List[Candidate]) -> Tuple[float, Dict[str, float]]:
  """
  Геометрическая оценка для паттерна (антифрагментация).

  Метрики:
  - density = used_area / bbox_area (bbox по XZ, объединение AABB группы)
  - slack = сумма зазоров bbox до границ free-rect (meta.rect)
  - touch_edges = сколько сторон bbox "касается" границ rect (0..4)

  quality = DENSITY_W*density + TOUCH_W*touch_edges - SLACK_W*slack
  """
  if not group:
    return 0.0, {}

  used = 0.0
  minX = 1e18
  maxX = -1e18
  minZ = 1e18
  maxZ = -1e18

  for c in group:
    used += float(c["dx"]) * float(c["dz"])
    a = c["aabb"]
    minX = min(minX, float(a["minX"]))
    maxX = max(maxX, float(a["maxX"]))
    minZ = min(minZ, float(a["minZ"]))
    maxZ = max(maxZ, float(a["maxZ"]))

  bbox_w = max(0.0, maxX - minX)
  bbox_l = max(0.0, maxZ - minZ)
  bbox_area = bbox_w * bbox_l
  density = (used / bbox_area) if bbox_area > 1e-9 else 0.0

  rect = (group[0].get("meta") or {}).get("rect")
  slack = 0.0
  touch = 0.0
  if rect:
    rminX, rmaxX, rminZ, rmaxZ = rect
    left_gap = max(0.0, float(minX) - float(rminX))
    right_gap = max(0.0, float(rmaxX) - float(maxX))
    front_gap = max(0.0, float(minZ) - float(rminZ))
    back_gap = max(0.0, float(rmaxZ) - float(maxZ))
    slack = left_gap + right_gap + front_gap + back_gap

    eps = 1e-3
    t = 0
    if left_gap <= eps:
      t += 1
    if right_gap <= eps:
      t += 1
    if front_gap <= eps:
      t += 1
    if back_gap <= eps:
      t += 1
    touch = float(t)

  DENSITY_W = float(getattr(SETTINGS, "PACK_DENSITY_W", 10.0))
  TOUCH_W = float(getattr(SETTINGS, "PACK_TOUCH_W", 0.6))
  SLACK_W = float(getattr(SETTINGS, "PACK_SLACK_W", 1.5))

  quality = (DENSITY_W * density) + (TOUCH_W * touch) - (SLACK_W * slack)

  dbg = {
    "used": float(used),
    "bboxArea": float(bbox_area),
    "density": float(density),
    "slack": float(slack),
    "touch": float(touch),
    "quality": float(quality),
  }
  return float(quality), dbg


def pack(items: List[Item], vehicle: Vehicle, task_id: str, transport_type: str, debug_log: DebugLogFn = None) -> PlanResult:
  mode = detect_mode(items, vehicle)

  state = PlanState(
    task_id=task_id,
    transport_type=transport_type,
    vehicle=vehicle,
    mode=mode,
  )
  state.init_free_rects()
  state.items_by_id = {it.id: it for it in items}

  state.emit("mode_detected", {
    "mode": mode.mode,
    "weight_pressure": mode.weight_pressure,
    "floor_pressure": mode.floor_pressure,
    "volume_pressure": mode.volume_pressure,
    "alpha": mode.alpha,
  })

  remaining = items[:]
  remaining.sort(key=lambda it: sort_key_for_queue(it, vehicle, mode))

  PATTERN_REJECT_LOG_LIMIT = int(getattr(SETTINGS, "PATTERN_REJECT_LOG_LIMIT", 25))

  while remaining:
    window = remaining[:SETTINGS.TOP_N_WINDOW]
    candidates = generate_floor_candidates(state, window)

    rem_ids = {it.id for it in remaining}
    pattern_groups = _group_pattern_candidates(candidates)

    # базовая статистика
    single_count = 0
    pat_count = 0
    for c in candidates:
      if (c.get("meta") or {}).get("patternId"):
        pat_count += 1
      else:
        single_count += 1

    state.emit("candidates_generated", {
      "count": len(candidates),
      "window": len(window),
      "singleCount": single_count,
      "patternCandCount": pat_count,
      "patternGroups": len(pattern_groups),
    })

    # держим отдельно лучший паттерн и лучший single, чтобы не смешивать шкалы
    best_pat_group: Optional[List[Candidate]] = None
    best_pat_score = None
    best_pat_pid: Optional[str] = None
    best_pat_dbg = None

    best_single: Optional[Candidate] = None
    best_single_score = None
    best_single_pol = None

    # -------------------------
    # 1) паттерны: приоритет антифрагментации
    # score_pat = (1, quality, used_area_sum, policy_sum, k_sum)
    # ВАЖНО: policy остаётся и влияет, но ПОСЛЕ геометрии.
    # -------------------------
    pattern_rejects_logged = 0
    pattern_reject_stats: Dict[str, int] = {}

    for pid, group in pattern_groups.items():
      if any(c["itemId"] not in rem_ids for c in group):
        pattern_reject_stats["not_available"] = pattern_reject_stats.get("not_available", 0) + 1
        if pattern_rejects_logged < PATTERN_REJECT_LOG_LIMIT:
          missing = [c["itemId"] for c in group if c["itemId"] not in rem_ids]
          state.emit("pattern_rejected", {
            "patternId": pid,
            "reason": "not_available",
            "missingItemIds": missing[:20],
            "groupSize": len(group),
          })
          pattern_rejects_logged += 1
        continue

      ok, reasons = _can_commit_group(state, group)
      if not ok:
        bucket = _pat_reason_bucket(reasons)
        pattern_reject_stats[bucket] = pattern_reject_stats.get(bucket, 0) + 1
        if pattern_rejects_logged < PATTERN_REJECT_LOG_LIMIT:
          state.emit("pattern_rejected", {
            "patternId": pid,
            "reason": bucket,
            "reasons": reasons[:20],
            "groupSize": len(group),
          })
          pattern_rejects_logged += 1
        continue

      # policy hard rules (оставляем как есть; по умолчанию allow_hard_rules=False)
      bad = False
      group_pol_terms = []
      hard_reasons: List[str] = []
      for c in group:
        it = state.items_by_id[c["itemId"]]
        pol = evaluate_candidate_policy(it, c, vehicle, mode, allow_hard_rules=False)
        if pol.hard_reject_reasons:
          bad = True
          hard_reasons.extend(pol.hard_reject_reasons)
          break
        group_pol_terms.append(pol)

      if bad:
        pattern_reject_stats["policy_hard"] = pattern_reject_stats.get("policy_hard", 0) + 1
        if pattern_rejects_logged < PATTERN_REJECT_LOG_LIMIT:
          state.emit("pattern_rejected", {
            "patternId": pid,
            "reason": "policy_hard",
            "reasons": hard_reasons[:20],
            "groupSize": len(group),
          })
          pattern_rejects_logged += 1
        continue

      # сумма used_area и сумма K по паллетам (K нужна как слабый tie-breaker)
      used_area_sum = 0.0
      k_sum = 0.0
      policy_sum = 0.0

      for idx, c in enumerate(group):
        sc = score_candidate(state, c, mode)  # (1, K, used_area, policy_term?) зависит от objective.py
        pol = group_pol_terms[idx]
        sc2 = _apply_policy_to_score(sc, pol)  # policy в sc2[3]
        k_sum += float(sc2[1])
        used_area_sum += float(sc2[2])
        policy_sum += float(sc2[3])

      quality, qdbg = _packing_quality(group)

      # ВАЖНО: геометрия впереди, policy остаётся, но ПОСЛЕ геометрии.
      # K_sum последним, чтобы не "перетягивал" выбор паттерна.
      pat_score = (1, float(quality), float(used_area_sum), float(policy_sum), float(k_sum))

      if best_pat_score is None or pat_score > best_pat_score:
        best_pat_score = pat_score
        best_pat_group = group
        best_pat_pid = pid
        best_pat_dbg = qdbg

    if pattern_groups:
      state.emit("pattern_reject_summary", {
        "groups": len(pattern_groups),
        "logged": pattern_rejects_logged,
        "stats": pattern_reject_stats,
        "logLimit": PATTERN_REJECT_LOG_LIMIT,
      })

    # -------------------------
    # 2) single: сравнение по K (а policy остаётся как tie-breaker)
    # score_single = (1, K, used_area, policy_term)
    # -------------------------
    for cand in candidates:
      if (cand.get("meta") or {}).get("patternId"):
        continue

      ok, reasons = state.can_place(cand)
      if not ok:
        continue

      it = state.items_by_id[cand["itemId"]]
      pol = evaluate_candidate_policy(it, cand, vehicle, mode, allow_hard_rules=False)
      if pol.hard_reject_reasons:
        continue

      sc = score_candidate(state, cand, mode)
      sc = _apply_policy_to_score(sc, pol)

      if best_single_score is None or sc > best_single_score:
        best_single_score = sc
        best_single = cand
        best_single_pol = pol

    # -------------------------
    # 3) выбор: если есть валидный паттерн — берём его (паттерны = антифрагментация)
    # иначе берём single.
    # -------------------------
    if best_pat_group is None and best_single is None:
      for it in remaining:
        it.status = "unplaced"
        state.unplaced.append(it)
      state.emit("unplaced_all_remaining", {"count": len(remaining)})
      break

    if best_pat_group is not None:
      committed_ids: List[str] = []
      for c in best_pat_group:
        state.commit(c)
        committed_ids.append(c["itemId"])

      state.emit("pattern_committed", {
        "patternId": best_pat_pid,
        "count": len(best_pat_group),
        "itemIds": committed_ids,
        "score": best_pat_score,
        "packing": best_pat_dbg,
      })

      committed_set = set(committed_ids)
      remaining = [it for it in remaining if it.id not in committed_set]
      continue

    # single commit
    assert best_single is not None
    state.commit(best_single)
    payload = {"itemId": best_single["itemId"], "kind": best_single["kind"], "score": best_single_score}
    if best_single_pol:
      payload["policy"] = {
        "zone": best_single_pol.tags.get("zone"),
        "class": best_single_pol.tags.get("class"),
        "hi": best_single_pol.tags.get("hi"),
        "bonus": best_single_pol.zone_bonus,
        "penalty": best_single_pol.zone_penalty,
      }
    state.emit("candidate_chosen", payload)

    remaining = [it for it in remaining if it.id != best_single["itemId"]]

  res = state.snapshot()

  if debug_log:
    for e in res.debug:
      debug_log(e.evt, e.payload)

  return res
