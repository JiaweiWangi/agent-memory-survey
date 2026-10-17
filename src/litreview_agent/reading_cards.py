"""阅读卡生成：核心池每篇一张（用户策略 §7 九要素）。

要素：研究问题；记忆机制；更新方式；评测设置；主要发现；适用条件与局限；
与其他方法的关系；拟用于正文的章节；原文定位。
数据源：core_pool.jsonl（层/角色/理由）+ evidence.jsonl（定位/摘录/条件）。
模型生成解释字段，机械字段（定位/层/RQ）从数据直取；卡片标注"模型综合，
待人工复核"。
"""

from __future__ import annotations

import json
from pathlib import Path

from .model_backends import AnthropicBackend
from .models import Evidence, load_valid_evidence
from .tools.dedup import distinct_works, load_papers

CARD_PROMPT = """你是文献综述的阅读卡撰写员。基于给定证据（全部来自该论文原文摘录，
带页码定位），为论文《{title}》写一张中文阅读卡。

严格规则：
- 只使用证据中出现的信息；证据未覆盖的字段写"（证据未覆盖，待补读）"；
- 数字必须来自证据摘录原文，不得推算或四舍五入；
- 区分"作者结论"（写"作者称…"）与"本卡综合"。

输出 JSON（字段如下，值为中文短句）：
{{
 "research_question": "研究问题",
 "memory_mechanism": "记忆机制：保存什么/何时写入/如何读取",
 "update_method": "更新方式：信息变化/冲突/遗忘如何处理",
 "evaluation_setup": "评测设置：任务/数据/模型/对照",
 "main_findings": "主要发现（含关键数字，标注来源定位）",
 "conditions_limitations": "适用条件与局限",
 "relations": "与其他方法的关系（基于证据中提到的对比/引用）",
 "target_sections": "拟用于正文章节（结合给定角色推断）"
}}

证据列表（work_id={work_id}，层={layer}，角色={role}）：
{evidence_block}"""


def generate_reading_cards(data_dir: Path, backend: AnthropicBackend,
                           out_path: Path) -> dict:
    pool = [json.loads(l) for l in
            (data_dir / "core_pool.jsonl").read_text().splitlines()]
    evidence = load_valid_evidence(data_dir)  # 废止证据（reviews fail）不进入阅读卡
    ev_by_work: dict[str, list[Evidence]] = {}
    for e in evidence:  # type: ignore[arg-type]
        ev_by_work.setdefault(e.work_id, []).append(e)

    cards = []
    n_skipped = 0
    for p in pool:
        evs = ev_by_work.get(p["work_id"], [])
        if not evs:
            n_skipped += 1
            continue
        block = "\n".join(
            f"- [{e.locator}] ({e.evidence_type}, {','.join(e.rq_tags)}) "
            f"摘录：{e.excerpt[:200]} | 解释：{e.interpretation[:150]}"
            f"{(' | 条件: ' + e.conditions) if e.conditions else ''}"
            for e in evs[:12])
        prompt = CARD_PROMPT.format(title=p["title"][:120],
                                    work_id=p["work_id"], layer=p["layer"],
                                    role=p["role"], evidence_block=block)
        try:
            result = backend.complete(
                system="只输出 JSON 对象，不要其他文字。",
                messages=[{"role": "user", "content": prompt}], max_tokens=1200)
            import re
            m = re.search(r"\{.*\}", result.text, re.S)
            card = json.loads(m.group(0)) if m else {}
        except Exception as e:  # noqa: BLE001 — 失败卡片如实标注
            card = {"error": str(e)[:200]}
        cards.append({
            "work_id": p["work_id"], "title": p["title"], "layer": p["layer"],
            "role": p["role"], "year": p["year"], "venue": p["venue"],
            "evidence_count": len(evs),
            "card": card,
            "locators": [e.locator for e in evs],
            "generated": "model（待人工复核）",
        })
    with out_path.open("w", encoding="utf-8") as f:
        for c in cards:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    return {"cards": len(cards), "skipped_no_evidence": n_skipped,
            "path": str(out_path)}


def render_cards_markdown(cards_path: Path, out_md: Path) -> int:
    cards = [json.loads(l) for l in cards_path.read_text().splitlines()]
    lines = ["# 核心池阅读卡（39 篇）", "",
             "模型基于逐字验证证据生成，**全部待人工复核**；定位字段来自证据记录",
             "（`data/evidence.jsonl`），可回查 `sources/` 存档 PDF 页码。", ""]
    by_layer: dict[str, list] = {}
    for c in cards:
        by_layer.setdefault(c["layer"], []).append(c)
    FIELDS = [("research_question", "研究问题"),
              ("memory_mechanism", "记忆机制"),
              ("update_method", "更新方式"),
              ("evaluation_setup", "评测设置"),
              ("main_findings", "主要发现"),
              ("conditions_limitations", "条件与局限"),
              ("relations", "与其他方法关系"),
              ("target_sections", "拟用章节")]
    for layer in sorted(by_layer):
        lines.append(f"## {layer}（{len(by_layer[layer])} 篇）\n")
        for c in by_layer[layer]:
            lines.append(f"### {c['work_id']} {c['title'][:70]}"
                         f"（{c['year']}，{c['venue'] or 'arXiv'}）")
            lines.append(f"*角色：{c['role']} | 证据 {c['evidence_count']} 条*")
            lines.append("")
            if "error" in c["card"]:
                lines.append(f"卡片生成失败：{c['card']['error']}（待重试）")
            else:
                for key, label in FIELDS:
                    v = c["card"].get(key, "（未生成）")
                    lines.append(f"- **{label}**：{v}")
            lines.append(f"- **原文定位**：{'; '.join(c['locators'][:6])}"
                         f"{'…' if len(c['locators']) > 6 else ''}")
            lines.append("")
    out_md.write_text("\n".join(lines), encoding="utf-8")
    return len(cards)


if __name__ == "__main__":
    from pathlib import Path as _P
    from .model_backends import AnthropicBackend as _B
    data = _P("data")
    stats = generate_reading_cards(data, _B(), data / "derived" / "reading_cards.jsonl")
    print(stats)
    n = render_cards_markdown(data / "derived" / "reading_cards.jsonl",
                              data / "derived" / "reading_cards.md")
    print(f"Markdown 渲染 {n} 张 → data/derived/reading_cards.md")
