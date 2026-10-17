"""论文身份核验：记录题名 vs 实际 PDF 首页（错配防线，D-6）。

用于：
- 批处理前置校验（evidence_batch 调用）；
- `litreview check --scope identity` 全量核验核心池。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .models import load_valid_evidence
from .tools.dedup import arxiv_id_from_doi, distinct_works, load_papers

DROP = set("‐‑-­ \t\n\r\f\v")


def _sig(s: str) -> str:
    return "".join(c for c in s.lower() if c not in DROP and not c.isspace())


def first_page_text(pdf: Path) -> str:
    out = subprocess.run(["pdftotext", "-f", "1", "-l", "1", str(pdf), "-"],
                         capture_output=True, text=True, timeout=30)
    return out.stdout[:2500] if out.returncode == 0 else ""


def check_identity(data_dir: Path, verbose: bool = True) -> list[dict]:
    """核心池全量身份核验。返回问题列表（空 = 全部通过）。"""
    import json
    pool = [json.loads(l) for l in
            (data_dir / "core_pool.jsonl").read_text().splitlines() if l.strip()]
    works = distinct_works(load_papers(data_dir))
    src = data_dir.parent / "sources"
    problems = []
    for p in pool:
        wid = p["work_id"]
        recs = works.get(wid, [])
        pdf = None
        for r in recs:
            if r.local_path and Path(r.local_path).exists():
                pdf = Path(r.local_path)
                break
            ax = r.arxiv_id or arxiv_id_from_doi(r.doi)
            if ax and (src / f"{ax}.pdf").exists():
                pdf = src / f"{ax}.pdf"
                break
        if pdf is None:
            problems.append({"work_id": wid, "issue": "no_pdf",
                             "detail": p["title"][:50]})
            continue
        ft = first_page_text(pdf)
        # 题名核心词必须出现在首页（en-dash 等排版差异已归一）
        words = [w for w in re.split(r"[\s:：,，—–-]+", p["title"]) if len(w) > 3][:6]
        sig = _sig(ft)
        hits = [w for w in words if _sig(w) in sig]
        if len(hits) < max(2, len(words) // 2):
            actual = next((l.strip() for l in ft.splitlines()
                           if len(l.strip()) > 20), "?")
            problems.append({"work_id": wid, "issue": "title_mismatch",
                             "pdf": pdf.name, "detail": actual[:70]})
    if verbose:
        print(f"身份核验：{len(pool)} 项核心池，{len(problems)} 个问题")
        for pr in problems:
            print(f"  [{pr['issue']}] {pr['work_id']}: {pr['detail']}")
    return problems
