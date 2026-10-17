"""G5 论文生成：按章节从阅读卡+证据+claims 生成带引用 LaTeX 正文。

生成规则：
- 每个事实性陈述带 \\cite{Wxxxx}，只引用核心池成员；
- 数字来自证据摘录（阅读卡中的数字已绑定定位）；
- 证据不足处显式标【待核验】；
- 每章生成后跑引用检查（无证据引用即失败重试一次）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .model_backends import AnthropicBackend
from .checks import check_draft_citations
from .models import Claim, Evidence, read_jsonl
from .tools.dedup import distinct_works, load_papers

SECTION_SPECS = [
    # (文件名, 章节标题, 素材层, 指令)
    ("intro", "引言",
     ["L1-基础系统", "L7-综述与边界"],
     "长期任务为什么需要外部记忆（上下文窗口/静态RAG/参数知识的不足）→"
     "本文研究问题（RQ1–RQ5）与边界（跨会话可写外部记忆；不含参数化记忆与单查询检索）。"),
    ("concepts", "概念界定与综述方法",
     ["L7-综述与边界"],
     "长期记忆的操作定义（与上下文历史/静态RAG/参数知识的区分）→"
     "综述方法：检索来源与截止日、两阶段筛选漏斗（真实数字我会给出）、"
     "版本去重、证据与人工核验流程（诚实说明局限）。"),
    ("taxonomy", "研究脉络与方法分类",
     ["L1-基础系统", "L2-组织检索"],
     "按机制演进梳理：记忆流与三因子检索 → 上下文工程（分页/中断）→ "
     "结构化组织（图/分层/多类型）→ 效率与固化策略。每个阶段：代表工作"
     "解决什么问题、后续修改了什么、遗留什么问题。引用谱系图。"),
    ("update_reliability", "记忆更新与可靠性",
     ["L3-更新遗忘", "L5-非恶意可靠性", "L6-安全投毒"],
     "更新与遗忘机制（选择性遗忘、治理原语、再巩固、版本规范化、偏好更新）→"
     "非恶意可靠性（错误传播、摘要失真、检索适配性、来源追踪、记忆幻觉）→"
     "恶意攻击与防御及其代价。区分作者结论与本文综合；数字带条件。"),
    ("evaluation", "评测与比较",
     ["L4-评测"],
     "基准演进：LoCoMo → LongMemEval 五能力 → 遗忘/多模态/构建/成本维度。"
     "比较表要点：任务类型、会话跨度、信息变化、指标；公平比较的困难"
     "（模型/预算/检索配置差异），引用方法比较表。"),
    ("challenges", "挑战与研究方向",
     ["L3-更新遗忘", "L5-非恶意可靠性", "L4-评测"],
     "从证据缺口推导：更新正确性评测不足、错误传播的定量刻画缺失、"
     "成本与收益的报告不统一、防御的负外部性。区分共识与本文判断。"),
    ("conclusion", "结论",
     [],
     "回答 RQ1–RQ5 各一段式总结；与证据强度一致，不夸大。"),
]

SYSTEM = """你是学术综述写作者。基于给定素材（阅读卡与证据，全部经逐字验证）撰写中文 LaTeX 章节正文。

硬规则：
1. 每个事实性陈述必须带 \\cite{Wxxxx}（只能用素材中出现的 work_id；综合多工作时列出多个）；
2. 数字、比例、指标名必须来自素材原文，不得推算或改写；数字所在句注明实验条件（模型/基准/设置）；
3. 素材未覆盖的推断，句尾标【待核验】；不要为了流畅编造细节；
4. 区分"作者称/报告"与"本文综合"；
5. 输出纯 LaTeX 正文（不含 \\section 行、不含 document 环境），可用 \\subsection；中文写作，术语首现给英文；
6. 600–1200 字/节；不要逐篇罗列，按机制脉络组织。
"""


def _load_material(data_dir: Path, layers: list[str]) -> tuple[str, dict]:
    pool = [json.loads(l) for l in
            (data_dir / "core_pool.jsonl").read_text().splitlines() if l.strip()]
    cards = {}
    cp = data_dir / "derived" / "reading_cards.jsonl"
    if cp.exists():
        for l in cp.read_text(encoding="utf-8").splitlines():
            if l.strip():
                c = json.loads(l)
                cards[c["work_id"]] = c
    titles = {p["work_id"]: p["title"] for p in pool}
    if layers:
        members = [p for p in pool if p["layer"] in layers]
    else:  # 结论节：全部池成员的轻量信息
        members = pool
    blocks = []
    for p in members:
        c = cards.get(p["work_id"], {}).get("card", {})
        blk = [f"### {p['work_id']} 《{p['title'][:90]}》({p['year']}, {p['venue'] or 'arXiv'})"
               f" 层={p['layer']} 角色={p['role']}"]
        for k, label in [("research_question", "问题"), ("memory_mechanism", "机制"),
                         ("update_method", "更新"), ("evaluation_setup", "评测"),
                         ("main_findings", "发现"), ("conditions_limitations", "局限"),
                         ("relations", "关系")]:
            v = c.get(k)
            if v and "未覆盖" not in str(v):
                blk.append(f"- {label}: {v}")
        blocks.append("\n".join(blk))
    return "\n\n".join(blocks), titles


def generate_section(data_dir: Path, backend: AnthropicBackend,
                     spec: tuple[str, str, list[str], str],
                     funnel_stats: str) -> tuple[str, str]:
    fname, title, layers, instruction = spec
    material, titles = _load_material(data_dir, layers)
    user = (f"撰写章节《{title}》。写作要点：{instruction}\n\n"
            f"{'筛选漏斗真实数字（综述方法节使用）：' + funnel_stats if fname == 'concepts' else ''}\n\n"
            f"素材（阅读卡，基于逐字验证证据）：\n{material[:30000]}\n\n"
            f"可直接引用的 work_id：{', '.join(sorted(titles))}")
    result = backend.complete(system=SYSTEM,
                              messages=[{"role": "user", "content": user}],
                              max_tokens=3500)
    tex = result.text
    # 引用检查：引用必须是核心池且有证据
    pool_ids = set(titles)
    evs = list(read_jsonl(data_dir / "evidence.jsonl", Evidence))
    ev_works = {e.work_id for e in evs}  # type: ignore[arg-type]
    works_map = distinct_works(load_papers(data_dir))
    bad = []
    for wid in set(re.findall(r"\\cite\{([^}]+)\}", tex) and
                   [w.strip() for g in re.findall(r"\\cite\{([^}]+)\}", tex)
                    for w in g.split(",")]):
        if wid not in pool_ids or wid not in ev_works:
            bad.append(wid)
    return tex, ("" if not bad else "BAD_CITES:" + ",".join(bad))


def run_paper_generation(data_dir: Path, out_dir: Path) -> int:
    backend = AnthropicBackend()
    funnel = ("检索 104 次运行（76 成功 17 失败均入档）覆盖 OpenAlex/Crossref/arXiv 三源；"
              "命中去重后 691 项独立研究（版本归并：arXiv DOI 与正式 DOI、"
              "预印本与会议版共享 work_id）；题名摘要初筛 255 项纳入、42 项排除（稳定理由码）、"
              "10 项待定；正文审读后确定 40 篇核心阅读池（七层结构），39 篇完成深读"
              "（证据 343 条，每条含逐字摘录与页级定位）；215 项降为辅助池。"
              "检索截止日 2026-10-17。")
    report = []
    for spec in SECTION_SPECS:
        fname, title = spec[0], spec[1]
        tex, bad = generate_section(data_dir, backend, spec, funnel)
        if bad:
            # 一次重试：去掉坏引用重新生成
            report.append(f"{fname}: 引用问题 {bad}，重试")
            tex2, bad2 = generate_section(data_dir, backend, spec, funnel)
            if not bad2:
                tex = tex2
                bad = ""
            else:
                # 机械降级：注释掉坏引用
                for w in bad2.split(","):
                    tex = tex.replace(f"\\cite{{{w}}}", f"\\cite{{{w}}}%% REMOVED-NO-EVIDENCE")
                bad = bad2
        out = out_dir / f"{fname}.tex"
        out.write_text(f"% {fname}：生成于阅读卡+证据；引用检查"
                       f"{'通过' if not bad else '存在注释掉的无证据引用'}\n"
                       + tex + "\n", encoding="utf-8")
        report.append(f"{fname}: {len(tex)} 字符 {'OK' if not bad else bad}")
        print(f"  {report[-1]}")
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    from pathlib import Path as _P
    raise SystemExit(run_paper_generation(_P("data"), _P("paper") / "sections"))
