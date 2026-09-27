"""故障处置业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "fault"
REQUIRED_FIELDS = ["故障编号", "涉及站点", "故障现象"]
STATUS_ORDER = ["待派单", "处置中", "已恢复", "已挂起"]
ACTION_RULES = {"派单处置": "处置中", "确认恢复": "已恢复", "挂起故障": "已挂起"}
NEGATIVE_ACTIONS = []

# 处置时效口径：从发生时刻起算，未恢复的故障超过该时长即判为超期
OVERDUE_LIMIT_HOURS = 24
# 重复报障口径：同一站点在该窗口内重复上报同一故障现象时合并登记
DUPLICATE_WINDOW_MINUTES = 30
# 挂起故障必须填写的项，条件不满足时按这里逐项点名
SUSPEND_REQUIRED_FIELDS = ["挂起原因"]

TIME_FORMAT = "%Y-%m-%d %H:%M"
TIME_FORMATS = [
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d",
]


def parse_moment(value: Any) -> datetime | None:
    """把页面填写的时刻文本解析成时间；认不出的格式按未填写处理。"""
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def format_moment(moment: datetime) -> str:
    return moment.strftime(TIME_FORMAT)


def handling_hours(entry: dict[str, Any], now: datetime) -> float | None:
    """处置时长：已恢复的算到恢复时刻，其余算到当前时间；发生时刻缺失时不参与判定。"""
    occurred = parse_moment(entry.get("发生时刻"))
    if occurred is None:
        return None
    end = now
    if entry.get("status") == "已恢复":
        end = parse_moment(entry.get("恢复时刻")) or now
    return max((end - occurred).total_seconds() / 3600, 0.0)


def is_overdue(entry: dict[str, Any], now: datetime) -> bool:
    """超期判定：尚未恢复的故障，处置时长超过上限即超期（含已挂起）。"""
    if entry.get("status") == "已恢复":
        return False
    hours = handling_hours(entry, now)
    return hours is not None and hours > OVERDUE_LIMIT_HOURS


def merge_elements(current: Any, extra: Any) -> str:
    """合并影响要素：保留原有顺序，追加重复报障里新出现的要素。"""
    items: list[str] = []
    for source in (current, extra):
        for piece in str(source or "").replace("，", "、").replace(",", "、").split("、"):
            piece = piece.strip()
            if piece and piece not in items:
                items.append(piece)
    return "、".join(items)


class FaultService:
    def _decorate(self, entry: dict[str, Any], now: datetime) -> dict[str, Any]:
        """给列表行补上处置时长与超期标识；每次请求现算，刷新后口径一致。"""
        item = dict(entry)
        hours = handling_hours(entry, now)
        item["处置时长"] = f"{hours:.1f}小时" if hours is not None else "—"
        overdue = is_overdue(entry, now)
        item["是否超期"] = "是" if overdue else "否"
        item["overdue"] = overdue
        item.setdefault("重复报障次数", 0)
        return item

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        station: str | None = None,
        phenomenon: str | None = None,
        overdue: bool = False,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
        now = datetime.now()
        rows = store.rows(MODULE)
        summary = {
            "待派单": sum(1 for row in rows if row.get("status") == "待派单"),
            "处置中": sum(1 for row in rows if row.get("status") == "处置中"),
            "已挂起": sum(1 for row in rows if row.get("status") == "已挂起"),
            "超期件数": sum(1 for row in rows if is_overdue(row, now)),
        }
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("故障编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if station:
            rows = [row for row in rows if station in str(row.get("涉及站点", ""))]
        if phenomenon:
            rows = [row for row in rows if phenomenon in str(row.get("故障现象", ""))]
        if overdue:
            rows = [row for row in rows if is_overdue(row, now)]
        total = len(rows)
        start = max(page - 1, 0) * size
        items = [self._decorate(row, now) for row in rows[start:start + size]]
        return items, total, summary

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._decorate(entry, datetime.now())

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, ""
        rows = store.rows(MODULE)
        duplicate = self._find_duplicate(rows, values)
        if duplicate is not None:
            duplicate["重复报障次数"] = int(duplicate.get("重复报障次数") or 0) + 1
            duplicate["影响要素"] = merge_elements(duplicate.get("影响要素"), values.get("影响要素"))
            merged_from = duplicate.setdefault("已合并报障", [])
            source_no = str(values.get("故障编号") or "").strip()
            if source_no and source_no not in merged_from:
                merged_from.append(source_no)
            return duplicate, [], (
                f"与 {duplicate.get('故障编号')} 属同一站点同一故障现象的重复报障，"
                f"已按重复报障合并（{DUPLICATE_WINDOW_MINUTES} 分钟窗口内），影响要素已归并到该编号下"
            )
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        for field in ["发生时刻", "影响要素", "处置人员", "恢复时刻"]:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        entry["status"] = STATUS_ORDER[0]
        entry["故障状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry["重复报障次数"] = 0
        rows.append(entry)
        return entry, [], "故障记录已登记"

    def _find_duplicate(self, rows: list[dict[str, Any]], values: dict[str, Any]) -> dict[str, Any] | None:
        """同一站点在短时间内重复上报同一故障现象时，返回应合并的目标记录。"""
        occurred = parse_moment(values.get("发生时刻"))
        station = str(values.get("涉及站点") or "").strip()
        phenomenon = str(values.get("故障现象") or "").strip()
        if occurred is None or not station or not phenomenon:
            return None
        window = DUPLICATE_WINDOW_MINUTES * 60
        for row in rows:
            if row.get("status") == "已恢复":
                continue
            if str(row.get("涉及站点", "")).strip() != station:
                continue
            if str(row.get("故障现象", "")).strip() != phenomenon:
                continue
            existing = parse_moment(row.get("发生时刻"))
            if existing is None:
                continue
            if abs((occurred - existing).total_seconds()) <= window:
                return row
        return None

    def run_action(self, entry_id: int, action: str, values: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"故障记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于故障处置可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        now = datetime.now()
        if action == "挂起故障":
            missing = [field for field in SUSPEND_REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
            if missing:
                return None, f"挂起条件不满足，缺少：{'、'.join(missing)}"
            entry["挂起原因"] = str(values["挂起原因"]).strip()
            entry["挂起时刻"] = format_moment(now)
        if action == "确认恢复":
            occurred = parse_moment(entry.get("发生时刻"))
            recovered_text = str(values.get("恢复时刻") or "").strip()
            if recovered_text:
                recovered = parse_moment(recovered_text)
                if recovered is None:
                    return None, f"恢复时刻「{recovered_text}」格式无法识别，请按 YYYY-MM-DD HH:MM 填写"
            else:
                recovered = now
            if occurred is not None and recovered < occurred:
                return None, (
                    f"恢复时刻 {format_moment(recovered)} 早于发生时刻 {format_moment(occurred)}，已拦下："
                    "恢复时刻不得早于发生时刻，请核对后重新提交"
                )
            entry["恢复时刻"] = format_moment(recovered)
        entry["status"] = target
        entry["故障状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"故障记录已{action}"
