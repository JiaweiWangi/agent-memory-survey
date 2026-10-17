"""研究状态记忆：追加事件 + supersedes 链 + 双状态（valid/trust）。

四类记忆（EXECUTION_PLAN §6.4）：
- task：研究范围、检索协议、进度、待办
- evidence：论文原文位置、摘录、版本与解释
- decision：人工意见、筛选原因、修改理由
- experience：流程经验（模型生成，默认未经事实核验）

不变量（tests 验证）：
- 默认检索过滤 valid_status != active；
- supersede 保留历史（被取代事件仍在文件中，状态置 superseded）；
- 草稿类记忆不得自动升级 trust_status。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .models import MemoryEvent, append_jsonl, read_jsonl


class MemoryStore:
    def __init__(self, data_dir: Path):
        self.path = data_dir / "memory_events.jsonl"
        self.data_dir = data_dir

    def _events(self) -> list[MemoryEvent]:
        if not self.path.exists():
            return []
        return list(read_jsonl(self.path, MemoryEvent))  # type: ignore[arg-type]

    def append(self, event: MemoryEvent) -> None:
        append_jsonl(self.path, event)

    def current_state(self, memory_kind: Optional[str] = None) -> dict[str, MemoryEvent]:
        """每个 memory_id 的当前有效事件（active 优先，按时间最新）。"""
        latest: dict[str, MemoryEvent] = {}
        for ev in self._events():
            if memory_kind and ev.memory_kind != memory_kind:
                continue
            prev = latest.get(ev.memory_id)
            # active 状态覆盖 superseded/rejected/disputed；同类状态取最新
            if prev is None or ev.valid_status == "active" or prev.valid_status != "active":
                if ev.valid_status == "active" or prev is None or prev.valid_status != "active":
                    latest[ev.memory_id] = ev
        return latest

    def supersede(self, memory_id: str, new_content: str,
                  source_ids: list[str], reason: str,
                  memory_kind: str = "task") -> MemoryEvent:
        """用新事件取代某记忆条目；旧事件状态改为 superseded（追加记录）。"""
        current = self.current_state().get(memory_id)
        new_ev = MemoryEvent(
            memory_id=memory_id, action="supersede", content=new_content,
            source_ids=source_ids, memory_kind=memory_kind,
            supersedes=current.event_id if current else None,
            valid_status="active",
            trust_status=(current.trust_status if current else "unverified"),
            notes=reason)
        self.append(new_ev)
        if current:
            self.append(current.model_copy(update={
                "action": "mark_superseded", "valid_status": "superseded",
                "valid_to": new_ev.created_at,
                "notes": f"被 {new_ev.event_id} 取代"}))
        return new_ev

    def task_facts(self) -> dict[str, str]:
        """任务记忆的当前快照（memory_id → content）。"""
        return {mid: ev.content for mid, ev in
                self.current_state("task").items()}
