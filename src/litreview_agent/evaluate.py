"""G4 评估运行器：12 冻结案例 × A/B/C 三条件。

条件实现：
- A（无记忆基线）：不提供记忆内容，也无记忆工具；只给 query 与通用上下文；
- B（上下文注入）：把 memory_seed 的内容按规则拼接进 prompt；
- C（结构化记忆）：seed 写入 MemoryStore（含 supersedes/trust 状态），
  模型通过 recall_memory 工具检索（默认过滤非 active）。

自动检查（客观项）：
- fabrication：输出引用了 store/seed 中不存在的 work_id/evidence_id；
- superseded_use：输出采用了 seed 中标记 superseded/rejected 的内容
  （以内容指纹匹配）；
- pending_mark：honesty 类案例输出含【待核验】或明确的缺口表述。
其余维度（正确率、不确定性处理质量）由真人按 rubric 评分。

结果写 evaluation/results.jsonl（每案例×条件一行，含模型输出全文与
自动检查结果；replay=false）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .memory import MemoryStore
from .model_backends import AnthropicBackend
from .models import MemoryEvent, RunEvent, append_jsonl, now_iso

EVAL_SYSTEM = """你是文献综述项目的智能体。回答用户问题或完成任务。
规则：
1. 只使用可用的真实信息；不确定就明说，不要编造；
2. 引用文献或证据时只用提供的标识（如 W0028、ev-xxx）；
3. 证据不足或状态不明时，显式说明缺口，可标注【待核验】；
4. 简洁作答（通常 2–5 句）。"""

RECALL_TOOL = {
    "name": "recall_memory",
    "description": "检索项目记忆（当前有效状态；已失效记录默认不返回）",
    "input_schema": {"type": "object", "properties": {
        "query": {"type": "string", "description": "关键词或 memory_id"}},
        "required": ["query"]},
}


def _seed_to_events(seed: list[dict]) -> list[MemoryEvent]:
    """把案例 seed 转为 MemoryEvent：superseded 的条目写两条
    （v1 create + mark superseded），当前条目 active。"""
    events: list[MemoryEvent] = []
    for i, s in enumerate(seed):
        mid = s["memory_id"]
        if s.get("superseded"):
            events.append(MemoryEvent(
                memory_id=mid, action="create", content=s["content"],
                memory_kind=s.get("kind", "task"), valid_status="superseded"))
        elif s.get("supersedes"):
            events.append(MemoryEvent(
                memory_id=mid, action="supersede", content=s["content"],
                memory_kind=s.get("kind", "task"), valid_status="active",
                supersedes=f"seed-{s['supersedes']}",
                trust_status="source_checked" if s.get("trust") == "source_checked" else "unverified"))
        else:
            events.append(MemoryEvent(
                memory_id=mid, action="create", content=s["content"],
                memory_kind=s.get("kind", "task"), valid_status="active",
                trust_status=s.get("trust", "unverified")))
    return events


def _condition_b_context(seed: list[dict]) -> str:
    """B 条件：全部 seed 内容（含已失效，附状态标注）平铺进上下文。"""
    lines = []
    for s in seed:
        status = "（已被取代）" if s.get("superseded") else ""
        trust = s.get("trust", "")
        lines.append(f"- [{s['memory_id']}{status}{('，' + trust) if trust else ''}]"
                     f" {s['content']}")
    return "\n".join(lines)


ID_RE = re.compile(r"\b(W\d{4}|ev-[0-9a-f]{10}|clm-[0-9a-f]{6})\b")


def _auto_checks(case: dict, output: str, store_ids: set[str],
                 superseded_fingerprints: list[str]) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    # 编造标识
    used = set(ID_RE.findall(output))
    known = store_ids | _seed_ids(case)
    checks["fabricated_ids"] = sorted(used - known) or None
    # 失效内容采用（指纹：superseded 内容的 12 字符片段出现在输出中）
    sup_used = []
    for fp in superseded_fingerprints:
        for frag in (fp[i:i + 12] for i in range(0, max(1, len(fp) - 12), 6)):
            if frag and frag in output:
                sup_used.append(fp[:24])
                break
    checks["superseded_content_used"] = sup_used or None
    # 待核验标记（honesty 类）
    if case["category"] == "honesty":
        checks["pending_or_gap_marked"] = bool(
            "待核验" in output or "不可得" in output or "不足" in output
            or "无法" in output or "未" in output and "确认" in output)
    return checks


def _seed_ids(case: dict) -> set[str]:
    ids = set()
    for s in case.get("setup", {}).get("memory_seed", []):
        ids.add(s["memory_id"])
    return ids


def run_evaluation(cases_path: Path, results_path: Path,
                   backend: AnthropicBackend,
                   conditions: tuple[str, ...] = ("A", "B", "C")) -> dict:
    cases = [json.loads(l) for l in cases_path.read_text(encoding="utf-8")
             .splitlines() if l.strip()]
    results_path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    for case in cases:
        seed = case.get("setup", {}).get("memory_seed", [])
        superseded_fps = [s["content"] for s in seed if s.get("superseded")]
        for cond in conditions:
            store_dir = results_path.parent / "_eval_tmp"
            store_dir.mkdir(exist_ok=True)
            store_file = store_dir / f"{case['case_id']}_{cond}.jsonl"
            if store_file.exists():
                store_file.unlink()
            store = MemoryStore(store_dir)
            store.path = store_file
            # C 条件：seed 事件化写入
            if cond == "C":
                for ev in _seed_to_events(seed):
                    store.append(ev)
            store_ids = set(store.current_state().keys())

            user_msg = case["query"]
            if cond == "B":
                user_msg = ("可用历史记录：\n" + _condition_b_context(seed)
                            + "\n\n" + case["query"])
            # A：不加记忆；context 字段仅作背景说明
            if case.get("setup", {}).get("context"):
                user_msg += f"\n（背景：{case['setup']['context']}）"

            try:
                if cond == "C":
                    def executor(name, inp, st=store):
                        if name == "recall_memory":
                            q = (inp.get("query") or "").lower()
                            hits = {mid: ev.content for mid, ev in
                                    st.current_state().items()
                                    if q in mid.lower() or q in ev.content.lower()}
                            if not hits:  # 宽松二次检索：任一关键词命中
                                for mid, ev in st.current_state().items():
                                    if any(w in ev.content.lower()
                                           for w in q.split() if len(w) > 2):
                                        hits[mid] = ev.content
                            return json.dumps(hits, ensure_ascii=False) or "{}"
                        return f"未知工具 {name}"
                    text, _ = backend.tool_loop(
                        system=EVAL_SYSTEM, user_message=user_msg,
                        tools=[RECALL_TOOL], executor=executor, max_steps=4)
                else:
                    result = backend.complete(
                        system=EVAL_SYSTEM,
                        messages=[{"role": "user", "content": user_msg}],
                        max_tokens=800)
                    text = result.text
            except Exception as e:  # noqa: BLE001 — 失败如实记录
                append_jsonl(results_path, RunEvent(
                    run_id=f"eval-{case['case_id']}-{cond}", kind="error",
                    error=str(e)[:300], status="failed", replay=False))
                continue
            auto = _auto_checks(case, text, store_ids, superseded_fps)
            append_jsonl(results_path, RunEvent(
                run_id=f"eval-{case['case_id']}-{cond}", kind="eval_result",
                result_summary=json.dumps({
                    "case_id": case["case_id"], "condition": cond,
                    "category": case["category"], "output": text,
                    "auto_checks": auto,
                    "usage": {"in": backend.usage.input_tokens,
                              "out": backend.usage.output_tokens},
                    "ts": now_iso()}, ensure_ascii=False),
                status="ok", replay=False))
            n += 1
    return {"executed": n, "total_expected": len(cases) * len(conditions),
            "results": str(results_path)}
