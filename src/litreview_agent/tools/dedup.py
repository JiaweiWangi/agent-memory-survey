"""身份归并与去重：SearchHit → papers.jsonl 的 work_id 记录。

规则（docs/protocol.md §5）：
1. arXiv ID（归一化后）优先匹配；
2. DOI（归一化后）次之；
3. 兜底：题名归一化 + 首作者姓氏 + 年份；
4. 同一研究的多版本共享 work_id；OpenAlex 的 arXiv DOI（10.48550/arxiv.*）
   与 arXiv ID 视为同一身份线索。
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Optional

from ..models import Paper, append_jsonl, read_jsonl
from .search import SearchHit, normalize_arxiv_id, normalize_doi

ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.(.+)$")


def _norm_title(title: str) -> str:
    """题名归一化：Unicode NFKC、小写、去标点与空白。"""
    t = unicodedata.normalize("NFKC", title or "").lower()
    t = re.sub(r"[^\w\s]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _first_author_surname(authors: list[str]) -> str:
    if not authors:
        return ""
    # "Charles Packer" → "packer"；中文/复合名取末词
    return authors[0].split()[-1].lower() if authors[0].split() else ""


def arxiv_id_from_doi(doi: Optional[str]) -> Optional[str]:
    """OpenAlex 常把 arXiv 预印本 DOI 记为 10.48550/arxiv.<id>。"""
    if not doi:
        return None
    m = ARXIV_DOI_RE.match(doi)
    return normalize_arxiv_id(m.group(1)) if m else None


class WorkRegistry:
    """已见工作登记表：三种键 → work_id。"""

    def __init__(self, papers: list[Paper]):
        self.papers = papers  # 既有记录（按追加顺序）
        self.by_arxiv: dict[str, str] = {}
        self.by_doi: dict[str, str] = {}
        self.by_title_key: dict[str, str] = {}
        for p in papers:
            self._index(p)

    def _index(self, p: Paper) -> None:
        if p.arxiv_id:
            self.by_arxiv.setdefault(p.arxiv_id, p.work_id)
        if p.doi:
            self.by_doi.setdefault(p.doi, p.work_id)
            ax = arxiv_id_from_doi(p.doi)
            if ax:
                self.by_arxiv.setdefault(ax, p.work_id)
        tk = (_norm_title(p.title), _first_author_surname(p.authors), p.year)
        self.by_title_key.setdefault(tk, p.work_id)

    def match(self, hit: SearchHit) -> Optional[str]:
        """返回已存在的 work_id，无匹配返回 None。"""
        ax = hit.arxiv_id or arxiv_id_from_doi(hit.doi)
        if ax and ax in self.by_arxiv:
            return self.by_arxiv[ax]
        if hit.doi and hit.doi in self.by_doi:
            return self.by_doi[hit.doi]
        tk = (_norm_title(hit.title), _first_author_surname(hit.authors), hit.year)
        if tk in self.by_title_key:
            return self.by_title_key[tk]
        # 题名+首作者（不带年份）作为弱匹配，防年份错录漏并
        for (t, a, y), wid in self.by_title_key.items():
            if t == tk[0] and a == tk[1] and tk[2] and y and abs(tk[2] - y) <= 1:
                return wid
        return None


def _next_work_id(papers: list[Paper]) -> str:
    if not papers:
        return "W0001"
    nums = [int(p.work_id[1:]) for p in papers if p.work_id.startswith("W") and p.work_id[1:].isdigit()]
    return f"W{max(nums) + 1:04d}" if nums else "W0001"


def merge_hits(hits: list[SearchHit], discovered_by: str,
               data_dir: Path) -> tuple[list[Paper], int, int]:
    """把检索命中合并进 papers.jsonl。

    返回 (本次涉及的全部记录, 新增 work_id 数, 追加版本记录数)。
    同一 hit 若命中已有 work_id 且该来源无记录，则追加一条 source_id 记录
    （保留版本线索），work_id 不重复计数。
    """
    path = data_dir / "papers.jsonl"
    papers = load_papers(data_dir)
    reg = WorkRegistry(papers)
    touched: list[Paper] = []
    new_works = appended = 0
    for hit in hits:
        if not hit.title:
            continue
        wid = reg.match(hit)
        if wid is None:
            wid = _next_work_id(papers)
            paper = Paper(
                work_id=wid, title=hit.title, authors=hit.authors, year=hit.year,
                venue=hit.venue, doi=hit.doi or None, arxiv_id=hit.arxiv_id or None,
                url=hit.url or None, discovered_by=discovered_by,
                inclusion_status="candidate")
            papers.append(paper)
            reg._index(paper)
            touched.append(paper)
            append_jsonl(path, paper)
            new_works += 1
            appended += 1
        else:
            # 已有 work_id：仅当带来新身份线索（如 OpenAlex 的正式 DOI）时追加版本记录
            existing = [p for p in papers if p.work_id == wid]
            known_dois = {p.doi for p in existing if p.doi}
            known_ax = {p.arxiv_id for p in existing if p.arxiv_id}
            new_doi = hit.doi if (hit.doi and hit.doi not in known_dois) else None
            new_ax = hit.arxiv_id if (hit.arxiv_id and hit.arxiv_id not in known_ax) else None
            if new_doi or new_ax:
                paper = Paper(
                    work_id=wid, title=hit.title, authors=hit.authors, year=hit.year,
                    venue=hit.venue, doi=new_doi, arxiv_id=new_ax, url=hit.url or None,
                    version="alt-version-record", discovered_by=discovered_by,
                    inclusion_status=existing[0].inclusion_status,
                    reason="alternate version record from " + hit.source)
                papers.append(paper)
                reg._index(paper)
                touched.append(paper)
                append_jsonl(path, paper)
                appended += 1
    return touched, new_works, appended


def load_papers(data_dir: Path) -> list[Paper]:
    """读取当前状态：papers.jsonl 追加式存储，同一 (work_id, source_id)
    的后续记录覆盖先前状态（事件化更新，历史保留在文件中）。"""
    path = data_dir / "papers.jsonl"
    if not path.exists():
        return []
    latest: dict[tuple[str, str], Paper] = {}
    for p in read_jsonl(path, Paper):
        latest[(p.work_id, p.source_id)] = p
    return list(latest.values())


def append_paper_update(data_dir: Path, paper: Paper) -> None:
    """追加一条状态更新记录（同 work_id + source_id）。"""
    append_jsonl(data_dir / "papers.jsonl", paper)


def distinct_works(papers: list[Paper]) -> dict[str, list[Paper]]:
    """work_id → 该研究的全部版本记录。"""
    out: dict[str, list[Paper]] = {}
    for p in papers:
        out.setdefault(p.work_id, []).append(p)
    return out
