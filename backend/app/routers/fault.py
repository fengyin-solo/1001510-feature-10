"""故障处置接口：维护故障记录，覆盖派单处置、确认恢复、挂起故障等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import Field

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.fault import FaultService

router = APIRouter(prefix="/api/fault", tags=["故障处置"])

service = FaultService()

LIST_FIELDS = ["故障编号", "涉及站点", "故障现象", "发生时刻", "影响要素", "处置人员", "恢复时刻", "故障状态"]
STATUSES = ["待派单", "处置中", "已恢复", "已挂起"]


class FaultPageResult(PageResult[dict]):
    """故障处置列表分页结果：附带超期件数等汇总口径，刷新后前后一致。"""

    summary: dict[str, Any] = Field(default_factory=dict)


@router.get("", response_model=FaultPageResult)
def list_entries(
    keyword: str | None = Query(default=None, description="按故障编号检索"),
    status: str | None = Query(default=None, description="待派单、处置中、已恢复、已挂起"),
    station: str | None = Query(default=None, description="按涉及站点检索"),
    phenomenon: str | None = Query(default=None, description="按故障现象检索"),
    overdue: bool = Query(default=False, description="为 true 时只列出超过处置时限的故障"),
    page: int = 1,
    size: int = 20,
) -> FaultPageResult:
    """按故障编号与状态过滤故障处置列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total, summary = service.list_entries(
        keyword=keyword,
        status=status,
        station=station,
        phenomenon=phenomenon,
        overdue=overdue,
        page=page,
        size=size,
    )
    return FaultPageResult(items=items, total=total, page=page, size=size, summary=summary)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出故障处置清单：返回当前过滤条件下的全量数据。"""
    items, total, _summary = service.list_entries(page=1, size=10000)
    return {"module": "fault", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条故障记录明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"故障记录 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条故障记录，缺字段时说明原因；同一站点短时间内重复报同一现象时按重复报障合并。"""
    entry, missing, message = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message=message, entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: EntryPayload) -> ActionResult:
    """对单条故障记录执行派单处置、确认恢复、挂起故障；条件不满足的动作会被拦下并说明缺哪一项。"""
    action = str(payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action, payload.values)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
