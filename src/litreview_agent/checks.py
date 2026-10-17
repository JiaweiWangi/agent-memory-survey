"""检查器：引用解析、证据支持、语料计数、记忆不变量。

G2 必要检查（EXECUTION_PLAN §7.5 的核心子集，G4 扩展）：
- 草稿中每个 \\cite{Wxxxx} 都有该 work 的有效证据；
- 无证据的陈述被标【待核验】（模型标注 + 检查器复核）；
- claims 引用的 evidence_id 均存在。
"""

from __future__ import annotations

import re
from typing import Optional

from .models import Claim, Evidence
from .tools.dedup import distinct_works

CITE_RE = re.compile(r"\\cite\{([^}]+)\}")
PENDING_MARK = "【待核验】"


def check_draft_citations(draft: str, evidence: list[Evidence],
                          claims: list[Claim], works: dict) -> str:
    """检查草稿引用：返回人可读报告（含错误与警告）。"""
    ev_works = {e.work_id for e in evidence}
    ev_ids = {e.evidence_id for e in evidence}
    lines = ["# 草稿引用检查报告", ""]

    cites = CITE_RE.findall(draft)
    unknown, no_evidence, ok = [], [], []
    for group in cites:
        for wid in [w.strip() for w in group.split(",")]:
            if wid not in works:
                unknown.append(wid)
            elif wid not in ev_works:
                no_evidence.append(wid)
            else:
                ok.append(wid)
    lines.append(f"- 引用总数：{len(cites)}（去重 {len(set(cites))}）")
    lines.append(f"- 有证据支撑的 work：{len(set(ok))}")
    if unknown:
        lines.append(f"- [错误] 不存在的 work_id：{sorted(set(unknown))}")
    if no_evidence:
        lines.append(f"- [错误] 无证据的引用（不得出现在定稿）：{sorted(set(no_evidence))}")

    # claims 证据存在性
    bad_claims = []
    for c in claims:
        missing_ev = [i for i in c.evidence_ids if i not in ev_ids]
        if missing_ev:
            bad_claims.append(f"{c.claim_id}（缺 {missing_ev}）")
    if bad_claims:
        lines.append(f"- [错误] 引用了不存在证据的 claims：{bad_claims}")

    # 【待核验】标记统计（模型诚实性输出）
    n_pending = draft.count(PENDING_MARK)
    lines.append(f"- 【待核验】标记数：{n_pending}")

    # 逐句粗查：句尾有 cite 但句内含待核验矛盾（同一句两者都有）
    conflicts = 0
    for sent in re.split(r"(?<=[。；])", draft):
        if CITE_RE.search(sent) and PENDING_MARK in sent:
            conflicts += 1
    if conflicts:
        lines.append(f"- [警告] 同句同时有引用与待核验标记：{conflicts} 处（请人工判断）")

    if not unknown and not no_evidence and not bad_claims:
        lines.append("- 结论：引用检查通过。")
    else:
        lines.append("- 结论：存在错误，需修正后重查。")
    return "\n".join(lines)


def count_distinct_cited_works(draft: str) -> int:
    """草稿中实际引用的独立 work_id 数（硬性 ≥30 的统计基础）。"""
    ids: set[str] = set()
    for group in CITE_RE.findall(draft):
        for wid in (w.strip() for w in group.split(",")):
            if wid.startswith("W"):
                ids.add(wid)
    return len(ids)
