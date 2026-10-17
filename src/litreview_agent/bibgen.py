"""references.bib 生成器：从 papers.jsonl 的 included 工作生成 BibTeX。

- 条目键 = work_id（与正文 \\cite{Wxxxx} 一一对应，引用检查器可直接对账）；
- 仅收录"有证据的 included"研究（正文实际引用池）；
- 元数据缺失字段留空/省略，禁止补造（protocol §5）；
- 特殊字符转义（& % # _）与作者 "Last, First" 格式化。
"""

from __future__ import annotations

import re
from pathlib import Path

from .models import Evidence, read_jsonl
from .tools.dedup import arxiv_id_from_doi, distinct_works, load_papers

ESCAPES = [("&", r"\&"), ("%", r"\%"), ("#", r"\#"), ("_", r"\_")]


def _tex_escape(s: str) -> str:
    for ch, rep in ESCAPES:
        s = s.replace(ch, rep)
    return s


def _format_authors(authors: list[str]) -> str:
    """作者名保持元数据原样拼接（'A and B'）。

    不做 Last-First 重排：显示名顺序忠实来源，避免中文名等
    顺序歧义引入新错误；BibTeX 对 'First Last' 形式可正常排序。
    仅清理尾随逗号/空白（OpenAlex 显示名偶带尾逗号）。
    """
    cleaned = [a.strip().rstrip(",").strip() for a in authors]
    return " and ".join(a for a in cleaned if a)


def _entry_type(p) -> str:
    """按 venue/发布状态推断 BibTeX 类型。"""
    venue = (p.venue or "").lower()
    if any(k in venue for k in ["arxiv", "preprint"]) or (not p.venue and p.arxiv_id):
        return "misc"
    if any(k in venue for k in ["conference", "proceedings", "meeting",
                                "acl", "emnlp", "neurips", "iclr", "icml",
                                "aaai", "ijcai"]):
        return "inproceedings"
    if any(k in venue for k in ["journal", "transactions", "letters", "survey"]):
        return "article"
    return "misc"


def generate_bib(data_dir: Path, out_path: Path,
                 only_with_evidence: bool = True) -> dict[str, int]:
    papers = load_papers(data_dir)
    works = distinct_works(papers)
    ev_path = data_dir / "evidence.jsonl"
    evidence = list(read_jsonl(ev_path, Evidence)) if ev_path.exists() else []
    ev_works = {e.work_id for e in evidence}  # type: ignore[arg-type]

    entries: list[str] = []
    n_misc = n_skipped = 0
    for wid, recs in sorted(works.items()):
        if not any(r.inclusion_status == "included" for r in recs):
            continue
        if only_with_evidence and wid not in ev_works:
            n_skipped += 1
            continue
        # 主记录：优先有 DOI 的（正式版），否则 arXiv 记录
        p = next((r for r in recs if r.doi and not (r.doi or "").startswith("10.48550")),
                 next((r for r in recs if r.arxiv_id), recs[0]))
        # arXiv ID：字段优先，缺失时从 arXiv DOI 确定性派生（10.48550/arxiv.<id>）
        ax = p.arxiv_id or arxiv_id_from_doi(p.doi)
        etype = _entry_type(p)
        lines = [f"@{etype}{{{wid},"]
        if p.authors:
            lines.append(f"  author = {{{_tex_escape(_format_authors(p.authors))}}},")
        lines.append(f"  title = {{{{{_tex_escape(p.title)}}}}},")
        if p.year:
            lines.append(f"  year = {{{p.year}}},")
        if p.venue and etype != "misc":
            lines.append(f"  booktitle = {{{_tex_escape(p.venue)}}},"
                         if etype == "inproceedings"
                         else f"  journal = {{{_tex_escape(p.venue)}}},")
        if p.doi and not p.doi.startswith("10.48550"):
            # arXiv DOI（10.48550）与 eprint 冗余，正式 DOI 才写 doi 字段
            lines.append(f"  doi = {{{p.doi}}},")
        if ax:
            lines.append(f"  eprint = {{{ax}}},")
            lines.append("  archivePrefix = {arXiv},")
            if etype == "misc":
                lines.append(f"  howpublished = {{arXiv:{ax}}},")
        elif etype == "misc" and p.url:
            lines.append(f"  howpublished = {{\\url{{{p.url}}}}},")
        if etype == "misc":
            n_misc += 1
        lines.append("}")
        entries.append("\n".join(lines))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "% 自动生成：uv run litreview bibgen（来源 data/papers.jsonl，仅含\n"
        "% included 且有证据的研究；键 = work_id，与正文 \\cite 对账）\n"
        "% 元数据缺失字段省略——不补造。\n\n" + "\n\n".join(entries) + "\n",
        encoding="utf-8")
    return {"entries": len(entries), "skipped_no_evidence": n_skipped,
            "arxiv_misc": n_misc}
