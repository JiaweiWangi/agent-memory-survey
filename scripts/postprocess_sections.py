"""章节后处理：
1. \subsection{X} 首标题 → \section{X}（main.tex 只 input，不加 section 行）；
2. intro.tex 的 RQ 块替换为 protocol.md 冻结版（生成模型的改写与全文
   组织不符：协议 RQ3=更新遗忘、RQ5=评测）；
3. 检查全部 \cite 是否为核心池成员（最终防线）。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

FROZEN_RQS = r"""\textbf{RQ1（定义与边界）：}长期记忆包含哪些信息和机制？它与上下文历史、静态知识检索、参数知识有什么关系？

\textbf{RQ2（组织与使用）：}写入、组织和检索方法如何影响信息可用性、任务表现和成本？

\textbf{RQ3（更新与遗忘）：}如何处理信息变化、时间条件、冲突、过时记忆和必要的删除？

\textbf{RQ4（可靠性）：}错误摘要、错误反思或来源混淆如何进入记忆并影响后续决策？现有方法怎样发现和控制这些问题？

\textbf{RQ5（评测）：}基准和实验是否真正考察跨会话记忆、更新能力和长期任务表现？不同结果能否公平比较？"""

SECTION_TITLES = {
    "intro": "引言", "concepts": "概念界定与综述方法",
    "taxonomy": "研究脉络与方法分类", "update_reliability": "记忆更新与可靠性",
    "evaluation": "评测与比较", "challenges": "挑战与研究方向", "conclusion": "结论",
}


def postprocess(sections_dir: Path, pool_path: Path) -> list[str]:
    pool_ids = set()
    for l in pool_path.read_text(encoding="utf-8").splitlines():
        if l.strip():
            pool_ids.add(__import__("json").loads(l)["work_id"])

    issues = []
    for fname, title in SECTION_TITLES.items():
        f = sections_dir / f"{fname}.tex"
        if not f.exists():
            issues.append(f"{fname}: 文件缺失")
            continue
        text = f.read_text(encoding="utf-8")
        # 1) 首个标题层级修正
        text = re.sub(r"^\\subsection\{[^}]*\}", f"\\\\section{{{title}}}",
                      text, count=1, flags=re.M)
        if f"\\section{{{title}}}" not in text:
            # 无标题则插入
            text = f"\\section{{{title}}}\n\n" + text
        # 2) RQ 冻结替换（intro）
        if fname == "intro":
            rq_pat = re.compile(
                r"(\\textbf\{RQ1[^%])*?(RQ1|\\textbf\{RQ1).*?(?=上述研究问题|本文综合|围绕|以下)",
                re.S)
            m = re.search(r"(\\textbf\{RQ1[：:].*?)(?=上述研究问题|本文综合|以下|为此，)", text, re.S)
            if m:
                text = text[:m.start(1)] + FROZEN_RQS + "\n\n" + text[m.end(1):]
            else:
                issues.append("intro: RQ 块未定位（人工检查）")
        # 3) 引用检查
        cites = set()
        for g in re.findall(r"\\cite\{([^}]+)\}", text):
            cites.update(w.strip() for w in g.split(","))
        bad = sorted(c for c in cites if c not in pool_ids)
        if bad:
            issues.append(f"{fname}: 非核心池引用 {bad}")
        f.write_text(text, encoding="utf-8")
    return issues


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    issues = postprocess(root / "paper" / "sections", root / "data" / "core_pool.jsonl")
    if issues:
        print("问题：")
        print("\n".join("  - " + i for i in issues))
        sys.exit(1)
    print("后处理完成：标题层级、RQ 冻结版、引用池检查全部通过")
