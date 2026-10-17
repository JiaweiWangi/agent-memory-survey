"""G3 批量证据提取：逐篇单次模型调用 + G2 同款摘录验证器。

每篇 included 且有正文通道的论文：
1. 取/下载 PDF，提取前 N 页 raw 文本（逐页缓存）；
2. 单次模型调用：从给定文本提取 2–4 条证据（JSON，excerpt 逐字）；
3. 每条 excerpt 用 Coordinator._find_verbatim_span 对实际页文本验证；
   失败条目丢弃并记录（不虚构、不降级）；
4. 通过者写 evidence.jsonl（verification_status=model_assisted）。

运行记录：runs/eb-<id>/events.jsonl（含每篇 token 用量与失败原因）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from .coordinator import Coordinator
from .model_backends import AnthropicBackend
from .models import Evidence, RunEvent, append_jsonl, now_iso, read_jsonl
from .tools.dedup import arxiv_id_from_doi, distinct_works, load_papers
from .tools.fetch import Fetcher

EXTRACT_PROMPT = """你是文献综述的证据提取员。主题：LLM 智能体长期记忆（组织、更新、可靠性、评测）。

从下方论文文本中提取 2–4 条最有综述价值的证据。每条输出 JSON：
{"page": <页码整数>, "locator": "pdf:p<N> <章节/表图，如 §3.2 / Table 2>",
 "excerpt": "<该页上连续的原文片段，1–3 句，逐字复制，不要改写/省略/合并>",
 "interpretation": "<用自己的话说明该证据的意义；区分作者结论与你的综合>",
 "evidence_type": "mechanism|experiment|benchmark|definition|limitation",
 "conditions": "<适用条件：模型/数据集/设置，没有则空串>",
 "limitations": "<局限，没有则空串>",
 "rq_tags": ["RQ1".."RQ5" 中相关的]}

规则：
- excerpt 必须逐字来自给定页文本（系统会验证；改写会被丢弃）；
- 优先覆盖：核心机制、实验/基准数字、明确声明的局限；
- 跨行连字符按原文即可（mem-
ory），系统匹配时忽略空白与连字符差异；
- 只输出 JSON 数组，不要其他文字。

论文题名：TITLE_PLACEHOLDER

文本：
PAGES_PLACEHOLDER"""


def _evidence_path(data_dir: Path) -> Path:
    return data_dir / "evidence.jsonl"


def _existing_evidence(data_dir: Path) -> dict[str, list[Evidence]]:
    """当前有效证据（按 work 分组）；被 reviews.jsonl 判 fail 的不计——
    废止的工作需要重新提取。"""
    from .models import load_valid_evidence
    out: dict[str, list[Evidence]] = {}
    for e in load_valid_evidence(data_dir):  # type: ignore[attr-defined]
        out.setdefault(e.work_id, []).append(e)
    return out


def _parse_json_array(text: str) -> Optional[list[dict]]:
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        return None
    try:
        data = json.loads(m.group(0))
        return data if isinstance(data, list) else None
    except json.JSONDecodeError:
        return None


def _identity_ok(recorded_title: str, first_page_text: str) -> bool:
    """PDF 首页必须出现记录题名的主要词（忽略大小写/空白/连字符）。

    反例教训：错配的 arXiv ID 会让气候论文的证据进入 MemoryBank 条目
    （docs/decisions.md D-6）。
    """
    import re as _re
    drop = set("‐‑-­ \t\n\r\f\v")
    sig = "".join(c for c in (first_page_text or "").lower()
                  if c not in drop and not c.isspace())
    # 取题名前 5 个实词（跳过冠词等短词）
    words = [w for w in _re.split(r"[\s:：,，—-]+", recorded_title) if len(w) > 3][:5]
    if not words:
        return True
    hit = sum(1 for w in words if "".join(w.lower().split()) in sig)
    return hit >= max(2, len(words) // 2)


def run_evidence_batch(data_dir: Path, backend: AnthropicBackend,
                       max_works: Optional[int] = None,
                       pages_per_work: int = 3,
                       only_work_ids: Optional[list[str]] = None) -> dict[str, Any]:
    run_id = f"eb-{now_iso()[11:13]}{now_iso()[14:16]}{now_iso()[17:19]}"
    events_path = data_dir.parent / "runs" / run_id / "events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)

    def log(**kw):
        append_jsonl(events_path, RunEvent(run_id=run_id, **kw))

    works = distinct_works(load_papers(data_dir))
    existing = _existing_evidence(data_dir)
    fetcher = Fetcher(data_dir.parent / "sources",
                      data_dir / "derived" / "http_cache")

    # 队列：included、有 arXiv 通道、尚无证据；分支优先级排序
    # （update/reliability/eval/survey 是核心章节，organize 数量大放后）
    branch_priority = {"update": 0, "reliability": 1, "eval": 2, "survey": 3,
                       "background": 4, "organize": 5}
    queue = []
    for wid, recs in works.items():
        if only_work_ids is not None and wid not in only_work_ids:
            continue
        if not any(r.inclusion_status == "included" for r in recs):
            continue
        if wid in existing:
            continue
        p = next((r for r in recs if r.arxiv_id or arxiv_id_from_doi(r.doi)
                  or r.local_path), recs[0])
        ax = p.arxiv_id or arxiv_id_from_doi(p.doi)
        if not (ax or (p.local_path and Path(p.local_path).exists())):
            continue
        pr = next((r for r in recs if r.inclusion_status == "included"), recs[0])
        branch = (pr.reason or "").replace("branch=", "").split("|")[0].strip()
        pri = branch_priority.get(branch, 5)
        queue.append((wid, ax, p, pri))
    # 稳定排序：分支优先级 → work_id（可复现）
    queue.sort(key=lambda x: (x[3], x[0]))
    queue = [(w, a, p) for w, a, p, _ in queue]
    queue = queue[:max_works] if max_works else queue
    log(kind="start", decision_reason=f"批量证据提取：{len(queue)} 篇待处理"
        f"（分支优先级排序）")

    stats = {"processed": 0, "evidence_added": 0, "excerpt_rejected": 0,
             "fetch_failed": 0, "model_failed": 0, "parse_failed": 0}
    for wid, ax, p in queue:
        # --- 正文获取 ---
        pdf_path = Path(p.local_path) if p.local_path and Path(p.local_path).exists() else None
        if pdf_path is None and ax:
            ft = fetcher.fetch_pdf(ax)
            if ft and ft.path:
                pdf_path = ft.path
        if pdf_path is None:
            stats["fetch_failed"] += 1
            log(kind="tool_result", tool="fetch_pdf", status="failed",
                input_summary=wid, error="正文不可得")
            continue
        # --- PDF 身份校验（防错配：首页签名必须含记录题名的核心词）---
        first_page = fetcher.extract_pages(pdf_path, 1, 1)
        if not _identity_ok(p.title or "", first_page):
            stats["identity_failed"] = stats.get("identity_failed", 0) + 1
            log(kind="tool_result", tool="identity_check", status="failed",
                input_summary=wid,
                error=f"PDF 首页与记录题名不符：{pdf_path.name}")
            continue

        # --- 页文本 ---
        pages: dict[int, str] = {}
        page_blocks = []
        for pg in range(1, pages_per_work + 1):
            pages[pg] = fetcher.extract_pages(pdf_path, pg, pg)
            page_blocks.append(f"=== 第 {pg} 页 ===\n{pages[pg]}")
        pages_text = "\n".join(page_blocks)
        if len(pages_text.strip()) < 500:
            stats["fetch_failed"] += 1
            log(kind="tool_result", tool="extract_pages", status="failed",
                input_summary=wid, error=f"页文本过短({len(pages_text.strip())})")
            continue
        # --- 模型提取 ---
        try:
            prompt = (EXTRACT_PROMPT
                      .replace("TITLE_PLACEHOLDER", (p.title or "")[:150])
                      .replace("PAGES_PLACEHOLDER", pages_text[:45000]))
            result = backend.complete(
                system=prompt,
                messages=[{"role": "user", "content":
                           "提取证据。只输出 JSON 数组。"}],
                max_tokens=3500)
        except Exception as e:  # noqa: BLE001
            stats["model_failed"] += 1
            log(kind="error", tool="model_call", input_summary=wid,
                error=str(e)[:300], status="failed")
            continue
        items = _parse_json_array(result.text)
        if not items:
            stats["parse_failed"] += 1
            log(kind="error", tool="parse", input_summary=wid,
                error=result.text[:200], status="failed")
            continue
        # --- 验证并写入 ---
        added = rejected = 0
        source_id = p.source_id
        for it in items:
            try:
                page_no = int(it.get("page", 0))
                excerpt = str(it.get("excerpt", ""))
                page_text = pages.get(page_no, "")
                if not page_text:
                    rejected += 1
                    continue
                verbatim = Coordinator._find_verbatim_span(excerpt, page_text)
                if verbatim is None:
                    rejected += 1
                    continue
                rq_tags = [r for r in (it.get("rq_tags") or [])
                           if str(r).startswith("RQ")] or ["RQ2"]
                ev = Evidence(
                    work_id=wid, source_id=source_id,
                    locator=str(it.get("locator") or f"pdf:p{page_no}"),
                    excerpt=verbatim.strip()[:1500],
                    interpretation=str(it.get("interpretation", ""))[:1200],
                    evidence_type=it.get("evidence_type") or "mechanism",
                    conditions=(str(it["conditions"]) if it.get("conditions") else None),
                    limitations=(str(it["limitations"]) if it.get("limitations") else None),
                    rq_tags=rq_tags,
                    verification_status="model_assisted")
                append_jsonl(_evidence_path(data_dir), ev)
                added += 1
            except (ValueError, TypeError, KeyError):
                rejected += 1
                continue
        stats["processed"] += 1
        stats["evidence_added"] += added
        stats["excerpt_rejected"] += rejected
        log(kind="tool_result", tool="extract_work", input_summary=wid,
            result_summary=f"+{added} 证据, {rejected} 摘录被拒", status="ok")
    log(kind="end", result_summary=json.dumps(stats, ensure_ascii=False))
    return {**stats, "run_id": run_id}
