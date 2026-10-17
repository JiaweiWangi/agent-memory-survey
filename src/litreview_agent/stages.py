"""阶段执行器：discovery（G1）→ evidence / draft（G2）。

每个阶段产出真实数据文件与控制台摘要；失败如实记录进 search_runs.jsonl
或 runs/<run_id>/events.jsonl，不用虚构数据填补。
"""

from __future__ import annotations

import sys
from pathlib import Path

from .tools.search import (ArxivSearcher, HttpCache, OpenAlexSearcher,
                           RateLimited, SearchHit, SemanticScholarSearcher)
from .tools.dedup import distinct_works, load_papers, merge_hits

# EXECUTION_PLAN §4.1 五组检索概念组合（按平台能力拆分）。
# OpenAlex 的 search 为全文相关度检索，用自然语言式关键词组。
OPENALEX_QUERIES: list[tuple[str, str]] = [
    ("q1-define", "LLM agent long-term memory"),
    ("q1-define", "large language model agent persistent memory"),
    ("q2-organize", "LLM agent episodic memory semantic memory"),
    ("q2-organize", "agent memory architecture language model"),
    ("q3-update", "agent memory update forgetting"),
    ("q3-update", "memory conflict temporal reasoning LLM"),
    ("q4-reliability", "agent memory hallucination"),
    ("q4-reliability", "memory poisoning LLM agent"),
    ("q4-reliability", "LLM memory reliability provenance"),
    ("q5-eval", "long-term conversational memory benchmark evaluation"),
    ("q5-eval", "multi-session dialogue memory LLM"),
]

# 种子论文（EXECUTION_PLAN §4.1）：作为发现线索，身份需逐一核验。
SEED_TITLES: list[tuple[str, str]] = [
    ("Generative Agents", "Generative Agents: Interactive Simulacra of Human Behavior"),
    ("MemGPT", "MemGPT: Towards LLMs as Operating Systems"),
    ("MemoryBank", "MemoryBank: Enhancing Large Language Models with Long-Term Memory"),
    ("Reflexion", "Reflexion: Language Agents with Verbal Reinforcement Learning"),
    ("LoCoMo", "Evaluating Very Long-Term Conversational Memory of LLM Agents"),
    ("LongMemEval", "LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory"),
]

# 初步 RQ 标注关键词（启发式，G1 可行性用；正式分类由模型+人工完成）
RQ_KEYWORDS: list[tuple[str, list[str]]] = [
    ("RQ3", ["update", "forget", "obsolet", "conflict", "outdated", "temporal",
             "supersed", "delete", "edit memory", "evolv"]),
    ("RQ4", ["hallucin", "reliab", "poison", "provenance", "trust", "error",
             "distort", "contaminat", "faithful"]),
    ("RQ5", ["benchmark", "evaluat", "locomo", "longmemeval", "test", "dataset"]),
    ("RQ2", ["retriev", "organiz", "store", "compress", "write", "index",
             "graph memory", "hierarch", "summariz"]),
    ("RQ1", ["defin", "survey", "taxonomy", "overview", "conceptu"]),
]


def _rq_tags(hit: SearchHit) -> list[str]:
    text = f"{hit.title} {(hit.abstract or '')}".lower()
    tags = [rq for rq, kws in RQ_KEYWORDS if any(k in text for k in kws)]
    return tags or ["RQ2"]  # 无标签时默认 RQ2（组织与使用为主流）


def run_discovery(data_dir: Path, per_query_pages: int = 2,
                  per_page: int = 25) -> int:
    """G1 检索：OpenAlex 五组检索式 + 种子核验 + arXiv（可用时）。

    返回退出码；所有计数来自真实合并结果。
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    cache = HttpCache(data_dir / "derived" / "http_cache")
    log_path = data_dir / "search_runs.jsonl"
    oa = OpenAlexSearcher(cache, data_dir)

    all_hits: list[SearchHit] = []
    print("== OpenAlex 检索（五组概念）==")
    for tag, query in OPENALEX_QUERIES:
        hits: list[SearchHit] = []
        for page_no in range(1, per_query_pages + 1):
            try:
                hits.extend(oa.search(query, per_page=per_page, page=page_no,
                                      log_path=log_path))
            except Exception as e:  # noqa: BLE001 — 页级失败保留已取结果
                print(f"  [{tag}] {query!r} 第{page_no}页失败: {e}", file=sys.stderr)
                break
        print(f"  [{tag}] {query!r}: {len(hits)} 命中")
        all_hits.extend(hits)

    print("== 种子论文核验 ==")
    for name, title in SEED_TITLES:
        try:
            hits = oa.search(title, per_page=3, log_path=log_path)
            exact = [h for h in hits if h.title and h.title.lower()[:40] == title.lower()[:40]]
            found = exact or hits[:1]
            if found:
                print(f"  {name}: 命中 {found[0].title[:60]} ({found[0].year})")
                all_hits.extend(found)
            else:
                print(f"  {name}: 未命中（需人工复核）")
        except Exception as e:  # noqa: BLE001
            print(f"  {name}: 检索失败 {e}", file=sys.stderr)

    # arXiv 补充（限流时跳过，不阻塞 G1）
    print("== arXiv 补充检索 ==")
    ax = ArxivSearcher(cache, data_dir, min_interval=3.5)
    ax_queries = [
        'all:"agent memory" AND all:"language model"',
        'all:"long-term memory" AND all:agent',
    ]
    for q in ax_queries:
        try:
            hits = ax.search(q, max_results=25, log_path=log_path)
            print(f"  {q!r}: {len(hits)} 命中")
            all_hits.extend(hits)
        except RateLimited as e:
            print(f"  {q!r}: 限流跳过（{e}）", file=sys.stderr)
            break  # 限流窗口内不再尝试
        except Exception as e:  # noqa: BLE001
            print(f"  {q!r}: 失败 {e}", file=sys.stderr)

    # 合并去重
    touched, new_works, appended = merge_hits(all_hits, "g1-discovery", data_dir)
    papers = load_papers(data_dir)
    works = distinct_works(papers)

    # 初步 RQ 标注（启发式）写回内存统计（不落盘 papers，正式标注在 G2 由模型完成）
    tag_counts: dict[str, set[str]] = {}
    for hit in all_hits:
        for rq in _rq_tags(hit):
            tag_counts.setdefault(rq, set()).add(hit.title[:60])

    print("== 合并结果 ==")
    print(f"  检索总命中: {len(all_hits)}")
    print(f"  papers.jsonl 记录: {len(papers)}（追加 {appended}）")
    print(f"  独立 work_id: {len(works)}（新增 {new_works}）")
    for rq in sorted(tag_counts):
        print(f"  启发式 {rq}: ≥{len(tag_counts[rq])} 条（初步，待模型正式标注）")
    return 0


def run_evidence(data_dir: Path) -> int:
    raise NotImplementedError("G2 阶段：见 coordinator（批次 3 实现）")


def run_draft(data_dir: Path) -> int:
    raise NotImplementedError("G2 阶段：见 coordinator（批次 3 实现）")


def check_corpus(data_dir: Path) -> int:
    """语料检查：计数与去重不变量。"""
    from .models import Evidence, SearchRun, read_jsonl

    papers = load_papers(data_dir)
    works = distinct_works(papers)
    included = {wid: recs for wid, recs in works.items()
                if any(r.inclusion_status == "included" for r in recs)}
    ev_path = data_dir / "evidence.jsonl"
    evidence = list(read_jsonl(ev_path, Evidence)) if ev_path.exists() else []
    sr_path = data_dir / "search_runs.jsonl"
    runs = list(read_jsonl(sr_path, SearchRun)) if sr_path.exists() else []

    print("== 语料检查 ==")
    print(f"  papers.jsonl 记录: {len(papers)}")
    print(f"  独立 work_id: {len(works)}")
    print(f"  inclusion_status=included 的研究: {len(included)}")
    print(f"  证据记录: {len(evidence)}")
    print(f"  检索运行记录: {len(runs)}"
          f"（failed: {sum(1 for r in runs if r.status == 'failed')}）")
    ok = True
    # 不变量：同一 work_id 的记录不得互相冲突地标记 included/excluded
    for wid, recs in works.items():
        statuses = {r.inclusion_status for r in recs}
        if "included" in statuses and "excluded" in statuses:
            print(f"  [WARN] {wid}: included 与 excluded 并存，需人工裁决")
            ok = False
    print(f"  不变量检查: {'通过' if ok else '存在问题（见上）'}")
    return 0 if ok else 1
