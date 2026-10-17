"""litreview CLI：文献综述智能体命令入口。

用法（uv run litreview ...）：
  run --stage discovery   G1 检索：五组检索式 + 种子论文核验 + 去重
  check --scope corpus    语料检查：计数、去重不变量
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import stages

ROOT = Path(__file__).resolve().parent.parent.parent  # 项目根


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="litreview",
                                     description="文献综述智能体（课程作业）")
    parser.add_argument("--data-dir", default=str(ROOT / "data"),
                        help="数据目录（默认 <项目根>/data）")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="执行阶段")
    p_run.add_argument("--stage", required=True,
                       choices=["discovery", "evidence", "draft", "screen",
                                "evidence_batch", "trace", "matrix",
                                "review_queue"],
                       help="discovery=G1；evidence/draft=G2；screen/evidence_batch/trace/matrix/review_queue=G3")
    p_run.add_argument("--max", type=int, default=None,
                       help="批处理上限（screen/evidence_batch）")

    p_check = sub.add_parser("check", help="检查器")
    p_check.add_argument("--scope", required=True, choices=["corpus", "manuscript", "identity"])

    p_bib = sub.add_parser("bibgen", help="从 papers.jsonl 生成 references.bib")
    p_bib.add_argument("--out", default=None, help="输出路径（默认 paper/references.bib）")

    p_eval = sub.add_parser("evaluate", help="运行冻结评估案例（A/B/C 条件）")
    p_eval.add_argument("--cases", default=None, help="案例文件（默认 evaluation/cases.jsonl）")

    args = parser.parse_args(argv)
    data_dir = Path(args.data_dir)

    if args.cmd == "run":
        if args.stage == "discovery":
            return stages.run_discovery(data_dir)
        if args.stage == "evidence":
            return stages.run_evidence(data_dir)
        if args.stage == "draft":
            return stages.run_draft(data_dir)
        if args.stage == "screen":
            return stages.run_screen(data_dir, max_candidates=args.max)
        if args.stage == "evidence_batch":
            return stages.run_evidence_batch(data_dir, max_works=args.max)
        if args.stage == "trace":
            return stages.run_trace(data_dir)
        if args.stage == "matrix":
            return stages.run_matrix(data_dir)
        if args.stage == "review_queue":
            from .review_queue import generate_review_queue
            stats = generate_review_queue(data_dir)
            print(f"核验队列：文献 {stats['cited_pool']} / 边界 {stats['boundary']}"
                  f" / claims {stats['claims']} → {stats['path']}")
            return 0
    if args.cmd == "check":
        if args.scope == "corpus":
            return stages.check_corpus(data_dir)
        if args.scope == "identity":
            from .identity import check_identity
            problems = check_identity(data_dir)
            return 1 if problems else 0
    if args.cmd == "bibgen":
        from .bibgen import generate_bib
        out = Path(args.out) if args.out else ROOT / "paper" / "references.bib"
        stats = generate_bib(data_dir, out)
        print(f"bib 生成：{stats['entries']} 条（跳过无证据 {stats['skipped_no_evidence']}"
              f"）→ {out}")
        return 0
    if args.cmd == "evaluate":
        # 标准评估入口（D-8）：R1/S2/H3 九案例单阶段 + M4 三案例两阶段
        # （阶段1持久化→新实例→阶段2恢复；结构化判分）
        import json as _json
        from .evaluate import run_evaluation, run_multirun_eval
        from .model_backends import AnthropicBackend
        cases = Path(args.cases) if args.cases else ROOT / "evaluation" / "cases.jsonl"
        results = cases.parent / "results.jsonl"
        if results.exists():
            stamp = now_stamp()
            results.rename(cases.parent / f"results_{stamp}.jsonl.bak")
        backend = AnthropicBackend()
        # 单阶段部分：过滤 M4（由两阶段实验接管）
        rows = [l for l in cases.read_text(encoding="utf-8").splitlines()
                if l.strip() and not _json.loads(l)["case_id"].startswith("M4")]
        tmp_cases = results.parent / "_cases_singlephase.jsonl"
        tmp_cases.write_text("\n".join(rows) + "\n", encoding="utf-8")
        stats1 = run_evaluation(tmp_cases, results, backend)
        stats2 = run_multirun_eval(results, results.parent / "_eval_tmp", backend)
        total = stats1["executed"] + stats2["executed"]
        print(f"评估执行：单阶段 {stats1['executed']}/27 + 两阶段 multirun "
              f"{stats2['executed']}/9 = {total}/36 → {results}")
        return 0
    parser.error("未知组合")
    return 2


def now_stamp() -> str:
    from datetime import datetime
    return datetime.now().strftime("%m%d%H%M%S")


if __name__ == "__main__":
    sys.exit(main())
