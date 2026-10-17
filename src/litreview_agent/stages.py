"""阶段执行器：discovery（G1）→ evidence / draft（G2）。

每个阶段产出真实数据文件与控制台摘要；失败如实记录进 search_runs.jsonl
或 runs/<run_id>/events.jsonl，不用虚构数据填补。
"""

from __future__ import annotations

import sys
from pathlib import Path

from .models import Claim, Evidence, read_jsonl
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
    """G2 证据阶段：选定代表论文 → 协调器提取证据 → 缺口检查。"""
    from .coordinator import Coordinator
    from .model_backends import AnthropicBackend

    works = distinct_works(load_papers(data_dir))
    # 代表论文选择：覆盖 5 个 RQ（种子 + 抽验池中的强相关项）
    wanted = [
        ("MemGPT: Towards LLMs as Operating Systems", "RQ2"),
        ("LongMemEval: Benchmarking Chat Assistants", "RQ5"),
        ("Selective Forgetting", "RQ3"),
        ("Memory Poisoning Attack and Defense", "RQ4"),
        ("A Survey on Long-Term Memory Security", "RQ1"),
    ]
    selected: list[str] = []
    for pattern, _rq in wanted:
        for wid, recs in works.items():
            if any(r.title and pattern in r.title for r in recs):
                selected.append(wid)
                break
    if len(selected) < 3:
        print(f"错误：代表论文不足（{len(selected)}），先运行 discovery", file=sys.stderr)
        return 1
    print(f"选定代表论文 {len(selected)} 项：{selected}")

    run_id = f"ev-{__import__('time').strftime('%m%d%H%M%S')}"
    events_path = data_dir.parent / "runs" / run_id / "events.jsonl"

    def _usage_logger(d: dict) -> None:
        """模型调用用量入运行日志（课程要求：真实成本信息可查）。"""
        if d.get("kind") == "model_result":
            from .models import RunEvent, append_jsonl
            u = d.get("usage") or {}
            append_jsonl(events_path, RunEvent(
                run_id=run_id, kind="usage", model=d.get("model"),
                prompt_version=d.get("prompt_version"),
                input_tokens=u.get("input_tokens"),
                output_tokens=u.get("output_tokens"),
                status="ok"))

    backend = AnthropicBackend(logger=_usage_logger)
    coord = Coordinator(data_dir, run_id, backend, selected_work_ids=selected)

    # 续跑感知：已有证据的论文不再重复提取；目标按剩余缺口组织
    ev_path = data_dir / "evidence.jsonl"
    existing = list(read_jsonl(ev_path, Evidence)) if ev_path.exists() else []
    done_works = {e.work_id for e in existing}
    remaining = [w for w in selected if w not in done_works]
    rq_counts: dict[str, int] = {}
    for e in existing:
        for rq in e.rq_tags:
            rq_counts[rq] = rq_counts.get(rq, 0) + 1
    gap_rqs = [f"RQ{i}" for i in range(1, 6) if rq_counts.get(f"RQ{i}", 0) < 2]

    if remaining:
        objective = (
            f"继续为以下尚未提取证据的论文工作：{remaining}。"
            f"每篇读取相关页（摘要、方法、实验），提交 1–3 条证据"
            f"（excerpt 逐字复制原文；系统会忽略空白差异匹配，但改写会被拒绝）。"
            f"本回合优先提交证据，减少重复读页。")
    elif gap_rqs:
        objective = (
            f"全部选定论文已有证据。当前 RQ 覆盖缺口：{gap_rqs}（目标每 RQ ≥2 条）。"
            f"对每个缺口：或从已选定论文的更深页段提取补充证据，"
            f"或自行选择检索词补检（说明缺口与检索理由），然后提取新候选的证据。")
    else:
        cl_path0 = data_dir / "claims.jsonl"
        n_claims = len(read_jsonl(cl_path0, Claim)) if cl_path0.exists() else 0
        if n_claims < 3 and len(existing) >= 10:
            objective = (
                f"证据已充足（{len(existing)} 条，五 RQ 覆盖达标）。"
                f"本回合**只做 claims 登记**，不要再提取证据："
                f"基于已登记证据，提交 5–8 条 claims（每条引用 1–3 个 evidence_id），"
                f"覆盖：方法脉络（RQ2）、记忆更新与遗忘（RQ3）、可靠性与攻击"
                f"（RQ4）、评测基准（RQ5）四类章节；跨论文综合标 synthesis，"
                f"单篇直接支持标 direct。完成后 finish 总结。")
        else:
            objective = (
                f"全部选定论文已有证据且 RQ 覆盖达标。请：1) 复核证据质量"
                f"（摘录定位准确、解释区分作者结论与综合）；2) 登记 5–8 条 claims，"
                f"覆盖脉络、更新与可靠性、评测三类章节；3) 总结证据库状态与剩余缺口。")

    # 阶段内多回合：每回合 ≤12 工具步，回合间状态（证据/页缓存）保持。
    # 完成条件：选定论文全部有证据 + 每 RQ≥2 条 + claims≥3；最多 4 回合。
    for turn_no in range(1, 5):
        text = coord.run_turn(f"[回合{turn_no}] {objective}", max_steps=12)
        print(f"== 回合 {turn_no} 输出（节选）==")
        print(text[:600])
        from .models import load_valid_evidence
        ev_now = load_valid_evidence(data_dir)
        cl_now = list(read_jsonl(data_dir / "claims.jsonl", Claim)
                      if (data_dir / "claims.jsonl").exists() else [])
        rq_now: dict[str, int] = {}
        for e in ev_now:
            for rq in e.rq_tags:
                rq_now[rq] = rq_now.get(rq, 0) + 1
        covered = {e.work_id for e in ev_now}
        gaps_now = [f"RQ{i}" for i in range(1, 6) if rq_now.get(f"RQ{i}", 0) < 2]
        print(f"   状态：证据 {len(ev_now)}，claims {len(cl_now)}，"
              f"RQ 缺口 {gaps_now or '无'}，未覆盖选定论文 "
              f"{[w for w in selected if w not in covered] or '无'}")
        if (set(selected) <= covered and not gaps_now and len(cl_now) >= 3):
            print("完成条件达成。")
            break
    print(f"== 运行记录：runs/{run_id}/events.jsonl ==")
    return 0


def run_draft(data_dir: Path) -> int:
    """G2 草稿阶段：基于已登记 claims/evidence 生成带引用短草稿 + 引用检查。"""
    from .coordinator import Coordinator
    from .model_backends import AnthropicBackend
    from .checks import check_draft_citations

    ev_path = data_dir / "evidence.jsonl"
    cl_path = data_dir / "claims.jsonl"
    if not ev_path.exists() or not cl_path.exists():
        print("错误：先运行 evidence 阶段", file=sys.stderr)
        return 1
    evidence = list(read_jsonl(ev_path, Evidence))
    claims = list(read_jsonl(cl_path, Claim))

    run_id = f"dr-{__import__('time').strftime('%m%d%H%M')}"
    backend = AnthropicBackend()
    coord = Coordinator(data_dir, run_id, backend)

    # 素材包：claims + 证据摘要（模型只见已验证素材）
    works = distinct_works(load_papers(data_dir))
    material = []
    ev_by_id = {e.evidence_id: e for e in evidence}
    for c in claims:
        evs = [ev_by_id[i] for i in c.evidence_ids if i in ev_by_id]
        material.append({
            "claim_id": c.claim_id, "text": c.text, "section": c.section,
            "claim_type": c.claim_type,
            "evidence": [{"work_id": e.work_id, "locator": e.locator,
                          "excerpt": e.excerpt[:200],
                          "conditions": e.conditions} for e in evs]})
    titles = {wid: recs[0].title for wid, recs in works.items()}

    user_message = (
        f"基于以下已验证的 claims 与证据，撰写综述的一节草稿（中文，400–600字），"
        f"主题：大模型智能体长期记忆的组织、更新与可靠性（引言之后的方法脉络节）。\n"
        f"规则：\n"
        f"1. 每个陈述句尾用 \\cite{{Wxxxx}} 标注支撑研究的 work_id；"
        f"只能引用素材中出现的 work_id。\n"
        f"2. 素材中标注的条件（模型、数据集）如影响结论，写入正文。\n"
        f"3. 证据不足或为 hypothesis 的内容，句尾加【待核验】。\n"
        f"4. 直接输出 Markdown 段落，不要额外解释。\n\n"
        f"论文题名对照：{__import__('json').dumps(titles, ensure_ascii=False)[:1500]}\n\n"
        f"素材：{__import__('json').dumps(material, ensure_ascii=False)[:8000]}")
    result = backend.complete(system=(
        "你是学术写作智能体。只用给定素材写作；每个事实性陈述必须有 cite；"
        "证据不足处显式标【待核验】，绝不编造。"), messages=[
        {"role": "user", "content": user_message}], max_tokens=2000)
    draft = result.text
    report = check_draft_citations(draft, evidence, claims, works)

    out_dir = data_dir / "derived"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "draft_g2.md").write_text(draft, encoding="utf-8")
    (out_dir / "draft_g2_check.md").write_text(report, encoding="utf-8")
    coord.log(kind="start", decision_reason="G2 草稿生成")
    coord.log(kind="end", result_summary=f"草稿 {len(draft)} 字；引用检查：\n{report[:400]}")
    print("== 草稿（data/derived/draft_g2.md）==")
    print(draft)
    print("== 引用检查报告（data/derived/draft_g2_check.md）==")
    print(report)
    return 0 if "错误" not in report else 1


# ================================================================ G3 阶段


def run_screen(data_dir: Path, max_candidates: int | None = None) -> int:
    """G3 筛选：批量模型筛选（题名+摘要），写回 inclusion_status。"""
    from .model_backends import AnthropicBackend
    from .screening import run_screening

    backend = AnthropicBackend()
    stats = run_screening(data_dir, backend,
                          max_candidates=max_candidates or 150)
    print("== 筛选结果 ==")
    for k, v in stats.items():
        if k != "run_id":
            print(f"  {k}: {v}")
    print(f"运行记录：runs/{stats['run_id']}/events.jsonl")
    return 0


def run_evidence_batch(data_dir: Path, max_works: int | None = None) -> int:
    """G3 批量证据提取（决策 D-2：单篇单调用 + G2 验证器）。"""
    from .evidence_batch import run_evidence_batch as _run
    from .model_backends import AnthropicBackend
    from .models import RunEvent, append_jsonl

    # usage 先记到临时位置，run_id 确定后由批处理自身日志接管不了——
    # 这里创建一个共享日志文件，与批处理 run 目录分开但可对账
    usage_path = data_dir / "derived" / "evidence_batch_usage.jsonl"
    usage_path.parent.mkdir(parents=True, exist_ok=True)

    def _usage_logger(d: dict) -> None:
        if d.get("kind") == "model_result":
            u = d.get("usage") or {}
            append_jsonl(usage_path, RunEvent(
                run_id="evidence-batch", kind="usage", model=d.get("model"),
                prompt_version=d.get("prompt_version"),
                input_tokens=u.get("input_tokens"),
                output_tokens=u.get("output_tokens"), status="ok"))

    backend = AnthropicBackend(logger=_usage_logger)
    stats = _run(data_dir, backend, max_works=max_works)
    print("== 批量证据提取结果 ==")
    for k, v in stats.items():
        if k != "run_id":
            print(f"  {k}: {v}")
    print(f"运行记录：runs/{stats['run_id']}/events.jsonl")
    return 0


# 前向追踪锚点（G2 代表作 + 种子经典；OA id 从 papers.jsonl 的 url 字段解析）
TRACE_TITLES = [
    "MemGPT: Towards LLMs as Operating Systems",
    "Generative Agents: Interactive Simulacra of Human Behavior",
    "Reflexion: language agents with verbal reinforcement learning",
    "MemoryBank: Enhancing Large Language Models with Long-Term Memory",
    "Evaluating Very Long-Term Conversational Memory of LLM Agents",
    "LongMemEval: Benchmarking Chat Assistants",
]
# 后向补齐：经典/代表工作名定向检索（综述相关工作章节提到的脉络节点）
CLASSIC_NAMES = [
    "Voyager: An Open-Ended Embodied Agent with Large Language Models",
    "RecurrentGPT: Interactive Generation of (Arbitrarily) Long Text",
    "RET-LLM: Towards a General Read-Write Memory for Large Language Models",
    "ExpeL: LLM Agents Are Experiential Learners",
    "A-MEM: Agentic Memory for LLM Agents",
    "Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory",
    "HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models",
    "Zep: A Temporal Knowledge Graph Architecture for Agent Memory",
    "Titans: Learning to Memorize at Test Time",
    "MemoRAG: Moving towards Long-Context LLMs through Retrieval-Augmented Long-term Memory",
]


def run_trace(data_dir: Path) -> int:
    """G3 引文追踪：前向 cites: + 经典名补检（决策 D-1）。"""
    from .tools.search import HttpCache, OpenAlexSearcher

    cache = HttpCache(data_dir / "derived" / "http_cache")
    oa = OpenAlexSearcher(cache, data_dir)
    log_path = data_dir / "search_runs.jsonl"
    works = distinct_works(load_papers(data_dir))

    # 1) 前向追踪：对锚点论文取 citing works
    oa_by_title = {}
    for wid, recs in works.items():
        for r in recs:
            if r.url and "openalex.org/W" in (r.url or ""):
                oa_by_title[r.title] = (wid, r.url.split("/")[-1])
    all_hits = []
    print("== 前向追踪（OpenAlex cites:）==")
    for title in TRACE_TITLES:
        match = next((v for k, v in oa_by_title.items()
                      if k and title[:30].lower() in k.lower()), None)
        if not match:
            print(f"  跳过（无 OA id）: {title[:50]}")
            continue
        wid, oa_id = match
        try:
            hits = oa.works_citing(oa_id, per_page=25, log_path=log_path,
                                   query_tag=f"from:{wid}")
            print(f"  {title[:45]}…: {len(hits)} 条被引")
            all_hits.extend(hits)
        except Exception as e:  # noqa: BLE001
            print(f"  {title[:45]}…: 失败 {e}", file=sys.stderr)

    # 2) 经典名定向检索（后向补齐）
    print("== 经典名定向检索 ==")
    for name in CLASSIC_NAMES:
        try:
            hits = oa.search(name, per_page=3, log_path=log_path)
            if hits:
                print(f"  {name[:50]}: 命中 {hits[0].title[:50]}")
                all_hits.extend(hits[:1])
            else:
                print(f"  {name[:50]}: 未命中")
        except Exception as e:  # noqa: BLE001
            print(f"  {name[:50]}: 失败 {e}", file=sys.stderr)

    touched, new_works, appended = merge_hits(all_hits, "g3-trace", data_dir)
    print(f"== 合并：新增 {new_works} 项独立研究（{appended} 条记录）==")
    print("后续：对新增候选跑 run --stage screen（可 --max 限定）。")
    return 0


def run_matrix(data_dir: Path) -> int:
    """G4 研究矩阵：核心池 40 篇按 §2.4 六维分类（阅读卡+证据驱动）。"""
    import json
    from .model_backends import AnthropicBackend

    pool_path = data_dir / "core_pool.jsonl"
    cards_path = data_dir / "derived" / "reading_cards.jsonl"
    if not pool_path.exists():
        print("无核心池，先完成 selection", file=sys.stderr)
        return 1
    pool = {(json.loads(l)["work_id"]): json.loads(l)
            for l in pool_path.read_text(encoding="utf-8").splitlines() if l.strip()}
    cards = {}
    if cards_path.exists():
        for l in cards_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                c = json.loads(l)
                cards[c["work_id"]] = c
    backend = AnthropicBackend()
    items = []
    for wid, meta in sorted(pool.items()):
        card = cards.get(wid, {}).get("card", {})
        items.append({"work_id": wid, "title": meta["title"][:90],
                      "year": meta["year"], "layer": meta["layer"][:14],
                      "role": meta["role"][:16],
                      "mechanism": (card.get("memory_mechanism") or "")[:200],
                      "update": (card.get("update_method") or "")[:150],
                      "evaluation": (card.get("evaluation_setup") or "")[:150]})
    matrix_prompt = """对下列 LLM 智能体长期记忆研究，按六个维度各给一个简短分类值
（从建议值中选或自造更贴切的词）：
content（事实/事件情景/任务状态/程序性经验/混合）、
representation（原始片段/摘要卡片/结构化记录/图/分层/向量库/混合）、
lifecycle_focus（写入/筛选/检索/更新/遗忘/全生命周期）、
time_handling（无/时间戳/有效区间/版本链/时间推理）、
trust_handling（无/来源标注/信任分数/验证过滤/人类确认）、
eval_target（无/召回精度/更新正确性/长期任务成功率/成本/攻击鲁棒性）。
输出 JSON 数组：{"work_id":..., "content":..., "representation":...,
"lifecycle_focus":..., "time_handling":..., "trust_handling":..., "eval_target":...}
只输出 JSON。

研究列表：
""" + "\n".join(f"- {json.dumps(it, ensure_ascii=False)}" for it in items)

    result = backend.complete(system=matrix_prompt,
                              messages=[{"role": "user", "content": "分类。只输出 JSON。"}],
                              max_tokens=4000)
    m = None
    import re as _re
    mm = _re.search(r"\[.*\]", result.text, _re.S)
    if mm:
        try:
            m = json.loads(mm.group(0))
        except json.JSONDecodeError:
            m = None
    if not m:
        print("矩阵生成失败（模型输出不可解析）", file=sys.stderr)
        print(result.text[:300])
        return 1
    by_wid = {it["work_id"]: it for it in items}
    out_dir = data_dir / "derived"
    out_dir.mkdir(exist_ok=True)
    rows = []
    for it in m:
        if it.get("work_id") not in by_wid:
            continue
        base = by_wid[it["work_id"]]
        rows.append({**base, **{k: it.get(k, "?") for k in
                                ("content", "representation", "lifecycle_focus",
                                 "time_handling", "trust_handling", "eval_target")}})
    (out_dir / "research_matrix.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    # Markdown 渲染
    md = ["# 研究矩阵（G4，六维分类；输入=阅读卡证据，输出待人工复核）", "",
          "| work | 年份 | 层 | 角色 | 内容 | 表示 | 生命周期 | 时间 | 信任 | 评测 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['work_id']} | {r.get('year', '?')} "
                  f"| {r.get('layer', '?')[:12]} | {r.get('role', '?')[:14]} "
                  f"| {r.get('content', '?')} | {r.get('representation', '?')} "
                  f"| {r.get('lifecycle_focus', '?')} | {r.get('time_handling', '?')} "
                  f"| {r.get('trust_handling', '?')} | {r.get('eval_target', '?')} |")
    (out_dir / "research_matrix.md").write_text("\n".join(md), encoding="utf-8")
    print(f"研究矩阵：{len(rows)} 项 → data/derived/research_matrix.md")
    return 0


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
