"""G3 筛选：题名+摘要批量模型筛选，带稳定理由码与分支标注。

流程：
1. 启发式预排序（相关度评分）限定送模型筛选的数量；
2. 批量模型筛选（每批 ~20 项，严格 JSON 输出）；
3. 结果写回 papers.jsonl（追加事件式更新，inclusion_status + reason）；
4. 汇总计数（含失败批如实报告）。

理由码（docs/protocol.md §4）：out_of_scope / no_memory_mechanism /
non_academic / duplicate_version / fulltext_unavailable / insufficient_content
+ include 时的分支标注。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .model_backends import AnthropicBackend, PROMPT_VERSION
from .models import RunEvent, append_jsonl, now_iso
from .tools.dedup import (append_paper_update, arxiv_id_from_doi,
                          distinct_works, load_papers)

# 启发式相关度：题名权重高于摘要
TITLE_KW = ["memory", "memgpt", "remember", "long-term", "lifelong",
            "multi-session", "cross-session", "conversation", "forget",
            "forgetting", "retrieval-augmented", "experience"]
STRONG_KW = ["agent memory", "memory update", "memory poison", "memory edit",
             "knowledge update", "temporal knowledge", "memory benchmark",
             "long-term memory", "persistent memory", "episodic",
             "procedural", "memory consolidation", "memory survey"]
ABSTRACT_KW = ["memory", "agent", "session", "forget", "update", "benchmark"]

SCREEN_PROMPT = """你是文献综述筛选员。研究主题：大模型（LLM）智能体的长期记忆——
跨会话外部记忆的组织、更新与可靠性评测。

研究问题（RQ）：
- RQ1 定义与边界（vs 长上下文 / 静态 RAG / 参数知识）
- RQ2 组织与使用（写入、结构化、检索、成本）
- RQ3 更新与遗忘（信息变化、时间条件、冲突、删除）
- RQ4 可靠性（错误信息进入记忆、投毒、来源追踪、防御）
- RQ5 评测（基准、指标、公平比较）

纳入标准：以 LLM 为核心、跨会话/跨任务保存并复用外部记忆的系统研究；
方法论文、实证分析、评测基准、高质量综述均纳入。时间 2020 至今为主，
2020 前的重要理论/方法（如记忆认知理论、经典遗忘机制）可作背景纳入。

排除理由码（ mutually exclusive ）：
- out_of_scope：与 LLM 记忆无关（如纯 RAG 检索质量、模型训练、其他领域记忆）
- no_memory_mechanism：智能体研究但无清晰记忆机制或记忆评测
- non_academic：非学术文献
- duplicate_version：与列表内其他项为同一研究（指出重复的 work_id）
- uncertain：无法从题名摘要判断（正文筛选阶段再定）

对每项输出 JSON：{"work_id": ..., "decision": "include|exclude|uncertain",
"reason_code": "理由码或 include 时填主要 RQ，如 RQ3",
"branch": "organize|update|reliability|eval|survey|background",
"rq_tags": ["RQ2",...], "note": "一句话理由（中文）"}

- include 时 branch 必填：organize=组织表示, update=更新遗忘, reliability=可靠性与安全,
  eval=评测基准, survey=综述视角, background=早期背景。
- 宁可 uncertain 不要猜；exclude 必须给理由码。
只输出 JSON 数组，不要其他文字。

候选列表：
"""


def _relevance_score(title: str, abstract: str | None) -> int:
    t = (title or "").lower()
    a = (abstract or "").lower()
    score = 0
    score += 3 * sum(1 for k in TITLE_KW if k in t)
    score += 5 * sum(1 for k in STRONG_KW if k in t)
    score += sum(1 for k in ABSTRACT_KW if k in a[:600])
    return score


def _has_fulltext_channel(recs: list) -> bool:
    return any(r.fulltext_status in ("pdf_ok", "html_ok")
               or r.arxiv_id or arxiv_id_from_doi(r.doi) for r in recs)


def run_screening(data_dir: Path, backend: AnthropicBackend,
                  max_candidates: int = 150, batch_size: int = 20,
                  focus_work_ids: list[str] | None = None) -> dict[str, Any]:
    """批量筛选；返回汇总。已筛过的（included/excluded）跳过。"""
    run_id = f"scr-{now_iso()[11:13]}{now_iso()[14:16]}{now_iso()[17:19]}"
    events_path = data_dir.parent / "runs" / run_id / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)

    def log(**kw):
        append_jsonl(events_path, RunEvent(run_id=run_id, **kw))

    papers = load_papers(data_dir)
    works = distinct_works(papers)
    log(kind="start", decision_reason=f"筛选 {len(works)} 项独立研究")

    # 待筛池：无最终状态的 work（candidate/pending）
    abstracts = _load_abstracts(data_dir)
    pending = []
    for wid, recs in works.items():
        if recs[0].inclusion_status in ("included", "excluded"):
            continue
        if focus_work_ids and wid not in focus_work_ids:
            continue
        title = recs[0].title or ""
        if not title:
            continue
        pending.append((wid, title, abstracts.get(wid, ""),
                        _has_fulltext_channel(recs)))
    # 排序：有正文通道优先，其次相关度
    pending.sort(key=lambda x: (not x[3], -_relevance_score(x[1], x[2])))
    pending = pending[:max_candidates]
    log(kind="decision", decision_reason=f"送筛 {len(pending)} 项"
        f"（启发式预排序：正文通道优先 + 相关度）")

    stats = {"screened": 0, "included": 0, "excluded": 0, "uncertain": 0,
             "batch_failures": 0, "parse_failures": 0}
    branch_counts: dict[str, int] = {}
    for i in range(0, len(pending), batch_size):
        batch = pending[i:i + batch_size]
        listing = "\n".join(
            f"- work_id={wid} | {title} | 摘要: {ab[:300] or '（无）'}"
            for wid, title, ab, _ in batch)
        try:
            result = backend.complete(
                system=SCREEN_PROMPT, messages=[{"role": "user", "content": listing}],
                max_tokens=4000)
        except Exception as e:  # noqa: BLE001 — 批失败如实记录继续
            stats["batch_failures"] += 1
            log(kind="error", tool="model_call", error=str(e)[:300],
                status="failed")
            continue
        items = _parse_json_array(result.text)
        if items is None:
            stats["parse_failures"] += 1
            log(kind="error", tool="parse", error=result.text[:300],
                status="failed")
            continue
        by_wid = {wid: (t, ab) for wid, t, ab, _ in batch}
        for it in items:
            wid = it.get("work_id")
            if wid not in by_wid:
                continue  # 模型编造的 id，丢弃
            decision = it.get("decision")
            if decision not in ("include", "exclude", "uncertain"):
                decision = "uncertain"
            status_map = {"include": "included", "exclude": "excluded",
                          "uncertain": "pending"}
            recs = works[wid]
            p = recs[0].model_copy(deep=True)
            p.inclusion_status = status_map[decision]
            p.reason = (f"{it.get('reason_code', '')} | {it.get('note', '')}"
                        if decision != "include"
                        else f"branch={it.get('branch', '?')} | {it.get('note', '')}")
            if it.get("rq_tags"):
                p.rq_tags = [r for r in it["rq_tags"] if str(r).startswith("RQ")]
            p.checked_at = now_iso()
            append_paper_update(data_dir, p)
            stats["screened"] += 1
            stats[f"{decision}d" if decision != "uncertain" else "uncertain"] += 1
            if decision == "include":
                branch_counts[it.get("branch", "?")] = \
                    branch_counts.get(it.get("branch", "?"), 0) + 1
        log(kind="tool_result", tool="screen_batch",
            result_summary=f"批 {i // batch_size + 1}: {len(items)} 项判定",
            status="ok")
    log(kind="end", result_summary=json.dumps(
        {**stats, "branches": branch_counts}, ensure_ascii=False))
    return {**stats, "branches": branch_counts, "run_id": run_id}


def _parse_json_array(text: str) -> list[dict] | None:
    """从模型输出提取 JSON 数组（容忍 markdown 代码围栏）。"""
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        return None


def _load_abstracts(data_dir: Path) -> dict[str, str]:
    """读取 work_id → 摘要映射（data/abstracts.jsonl；缺失时从 HTTP
    缓存的 OpenAlex 响应回填一次并写回）。"""
    path = data_dir / "abstracts.jsonl"
    out: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                rec = json.loads(line)
                out[rec["work_id"]] = rec.get("abstract") or ""
            except (json.JSONDecodeError, KeyError):
                continue
    if not out:
        out = rebuild_abstracts_from_cache(data_dir)
    return out


def rebuild_abstracts_from_cache(data_dir: Path) -> dict[str, str]:
    """从缓存的 OpenAlex 响应重建摘要（一次性回填，写回 abstracts.jsonl）。"""
    from .tools.dedup import _norm_title
    from .tools.search import _oa_abstract

    cache_dir = data_dir / "derived" / "http_cache"
    works = distinct_works(load_papers(data_dir))
    title_map = {_norm_title(recs[0].title): wid
                 for wid, recs in works.items() if recs[0].title}
    out: dict[str, str] = {}
    for f in sorted(cache_dir.glob("*.txt")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for w in data.get("results") or []:
            wid = title_map.get(_norm_title(w.get("title") or ""))
            if wid and wid not in out:
                ab = _oa_abstract(w)
                if ab:
                    out[wid] = ab
    path = data_dir / "abstracts.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        for wid, ab in out.items():
            fh.write(json.dumps({"work_id": wid, "abstract": ab},
                                ensure_ascii=False) + "\n")
    return out


def load_included(data_dir: Path) -> dict[str, list]:
    works = distinct_works(load_papers(data_dir))
    return {wid: recs for wid, recs in works.items()
            if any(r.inclusion_status == "included" for r in recs)}
