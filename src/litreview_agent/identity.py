"""论文身份核验：记录题名 vs 实际 PDF 首页（错配防线，D-6；v2 收紧判别规则）。

v1 教训：按"题名词半数命中"放行了 Reflexion 标题 + MemoryBank PDF
（language/agents 等通用词即可凑满半数）。v2 规则：
1. 题名首个显著词（≥4 字符、非停用词）**必须**命中——论文首页几乎总含
   自身题名，首词（如 Reflexion / MemoryBank / MemGPT）是最强判别词；
2. 其余显著词须命中 ≥ 半数；
3. 停用词（language/model/memory/learning/agent 等通用词）不参与命中
   计数，避免通用词放行。
回归案例（真实错配，见 tests）：
- Reflexion 标题 + MemoryBank(2305.10250) 首页 → 必须拒绝；
- MemoryBank 标题 + 气候论文(2307.08909) 首页 → 必须拒绝；
- 两者各自正确配对 → 必须通过。
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from .tools.dedup import arxiv_id_from_doi, distinct_works, load_papers

DROP = set("‐‑-­ \t\n\r\f\v")
# 通用词黑名单：领域内几乎任何 LLM 论文首页都会出现，无判别力
STOPWORDS = {
    "language", "model", "models", "memory", "learning", "agent", "agents",
    "large", "long-term", "long", "term", "based", "towards", "toward",
    "with", "using", "via", "for", "from", "about", "study", "survey",
    "approach", "framework", "system", "systems", "research", "enhancing",
    "empowering", "verbal", "reinforcement", "neural", "networks",
}


def _sig(s: str) -> str:
    return "".join(c for c in s.lower() if c not in DROP and not c.isspace())


def significant_words(title: str) -> list[str]:
    """题名显著词：≥4 字符且非停用词。"""
    words = re.split(r"[\s:：,，。.—–\-!?()]+", title or "")
    return [w for w in words if len(w) >= 4 and w.lower() not in STOPWORDS]


def identity_ok(recorded_title: str, first_page_text: str) -> bool:
    """PDF 首页与记录题名是否匹配（v2 规则，见模块 docstring）。"""
    sig = _sig(first_page_text or "")
    words = significant_words(recorded_title)
    if not words:
        # 无显著词可判（极短题名）：退化为全词命中检查
        words = [w for w in re.split(r"\s+", recorded_title or "") if w]
        if not words:
            return True
        return all(_sig(w) in sig for w in words)
    hits = [w for w in words if _sig(w) in sig]
    # 规则 1：首显著词必须命中
    if _sig(words[0]) not in sig:
        return False
    # 规则 2：其余显著词命中过半
    return len(hits) >= max(1, (len(words) + 1) // 2)


def first_page_text(pdf: Path) -> str:
    out = subprocess.run(["pdftotext", "-f", "1", "-l", "1", str(pdf), "-"],
                         capture_output=True, text=True, timeout=30)
    return out.stdout[:2500] if out.returncode == 0 else ""


def find_pdf_for(wid: str, works: dict, sources_dir: Path) -> Path | None:
    recs = works.get(wid, [])
    for r in recs:
        if r.local_path and Path(r.local_path).exists():
            return Path(r.local_path)
    for r in recs:
        ax = r.arxiv_id or arxiv_id_from_doi(r.doi)
        if ax and (sources_dir / f"{ax}.pdf").exists():
            return sources_dir / f"{ax}.pdf"
    return None


def check_identity(data_dir: Path, verbose: bool = True) -> list[dict]:
    """核心池全量身份核验。返回问题列表（空 = 全部通过）。"""
    import json
    pool = [json.loads(l) for l in
            (data_dir / "core_pool.jsonl").read_text().splitlines() if l.strip()]
    works = distinct_works(load_papers(data_dir))
    sources_dir = data_dir.parent / "sources"
    problems = []
    for p in pool:
        wid = p["work_id"]
        pdf = find_pdf_for(wid, works, sources_dir)
        if pdf is None:
            problems.append({"work_id": wid, "issue": "no_pdf",
                             "detail": p["title"][:50]})
            continue
        ft = first_page_text(pdf)
        if not identity_ok(p["title"], ft):
            actual = next((l.strip() for l in ft.splitlines()
                           if len(l.strip()) > 20), "?")
            problems.append({"work_id": wid, "issue": "title_mismatch",
                             "pdf": pdf.name, "detail": actual[:70]})
    if verbose:
        print(f"身份核验：{len(pool)} 项核心池，{len(problems)} 个问题")
        for pr in problems:
            print(f"  [{pr['issue']}] {pr['work_id']}: {pr['detail']}")
    return problems
