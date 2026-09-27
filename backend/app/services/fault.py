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

MERGED_STATUS = "重复报障"  # 重复报障合并后的状态，不在正常流转序列里
OPEN_STATUSES = ["待派单", "处置中", "已挂起"]  # 未恢复状态：处置时长一直计到当前时刻
OVERDUE_LIMIT_HOURS = 24  # 处置时效上限：发生时刻起超过 24 小时未恢复即超期
DUPLICATE_WINDOW_HOURS = 2  # 重复报障窗口：同站点同现象 2 小时内再报按重复报障合并
SUSPEND_REQUIRED_FIELDS = ["挂起原因"]  # 挂起必须项，缺哪一项就指哪一项

TIME_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d")


def parse_moment(value: Any) -> datetime | None:
    """把时刻字段解析成 datetime；空值或格式不认时返回 None，由调用方决定口径。"""
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def disposal_hours(entry: dict[str, Any], now: datetime) -> float | None:
    """处置时长（小时）：已恢复的算到恢复时刻，其余一律从发生时刻算到当前时刻。"""
    start = parse_moment(entry.get("发生时刻"))
    if start is None:
        return None
    end = now
    if entry.get("status") == "已恢复":
        end = parse_moment(entry.get("恢复时刻")) or now
    # 发生时刻在未来（时钟偏差或录入异常）时不出现负时长
    return round(max((end - start).total_seconds() / 3600, 0.0), 1)


def is_overdue(entry: dict[str, Any], now: datetime) -> bool:
    """超期口径：未恢复且处置时长超过上限；发生时刻缺失时不做超期认定。"""
    if entry.get("status") not in OPEN_STATUSES:
        return False
    hours = disposal_hours(entry, now)
    return hours is not None and hours > OVERDUE_LIMIT_HOURS


def recovery_rule_message(occurred: Any, recovered: Any) -> str | None:
    """恢复时刻不得早于发生时刻；恢复时刻填了却解析不了同样拦下。"""
    recovered_text = str(recovered or "").strip()
    if not recovered_text:
        return None
    end = parse_moment(recovered_text)
    if end is None:
        return f"恢复时刻「{recovered_text}」无法识别，请按 YYYY-MM-DD HH:MM 填写"
    start = parse_moment(occurred)
    if start is not None and end < start:
        return "恢复时刻早于发生时刻，违反「恢复时刻不得早于发生时刻」的登记规则，请核对后重新填写"
    return None


class FaultService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        overdue: bool | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        now = datetime.now()
        rows = [self._enrich(row, now) for row in store.rows(MODULE)]
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("故障编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if overdue is not None:
            rows = [row for row in rows if row["是否超期"] is overdue]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def summarize(self) -> dict[str, Any]:
        """处置时效汇总：与列表共用同一套超期口径，保证刷新后件数一致。"""
        now = datetime.now()
        rows = [self._enrich(row, now) for row in store.rows(MODULE)]
        summary: dict[str, Any] = {
            "总件数": len(rows),
            "超期件数": sum(1 for row in rows if row["是否超期"]),
            "超期上限小时": OVERDUE_LIMIT_HOURS,
        }
        for status in STATUS_ORDER + [MERGED_STATUS]:
            summary[status] = sum(1 for row in rows if row.get("status") == status)
        return summary

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._enrich(entry, datetime.now())

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, f"缺少必填字段：{'、'.join(missing)}"
        violation = recovery_rule_message(values.get("发生时刻"), values.get("恢复时刻"))
        if violation:
            return None, violation
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS + ["发生时刻", "影响要素", "处置人员", "恢复时刻"]:
            text = str(values.get(field) or "").strip()
            if text:
                entry[field] = text
        main = self._find_duplicate(entry)
        if main is not None:
            # 重复报障合并：保留自己的故障编号，挂到主故障上，影响要素与主故障对齐
            entry["status"] = MERGED_STATUS
            entry["故障状态"] = MERGED_STATUS
            entry["pending"] = False
            entry["abnormal"] = False
            entry["合并到"] = main.get("故障编号")
            entry["影响要素"] = main.get("影响要素") or entry.get("影响要素")
            rows.append(entry)
            return entry, (
                f"与 {main.get('故障编号')} 属同一站点同一故障现象的重复报障，已按重复报障合并；"
                f"影响要素对应为：{entry.get('影响要素') or '—'}"
            )
        entry["status"] = STATUS_ORDER[0]
        entry["故障状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, "故障记录已登记"

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"故障记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于故障处置可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        values = values or {}
        if action == "挂起故障":
            missing = [field for field in SUSPEND_REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
            if missing:
                return None, f"挂起条件不满足，缺少：{'、'.join(missing)}"
            entry["挂起原因"] = str(values.get("挂起原因")).strip()
            entry["挂起时刻"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        if action == "确认恢复":
            recovered = str(values.get("恢复时刻") or "").strip() or datetime.now().strftime("%Y-%m-%d %H:%M")
            violation = recovery_rule_message(entry.get("发生时刻"), recovered)
            if violation:
                return None, violation
            entry["恢复时刻"] = recovered
        entry["status"] = target
        entry["故障状态"] = target
        entry["pending"] = target in ("待派单", "处置中")
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"故障记录已{action}"

    def _enrich(self, row: dict[str, Any], now: datetime) -> dict[str, Any]:
        enriched = dict(row)
        enriched["处置时长"] = disposal_hours(row, now)
        enriched["是否超期"] = is_overdue(row, now)
        return enriched

    def _find_duplicate(self, candidate: dict[str, Any]) -> dict[str, Any] | None:
        """同站点、同现象、发生时刻相差在窗口内的未闭环故障，视为同一故障的重复报障。"""
        station = str(candidate.get("涉及站点") or "").strip()
        symptom = str(candidate.get("故障现象") or "").strip()
        moment = parse_moment(candidate.get("发生时刻"))
        if not station or not symptom or moment is None:
            return None
        for row in store.rows(MODULE):
            if row.get("status") in ("已恢复", MERGED_STATUS):
                continue  # 已恢复与已合并的记录不再作为合并目标
            if str(row.get("涉及站点") or "").strip() != station:
                continue
            if str(row.get("故障现象") or "").strip() != symptom:
                continue
            base = parse_moment(row.get("发生时刻"))
            if base is None:
                continue
            if abs((moment - base).total_seconds()) <= DUPLICATE_WINDOW_HOURS * 3600:
                return row
        return None
