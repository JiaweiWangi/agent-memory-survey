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


# ------------------------- 身份核验 v2 回归（D-6 真实错配案例）


def _mb_first_page():
    from litreview_agent.tools.fetch import Fetcher
    from pathlib import Path
    f = Fetcher(Path("sources"), Path("data/derived/http_cache"))
    ft = f.fetch_pdf("2305.10250")   # 真实 MemoryBank PDF（本地已存档）
    return f.extract_pages(ft.path, 1, 1) if ft else ""


def test_identity_rejects_reflexion_title_with_memorybank_pdf():
    """真实错配回归 1：Reflexion 标题 + MemoryBank 首页必须被拒（v1 放行过）。"""
    from litreview_agent.identity import identity_ok
    page = _mb_first_page()
    if not page:
        pytest.skip("MemoryBank PDF 未存档")
    assert not identity_ok(
        "Reflexion: language agents with verbal reinforcement learning", page)


def test_identity_rejects_memorybank_title_with_climate_pdf():
    """真实错配回归 2：MemoryBank 标题 + 气候论文(2307.08909)首页必须被拒。"""
    from litreview_agent.identity import identity_ok
    from litreview_agent.tools.fetch import Fetcher
    from pathlib import Path
    f = Fetcher(Path("sources"), Path("data/derived/http_cache"))
    ft = f.fetch_pdf("2307.08909")
    if not ft:
        pytest.skip("气候论文 PDF 未存档")
    page = f.extract_pages(ft.path, 1, 1)
    assert not identity_ok(
        "MemoryBank: Enhancing Large Language Models with Long-Term Memory", page)


def test_identity_accepts_correct_pairs():
    """正确配对不得误拒：MemoryBank/Reflexion 各自的正确首页必须通过。"""
    from litreview_agent.identity import identity_ok
    from litreview_agent.tools.fetch import Fetcher
    from pathlib import Path
    f = Fetcher(Path("sources"), Path("data/derived/http_cache"))
    mb = f.fetch_pdf("2305.10250")
    if mb:
        assert identity_ok(
            "MemoryBank: Enhancing Large Language Models with Long-Term Memory",
            f.extract_pages(mb.path, 1, 1))
    rf = f.fetch_pdf("2303.11366")
    if rf:
        assert identity_ok(
            "Reflexion: language agents with verbal reinforcement learning",
            f.extract_pages(rf.path, 1, 1))


# ------------------- multirun 判分 v2 回归（D-8 真实误判输出）


def test_score_multirun_rejects_fabricated_claim():
    """M4-03/A 真实输出（编造 S102）必须判未完成。"""
    from litreview_agent.evaluate import score_multirun
    out = ("可基于 S102（跨基准连贯性主张）写：LoCoMo 与 LongMemEval "
           "虽都测长程记忆【依据 claim S102】【待核验】。")
    r = score_multirun("M4-03", out)
    assert not r["task_completed"]
    assert any("S102" in p or "s102" in p for p in r["problems"])


def test_score_multirun_rejects_overcertainty():
    """M4-03/C 真实输出（已核验/证据可靠/无缺口 + 虚构评分）必须判未完成。"""
    from litreview_agent.evaluate import score_multirun
    out = ("两个检索结果返回相同记录，已核验：claim-1、claim-2。两项均属实，"
           "且综合评估得分分别为 0.923 和 0.944，证据可靠，无缺口。")
    r = score_multirun("M4-03", out)
    assert not r["task_completed"]
    assert any("过度" in p or "核验" in p for p in r["problems"])
    assert any("评分" in p for p in r["problems"])


def test_score_multirun_requires_action_not_keywords():
    """M4-01/C 真实输出（复述统计但未指出最少 RQ）必须判未完成。"""
    from litreview_agent.evaluate import score_multirun
    out = ("核心池 40 篇，29 篇已有证据。RQ3：20 条 RQ4：15 条 RQ5：12 条。"
           "如需进一步展开统计请说明维度。")
    r = score_multirun("M4-01", out)
    assert not r["task_completed"]
    assert any("RQ5" in p for p in r["problems"])


def test_score_multirun_accepts_genuine_completion():
    """真实完成（事实+动作齐备）必须通过，防判分过严。"""
    from litreview_agent.evaluate import score_multirun
    out = ("根据记忆：核心池 40 篇。RQ3 有 20 条、RQ4 有 15 条、RQ5 仅 12 条。"
           "RQ5 证据最少，建议作为下一步重点补强。")
    assert score_multirun("M4-01", out)["task_completed"]
    out2 = ("上一篇已完成 W0002 的证据提取，接下来应处理 W0006。")
    assert score_multirun("M4-02", out2)["task_completed"]
    # M4-03 在 D-13 保守规则下：正常回答也转待核验（内容相符性交人工）
    out3 = ("依据 claim-1（LoCoMo，ACL 2024）与 claim-2（LongMemEval 五能力），"
            "两个基准分别覆盖超长期对话 QA 与能力维度。")
    r3 = score_multirun("M4-03", out3)
    assert not r3["task_completed"] and r3["needs_human_review"]


# ------------- 废止证据退出协调器生产路径（D-9，真实 7 条 ID 回归）


def _coordinator_with_invalidated(tmp_path: Path):
    """临时库：2 条有效 + 1 条废止（reviews fail）证据 + 对应 papers 记录。"""
    from litreview_agent.coordinator import Coordinator
    from litreview_agent.models import Evidence, Paper, Review, append_jsonl
    from litreview_agent.memory import MemoryStore
    e_ok = Evidence(work_id="W0001", source_id="s", locator="pdf:p1",
                    excerpt="valid evidence about memory", interpretation="i",
                    evidence_type="mechanism", rq_tags=["RQ3"])
    e_bad = Evidence(work_id="W0002", source_id="s", locator="pdf:p1",
                     excerpt="stale evidence from mismatched pdf", interpretation="i",
                     evidence_type="mechanism", rq_tags=["RQ3"])
    append_jsonl(tmp_path / "evidence.jsonl", e_ok)
    append_jsonl(tmp_path / "evidence.jsonl", e_bad)
    append_jsonl(tmp_path / "papers.jsonl", Paper(work_id="W0001", title="T1"))
    append_jsonl(tmp_path / "papers.jsonl", Paper(work_id="W0002", title="T2"))
    append_jsonl(tmp_path / "reviews.jsonl", Review(
        target_id=e_bad.evidence_id, reviewer_type="auto_check",
        reviewer_name="test", result="fail", correction="废止"))
    coord = Coordinator.__new__(Coordinator)
    coord.data_dir = tmp_path
    coord.run_id = "test-d9"
    coord.selected = []
    coord._page_cache = {}
    coord.memory = MemoryStore(tmp_path)
    coord.events_path = tmp_path / "runs" / "t" / "events.jsonl"
    coord.events_path.parent.mkdir(parents=True, exist_ok=True)
    return coord, e_ok, e_bad


def test_coordinator_hides_invalidated_evidence(tmp_path: Path):
    """list_evidence 与 RQ 覆盖统计不得计入废止证据（工具行为，非加载器）。"""
    coord, e_ok, e_bad = _coordinator_with_invalidated(tmp_path)
    listing = coord._tool_list_evidence({})
    assert e_bad.evidence_id not in listing, "废止证据不得出现在工具输出"
    assert e_ok.evidence_id in listing, "有效证据应展示"
    cov = coord._tool_get_rq_coverage({})
    # 唯一有效证据带 RQ3 → RQ3 计 1，不得把废止的 RQ3 也计入变 2
    assert '"RQ3": 1' in cov, f"覆盖统计计入了废止证据: {cov}"


def test_coordinator_rejects_claim_on_invalidated_evidence(tmp_path: Path):
    """submit_claim 引用废止证据 ID 必须明确拒绝（不能仅因 ID 存在而接受）。"""
    coord, e_ok, e_bad = _coordinator_with_invalidated(tmp_path)
    r = coord._tool_submit_claim({"text": "论断", "evidence_ids": [e_bad.evidence_id],
                                  "claim_type": "direct", "section": "脉络"})
    assert "已废止" in r, r
    r2 = coord._tool_submit_claim({"text": "论断", "evidence_ids": [e_ok.evidence_id],
                                   "claim_type": "direct", "section": "脉络"})
    assert "已登记" in r2 or "claim" in r2.lower(), r2


# ------------- 判分 v3 回归（D-11 独立验收发现的三类放行）


def test_score_v3_rejects_fabricated_stats_numbers():
    """M4-01：编造 999/888/777 必须判未完成（数字出现但对象错绑不算事实正确）。"""
    from litreview_agent.evaluate import score_multirun
    out = ("核心池 40 篇。RQ3：999 条 RQ4：888 条 RQ5：777 条。"
           "RQ5 证据最少，下一步重点。")
    r = score_multirun("M4-01", out)
    assert not r["task_completed"]
    assert any("999" in p for p in r["problems"])


def test_score_v3_rejects_reversed_queue():
    """M4-02：'已完成 W0006，下一篇 W0002' 颠倒队列必须判未完成。"""
    from litreview_agent.evaluate import score_multirun
    for out in ("已完成 W0006 的证据提取，接下来应处理 W0002。",
                "W0006 已完成，下一篇处理 W0002。"):
        r = score_multirun("M4-02", out)
        assert not r["task_completed"], out
        assert any("颠倒" in p for p in r["problems"])


def test_score_v3_rejects_contradicted_claim_content():
    """M4-03（D-13 三态版）：合法编号 + 内容存疑不再自动判失败——
    开放式内容主张超出自动规则可靠边界，转待人工核验（不默认成功）。"""
    from litreview_agent.evaluate import score_multirun
    out = "依据 claim-1，LoCoMo 是图像分类数据集；LongMemEval 不涉及长期记忆。"
    r = score_multirun("M4-03", out)
    assert not r["task_completed"], "不得默认成功"
    assert r["needs_human_review"] and not r["problems"], "内容主张应转待核验而非自动失败"


def test_score_v3_accepts_paraphrased_genuine_answers():
    """防过严：正常改写（'RQ3 共 20 条'分隔符、markdown 列表）必须通过。"""
    from litreview_agent.evaluate import score_multirun
    r1 = score_multirun("M4-01",
        "核心池 40 篇，29 篇已有证据；RQ3 共 20 条，RQ4 共 15 条，RQ5 共 12 条。"
        "证据最少的是 RQ5，建议作为下一步处理重点。")
    assert r1["task_completed"], r1
    r2 = score_multirun("M4-02",
        "根据上次运行的输出记录：\n- 上一篇处理完的论文：W0002（已完成证据提取）"
        "\n- 接下来应处理的论文：W0006")
    assert r2["task_completed"], r2


# ------------- 语料检查失败行为（D-12：空目录不得返回成功）


def test_check_corpus_fails_on_empty_or_missing(tmp_path: Path, capsys):
    """空目录/缺必需文件必须返回失败并打印原因。"""
    from litreview_agent.stages import check_corpus
    # 空目录
    rc = check_corpus(tmp_path)
    assert rc == 1, "空目录必须失败"
    out = capsys.readouterr().out
    assert "必需文件缺失" in out or "失败" in out
    # 只有 papers.jsonl（缺 evidence/search_runs）
    (tmp_path / "papers.jsonl").write_text(
        '{"work_id": "W0001", "title": "T", "source_id": "s1", '
        '"inclusion_status": "candidate", "discovered_by": "t", '
        '"fulltext_status": "unknown", "authors": [], "rq_tags": [], '
        '"url": null, "doi": null, "arxiv_id": null, "venue": null, '
        '"year": null, "version": null, "reason": null, "local_path": null, '
        '"file_hash": null, "publication_status": null, "checked_at": null}\n')
    rc2 = check_corpus(tmp_path)
    assert rc2 == 1, "缺 evidence/search_runs 必须失败"


# ------------- M4-03 保守三态判分（D-13）-------------


def test_m403_definite_errors_fail():
    """确定性错误必须判失败：编造标识、过度确定断言。"""
    from litreview_agent.evaluate import score_multirun
    r = score_multirun("M4-03", "可基于 S102 写：LoCoMo 与 LongMemEval 互补。")
    assert not r["task_completed"] and r["problems"] and not r["needs_human_review"]
    r2 = score_multirun("M4-03", "claim-1、claim-2 已核验，证据可靠，无缺口。")
    assert not r2["task_completed"] and r2["problems"] and not r2["needs_human_review"]


def test_m403_openended_content_goes_to_review():
    """开放式内容主张（含明显荒谬与正常表述）一律待核验，不得默认成功。"""
    from litreview_agent.evaluate import score_multirun
    for out in ("依据 claim-1，LoCoMo 用于识别猫狗照片；LongMemEval 评测的是天气预报。",
                "依据 claim-1，LoCoMo 是图像分类数据集。",
                "依据 claim-1（ACL 2024）与 claim-2（五能力），两基准互补。"):
        r = score_multirun("M4-03", out)
        assert not r["task_completed"], f"不得默认成功: {out[:30]}"
        assert r["needs_human_review"] and not r["problems"], out[:30]


def test_aggregation_excludes_needs_review_from_success():
    """汇总统计不得把待核验计入成功或失败（三态互斥）。"""
    from litreview_agent.evaluate import score_multirun
    outputs = ["依据 claim-1，LoCoMo 用于识别猫狗照片。",       # 待核验
               "可基于 S102 写任何东西。",                      # 失败
               "claim-1、claim-2 均属实，证据可靠无缺口。",      # 失败
               "依据 claim-1 与 claim-2 正常草稿。"]            # 待核验
    verdicts = []
    for o in outputs:
        r = score_multirun("M4-03", o)
        v = ("success" if r["task_completed"]
             else "fail" if r["problems"] else "needs_review")
        assert v != "success"
        verdicts.append(v)
    assert verdicts.count("needs_review") == 2
    assert verdicts.count("fail") == 2
    # 三态互斥：needs_review 不在 success/fail 计数内
    success = verdicts.count("success")
    fail = verdicts.count("fail")
    review = verdicts.count("needs_review")
    assert success + fail + review == len(outputs)
