from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.engine import Engine


SQL_TASK_ROWS = text("""
select
    vlt.task_id as _id,
    vlt.route_id,
    vlt.transport_type,

    p.drop_container_id,
    p.weight,
    vac.height,
    p.volume,
    p.pallet_type,
    t.ratio,

    sl.external_id as provider_id,
    sl."name" as provider_name

from wms_adeo_handover_loading_task_ods.v_loading_task vlt

left join wms_adeo_packaging_ods.v_package p
    on vlt.task_id = p.loading_task_id

left join wms_adeo_receivit_data_storage_ods.v_actual_containers vac
    on vac.external_id = p.drop_container_id

left join logbrick_ods.v_tara t
    on p.pallet_type = t.name

left join wms_adeo_receivit_data_storage_ods.goods_receiving gr
    on gr.id = vac.goods_receiving_id

left join wms_adeo_receivit_data_storage_ods.shipping_locations sl
    on gr.shipping_location_id = sl.id

where vlt.task_id = :task_id
""")


def fetch_task_rows(engine: Engine, task_id: str) -> List[Dict[str, Any]]:
  with engine.connect() as conn:
    rows = conn.execute(SQL_TASK_ROWS, {"task_id": task_id}).mappings().all()

  seen = set()
  dup = 0
  for r in rows:
    sscc = r.get("drop_container_id")
    if sscc in seen:
      dup += 1
    seen.add(sscc)

  if dup > 0:
    print(f"[WARN] task {task_id}: duplicated sscc rows = {dup}")

  return [dict(r) for r in rows]

