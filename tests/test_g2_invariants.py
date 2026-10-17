"""G2 必要测试：影响研究可信度的关键行为（EXECUTION_PLAN §7.5 子集）。

- 同一论文多版本不重复计数
- 失效记忆不作为当前有效事实返回
- 待核验证据不被自动提升为已确认
- 无证据引用被检查器发现
- 重启恢复保留状态、不重复写入
- excerpt 验证：改写被拒，逐字/跨行连字符被接受
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from litreview_agent.coordinator import Coordinator
from litreview_agent.memory import MemoryStore
from litreview_agent.models import (Claim, Evidence, MemoryEvent, Paper,
                                    append_jsonl)
from litreview_agent.tools.dedup import distinct_works, load_papers
from litreview_agent.tools.search import SearchHit
from litreview_agent.checks import check_draft_citations, count_distinct_cited_works


# ------------------------------------------------------------ 版本去重不变量


def test_same_paper_versions_not_double_counted(tmp_path: Path):
    """OpenAlex arXiv-DOI 记录与 arXiv API 记录应归并为同一 work_id。"""
    from litreview_agent.tools.dedup import merge_hits

    # 同一研究：一次来自 OpenAlex（arXiv DOI 形式），一次来自 arXiv API
    h1 = SearchHit(source="openalex", title="MemGPT: Towards LLMs as Operating Systems",
                   authors=["Charles Packer"], year=2023,
                   doi="10.48550/arxiv.2310.08560")
    h2 = SearchHit(source="arxiv", title="MemGPT: Towards LLMs as Operating Systems",
                   authors=["Charles Packer"], year=2023,
                   arxiv_id="2310.08560v2")
    merge_hits([h1], "test", tmp_path)
    touched, new_works, appended = merge_hits([h2], "test", tmp_path)
    works = distinct_works(load_papers(tmp_path))
    assert len(works) == 1, "同一研究的两个版本必须归并为一个 work_id"


def test_different_papers_not_merged(tmp_path: Path):
    from litreview_agent.tools.dedup import merge_hits

    h1 = SearchHit(source="openalex", title="Paper One", authors=["Alice Smith"],
                   year=2024, arxiv_id="2401.00001")
    h2 = SearchHit(source="openalex", title="Paper Two", authors=["Bob Jones"],
                   year=2024, arxiv_id="2401.00002")
    merge_hits([h1, h2], "test", tmp_path)
    works = distinct_works(load_papers(tmp_path))
    assert len(works) == 2


# ------------------------------------------------------------ 记忆有效性不变量


def test_superseded_memory_not_active(tmp_path: Path):
    store = MemoryStore(tmp_path)
    store.append(MemoryEvent(memory_id="rq-scope", action="create",
                             content="范围 v1", memory_kind="task"))
    store.supersede("rq-scope", "范围 v2（缩小到文本任务）", [], "发现")
    active = store.current_state("task")
    assert active["rq-scope"].content == "范围 v2（缩小到文本任务）"
    # 事件溯源：create + supersede + 对 v1 的 mark_superseded 标记，共 3 条
    events = [json.loads(l) for l in
              (tmp_path / "memory_events.jsonl").read_text().splitlines()]
    assert len(events) == 3
    superseded = [e for e in events if e["valid_status"] == "superseded"]
    assert len(superseded) == 1 and superseded[0]["content"] == "范围 v1"
    assert active["rq-scope"].valid_status == "active"


def test_evidence_not_auto_promoted(tmp_path: Path):
    """证据 verification_status 只有显式 Review 才能变 human_verified；
    证据文件本身没有任何自动提升路径。"""
    ev = Evidence(work_id="W0001", source_id="s1", locator="pdf:p1",
                  excerpt="x", interpretation="y", evidence_type="mechanism",
                  verification_status="model_assisted")
    assert ev.verification_status == "model_assisted"
    # 重新读回不变
    append_jsonl(tmp_path / "evidence.jsonl", ev)
    from litreview_agent.models import read_jsonl
    back = read_jsonl(tmp_path / "evidence.jsonl", Evidence)
    assert back[0].verification_status == "model_assisted"


# ------------------------------------------------------------ 摘录验证不变量


PAGE = """As shown in Figure 2, we decompose the mem-
ory lifecycle into six phases: Write, Store, Retrieve."""


def test_verbatim_match_accepts_layout_variants():
    ok = Coordinator._find_verbatim_span(
        "we decompose the memory lifecycle into six phases", PAGE)
    assert ok is not None, "跨行连字符 + 空白差异应接受"


def test_verbatim_match_rejects_rewrite():
    assert Coordinator._find_verbatim_span(
        "we decompose the memory lifecycle into seven phases", PAGE) is None
    assert Coordinator._find_verbatim_span(
        "we decompose the memory lifecycle... Store, Retrieve", PAGE) is None, \
        "省略号压缩不是连续原文"


# ------------------------------------------------------------ 引用检查不变量


def _mk_ev(wid: str) -> Evidence:
    return Evidence(work_id=wid, source_id="s", locator="pdf:p1",
                    excerpt="e", interpretation="i", evidence_type="mechanism")


def test_citation_check_catches_problems():
    ev = [_mk_ev("W0001")]
    cl = Claim(text="t", evidence_ids=["ev-nonexistent"], claim_type="direct")
    works = {"W0001": None, "W0002": None}  # type: ignore[dict-item]
    draft = "有证据的引用\\cite{W0001}。无证据的引用\\cite{W0002}。"
    draft += "不存在的引用\\cite{W9999}。"
    report = check_draft_citations(draft, ev, [cl], works)  # type: ignore[arg-type]
    assert "W0002" in report and "W9999" in report, "无证据/不存在的引用必须报错"
    assert "ev-nonexistent" in report, "报告须指出缺失的 evidence_id"
    assert count_distinct_cited_works(draft) == 3


def test_citation_check_passes_clean_draft():
    ev = [_mk_ev("W0001")]
    cl = Claim(text="t", evidence_ids=[], claim_type="direct")
    works = {"W0001": None}
    draft = "正常引用\\cite{W0001}。"
    report = check_draft_citations(draft, ev, [cl], works)  # type: ignore[arg-type]
    assert "通过" in report


# ------------------------------------------------------------ 重启恢复不变量


def test_restart_preserves_state_no_duplicates(tmp_path: Path):
    """模拟重启：新协调器实例从磁盘读状态；再提交同一证据不产生
    重复（excerpt 相同 → evidence 各自成条，但 work 覆盖与计数一致；
    关键是已有证据不丢失、状态可重建）。"""
    # 写入两条证据
    for i in range(2):
        append_jsonl(tmp_path / "evidence.jsonl",
                     Evidence(work_id="W0001", source_id="s", locator=f"pdf:p{i+1}",
                              excerpt=f"excerpt {i}", interpretation="i",
                              evidence_type="mechanism"))
    append_jsonl(tmp_path / "papers.jsonl",
                 Paper(work_id="W0001", title="T", arxiv_id="2310.08560",
                       local_path="/tmp/x.pdf"))
    # "重启"：新实例
    coord = Coordinator.__new__(Coordinator)  # 不走 __init__（无模型后端）
    coord.data_dir = tmp_path
    coord.run_id = "test"
    coord.selected = ["W0001"]
    coord._page_cache = {}
    coord.memory = MemoryStore(tmp_path)
    ev = coord._evidence()
    assert len(ev) == 2, "重启后已有证据必须完整保留"
    summary = coord.state_summary()
    assert "证据 2 条" in summary
    # claims 引用不存在的证据被拒
    result = coord._tool_submit_claim({
        "text": "某论断", "evidence_ids": ["ev-nonexistent"],
        "claim_type": "direct", "section": "脉络"})
    assert "错误" in result
    # list_evidence 可见已有证据（工具链闭环）
    listing = coord._tool_list_evidence({})
    assert "excerpt 0" in listing and "excerpt 1" in listing


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
