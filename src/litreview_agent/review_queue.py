"""人工核验包生成：按 EXECUTION_PLAN §5.4 组织待办，输出 Markdown。

层次：
1. 每项最终候选引用文献：身份核验 + 版本核验 + ≥1 条使用证据抽查；
2. 边界判定复核：纳入/排除的边缘案例（模型判定，须真人裁决）；
3. claims 复核：direct/synthesis 全部，含证据定位；
4. 优先级标注（引用概率高的工作优先）。

本工具只生成待办与材料指针，不预填"已通过"结论（reviews.jsonl 由真人
核验后写入）。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Claim, Evidence, read_jsonl
from .tools.dedup import distinct_works, load_papers


def generate_review_queue(data_dir: Path) -> dict[str, Any]:
    papers = load_papers(data_dir)
    works = distinct_works(papers)
    ev_path = data_dir / "evidence.jsonl"
    evidence = list(read_jsonl(ev_path, Evidence)) if ev_path.exists() else []
    cl_path = data_dir / "claims.jsonl"
    claims = list(read_jsonl(cl_path, Claim)) if cl_path.exists() else []

    ev_by_work: dict[str, list[Evidence]] = {}
    for e in evidence:  # type: ignore[arg-type]
        ev_by_work.setdefault(e.work_id, []).append(e)

    # 候选引用 = 核心阅读池成员（D-3 策略；core_pool.jsonl 为准）
    core_path = data_dir / "core_pool.jsonl"
    if core_path.exists():
        core_ids = {json.loads(l)["work_id"] for l in
                    core_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    else:
        core_ids = {wid for wid, recs in works.items()
                    if any(r.inclusion_status == "included" for r in recs)
                    and wid in ev_by_work}
    cited_pool = [wid for wid in core_ids if wid in ev_by_work or wid in works]
    # 优先级：更新与可靠性层 P0（用户策略：综述重点）
    prio = {"L3-更新遗忘": "P0", "L5-非恶意可靠性": "P0", "L6-安全投毒": "P0",
            "L4-评测": "P1", "L1-基础系统": "P1", "L2-组织检索": "P1",
            "L7-综述与边界": "P2"}
    # core_pool 的层信息
    layer_of = {}
    if core_path.exists():
        for l in core_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                rec = json.loads(l)
                layer_of[rec["work_id"]] = rec["layer"]

    lines = ["# 人工核验队列（真人任务）", "",
             "生成时间：" + _now() + "。本清单由核验包生成器从真实数据产生；",
             "所有条目状态为**待核验**。核验结果由成员写入 `data/reviews.jsonl`，",
             "格式见 `docs/protocol.md` §7；不要在本文件直接打勾——以 reviews.jsonl 为准。",
             ""]

    # ---- 1. 文献身份/版本/证据核验
    lines += ["## 1. 文献核验（核心阅读池：" + str(len(cited_pool)) + " 项）", "",
              "每项需要：① 身份核验（题名/作者/年份/venue/DOI 与正式记录一致）；",
              "② 版本核验（预印本 vs 正式版，主引用版本正确，证据页码绑定读取版本）；",
              "③ 抽查 ≥1 条使用证据（excerpt 与所指标记页是否逐字一致、interpretation 无过度引申）。",
              "",
              "| 优先级 | work | 层 | 题名（截断） | 年份 | 证据数 | 核验要点 |",
              "|---|---|---|---|---|---|---|"]
    for wid in sorted(cited_pool,
                      key=lambda w: (prio.get(layer_of.get(w, ""), "P2"), w)):
        recs = works[wid]
        p = next((r for r in recs if r.inclusion_status == "included"), recs[0])
        n_versions = len(recs)
        version_note = f"{n_versions} 版本记录" if n_versions > 1 else "单版本"
        ax = p.arxiv_id or ""
        layer = layer_of.get(wid, "?")
        lines.append(f"| {prio.get(layer, 'P2')} | {wid} | {layer[:12]} "
                     f"| {p.title[:56]} | {p.year or '?'} "
                     f"| {len(ev_by_work.get(wid, []))} | {version_note}"
                     f"{'；arXiv:' + ax if ax else ''} |")
    lines.append("")

    # ---- 2. 边界判定复核
    lines += ["## 2. 边界判定复核（模型判定，建议真人裁决）", ""]
    boundary = [(wid, recs) for wid, recs in works.items()
                if recs[0].reason and (
                    "out_of_scope" in recs[0].reason
                    or recs[0].inclusion_status == "pending")]
    for wid, recs in boundary[:60]:
        p = recs[0]
        status = p.inclusion_status
        lines.append(f"- **{wid}**（{status}）：{p.title[:70]} — "
                     f"理由：{(p.reason or '')[:90]}")
    if len(boundary) > 60:
        lines.append(f"- …另有 {len(boundary) - 60} 项见 papers.jsonl（reason 字段）")
    lines.append("")

    # ---- 3. claims 复核
    lines += ["## 3. Claims 复核（当前 " + str(len(claims)) + " 条）", "",
              "每条需回到证据定位核对：原文是否支持该陈述及其范围；",
              "synthesis 类需核对全部引用证据与综合理由。", ""]
    for c in claims:  # type: ignore[arg-type]
        lines.append(f"- **{c.claim_id}** [{c.claim_type}] {c.section or '?'}："
                     f"{c.text[:100]}…")
        for eid in c.evidence_ids:
            ev = next((e for e in evidence if e.evidence_id == eid), None)  # type: ignore[arg-type]
            if ev:
                lines.append(f"  - {eid}: {ev.work_id} {ev.locator}")
    lines.append("")

    # ---- 4. 汇总
    total_tasks = len(cited_pool) + len(claims) + min(len(boundary), 60)
    lines += ["## 4. 汇总", "",
              f"- 文献核验任务：{len(cited_pool)} 项（P0 优先：更新与可靠性分支）",
              f"- 边界复核：{min(len(boundary), 60)} 项",
              f"- Claims 复核：{len(claims)} 条",
              f"- 合计约 {total_tasks} 个核验任务；建议三人按 P0→P1→P2 分摊，",
              f"  同一人整理的关键部分由另一成员复核（EXECUTION_PLAN §5.4）。",
              ""]

    out = data_dir.parent / "docs" / "human_review_queue.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"cited_pool": len(cited_pool), "boundary": len(boundary),
            "claims": len(claims), "path": str(out)}


def _branch(works: dict, wid: str) -> str:
    recs = works.get(wid) or []
    for r in recs:
        if r.inclusion_status == "included" and r.reason:
            return r.reason.replace("branch=", "").split("|")[0].strip()
    return "?"


def _now() -> str:
    from .models import now_iso
    return now_iso()
