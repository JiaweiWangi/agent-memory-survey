"""评估结果分析：从 results.jsonl 生成 evaluation/report.md。

自动指标统计（rubric.md）：
- 编造标识率（fabricated_ids）
- 失效内容采用率（superseded_content_used）
- honesty 类待核验标记率
- 各条件完成数（分母显式）
语义正确率维度留给真人按 rubric 评分（本工具不代判）。
"""

from __future__ import annotations

import json
from pathlib import Path


def analyze(results_path: Path, out_md: Path) -> dict:
    rows = []
    for l in results_path.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        ev = json.loads(l)
        if ev.get("kind") == "eval_result":
            rows.append(json.loads(ev["result_summary"]))
        elif ev.get("kind") == "error":
            rows.append({"case_id": ev["run_id"].split("-")[1],
                         "condition": ev["run_id"].split("-")[-1],
                         "error": ev.get("error", "")})

    conds = ("A", "B", "C")
    lines = ["# 智能体评估报告（G4）", "",
             "来源：`evaluation/results.jsonl`（真实运行，replay=false）。",
             "自动指标如下；任务正确率与不确定性处理质量按 `rubric.md` 由真人评分",
             "（本报告不代判语义维度）。", ""]

    # 总览
    lines += ["## 执行总览", "",
              "| 条件 | 完成 | 失败 | 编造标识 | 失效内容采用 | honesty 待核验标记 |",
              "|---|---|---|---|---|---|"]
    summary = {}
    for c in conds:
        sub = [r for r in rows if r.get("condition") == c]
        ok = [r for r in sub if "output" in r]
        errs = [r for r in sub if "error" in r]
        fab = sum(1 for r in ok if r["auto_checks"].get("fabricated_ids"))
        sup = sum(1 for r in ok if r["auto_checks"].get("superseded_content_used"))
        hon = [r for r in ok if r.get("category") == "honesty"]
        hon_marked = sum(1 for r in hon
                         if r["auto_checks"].get("pending_or_gap_marked"))
        summary[c] = {"n": len(ok), "err": len(errs), "fab": fab, "sup": sup,
                      "hon_n": len(hon), "hon_marked": hon_marked}
        lines.append(f"| {c} | {len(ok)}/12 | {len(errs)} | {fab} | {sup} "
                     f"| {hon_marked}/{len(hon)} |")
    lines.append("")

    # 分类明细
    lines += ["## 分类明细（自动检查）", "",
              "| 案例 | 类别 | A | B | C |", "|---|---|---|---|---|"]
    cats = {}
    for r in rows:
        cats.setdefault(r.get("case_id", "?"), r.get("category", "?"))
    for cid in sorted(cats):
        cells = []
        for c in conds:
            r = next((x for x in rows
                      if x.get("case_id") == cid and x.get("condition") == c), None)
            if r is None:
                cells.append("—")
            elif "error" in r:
                cells.append("ERR")
            else:
                flags = []
                if r["auto_checks"].get("fabricated_ids"):
                    flags.append("编造")
                if r["auto_checks"].get("superseded_content_used"):
                    flags.append("用失效")
                if r.get("category") == "honesty" and not r["auto_checks"].get("pending_or_gap_marked"):
                    flags.append("无缺口标注")
                cells.append("✓" if not flags else "⚠" + "/".join(flags))
        lines.append(f"| {cid} | {cats[cid]} | {cells[0]} | {cells[1]} | {cells[2]} |")
    lines += ["", "✓=自动检查通过；⚠=存在违规（详情见 results.jsonl）；"
              "语义正确率待真人评分。", ""]

    # 逐案例输出全文（供人工评分）
    lines += ["## 原始输出（供真人按 rubric 评分）", ""]
    for cid in sorted(cats):
        for c in conds:
            r = next((x for x in rows
                      if x.get("case_id") == cid and x.get("condition") == c), None)
            if r and "output" in r:
                lines.append(f"### {cid} / 条件 {c}（{r.get('category')}）")
                lines.append("")
                lines.append(f"> {r['output'][:600]}")
                lines.append("")

    out_md.write_text("\n".join(lines), encoding="utf-8")
    return {"rows": len(rows), "conditions": summary}


if __name__ == "__main__":
    from pprint import pprint
    pprint(analyze(Path("evaluation/results.jsonl"),
                   Path("evaluation/report.md")))
