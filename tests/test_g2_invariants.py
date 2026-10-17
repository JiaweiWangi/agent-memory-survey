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


# ------------------------------------------------------------ G4 评估组件测试


def test_eval_seed_supersede_events():
    """评估 seed 转事件：superseded 条目不得成为 active。"""
    from litreview_agent.evaluate import _seed_to_events
    from litreview_agent.memory import MemoryStore
    import tempfile
    seed = [
        {"memory_id": "v1", "content": "旧规则", "kind": "task", "superseded": True},
        {"memory_id": "v2", "content": "新规则", "kind": "task", "supersedes": "v1"},
    ]
    evs = _seed_to_events(seed)
    with tempfile.TemporaryDirectory() as td:
        store = MemoryStore(Path(td))
        for e in evs:
            if e.memory_id == "v1":
                store.append(e)
        active = store.current_state()
        assert "v1" not in active, "superseded 条目不得出现在当前有效状态"


def test_eval_auto_checks_fabrication():
    """编造标识检查：输出引用不存在的 W0999 应被抓。"""
    from litreview_agent.evaluate import _auto_checks
    case = {"category": "recovery",
            "setup": {"memory_seed": [{"memory_id": "m1", "content": "x"}]}}
    out = "根据 W0002 与 ev-deadbeef01 的记录……"
    checks = _auto_checks(case, out, set(), [])
    assert checks["fabricated_ids"], "编造标识必须被检出"


def test_eval_auto_checks_superseded_use():
    """失效内容采用检查：输出复述被取代内容应被抓。"""
    from litreview_agent.evaluate import _auto_checks
    case = {"category": "supersede", "setup": {"memory_seed": []}}
    # 指纹用真实长度（含实体名区+特征区；算法跳过前12字符实体名窗口）
    fp = "范围：含多模态记忆系统，包括图像视频与音频输入"
    out = "当前规则是：收录多模态记忆系统，包括图像视频与音频输入。"
    checks = _auto_checks(case, out, set(), [fp])
    assert checks["superseded_content_used"], "失效内容采用必须被检出"
    # 精度验证：仅正常提及实体名（无特征区内容）不应命中
    checks2 = _auto_checks(case, "关于多模态记忆的规则见新版本。", set(), [fp])
    assert not checks2["superseded_content_used"], "实体名窗口不得误报"


# ------------------------------------------------- 身份核验（D-6 防线）


def test_identity_check_rejects_mismatched_pdf():
    """错配 PDF（记录题名 vs 首页不符）必须被前置校验拒绝。"""
    from litreview_agent.evidence_batch import _identity_ok
    # MemoryBank 记录题名 vs 气候论文首页（真实错配案例）
    climate_first_page = ("We define the Climatological Renewable Energy Deviation Index "
                          "(credi) for researchers and stakeholders of wind and solar resources.")
    assert not _identity_ok("MemoryBank: Enhancing Large Language Models with Long-Term Memory",
                            climate_first_page), "气候论文首页不得通过 MemoryBank 的身份校验"
    # 正确首页
    mb_first_page = ("MemoryBank: Enhancing Large Language Models with Long-Term Memory. "
                     "Wanjun Zhong, Lianghong Guo, Qiqi Gao. An AI companion with forgetting.")
    assert _identity_ok("MemoryBank: Enhancing Large Language Models with Long-Term Memory",
                        mb_first_page), "真实 MemoryBank 首页应通过校验"


def test_valid_evidence_excludes_invalidated():
    """废止证据（reviews.jsonl fail）不得出现在有效证据中。"""
    import tempfile
    from litreview_agent.models import Evidence, Review, append_jsonl
    from litreview_agent.models import load_valid_evidence
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        e_good = Evidence(work_id="W0001", source_id="s", locator="pdf:p1",
                          excerpt="good", interpretation="i",
                          evidence_type="mechanism")
        e_bad = Evidence(work_id="W0002", source_id="s", locator="pdf:p1",
                         excerpt="bad", interpretation="i",
                         evidence_type="mechanism")
        append_jsonl(d / "evidence.jsonl", e_good)
        append_jsonl(d / "evidence.jsonl", e_bad)
        append_jsonl(d / "reviews.jsonl",
                     Review(target_id=e_bad.evidence_id, reviewer_type="auto_check",
                            reviewer_name="test", result="fail",
                            correction="废止测试"))
        valid = load_valid_evidence(d)
        assert len(valid) == 1 and valid[0].excerpt == "good"
