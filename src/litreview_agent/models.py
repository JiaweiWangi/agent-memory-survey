"""pydantic 数据模型：六个 JSONL 主文件 + 运行事件。

对应 docs/protocol.md §7 与 EXECUTION_PLAN.md §5.1。
原则：未知值留空（None）并注明原因，不用推测补齐；追加写入，不覆盖历史。
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------- search_runs


class SearchRun(BaseModel):
    """一次检索调用的完整记录（含失败与未完整分页）。"""

    search_id: str = Field(default_factory=lambda: new_id("srch"))
    source: str  # openalex / arxiv / s2
    query: str
    executed_at: str = Field(default_factory=now_iso)
    filters: Optional[str] = None  # 平台过滤条件原文
    result_count: Optional[int] = None  # None = 未取得（失败/中断）
    cursor_or_page: Optional[str] = None
    status: str  # ok / partial / failed
    error: Optional[str] = None
    notes: Optional[str] = None


# -------------------------------------------------------------------- papers


class Paper(BaseModel):
    """一项独立研究（work_id）的一条来源记录；同一 work_id 可有多条版本记录。"""

    work_id: str
    source_id: str = Field(default_factory=lambda: new_id("src"))
    title: str
    authors: list[str] = []
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None  # 归一化：小写、去前缀
    arxiv_id: Optional[str] = None  # 归一化：去版本后缀
    url: Optional[str] = None
    version: Optional[str] = None  # v1/v2/正式版等
    discovered_by: Optional[str] = None  # search_id 或 "citation_tracing"
    inclusion_status: str = "candidate"  # candidate / included / excluded / pending
    reason: Optional[str] = None  # 纳入/排除理由码或说明
    fulltext_status: str = "unknown"  # unknown / pdf_ok / html_ok / unavailable / failed
    local_path: Optional[str] = None  # sources/ 下的存档路径
    file_hash: Optional[str] = None  # sha256，正文版本绑定
    publication_status: Optional[str] = None  # preprint / conference / journal
    rq_tags: list[str] = []  # RQ1..RQ5
    checked_at: Optional[str] = None


# ------------------------------------------------------------------ evidence


class Evidence(BaseModel):
    """一条证据：原文片段 + 定位 + 解释 + 条件局限 + 核验状态。"""

    evidence_id: str = Field(default_factory=lambda: new_id("ev"))
    work_id: str
    source_id: str
    locator: str  # 如 "pdf:p5 Table 2" / "html:§3.2" / "abs 页" — 可回查
    excerpt: str  # 实际查看的原文片段（保留必要上下文）
    interpretation: str  # 用自己的话解释；区分作者结论与本组综合
    evidence_type: str  # mechanism / experiment / benchmark / definition / limitation
    conditions: Optional[str] = None  # 适用条件（模型、数据集、预算）
    limitations: Optional[str] = None
    extraction_status: str = "extracted"  # extracted / failed / partial
    verification_status: str = "auto_checked"  # auto_checked / model_assisted / human_verified
    rq_tags: list[str] = []
    extracted_at: str = Field(default_factory=now_iso)
    access_date: Optional[str] = None  # HTML 证据的访问日期


# -------------------------------------------------------------------- claims


class Claim(BaseModel):
    """一条可检查的陈述及其证据支持关系。"""

    claim_id: str = Field(default_factory=lambda: new_id("clm"))
    text: str
    evidence_ids: list[str] = []
    claim_type: str  # direct / synthesis / hypothesis
    support_status: str = "pending"  # supported / partial / pending / unsupported
    scope: Optional[str] = None  # 适用范围限定
    manuscript_location: Optional[str] = None  # 正文位置（章节/文件:行）
    issue_ids: list[str] = []  # 关联的核验问题
    section: Optional[str] = None  # 所属章节（引言/脉络/更新可靠性/评测/挑战）


# ------------------------------------------------------------------ reviews


class Review(BaseModel):
    """一次核验记录（真人或自动检查）。reviewer_type 区分，不得冒充。"""

    review_id: str = Field(default_factory=lambda: new_id("rev"))
    target_id: str  # paper.work_id / evidence.evidence_id / claim.claim_id
    reviewer_type: str  # human / auto_check / model_assisted
    reviewer_name: str  # 真人成员（A/B/C）或工具名；不得代签
    reviewed_at: str = Field(default_factory=now_iso)
    result: str  # pass / fail / needs_fix
    source_checked: Optional[str] = None  # 核验时查看的来源
    correction: Optional[str] = None
    resolved_at: Optional[str] = None


# ------------------------------------------------------------- memory_events


class MemoryEvent(BaseModel):
    """记忆事件（追加式）：更新通过 supersedes 链，不覆盖历史。"""

    event_id: str = Field(default_factory=lambda: new_id("mev"))
    memory_id: str  # 稳定记忆条目标识
    action: str  # create / update / supersede / dispute / reject / reactivate
    content: str
    source_ids: list[str] = []  # 支撑该记忆的 source_id / evidence_id
    created_at: str = Field(default_factory=now_iso)
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    supersedes: Optional[str] = None  # 被本条取代的 event_id
    valid_status: str = "active"  # active / superseded / disputed / rejected
    trust_status: str = "unverified"  # unverified / source_checked / human_verified
    memory_kind: str  # task / evidence / decision / experience（EXECUTION_PLAN §6.4）
    notes: Optional[str] = None


# ---------------------------------------------------------------- run events


class RunEvent(BaseModel):
    """runs/<run_id>/events.jsonl 的一条事件：决策链与用量的完整记录。"""

    event_id: str = Field(default_factory=lambda: new_id("run"))
    run_id: str
    ts: str = Field(default_factory=now_iso)
    kind: str  # start / tool_call / tool_result / model_call / model_result / decision / error / usage / end
    tool: Optional[str] = None
    input_summary: Optional[str] = None  # 简短可审查，不复制全文
    result_summary: Optional[str] = None
    decision_reason: Optional[str] = None  # 协调者的行动理由摘要
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    duration_ms: Optional[int] = None
    status: Optional[str] = None  # ok / failed / retried
    error: Optional[str] = None
    replay: bool = False  # 重放/模拟事件必须显式标识


# ---------------------------------------------------------------- JSONL I/O


def append_jsonl(path: Path, record: BaseModel) -> None:
    """追加一条记录（带字段验证）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json() + "\n")


def read_jsonl(path: Path, model: type[BaseModel]) -> list[BaseModel]:
    """读取并验证全部记录；坏行直接抛错（宁停不静默丢弃）。"""
    records = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(model.model_validate(json.loads(line)))
            except Exception as e:  # noqa: BLE001 — 上抛时带行号
                raise ValueError(f"{path}:{i} 无效记录: {e}") from e
    return records


MODEL_BY_FILE = {
    "search_runs.jsonl": SearchRun,
    "papers.jsonl": Paper,
    "evidence.jsonl": Evidence,
    "claims.jsonl": Claim,
    "reviews.jsonl": Review,
    "memory_events.jsonl": MemoryEvent,
    "events.jsonl": RunEvent,
}
