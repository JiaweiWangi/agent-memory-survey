"""学术检索工具：OpenAlex / arXiv / Semantic Scholar 适配器。

设计要点（docs/protocol.md §6）：
- 每次调用（含失败）写 data/search_runs.jsonl；
- 响应缓存到 data/derived/http_cache/，避免重复请求与限流；
- arXiv 实测连续快请求返回 "Rate exceeded."，强制 ≥min_interval 间隔 + 指数退避；
- S2 429 严重，仅作增益源：重试耗尽后抛 RateLimited，不阻塞调用方。
"""

from __future__ import annotations

import hashlib
import json
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

from ..models import SearchRun, append_jsonl

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class SearchError(Exception):
    pass


class RateLimited(SearchError):
    pass


@dataclass
class SearchHit:
    """归一化检索结果：来源无关的候选记录。"""

    source: str
    title: str
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    oa_id: Optional[str] = None  # OpenAlex work id（引文追踪用）
    is_oa: Optional[bool] = None
    oa_url: Optional[str] = None


class HttpCache:
    """简单文件缓存：URL+参数哈希 → 响应体。"""

    def __init__(self, cache_dir: Path):
        self.dir = cache_dir
        self.dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def _key(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:24]

    def get(self, url: str) -> Optional[str]:
        f = self.dir / f"{self._key(url)}.txt"
        if f.exists():
            self.hits += 1
            return f.read_text(encoding="utf-8")
        self.misses += 1
        return None

    def put(self, url: str, body: str) -> None:
        f = self.dir / f"{self._key(url)}.txt"
        f.write_text(body, encoding="utf-8")


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "https://dx.doi.org/", "doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d or None


def normalize_arxiv_id(aid: Optional[str]) -> Optional[str]:
    """'2310.08560v2' → '2310.08560'；旧式 'cs/0301012v1' → 'cs/0301012'。"""
    if not aid:
        return None
    a = aid.strip()
    # 去版本后缀（新旧式 ID 均为 v<digits> 结尾）
    if "v" in a.split("/")[-1]:
        base, sep, ver = a.rpartition("v")
        if sep and ver.isdigit() and ("." in base or "/" in base):
            return base
    return a


class BaseSearcher:
    name = "base"

    def __init__(self, cache: HttpCache, data_dir: Path, timeout: float = 30.0,
                 max_retries: int = 2):
        self.cache = cache
        self.data_dir = data_dir
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=timeout, follow_redirects=True,
                                    headers={"User-Agent": "litreview-agent/0.1 (course project)"})

    def _fetch(self, url: str, params: Optional[dict] = None,
               use_cache: bool = True) -> str:
        """带缓存与退避的 GET；最终失败抛 SearchError。"""
        full = url
        if params:
            full = str(httpx.URL(url, params=params))
        if use_cache:
            cached = self.cache.get(full)
            if cached is not None:
                return cached
        last_err: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                r = self._client.get(url, params=params)
                if r.status_code == 200:
                    if use_cache:
                        self.cache.put(full, r.text)
                    return r.text
                if r.status_code in (429, 503):
                    wait = 2 ** attempt * 3
                    time.sleep(wait)
                    last_err = f"HTTP {r.status_code}"
                    continue
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                break
            except httpx.HTTPError as e:
                last_err = f"{type(e).__name__}: {e}"
                time.sleep(2 ** attempt * 2)
        raise SearchError(f"{self.name} 请求失败 {full[:120]}: {last_err}")

    def _log(self, run: SearchRun, path: Path) -> None:
        append_jsonl(path, run)


class OpenAlexSearcher(BaseSearcher):
    name = "openalex"
    BASE = "https://api.openalex.org/works"

    def __init__(self, cache: HttpCache, data_dir: Path, mailto: str = "",
                 per_page: int = 50, **kw):
        super().__init__(cache, data_dir, **kw)
        self.mailto = mailto
        self.per_page = per_page

    def search(self, query: str, per_page: Optional[int] = None,
               from_year: Optional[int] = None, page: int = 1,
               log_path: Optional[Path] = None) -> list[SearchHit]:
        """page 翻页（cursor 翻页需 API key，实测 page 参数无需）。"""
        params: dict = {"search": query, "per-page": per_page or self.per_page,
                        "page": page}
        if self.mailto:
            params["mailto"] = self.mailto
        if from_year:
            params["filter"] = f"from_publication_date:{from_year}-01-01"
        run = SearchRun(source=self.name, query=query, filters=params.get("filter"),
                        cursor_or_page=f"page={page}", status="ok")
        try:
            text = self._fetch(self.BASE, params)
            data = json.loads(text)
        except SearchError as e:
            run.status, run.error = "failed", str(e)
            if log_path:
                self._log(run, log_path)
            raise
        hits = [self._to_hit(w) for w in data.get("results", [])]
        run.result_count = len(hits)
        if log_path:
            self._log(run, log_path)
        return hits

    def get_work(self, oa_id: str) -> Optional[dict]:
        """取单个 work 完整记录（含 referenced_works，向后追踪用）。"""
        try:
            text = self._fetch(oa_id)
            return json.loads(text)
        except (SearchError, json.JSONDecodeError):
            return None

    def works_citing(self, oa_id: str, per_page: int = 25,
                     log_path: Optional[Path] = None,
                     query_tag: str = "") -> list[SearchHit]:
        """向前追踪：引用了某 work 的后续研究（filter=cites:<id>）。"""
        params: dict = {"filter": f"cites:{oa_id}", "per-page": per_page}
        if self.mailto:
            params["mailto"] = self.mailto
        run = SearchRun(source=self.name, query=f"cites:{oa_id} {query_tag}".strip(),
                        filters=f"cites:{oa_id}", status="ok")
        try:
            text = self._fetch(self.BASE, params)
            data = json.loads(text)
        except SearchError as e:
            run.status, run.error = "failed", str(e)
            if log_path:
                self._log(run, log_path)
            raise
        hits = [self._to_hit(w) for w in data.get("results", [])]
        run.result_count = len(hits)
        if log_path:
            self._log(run, log_path)
        return hits

    def referenced_works(self, oa_id: str,
                         log_path: Optional[Path] = None) -> list[SearchHit]:
        """向后追踪：某 work 引用的参考文献（只返回有 title 的记录）。"""
        rec = self.get_work(oa_id)
        run = SearchRun(source=self.name, query=f"refs:{oa_id}",
                        status="ok" if rec else "failed")
        if not rec:
            if log_path:
                self._log(run, log_path)
            return []
        ref_ids = rec.get("referenced_works") or []
        hits: list[SearchHit] = []
        # 批量取：OpenAlex 支持 filter=ids.openalex:W1|W2|...
        for i in range(0, len(ref_ids), 50):
            chunk = ref_ids[i:i + 50]
            params: dict = {"filter": f"ids.openalex:{'|'.join(chunk)}",
                            "per-page": 50}
            if self.mailto:
                params["mailto"] = self.mailto
            try:
                text = self._fetch(self.BASE, params)
                data = json.loads(text)
                hits.extend(self._to_hit(w) for w in data.get("results", []))
            except SearchError:
                continue  # 单批失败不阻塞整轮追踪
        run.result_count = len(hits)
        if log_path:
            self._log(run, log_path)
        return hits

    @staticmethod
    def _to_hit(w: dict) -> SearchHit:
        doi = normalize_doi(w.get("doi"))
        year = w.get("publication_year")
        venue = None
        src = w.get("primary_location") or {}
        if src.get("source") and src["source"].get("display_name"):
            venue = src["source"]["display_name"]
        authors = [a.get("author", {}).get("display_name") or ""
                   for a in w.get("authorships", [])]
        oa = w.get("open_access") or {}
        return SearchHit(source="openalex", title=w.get("title") or "",
                         authors=[a for a in authors if a], year=year, venue=venue,
                         doi=doi, url=w.get("id"),
                         abstract=_oa_abstract(w), oa_id=w.get("id"),
                         is_oa=oa.get("is_oa"), oa_url=oa.get("oa_url"))


def _oa_abstract(w: dict) -> Optional[str]:
    inv = w.get("abstract_inverted_index")
    if not inv:
        return None
    pos_word: list[tuple[int, str]] = []
    for word, positions in inv.items():
        for p in positions:
            pos_word.append((p, word))
    return " ".join(w for _, w in sorted(pos_word))[:2000] or None


class ArxivSearcher(BaseSearcher):
    name = "arxiv"
    BASE = "https://export.arxiv.org/api/query"
    _last_call = 0.0  # 类级节流：全进程共享上次调用时间

    def __init__(self, cache: HttpCache, data_dir: Path,
                 min_interval: float = 3.0, **kw):
        kw.setdefault("timeout", 60.0)  # arXiv 复杂查询可能较慢
        super().__init__(cache, data_dir, **kw)
        self.min_interval = min_interval

    def _throttle(self) -> None:
        wait = ArxivSearcher._last_call + self.min_interval - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        ArxivSearcher._last_call = time.monotonic()

    def search(self, query: str, max_results: int = 50, start: int = 0,
               log_path: Optional[Path] = None) -> list[SearchHit]:
        params = {"search_query": query, "max_results": max_results, "start": start}
        run = SearchRun(source=self.name, query=query, cursor_or_page=str(start),
                        status="ok")
        last_err: Optional[str] = None
        for attempt in range(self.max_retries + 1):
            try:
                self._throttle()
                r = self._client.get(self.BASE, params=params)
                if r.status_code == 200 and not r.text.strip().startswith("Rate exceeded"):
                    self.cache.put(str(httpx.URL(self.BASE, params=params)), r.text)
                    hits = self._parse(r.text)
                    run.result_count = len(hits)
                    if log_path:
                        self._log(run, log_path)
                    return hits
                last_err = f"HTTP {r.status_code} / rate_limited"
            except httpx.HTTPError as e:
                last_err = f"{type(e).__name__}: {e}"
            # 限流或网络错误：指数退避后重试
            wait = 3 * (2 ** attempt)
            time.sleep(wait)
            run.error = f"attempt{attempt}: {last_err}"
        run.status = "failed"
        if log_path:
            self._log(run, log_path)
        raise RateLimited(f"arXiv 重试耗尽 ({last_err}): {query[:80]}")

    def _parse(self, atom_xml: str) -> list[SearchHit]:
        root = ET.fromstring(atom_xml)
        hits = []
        for entry in root.findall(f"{ATOM_NS}entry"):
            arxiv_id = normalize_arxiv_id(
                (entry.findtext(f"{ATOM_NS}id") or "").replace("http://arxiv.org/abs/", ""))
            title = (entry.findtext(f"{ATOM_NS}title") or "").strip().replace("\n", " ")
            authors = [a.findtext(f"{ATOM_NS}name") or ""
                       for a in entry.findall(f"{ATOM_NS}author")]
            published = entry.findtext(f"{ATOM_NS}published") or ""
            year = int(published[:4]) if published[:4].isdigit() else None
            summary = (entry.findtext(f"{ATOM_NS}summary") or "").strip()
            hits.append(SearchHit(source="arxiv", title=title, authors=authors,
                                  year=year, venue="arXiv", arxiv_id=arxiv_id,
                                  url=entry.findtext(f"{ATOM_NS}id"),
                                  abstract=summary[:2000] or None))
        return hits


class SemanticScholarSearcher(BaseSearcher):
    name = "s2"
    BASE = "https://api.semanticscholar.org/graph/v1/paper/search"

    def search(self, query: str, limit: int = 20, log_path: Optional[Path] = None,
               ) -> list[SearchHit]:
        params = {"query": query, "limit": limit,
                  "fields": "title,authors,year,venue,externalIds,abstract"}
        run = SearchRun(source=self.name, query=query, status="ok")
        try:
            text = self._fetch(self.BASE, params, use_cache=True)
            data = json.loads(text)
        except SearchError as e:
            run.status, run.error = "failed", str(e)
            if log_path:
                self._log(run, log_path)
            raise
        hits = []
        for p in data.get("data", []):
            ext = p.get("externalIds") or {}
            hits.append(SearchHit(
                source="s2", title=p.get("title") or "",
                authors=[a.get("name") or "" for a in p.get("authors", [])],
                year=p.get("year"), venue=p.get("venue") or None,
                doi=normalize_doi(ext.get("DOI")), arxiv_id=normalize_arxiv_id(ext.get("ArXiv")),
                abstract=(p.get("abstract") or "")[:2000] or None))
        run.result_count = len(hits)
        if log_path:
            self._log(run, log_path)
        return hits


class CrossrefSearcher(BaseSearcher):
    """Crossref：正式出版记录为主（DOI 核验与正式版本发现）。"""

    name = "crossref"
    BASE = "https://api.crossref.org/works"

    def __init__(self, cache: HttpCache, data_dir: Path, mailto: str = "", **kw):
        super().__init__(cache, data_dir, **kw)
        self.mailto = mailto

    def search(self, query: str, rows: int = 20, log_path: Optional[Path] = None,
               ) -> list[SearchHit]:
        params: dict = {"query": query, "rows": rows,
                        "select": "title,DOI,published,container-title,author"}
        if self.mailto:
            params["mailto"] = self.mailto
        run = SearchRun(source=self.name, query=query, status="ok")
        try:
            text = self._fetch(self.BASE, params)
            data = json.loads(text)
        except SearchError as e:
            run.status, run.error = "failed", str(e)
            if log_path:
                self._log(run, log_path)
            raise
        hits = []
        for it in data.get("message", {}).get("items", []):
            title = (it.get("title") or [""])[0]
            authors = [f"{a.get('given', '')} {a.get('family', '')}".strip()
                       for a in it.get("author", []) if a.get("family")]
            year = None
            dp = (it.get("published") or {}).get("date-parts", [[None]])[0]
            if dp and dp[0]:
                year = dp[0]
            hits.append(SearchHit(
                source="crossref", title=title, authors=authors, year=year,
                venue=(it.get("container-title") or [None])[0],
                doi=normalize_doi(it.get("DOI"))))
        run.result_count = len(hits)
        if log_path:
            self._log(run, log_path)
        return hits
