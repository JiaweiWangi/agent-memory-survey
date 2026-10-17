"""正文获取工具：arXiv PDF 下载 + pdftotext 页级提取 + HTML 章节提取。

- PDF 存档到 sources/<arxiv_id>.pdf，记录 sha256（版本绑定）；
- 页级文本提取用 poppler pdftotext（保留页码定位，供证据 locator 使用）；
- HTML 通道：arxiv.org/html 优先，ar5iv 兜底；记录 URL 与访问日期；
- 提取失败如实返回 None / False，不虚构内容。
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import httpx


@dataclass
class Fulltext:
    kind: str  # pdf / html
    path: Optional[Path] = None  # pdf 存档路径
    url: Optional[str] = None
    sha256: Optional[str] = None
    pages: Optional[int] = None
    text: Optional[str] = None  # html 正文文本（已去标签）
    sections: Optional[dict[str, str]] = None  # html: 章节名 → 文本


class Fetcher:
    def __init__(self, sources_dir: Path, cache_dir: Path, timeout: float = 90.0):
        self.sources_dir = sources_dir
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = httpx.Client(timeout=timeout, follow_redirects=True,
                                    headers={"User-Agent": "litreview-agent/0.1 (course project)"})

    # ------------------------------------------------------------------ PDF

    def fetch_pdf(self, arxiv_id: str) -> Optional[Fulltext]:
        """下载 arXiv PDF 并存档；已存在则直接复用（按文件名即版本标识）。"""
        pdf_path = self.sources_dir / f"{arxiv_id}.pdf"
        if not pdf_path.exists():
            url = f"https://arxiv.org/pdf/{arxiv_id}"
            try:
                r = self._client.get(url)
                if r.status_code != 200 or not r.content[:5].startswith(b"%PDF"):
                    return None
                pdf_path.write_bytes(r.content)
            except httpx.HTTPError:
                return None
        return Fulltext(kind="pdf", path=pdf_path,
                        sha256=_sha256(pdf_path), pages=_pdf_pages(pdf_path))

    def extract_pages(self, pdf_path: Path, first: int, last: int) -> str:
        """pdftotext 页级提取（first/last 均 1-based）。

        用 raw 模式（无 -layout）：按文本流逻辑顺序输出，双栏论文逐栏读取，
        连续摘录可验证；-layout 模式按视觉布局交错两栏，引用拼接会失败。
        """
        out = subprocess.run(
            ["pdftotext", "-f", str(first), "-l", str(last),
             str(pdf_path), "-"],
            capture_output=True, text=True, timeout=60)
        return out.stdout if out.returncode == 0 else ""

    def full_text(self, pdf_path: Path) -> str:
        out = subprocess.run(["pdftotext", str(pdf_path), "-"],
                             capture_output=True, text=True, timeout=120)
        return out.stdout if out.returncode == 0 else ""

    # ------------------------------------------------------------------ HTML

    def fetch_html(self, arxiv_id: str) -> Optional[Fulltext]:
        """arxiv.org/html 优先，ar5iv 兜底；返回章节化文本。"""
        for url in (f"https://arxiv.org/html/{arxiv_id}",
                    f"https://ar5iv.labs.arxiv.org/html/{arxiv_id}"):
            try:
                r = self._client.get(url)
                if r.status_code == 200 and len(r.text) > 5000:
                    sections = _parse_html_sections(r.text)
                    if sections:
                        return Fulltext(kind="html", url=url,
                                        sections=sections,
                                        text="\n\n".join(sections.values()))
            except httpx.HTTPError:
                continue
        return None


# ---------------------------------------------------------------------- utils


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _pdf_pages(path: Path) -> Optional[int]:
    out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True,
                         timeout=30)
    m = re.search(r"Pages:\s+(\d+)", out.stdout)
    return int(m.group(1)) if m else None


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\n{3,}")


def _parse_html_sections(html: str) -> dict[str, str]:
    """粗糙但可定位的 HTML 章节切分：按 <h2>/<h3> 标题。"""
    sections: dict[str, str] = {}
    parts = re.split(r"<h[23][^>]*>(.*?)</h[23]>", html, flags=re.S)
    # parts: [pre, title1, body1, title2, body2, ...]
    if len(parts) >= 3:
        for i in range(1, len(parts) - 1, 2):
            title = _TAG_RE.sub("", parts[i]).strip()[:120]
            body = _TAG_RE.sub(" ", parts[i + 1])
            body = _WS_RE.sub("\n\n", body.replace("<", " <")).strip()
            if title and len(body) > 200:
                sections[title] = body
    return sections
