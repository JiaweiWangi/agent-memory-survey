"""核心阅读池构建：按综述作用分层选取（用户策略对齐版）。

输入：papers.jsonl（含筛选状态）+ evidence.jsonl（阅读状态）
输出：data/core_pool.jsonl + docs/derived 三件套（拟选表/覆盖矩阵/降级清单）

选取规则（docs/decisions.md D-3）：
- 每篇必须回答：解决什么问题 / 承担什么作用 / 提供什么不同；
- "标题相关""可下载""发表新"不构成入选理由；
- 分层结构为参考而非机械配额，每篇计一个主要角色。
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Evidence, read_jsonl
from .tools.dedup import distinct_works, load_papers

# 分层选取清单： (层, 作用角色, 题名锚, 纳入理由[三问浓缩], 关联RQ)
SELECTION: list[tuple[str, str, str, str, list[str]]] = [
    # ---- L1 基础系统与代表方法（8）----
    ("L1-基础系统", "奠基范式", "Generative Agents: Interactive Simulacra",
     "记忆流+新近度/重要度/相关度三因子检索+反思生成高层记忆；后续几乎所有智能体记忆工作引用此范式。作用：组织与检索层的起点。差异：首次把'记忆流'作为智能体基础设施。",
     ["RQ1", "RQ2"]),
    ("L1-基础系统", "虚拟上下文管理", "MemGPT: Towards LLMs as Operating Systems",
     "把上下文窗口当内存、外部存储当磁盘的 OS 隐喻，self-editing 记忆。作用：上下文工程路线代表。差异：以分页/中断机制解决容量，而非检索质量。",
     ["RQ1", "RQ2"]),
    ("L1-基础系统", "遗忘引入", "MemoryBank: Enhancing Large Language Models",
     "Ebbinghaus 遗忘曲线做记忆强度衰减+每日更新。作用：遗忘机制的早期代表（AAAI 2024）。差异：首个把认知遗忘曲线用于 LLM 助理记忆。",
     ["RQ3"]),
    ("L1-基础系统", "语言化经验", "Reflexion: language agents",
     "失败后生成语言化自我反思存入情景记忆供后续尝试。作用：经验记忆代表。边界：任务级重试记忆，非助理跨会话记忆——须在正文明确区分。",
     ["RQ2", "RQ1"]),
    ("L1-基础系统", "读写式记忆", "RET-LLM: Towards a General Read-Write Memory",
     "DB 管理员隐喻：非参数记忆先检索后改写。作用：可写外部记忆的早期结构化方案。差异：显式读写操作而非追加式日志。",
     ["RQ2", "RQ3"]),
    ("L1-基础系统", "经验池", "ExpeL: LLM Agents Are Experiential Learners",
     "跨任务积累成功轨迹并提炼 insights（AAAI 2024）。作用：程序性经验记忆。差异：从轨迹到规则的抽象层。",
     ["RQ2"]),
    ("L1-基础系统", "动态组织", "A-Mem: Agentic Memory",
     "Zettelkasten 式笔记：新记忆触发邻接链接与记忆演化。作用：动态组织代表。差异：记忆自组织更新，区别于固定 schema。",
     ["RQ2", "RQ3"]),
    ("L1-基础系统", "生产级记忆操作", "Mem0: Building Production-Ready AI Agents",
     "ADD/UPDATE/DELETE/NOOP 四操作的记忆管理管线+评估。作用：工程化更新路线。差异：把更新建模为显式操作决策。",
     ["RQ2", "RQ3", "RQ5"]),
    # ---- L2 组织、表示与检索（7）----
    ("L2-组织检索", "时间知识图谱", "Zep: A Temporal Knowledge Graph Architecture",
     "对话事件实时构建带时间有效期的实体关系图。作用：时间感知组织。差异：图结构+时间元数据，区别于向量库。",
     ["RQ2", "RQ3"]),
    ("L2-组织检索", "非破坏性组织", "Mem++: Non-Destructive Memory",
     "写入不破坏原始记录，读取时按查询物化视图。作用：解决'保留原始 vs 结构化'权衡。差异：读时选择范式。",
     ["RQ2", "RQ3"]),
    ("L2-组织检索", "情景-语义分层", "Synapse: Empowering LLM Agents",
     "情景记忆(trail)与语义记忆分层。作用：记忆类型学实现。差异：显式区分两类记忆及其转换。",
     ["RQ1", "RQ2"]),
    ("L2-组织检索", "分层图记忆", "HiGMem: A Hierarchical and LLM-Guided",
     "LLM 引导的分层图组织。作用：分层表示代表。差异：层间抽象与 LLM 判断结合。",
     ["RQ2"]),
    ("L2-组织检索", "递归巩固", "RecMem: Recurrence-based Memory Consolidation",
     "递归巩固替代每条交互调用 LLM。作用：效率维度。差异：解决 eager 固化的 token 成本问题。",
     ["RQ2", "RQ3"]),
    ("L2-组织检索", "证据锚定时间图", "SodaMem: Evidence-Grounded Temporal Graph",
     "证据锚定的时间图记忆。作用：组织与可追溯结合。差异：记忆条目绑定证据来源。",
     ["RQ2", "RQ4"]),
    ("L2-组织检索", "多类型记忆系统", "MIRIX: Multi-Agent Memory System",
     "情景/语义/程序性等多类型记忆的多智能体管理系统（2025）。作用：记忆类型学系统实现。差异：六类记忆显式分型与并行 worker 架构，区别于单一记忆流。",
     ["RQ1", "RQ2"]),
    # ---- L3 更新、遗忘、时间与冲突（8）----
    ("L3-更新遗忘", "图记忆选择性遗忘", "Selective Forgetting: A Graph-Based",
     "图记忆上的一次性剪枝：27,021 节点图移除 9.8% 节点/9.5% 字节而 token F1 基本不变。作用：遗忘的实证效果。差异：图粒度遗忘及成本-效果测量。",
     ["RQ3", "RQ5"]),
    ("L3-更新遗忘", "遗忘治理原语", "When to Forget: A Memory Governance",
     "记忆价值(MW)指标+遗忘决策原语；过时记忆 MW 0.17 vs 专家记忆 0.77。作用：何时遗忘的可操作判据。差异：治理视角而非机制视角。",
     ["RQ3", "RQ5"]),
    ("L3-更新遗忘", "存储/使用分离", "What Should an Agent Forget?",
     "区分'存了什么'与'检索时用什么'。作用：遗忘的作用域澄清。差异：遗忘决策从写入移到使用点。",
     ["RQ3"]),
    ("L3-更新遗忘", "偏好演变更新", "Preference-Aware Memory Update",
     "用户偏好变化的记忆更新。作用：冲突信息的一类真实场景。差异：偏好漂移 vs 事实失效的区分。",
     ["RQ3"]),
    ("L3-更新遗忘", "预算策展遗忘", "Forget to Improve: On-Device",
     "设备端预算约束下的持续学习与遗忘。作用：资源约束维度。差异：遗忘作为性能手段。",
     ["RQ3"]),
    ("L3-更新遗忘", "检索驱动再巩固", "Retrieval-Driven Memory Reconsolidation",
     "检索时触发记忆再巩固（认知科学机制）。作用：更新的认知理论路径。差异：再巩固 vs 重写。",
     ["RQ3", "RQ1"]),
    ("L3-更新遗忘", "版本规范化", "Memory Canonicalization: A Framework",
     "记忆条目版本混乱的规范化框架+基准。作用：更新一致性。差异：把'同一事实多版本'显式定义为研究对象。",
     ["RQ3", "RQ5"]),
    # ---- L4 评测基准与方法（7）----
    ("L4-评测", "超长期对话QA", "Evaluating Very Long-Term Conversational Memory",
     "LoCoMo 基准（ACL 2024，被引85）：超长对话+多类型 QA。作用：评测层锚点。差异：会话跨度(35轮/最高26K token)远超此前基准。",
     ["RQ5"]),
    ("L4-评测", "五能力维度", "LongMemEval: Benchmarking Chat Assistants",
     "ICLR 2025：信息抽取/多会话推理/时间推理/知识更新/拒绝回答五维度。作用：能力分类学。差异：知识更新与拒绝首次入基准。",
     ["RQ5", "RQ3"]),
    ("L4-评测", "召回vs遗忘", "From Recall to Forgetting: Benchmarking",
     "ACL Findings 2026：同时评测记忆与遗忘。作用：补齐评测缺口。差异：遗忘正确性作为一等指标。",
     ["RQ5", "RQ3"]),
    ("L4-评测", "多模态评测", "Mem-Gallery: Benchmarking Multimodal",
     "ACL 2026：多模态长期对话记忆基准。作用：模态边界。差异：多模态记忆组织与检索。",
     ["RQ5", "RQ1"]),
    ("L4-评测", "记忆构建评测", "MemBuilder: Reinforcing LLMs",
     "ACL 2026：RL 构建长期记忆+属性评测。作用：构建质量评测。差异：评'怎么写'而非'怎么用'。",
     ["RQ5", "RQ2"]),
    ("L4-评测", "综合记忆评测", "MemBench: Towards More Comprehensive Evaluation",
     "LLM 智能体记忆的综合评测基准（2025）。作用：评测维度系统化。差异：QA+开放域对话双通道，覆盖检索与推理。",
     ["RQ5"]),
    ("L4-评测", "成本感知评测", "When Does Memory Help? A Cost-Aware",
     "记忆收益与成本的联合评测。作用：公平比较框架。差异：成本纳入指标而非只看准确率。",
     ["RQ5", "RQ2"]),
    # ---- L5 非恶意可靠性（4）----
    ("L5-非恶意可靠性", "错误传播", "The Hallucination Snowball",
     "错误经状态转移传播的建模（雪球效应）。作用：可靠性核心问题——错误如何进入并放大。差异：传播动力学视角。",
     ["RQ4"]),
    ("L5-非恶意可靠性", "检索可采纳性", "The Right Memory in the Wrong Context",
     "记忆内容正确但上下文不适配（admissibility）的验证。作用：错误使用维度。差异：'检索对了但用错'这一被忽视的失效模式。",
     ["RQ4", "RQ3"]),
    ("L5-非恶意可靠性", "压缩信息损失", "What to Keep, What to Forget: A Rate",
     "率失真理论视角看记忆压缩的信息损失。作用：摘要失真的理论刻画。差异：给出压缩-保真的形式框架。",
     ["RQ4", "RQ3"]),
    ("L5-非恶意可靠性", "记忆幻觉评测", "HaluMem: Evaluating Hallucinations in Memory",
     "记忆系统幻觉的专项评测基准（2025）。作用：错误写入/错误检索的直接测量。差异：把'记忆导致的幻觉'与'模型幻觉'分离量化。",
     ["RQ4", "RQ5"]),
    ("L5-非恶意可靠性", "来源感知", "Agent Zero Memory: Provenance-Aware",
     "来源感知的长期记忆。作用：来源丢失防线。差异：provenance 作为记忆一等公民。",
     ["RQ4"]),
    # ---- L6 安全与投毒（3）----
    ("L6-安全投毒", "攻防综合", "Memory Poisoning Attack and Defense",
     "记忆投毒攻击面+防御模块（信任过滤+复合门槛）。作用：安全分支代表。差异：攻防对照的完整实证。",
     ["RQ4"]),
    ("L6-安全投毒", "选择性绕过后门", "MemPoison: Bypassing Selective Memory",
     "绕过选择性记忆机制植入后门。作用：攻击与防御机制共同演化例证。差异：对记忆筛选机制本身的攻击。",
     ["RQ4"]),
    ("L6-安全投毒", "防御成本", "The Price of Safety",
     "记忆防护的良性场景效用损失与 token 开销。作用：安全的代价维度。差异：防御本身的负外部性。",
     ["RQ4", "RQ2"]),
    # ---- L7 综述/框架/边界对照（3）----
    ("L7-综述与边界", "概念框架", "Cognitive Architectures for Language Agents",
     "CoALA：LLM 智能体认知架构统一框架（决策/记忆/学习模块）。作用：概念地图与术语对齐。差异：把记忆放进完整认知架构而非孤立组件。",
     ["RQ1"]),
    ("L7-综述与边界", "安全综述", "A Survey on Long-Term Memory Security",
     "6 阶段记忆生命周期安全框架。作用：可靠性的系统化图谱。差异：攻击/防御按生命周期阶段组织。",
     ["RQ4", "RQ1"]),
    ("L7-综述与边界", "记忆机制综述", "A Survey on the Memory Mechanism",
     "LLM 智能体记忆机制综述（2025，被引143）。作用：机制分类图谱与本文分类的对照基准。差异：本综述聚焦更新与可靠性纵深，与其广度互补。",
     ["RQ1", "RQ2"]),
]


def build_core_pool(data_dir: Path) -> dict:
    works = distinct_works(load_papers(data_dir))
    ev_path = data_dir / "evidence.jsonl"
    evidence = list(read_jsonl(ev_path, Evidence)) if ev_path.exists() else []
    ev_counts: dict[str, int] = {}
    for e in evidence:  # type: ignore[arg-type]
        ev_counts[e.work_id] = ev_counts.get(e.work_id, 0) + 1

    pool = []
    unresolved = []
    for layer, role, title_pat, reason, rqs in SELECTION:
        wid = None
        for w, recs in works.items():
            if title_pat.lower()[:32] in (recs[0].title or "").lower():
                wid = w
                rec = next((r for r in recs if r.inclusion_status == "included"),
                           recs[0])
                break
        if wid is None:
            unresolved.append(title_pat)
            continue
        n_ev = ev_counts.get(wid, 0)
        pool.append({
            "work_id": wid, "layer": layer, "role": role,
            "title": works[wid][0].title, "year": rec.year,
            "venue": rec.venue, "arxiv_id": rec.arxiv_id,
            "inclusion_status": rec.inclusion_status,
            "reason": reason, "rqs": rqs,
            "evidence_count": n_ev,
            "reading_status": ("已读(证据%d条)" % n_ev) if n_ev else "待正文审读",
        })
    # 写 core_pool.jsonl
    out = data_dir / "core_pool.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for p in pool:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    return {"pool": pool, "unresolved": unresolved, "works": works}


def render_deliverables(data_dir: Path) -> dict:
    stats = build_core_pool(data_dir)
    pool, works = stats["pool"], stats["works"]

    # ---------- 1. 拟选文献表 ----------
    lines = ["# 核心阅读池（拟选 40 篇）", "",
             "按用户策略构建（docs/decisions.md D-3）：每篇回答三问（解决什么问题 /",
             "承担什么作用 / 提供什么不同）；分层为参考结构，每篇计一个主要角色。",
             "状态为拟选；正文审读（阅读卡）后才最终定稿 35–45 篇。", ""]
    by_layer: dict[str, list] = {}
    for p in pool:
        by_layer.setdefault(p["layer"], []).append(p)
    for layer in sorted(by_layer):
        items = by_layer[layer]
        lines.append(f"## {layer}（{len(items)} 篇）")
        lines.append("")
        lines.append("| work | 题名（截断） | 年份 | 发表 | 角色 | RQ | 阅读 |")
        lines.append("|---|---|---|---|---|---|---|")
        for p in items:
            venue = (p["venue"] or "arXiv")[:24]
            lines.append(f"| {p['work_id']} | {p['title'][:46]} | {p['year'] or '?'} "
                         f"| {venue} | {p['role']} | {','.join(p['rqs'])} "
                         f"| {p['reading_status']} |")
        lines.append("")
        for p in items:
            lines.append(f"- **{p['work_id']} {p['role']}**：{p['reason']}")
        lines.append("")

    # ---------- 2. 覆盖矩阵 ----------
    ml = ["# 覆盖矩阵（层 × RQ）", "",
          "| 层 | 篇数 | RQ1 | RQ2 | RQ3 | RQ4 | RQ5 | 已读 | 待读 |",
          "|---|---|---|---|---|---|---|---|---|"]
    rq_totals = {f"RQ{i}": 0 for i in range(1, 6)}
    total_read = total_todo = 0
    for layer in sorted(by_layer):
        items = by_layer[layer]
        rqs = {f"RQ{i}": sum(1 for p in items if f"RQ{i}" in p["rqs"])
               for i in range(1, 6)}
        for k, v in rqs.items():
            rq_totals[k] += v
        read = sum(1 for p in items if p["evidence_count"] > 0)
        todo = len(items) - read
        total_read += read
        total_todo += todo
        ml.append(f"| {layer} | {len(items)} | {rqs['RQ1']} | {rqs['RQ2']} "
                  f"| {rqs['RQ3']} | {rqs['RQ4']} | {rqs['RQ5']} | {read} | {todo} |")
    ml.append(f"| **合计** | **{len(pool)}** | **{rq_totals['RQ1']}** "
              f"| **{rq_totals['RQ2']}** | **{rq_totals['RQ3']}** "
              f"| **{rq_totals['RQ4']}** | **{rq_totals['RQ5']}** "
              f"| **{total_read}** | **{total_todo}** |")
    ml += ["", "## 已识别缺口（补检后仍未覆盖或证据不足时在正文如实说明）", ""]
    # 自动检查各 RQ 是否有已读证据支撑
    ev_rqs: dict[str, int] = {}
    ev_path = data_dir / "evidence.jsonl"
    if ev_path.exists():
        pool_ids = {p["work_id"] for p in pool}
        for e in read_jsonl(ev_path, Evidence):  # type: ignore[arg-type]
            if e.work_id in pool_ids:
                for rq in e.rq_tags:
                    ev_rqs[rq] = ev_rqs.get(rq, 0) + 1
    for i in range(1, 6):
        rq = f"RQ{i}"
        n = ev_rqs.get(rq, 0)
        ml.append(f"- {rq}：核心池内证据 {n} 条"
                  f"{'（充足）' if n >= 4 else '（待补读）'}")

    # ---------- 3. 降级/排除/合并清单 ----------
    pool_ids = {p["work_id"] for p in pool}
    dl = ["# 降级、排除与合并清单", "",
          "## 降级为辅助文献（不进入核心阅读池，可作正文补充引用或数据来源）", ""]
    aux = [(wid, recs) for wid, recs in works.items()
           if wid not in pool_ids
           and any(r.inclusion_status == "included" for r in recs)]
    dl.append(f"共 {len(aux)} 项 included 研究降级为辅助池。作用：核心池的证据缺口备选、"
              "正文个别论断的补充引用；不再无差别提取证据。")
    dl += ["", "## 本轮排除与合并（含理由）", "",
           "| work | 处理 | 理由 |", "|---|---|---|"]
    for wid, recs in works.items():
        p = recs[0]
        if p.inclusion_status == "excluded" and p.reason and any(
                k in p.reason for k in ["non_paper_resource", "duplicate_medium"]):
            dl.append(f"| {wid} | 排除 | {p.reason[:80]} |")
    dl += ["", "## 版本归并待办（同研究多记录，需在 bib 生成时合并）", ""]
    for a, b in [("W0099", "W0100"), ("W0411", "W0416")]:
        if a in works and b in works:
            dl.append(f"- {a} 与 {b}：题名相同的不同来源记录（{works[a][0].title[:40]}…），"
                      f"bib 生成时以 {a} 为主记录")

    # 写文件
    out_dir = data_dir / "derived"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "core_selection.md").write_text("\n".join(lines), encoding="utf-8")
    (out_dir / "coverage_matrix.md").write_text("\n".join(ml), encoding="utf-8")
    (out_dir / "downgrade_exclusion.md").write_text("\n".join(dl), encoding="utf-8")
    return {"pool_size": len(pool), "unresolved": stats["unresolved"],
            "aux_size": len(aux), "total_read": total_read,
            "total_todo": total_todo,
            "files": ["data/core_pool.jsonl", "data/derived/core_selection.md",
                      "data/derived/coverage_matrix.md",
                      "data/derived/downgrade_exclusion.md"]}


if __name__ == "__main__":
    from pprint import pprint
    pprint(render_deliverables(Path("data")))
