#!/bin/bash
# G7 打包脚本：从当前工程构建提交包（submission/ 已 gitignore，仅本地构建）
set -euo pipefail
cd "$(dirname "$0")/.."
SUB=submission
rm -rf "$SUB" && mkdir -p "$SUB"/{latex_source,agent_source,evidence_manifest}

# 1) PDF（三份均已编译验证）
cp paper/main.pdf "$SUB/review.pdf"
cp agent_report/main.pdf "$SUB/agent_report.pdf"
cp slides/main.pdf "$SUB/presentation.pdf"

# 2) LaTeX 源
cp -r paper agent_report slides "$SUB/latex_source/"
find "$SUB/latex_source" -name '*.pdf' -delete   # 源码包不含二进制

# 3) 智能体源码与评估
mkdir -p "$SUB/agent_source"
cp -r src tests pyproject.toml uv.lock config.example.yaml .env.example README.md "$SUB/agent_source/"
cp -r evaluation "$SUB/agent_source/evaluation"
find "$SUB/agent_source" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true

# 4) 证据清单（不含论文 PDF 原档与 HTTP 缓存）
mkdir -p "$SUB/evidence_manifest"
cp data/core_pool.jsonl data/abstracts.jsonl "$SUB/evidence_manifest/" 2>/dev/null || true
cp data/derived/{core_selection,coverage_matrix,downgrade_exclusion,reading_cards,research_matrix}.md "$SUB/evidence_manifest/"
cp data/derived/reading_cards.jsonl data/derived/research_matrix.jsonl "$SUB/evidence_manifest/"
cp docs/{human_review_queue,final_acceptance,protocol,decisions}.md "$SUB/evidence_manifest/"
cp PROGRESS.md EXECUTION_PLAN.md "$SUB/evidence_manifest/"

# 5) 复现说明
cat > "$SUB/README.md" <<'README'
# 提交包说明
- review.pdf / agent_report.pdf / presentation.pdf：三份交付 PDF
- latex_source/：三个 LaTeX 工程源文件（tectonic 编译）
- agent_source/：智能体源码（uv 管理）、测试（12 项）、评估案例与结果
- evidence_manifest/：核心池 40 篇清单、39 张阅读卡、研究矩阵、核验队列、验收报告
- 复现：cd agent_source && uv sync && uv run pytest && uv run litreview check --scope corpus
- 模型凭证走环境变量（.env.example 列出变量名）；论文原档与缓存不入包，清单含定位可溯源
README

echo "提交包构建完成："
find "$SUB" -type f | wc -l | xargs echo "  文件数:"
du -sh "$SUB" | awk '{print "  大小: "$1}'
