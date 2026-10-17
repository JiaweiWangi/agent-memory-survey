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
    p_check.add_argument("--scope", required=True, choices=["corpus", "manuscript"])

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
    parser.error("未知组合")
    return 2


if __name__ == "__main__":
    sys.exit(main())
