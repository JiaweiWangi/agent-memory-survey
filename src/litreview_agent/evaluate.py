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
    # 编造标识：已知 = 记忆 store + seed + 案例 query/context 中出现的标识
    # （query 里给出的标识（如任务指令中的 W0002）是模型合法可见的输入）
    given_text = case.get("query", "") + " " + str(case.get("setup", {}).get("context", ""))
    known = store_ids | _seed_ids(case) | set(ID_RE.findall(given_text))
    used = set(ID_RE.findall(output))
    checks["fabricated_ids"] = sorted(used - known) or None
    # 失效内容采用（指纹窗口匹配）。精度注意：
    # - 跳过前 2 个窗口（实体名区域——正常提及论文标题会误命中）；
    # - 拒绝性提及（"不使用 v1 的 X"）同样命中，自动标记解释为
    #   "需人工复核"，不直接判负（rubric 明示语义由真人判定）。
    sup_used = []
    for fp in superseded_fingerprints:
        windows = [fp[i:i + 12] for i in range(12, max(13, len(fp) - 12), 6)]
        if any(frag and frag in output for frag in windows):
            sup_used.append(fp[:24])
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


def _recall_from_store(store, query: str, top_k: int = 3) -> dict[str, dict]:
    """记忆检索：memory_id 精确命中或内容相关度（字符覆盖 + 2-gram）。

    子串匹配对中文失效（"研究范围" ≠ "综述范围"），用字符级评分。
    返回 top_k 及分数——低分结果交给模型判断相关性（评估案例的记忆库
    只有 2–4 条，空结果会导致"查无记录"的错误结论，比低分结果更有害）。
    """
    q = (query or "").lower().strip()
    active = store.current_state()
    if not q or not active:
        return {}
    if q in active:  # memory_id 精确命中
        return {q: {"score": 1.0, "content": active[q].content}}

    def score(content: str) -> float:
        c = content.lower()
        chars = [ch for ch in q if not ch.isspace()]
        if not chars:
            return 0.0
        cover = sum(1 for ch in chars if ch in c) / len(chars)
        bigrams = [q[i:i + 2] for i in range(len(q) - 1) if not q[i:i+2].isspace()]
        bg = (sum(1 for b in bigrams if b in c) / len(bigrams)) if bigrams else 0.0
        return round(0.5 * cover + 0.5 * bg, 3)

    scored = sorted(((score(ev.content), mid, ev.content)
                     for mid, ev in active.items()), reverse=True)
    return {mid: {"score": s, "content": content}
            for s, mid, content in scored[:top_k]}


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
                            hits = _recall_from_store(st, inp.get("query", ""))
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


# ===================================================== 两阶段 multirun 评估

WRITE_TOOL = {
    "name": "write_memory",
    "description": "把信息写入项目记忆（持久化，跨会话保留）",
    "input_schema": {"type": "object", "properties": {
        "key": {"type": "string", "description": "记忆条目标识，如 stats-summary"},
        "content": {"type": "string", "description": "要记住的内容"},
        "kind": {"type": "string", "description": "task/evidence/decision"}},
        "required": ["key", "content"]},
}

MULTIRUN_CASES = {
    "M4-01": {
        "phase1": ("运行1（文献综述项目）：当前证据库统计——核心池 40 篇，其中 29 篇已有证据；"
                   "各 RQ 证据数：RQ3 共 20 条，RQ4 共 15 条，RQ5 共 12 条。"
                   "请把这份统计摘要存入项目记忆（key=stats-summary），然后简述已存内容。"),
        "phase2": ("运行2（新会话启动，上一次运行已结束）：报告上次运行存入的统计结果"
                   "（核心池规模与各 RQ 证据数），并指出证据最少的 RQ 作为下一步处理重点。"),
        "expect": ["40", "RQ5"],          # 必须含的关键事实
        "expect_not": [],                  # 不得出现
    },
    "M4-02": {
        "phase1": ("运行1：你刚完成论文 W0002 的证据提取（新增 3 条证据）。"
                   "请记录任务进度到项目记忆（key=paper-queue）：已完成 W0002，"
                   "下一个待处理论文是 W0006。"),
        "phase2": ("运行2（新会话启动）：继续文献处理工作。上一篇处理完的论文是哪篇？"
                   "接下来应该处理哪篇？"),
        "expect": ["W0002", "W0006"],
        "expect_not": [],
    },
    "M4-03": {
        "phase1": ("运行1：登记了两条 claims 到项目记忆（key=claims-eval）："
                   "claim-1：LoCoMo 是超长期对话记忆基准（ACL 2024）；"
                   "claim-2：LongMemEval 定义了长期记忆的五能力维度。请存入。"),
        "phase2": ("运行2（新会话启动）：基于已登记的 claims，写一句评测章节的草稿，"
                   "须同时涉及两个基准（LoCoMo 与 LongMemEval），并注明所依据的 claim。"),
        "expect": ["LoCoMo", "LongMemEval"],
        "expect_not": [],
    },
}


def run_multirun_eval(results_path: Path, store_dir: Path,
                      backend: AnthropicBackend) -> dict:
    """真实两阶段跨运行评估：阶段1写入持久化 → 新实例 → 阶段2恢复。

    - C：阶段1 用 write_memory 工具写入 MemoryStore 文件；阶段2 新开
      MemoryStore 实例（同一文件=重启后状态），用 recall_memory 检索；
    - B：阶段2 把阶段1的输出原文注入上下文（上下文注入基线）；
    - A：阶段2 不提供任何阶段1信息（无记忆基线）。
    任务完成 = 阶段2输出含全部 expect 关键事实（自动判定）。
    """
    import shutil

    results_path.parent.mkdir(parents=True, exist_ok=True)
    n_done = 0
    for cid, spec in MULTIRUN_CASES.items():
        for cond in ("A", "B", "C"):
            store_file = store_dir / f"{cid}_{cond}.jsonl"
            if store_file.exists():
                store_file.unlink()  # 每案例×条件全新状态
            store_dir.mkdir(parents=True, exist_ok=True)
            store = MemoryStore(store_dir)
            store.path = store_file

            # ---- 阶段 1（新运行实例）----
            if cond == "C":
                def w_exec(name, inp, st=store):
                    if name == "write_memory":
                        st.append(MemoryEvent(
                            memory_id=inp["key"], action="create",
                            content=inp["content"],
                            memory_kind=inp.get("kind", "task")))
                        return f"已写入 {inp['key']}"
                    if name == "recall_memory":
                        return json.dumps(_recall_from_store(st, inp.get("query", "")),
                                          ensure_ascii=False)
                    return f"未知工具 {name}"
                p1_out, _ = backend.tool_loop(
                    system=EVAL_SYSTEM,
                    user_message=spec["phase1"] + "（使用 write_memory 工具持久化）",
                    tools=[WRITE_TOOL, RECALL_TOOL], executor=w_exec, max_steps=4)
            else:
                r1 = backend.complete(
                    system=EVAL_SYSTEM,
                    messages=[{"role": "user", "content": spec["phase1"]}],
                    max_tokens=600)
                p1_out = r1.text

            # ---- 阶段 2（新实例：C 重新打开同一 store 文件 = 重启）----
            store2 = MemoryStore(store_dir)          # 新实例
            store2.path = store_file                  # 同一持久化文件
            p2_msg = spec["phase2"]
            if cond == "B":
                p2_msg = ("上次运行的输出记录：\n" + p1_out[:1500]
                          + "\n\n" + spec["phase2"])
            if cond == "C":
                def r_exec(name, inp, st=store2):
                    if name == "recall_memory":
                        return json.dumps(_recall_from_store(st, inp.get("query", "")),
                                          ensure_ascii=False)
                    return f"未知工具 {name}"
                p2_out, _ = backend.tool_loop(
                    system=EVAL_SYSTEM, user_message=p2_msg,
                    tools=[RECALL_TOOL], executor=r_exec, max_steps=4)
            else:
                r2 = backend.complete(
                    system=EVAL_SYSTEM,
                    messages=[{"role": "user", "content": p2_msg}],
                    max_tokens=600)
                p2_out = r2.text

            # ---- 任务完成判定（关键事实）----
            missing = [e for e in spec["expect"] if e not in p2_out]
            bad = [x for x in spec["expect_not"] if x in p2_out]
            completed = not missing and not bad
            append_jsonl(results_path, RunEvent(
                run_id=f"eval-{cid}-{cond}", kind="eval_result",
                result_summary=json.dumps({
                    "case_id": cid, "condition": cond, "category": "multirun",
                    "output": f"[阶段1]\n{p1_out[:400]}\n[阶段2]\n{p2_out[:600]}",
                    "phase2_output": p2_out[:800],
                    "auto_checks": {
                        "task_completed": completed,
                        "missing_facts": missing or None,
                        "forbidden_present": bad or None,
                    },
                    "usage": {"in": backend.usage.input_tokens,
                              "out": backend.usage.output_tokens},
                    "ts": now_iso(), "design": "two_phase_v2"},
                ensure_ascii=False),
                status="ok", replay=False))
            n_done += 1
            print(f"  {cid}/{cond}: {'完成' if completed else '未完成' + str(missing)}")
    return {"executed": n_done}
