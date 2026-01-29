# scoring/objective.py
from __future__ import annotations

from typing import Tuple

from domain.types import Candidate, ModeDecision
from scoring.coeff import compute_k


def score_candidate(state, candidate: Candidate, mode: ModeDecision) -> Tuple:
  """
  tuple: чем больше, тем лучше.
  1) placed_count_delta (в MVP всегда 1, но оставляем первым компонентом)
  2) K (ценность)
  3) used_area (внутри прямоугольника пола) — proxy против фрагментации
  4) reserved (0.0) — оставляем компоненту для совместимости с packer/_apply_policy_to_score
  """
  item = state.items_by_id[candidate["itemId"]]
  k = compute_k(item, mode)

  used_area = float(candidate["dx"]) * float(candidate["dz"])

  # policy теперь добавляется только в solver/packer.py через _apply_policy_to_score()
  return (1, float(k), float(used_area), 0.0)



"""
Закомментил, т.к. дублирование policies происходит тут и в packer, пока не понял глубину влияния этого на выбор паттернов
# scoring/objective.py
from __future__ import annotations

from typing import Tuple

from domain.types import Candidate, ModeDecision
from scoring.coeff import compute_k
from constraints.policies import evaluate_candidate_policy


def score_candidate(state, candidate: Candidate, mode: ModeDecision) -> Tuple:

  tuple: чем больше, тем лучше.
  1) placed_count_delta (в MVP всегда 1, но оставляем первым компонентом)
  2) K (ценность)
  3) used_area (внутри прямоугольника пола) — proxy против фрагментации
  4) policy_bonus_minus_penalty

  item = state.items_by_id[candidate["itemId"]]
  k = compute_k(item, mode)

  used_area = float(candidate["dx"]) * float(candidate["dz"])

  pol = evaluate_candidate_policy(item, candidate, state.vehicle, mode, allow_hard_rules=False)
  policy_term = float(pol.zone_bonus) - float(pol.zone_penalty)

  # Важно: если появятся hard rules — тут можно сразу выбрасывать кандидата,
  # но сейчас это делаем в фильтре packer/state.can_place.
  return (1, float(k), float(used_area), float(policy_term))
"""