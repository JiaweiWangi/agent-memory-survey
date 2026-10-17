"""协调 Agent：观察状态 → 选择工具 → 执行 → 记录。

G2 演示目标（AGENT_HANDOFF / EXECUTION_PLAN §6.2）：
1. 缺口驱动：观察到 RQ 覆盖不足后，模型自主选择补充检索词（非脚本预设）；
2. 诚实性：正文不可得或证据不支持时保持 pending/failed 状态，
   草稿输出【待核验】标记，不编造。

反幻觉硬约束（代码强制，不依赖模型自觉）：
- submit_evidence 的 excerpt 必须在所指定位的提取文本中找到（空白归一后匹配），
  否则拒绝，模型须重试或如实标 failed；
- submit_claim 引用的 evidence_id 必须存在；
- 草稿引用检查：\\cite{work_id} 必须有该 work 的有效证据。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .model_backends import AnthropicBackend
from .models import (Claim, Evidence, RunEvent, append_jsonl, now_iso,
                     read_jsonl)
from .memory import MemoryStore
from .tools.dedup import load_papers, distinct_works, merge_hits
from .tools.fetch import Fetcher
from .tools.search import CrossrefSearcher, HttpCache, OpenAlexSearcher

# ---------------------------------------------------------------- 提示词（版本化）

SYSTEM_PROMPT = """你是文献综述项目的协调智能体（prompt 版本 g2-v1）。

研究问题（RQ）：
- RQ1 定义与边界：LLM 智能体长期记忆包含哪些机制？与上下文历史、RAG、参数知识的边界？
- RQ2 组织与使用：写入、组织、检索方法如何影响可用性、任务表现和成本？
- RQ3 更新与遗忘：信息变化、时间条件、冲突、过时记忆与删除如何处理？
- RQ4 可靠性：错误信息如何进入记忆并影响决策？如何发现与控制？
- RQ5 评测：基准是否真正考察跨会话记忆与更新能力？结果能否公平比较？

工作规则：
1. 只使用工具提供的真实数据；禁止编造数字、结论或引文。
2. 提交证据的纪律（系统强制验证，失败会返回原文提示）：
   a. excerpt 必须是 read_pages 返回文本中**连续**的片段——刚读完就提交，
      不要读大段后凭记忆复述；
   b. 不要用 ... 省略中间内容；表格的多个单元格、多个列表项分别提交为多条证据；
   c. 优先选短而准的片段（1–3 句），不必整段照抄。
3. 每项证据注明适用条件（模型、数据集、设置）与局限；解释里区分作者结论与你的综合。
4. 观察到某 RQ 证据不足时，主动选择检索词补检（说明缺口与检索理由）。
5. 正文不可得、证据冲突或支持不足时，如实标注，不写确定为已确认。
6. 完成当前目标或达到步数限制时，总结已完成、缺口与建议下一步。"""


def _fuzzy_hint(excerpt: str, page_text: str) -> str:
    """验证失败时，返回页面上与摘录最相似的连续片段，供模型直接复制。"""
    import difflib

    probe, _ = Coordinator._signature(excerpt)
    probe = probe[:120]
    if not probe:
        return ""
    # 候选单元：页面按句/行切分的片段（保留原样）
    units = [u for u in re.split(r"(?<=[.!?。])\s+|\n", page_text) if u.strip()]
    if not units:
        return ""
    sigs = [Coordinator._signature(u)[0] for u in units]
    best = max(range(len(units)),
               key=lambda i: difflib.SequenceMatcher(
                   None, probe, sigs[i][:200]).ratio())
    ratio = difflib.SequenceMatcher(None, probe, sigs[best][:200]).ratio()
    if ratio < 0.4:
        return ("\n提示：该页没有明显相似的段落——请核对页码是否正确。")
    return (f"\n提示：页面上最相似的原文片段（相似度 {ratio:.0%}），"
            f"请直接从这里复制连续段落：\n{units[best][:400]}")


# ---------------------------------------------------------------- 工具规格


def tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": "list_works",
         "description": "列出选定的代表论文（含正文状态与已有证据数）",
         "input_schema": {"type": "object", "properties": {}}},
        {"name": "read_pages",
         "description": "读取某论文 PDF 的指定页（1-based，含边界），返回文本",
         "input_schema": {"type": "object", "properties": {
             "work_id": {"type": "string"},
             "first": {"type": "integer"},
             "last": {"type": "integer"}},
             "required": ["work_id", "first", "last"]}},
        {"name": "submit_evidence",
         "description": "提交一条证据。excerpt 必须逐字来自 read_pages 所见文本（系统验证）。",
         "input_schema": {"type": "object", "properties": {
             "work_id": {"type": "string"},
             "locator": {"type": "string", "description": "如 'pdf:p5 Table 2'"},
             "excerpt": {"type": "string"},
             "interpretation": {"type": "string"},
             "evidence_type": {"type": "string",
                               "enum": ["mechanism", "experiment", "benchmark",
                                        "definition", "limitation"]},
             "conditions": {"type": "string"},
             "limitations": {"type": "string"},
             "rq_tags": {"type": "array", "items": {"type": "string"},
                         "description": "如 ['RQ3']"}},
             "required": ["work_id", "locator", "excerpt", "interpretation",
                          "evidence_type", "rq_tags"]}},
        {"name": "list_evidence",
         "description": "列出已登记证据（evidence_id、work、定位、摘录开头、RQ）——submit_claim 需引用这些 id",
         "input_schema": {"type": "object", "properties": {
             "work_id": {"type": "string", "description": "可选，按论文过滤"},
             "rq": {"type": "string", "description": "可选，按 RQ 过滤（如 RQ3）"}}}},
        {"name": "get_rq_coverage",
         "description": "查看各 RQ 当前证据数与缺口",
         "input_schema": {"type": "object", "properties": {}}},
        {"name": "search_openalex",
         "description": "OpenAlex 关键词检索（补充候选）",
         "input_schema": {"type": "object", "properties": {
             "query": {"type": "string"}}, "required": ["query"]}},
        {"name": "search_crossref",
         "description": "Crossref 检索（正式出版记录）",
         "input_schema": {"type": "object", "properties": {
             "query": {"type": "string"}}, "required": ["query"]}},
        {"name": "submit_claim",
         "description": "登记一条陈述（claim），须引用已有 evidence_id",
         "input_schema": {"type": "object", "properties": {
             "text": {"type": "string"},
             "evidence_ids": {"type": "array", "items": {"type": "string"}},
             "claim_type": {"type": "string", "enum": ["direct", "synthesis", "hypothesis"]},
             "section": {"type": "string",
                         "description": "引言/脉络/更新可靠性/评测/挑战 之一"}},
             "required": ["text", "evidence_ids", "claim_type", "section"]}},
        {"name": "finish",
         "description": "结束当前回合：总结已完成、缺口、下一步建议",
         "input_schema": {"type": "object", "properties": {
             "summary": {"type": "string"}}, "required": ["summary"]}},
    ]


# ---------------------------------------------------------------- 协调器


class Coordinator:
    def __init__(self, data_dir: Path, run_id: str,
                 backend: AnthropicBackend,
                 selected_work_ids: Optional[list[str]] = None):
        self.data_dir = data_dir
        self.run_id = run_id
        self.backend = backend
        self.events_path = data_dir.parent / "runs" / run_id / "events.jsonl"
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.memory = MemoryStore(data_dir)
        self.cache = HttpCache(data_dir / "derived" / "http_cache")
        self.fetcher = Fetcher(data_dir.parent / "sources", self.cache.dir)
        self.selected = selected_work_ids or []
        # 证据摘录验证所需的页面文本缓存：work_id -> {page: text}
        self._page_cache: dict[str, dict[int, str]] = {}

    # ------------------------------------------------------------ 事件日志

    def log(self, **kw: Any) -> None:
        ev = RunEvent(run_id=self.run_id, **kw)
        append_jsonl(self.events_path, ev)

    # ------------------------------------------------------------ 数据访问

    def _papers(self):
        return load_papers(self.data_dir)

    def _works_map(self):
        return distinct_works(self._papers())

    def _evidence(self) -> list[Evidence]:
        path = self.data_dir / "evidence.jsonl"
        return list(read_jsonl(path, Evidence)) if path.exists() else []  # type: ignore[arg-type]

    def _claims(self) -> list[Claim]:
        path = self.data_dir / "claims.jsonl"
        return list(read_jsonl(path, Claim)) if path.exists() else []  # type: ignore[arg-type]

    # ------------------------------------------------------------ 状态摘要

    def state_summary(self) -> str:
        works = self._works_map()
        ev = self._evidence()
        claims = self._claims()
        lines = [f"语料：{len(works)} 项独立研究；证据 {len(ev)} 条；claims {len(claims)} 条。"]
        lines.append("选定代表论文：")
        for wid in self.selected:
            recs = works.get(wid, [])
            if not recs:
                lines.append(f"  {wid}: （未找到记录）")
                continue
            p = recs[0]
            n_ev = sum(1 for e in ev if e.work_id == wid)
            lines.append(f"  {wid}: {p.title[:60]} | {p.fulltext_status} | "
                         f"证据 {n_ev} 条")
        rq_counts: dict[str, int] = {}
        for e in ev:
            for rq in e.rq_tags:
                rq_counts[rq] = rq_counts.get(rq, 0) + 1
        lines.append("RQ 证据分布：" + json.dumps(
            {f"RQ{i}": rq_counts.get(f"RQ{i}", 0) for i in range(1, 6)},
            ensure_ascii=False))
        task = self.memory.task_facts()
        if task:
            lines.append("任务记忆：" + json.dumps(task, ensure_ascii=False)[:500])
        return "\n".join(lines)

    # ------------------------------------------------------------ 工具执行

    def _norm(self, s: str) -> str:
        return re.sub(r"\s+", " ", s).strip()

    # 验证签名中剔除的字符：空白 + 连字符类（跨行连字符与复合词连字符
    # 均为排版产物；内容字符序列仍逐字严格）。软连字符 \xad 一并处理。
    _DROP_CHARS = set("‐‑-­ \t\n\r\f\v")

    @classmethod
    def _signature(cls, text: str) -> tuple[str, list[int]]:
        """返回 (非空白非连字符签名字符串, 签名位置→原文下标映射)。"""
        chars, idx = [], []
        for i, ch in enumerate(text):
            if ch not in cls._DROP_CHARS and not ch.isspace():
                chars.append(ch)
                idx.append(i)
        return "".join(chars), idx

    @classmethod
    def _find_verbatim_span(cls, excerpt: str, page_text: str) -> Optional[str]:
        """在 page_text 中找到与 excerpt 内容一致的原文片段。

        匹配规则：忽略空白与连字符差异（排版产物），其余字符序列必须
        完全一致（子串匹配）。返回原文真实片段用于存档（保留原样连字符
        与换行），保证 evidence.excerpt 可回查；找不到返回 None。
        """
        exc = excerpt.replace("\\n", " ").replace("\\t", " ")
        page_sig, sig_idx = cls._signature(page_text)
        exc_sig, _ = cls._signature(exc)
        if not exc_sig:
            return None
        pos = page_sig.find(exc_sig)
        if pos < 0:
            return None
        start = sig_idx[pos]
        end = sig_idx[pos + len(exc_sig) - 1] + 1
        return page_text[start:end]

    def _tool_list_works(self, _: dict) -> str:
        return self.state_summary()

    def _tool_read_pages(self, inp: dict) -> str:
        wid, first, last = inp["work_id"], int(inp["first"]), int(inp["last"])
        recs = self._works_map().get(wid)
        if not recs:
            return f"错误：work_id {wid} 不存在"
        p = next((r for r in recs if r.local_path), recs[0])
        if not p.local_path or not Path(p.local_path).exists():
            # 尝试按 arXiv ID 现场获取
            ax = p.arxiv_id
            if not ax and p.doi and p.doi.startswith("10.48550/arxiv."):
                ax = p.doi.split("arxiv.", 1)[1]
            if ax:
                ft = self.fetcher.fetch_pdf(ax)
                if ft and ft.path:
                    p.local_path, p.fulltext_status = str(ft.path), "pdf_ok"
                else:
                    return (f"错误：{wid} 正文不可得（arXiv {ax} 下载失败）。"
                            f"请如实将该论文标为正文不可得，不要编造内容。")
            else:
                return f"错误：{wid} 无已存档正文且无 arXiv 通道，如实标注不可得。"
        pages = self._page_cache.setdefault(wid, {})
        out_lines = []
        for pg in range(first, last + 1):
            if pg not in pages:
                pages[pg] = self.fetcher.extract_pages(Path(p.local_path), pg, pg)
            out_lines.append(f"=== {wid} 第 {pg} 页 ===\n{pages[pg]}")
        text = "\n".join(out_lines)
        if len(text) > 60000:
            text = text[:60000] + "\n...(截断，请缩小页范围)"
        return text or "（空文本）"

    def _tool_submit_evidence(self, inp: dict) -> str:
        wid = inp["work_id"]
        locator = inp["locator"]
        excerpt = inp["excerpt"]
        # 反幻觉验证：摘录内容必须出现在所指页的提取文本中
        m = re.search(r"p(\.?\s*)(\d+)", locator)
        if not m:
            return ("错误：locator 需包含页码（如 'pdf:p5 Table 2'）以便验证摘录。")
        page_no = int(m.group(2))
        page_text = self._page_cache.get(wid, {}).get(page_no, "")
        if not page_text:
            return (f"错误：尚未读取 {wid} 第 {page_no} 页，先 read_pages 再提交。")
        verbatim = self._find_verbatim_span(excerpt, page_text)
        if verbatim is None:
            # 给出最近似片段，帮助模型定位真实原文（自纠错闭环）
            hint = _fuzzy_hint(excerpt, page_text)
            return ("错误：excerpt 未在该页找到（忽略空白后逐字匹配失败）。"
                    "excerpt 必须是该页上**连续**的原文段落：不要用 ... 省略、"
                    "不要合并表格多个单元格或多个列表项（拆成多条证据分别提交）、"
                    "不要凭记忆复述（重新 read_pages 后直接复制）。"
                    f"{hint}")
        ev = Evidence(
            work_id=wid, source_id=(self._works_map().get(wid) or [None])[0].source_id
            if self._works_map().get(wid) else "unknown",
            locator=locator, excerpt=verbatim.strip()[:1500],
            interpretation=inp["interpretation"],
            evidence_type=inp["evidence_type"],
            conditions=inp.get("conditions"),
            limitations=inp.get("limitations"),
            rq_tags=inp["rq_tags"],
            verification_status="model_assisted")
        append_jsonl(self.data_dir / "evidence.jsonl", ev)
        self.log(kind="tool_result", tool="submit_evidence",
                 result_summary=f"{ev.evidence_id} {wid} {locator} RQ{ev.rq_tags}",
                 status="ok")
        return (f"已登记证据 {ev.evidence_id}（验证通过，摘录已回存原文逐字片段，"
                f"长度 {len(verbatim.strip())} 字符）")

    def _tool_list_evidence(self, inp: dict) -> str:
        ev = self._evidence()
        if inp.get("work_id"):
            ev = [e for e in ev if e.work_id == inp["work_id"]]
        if inp.get("rq"):
            ev = [e for e in ev if inp["rq"] in e.rq_tags]
        lines = [f"共 {len(ev)} 条证据："]
        for e in ev:
            lines.append(f"- {e.evidence_id} | {e.work_id} | {e.locator[:40]} "
                         f"| {','.join(e.rq_tags)} | {e.excerpt[:80]}")
        return "\n".join(lines)[:12000]

    def _tool_get_rq_coverage(self, _: dict) -> str:
        ev = self._evidence()
        rq_counts: dict[str, int] = {}
        for e in ev:
            for rq in e.rq_tags:
                rq_counts[rq] = rq_counts.get(rq, 0) + 1
        out = {f"RQ{i}": rq_counts.get(f"RQ{i}", 0) for i in range(1, 6)}
        gaps = [rq for rq, n in out.items() if n < 2]
        msg = json.dumps(out, ensure_ascii=False)
        if gaps:
            msg += (f"\n证据不足的 RQ：{', '.join(gaps)}（每 RQ 目标至少 2 条）。"
                    f"如当前选定论文不足以覆盖，可用检索工具补充候选。")
        return msg

    def _tool_search(self, source: str, inp: dict) -> str:
        query = inp["query"]
        if source == "openalex":
            searcher = OpenAlexSearcher(self.cache, self.data_dir)
            hits = searcher.search(query, per_page=15,
                                   log_path=self.data_dir / "search_runs.jsonl")
        else:
            searcher = CrossrefSearcher(self.cache, self.data_dir,
                                        mailto="litreview-course@example.com")
            hits = searcher.search(query, rows=15,
                                   log_path=self.data_dir / "search_runs.jsonl")
        touched, new_works, _ = merge_hits(hits, f"{self.run_id}-{source}",
                                           self.data_dir)
        titles = [f"- {h.title[:70]} ({h.year})" for h in hits[:15]]
        return (f"检索 {query!r}: {len(hits)} 命中，新增 {new_works} 项独立研究。\n"
                + "\n".join(titles))

    def _tool_submit_claim(self, inp: dict) -> str:
        ev_ids = {e.evidence_id for e in self._evidence()}
        missing = [i for i in inp["evidence_ids"] if i not in ev_ids]
        if missing:
            return f"错误：evidence_id 不存在：{missing}。只能引用已登记的证据。"
        c = Claim(text=inp["text"], evidence_ids=inp["evidence_ids"],
                  claim_type=inp["claim_type"], section=inp.get("section"),
                  support_status="supported")
        append_jsonl(self.data_dir / "claims.jsonl", c)
        return f"已登记 claim {c.claim_id}（{len(inp['evidence_ids'])} 条证据支持）"

    def make_executor(self):
        def executor(name: str, inp: dict) -> str:
            self.log(kind="tool_call", tool=name,
                     input_summary=json.dumps(inp, ensure_ascii=False)[:300])
            if name == "list_works":
                out = self._tool_list_works(inp)
            elif name == "read_pages":
                out = self._tool_read_pages(inp)
            elif name == "submit_evidence":
                out = self._tool_submit_evidence(inp)
            elif name == "list_evidence":
                out = self._tool_list_evidence(inp)
            elif name == "get_rq_coverage":
                out = self._tool_get_rq_coverage(inp)
            elif name == "search_openalex":
                out = self._tool_search("openalex", inp)
            elif name == "search_crossref":
                out = self._tool_search("crossref", inp)
            elif name == "submit_claim":
                out = self._tool_submit_claim(inp)
            elif name == "finish":
                self.log(kind="decision", decision_reason=inp.get("summary", "")[:500])
                out = "已记录总结。回合结束。"
            else:
                out = f"错误：未知工具 {name}"
            self.log(kind="tool_result", tool=name,
                     result_summary=str(out)[:300])
            return out
        return executor

    # ------------------------------------------------------------ 回合执行

    def run_turn(self, objective: str, max_steps: int = 12) -> str:
        """执行一个回合：状态 + 目标 → 模型工具循环 → 记录。"""
        self.log(kind="start", decision_reason=objective[:300])
        user_message = (f"当前状态：\n{self.state_summary()}\n\n"
                        f"本回合目标：{objective}\n\n"
                        f"请使用工具完成目标；结束时调用 finish 并总结"
                        f"（已完成、证据缺口、下一步建议）。")
        text, _ = self.backend.tool_loop(
            system=SYSTEM_PROMPT, user_message=user_message,
            tools=tool_specs(), executor=self.make_executor(),
            max_steps=max_steps)
        self.log(kind="end", result_summary=text[:500])
        # 任务记忆更新（进度）
        self.memory.append(
            __import__("litreview_agent.models", fromlist=["MemoryEvent"])
            .MemoryEvent(memory_id="progress-last-turn", action="update",
                         content=f"[{now_iso()}] {objective[:200]} → {text[:300]}",
                         source_ids=[], memory_kind="task"))
        return text
