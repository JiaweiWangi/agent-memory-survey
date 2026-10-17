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
# 证据链主数据（重建本次结果所必需；含废止记录用于追溯）
cp data/papers.jsonl data/evidence.jsonl data/claims.jsonl data/reviews.jsonl \
   data/search_runs.jsonl data/memory_events.jsonl "$SUB/evidence_manifest/"
cp data/derived/{core_selection,coverage_matrix,downgrade_exclusion,reading_cards,research_matrix}.md "$SUB/evidence_manifest/"
cp data/derived/reading_cards.jsonl data/derived/research_matrix.jsonl data/derived/claims_map.md "$SUB/evidence_manifest/"
cp docs/{human_review_queue,final_acceptance,protocol,decisions}.md "$SUB/evidence_manifest/"
cp PROGRESS.md EXECUTION_PLAN.md "$SUB/evidence_manifest/"

# 5) 复现说明
cat > "$SUB/README.md" <<'README'
# 提交包说明

## 内容
- review.pdf / agent_report.pdf / presentation.pdf：三份交付 PDF（与 latex_source 一致）
- latex_source/：三个 LaTeX 工程源文件（tectonic 编译）
- agent_source/：智能体源码（uv 管理）、测试（28 项）、评估案例与结果
- evidence_manifest/：证据链主数据（papers/evidence/claims/reviews/search_runs/
  memory_events 六个 JSONL，含 7 条错配废止记录——原始记录保留、生产路径排除）、
  核心池清单、39 张阅读卡、研究矩阵、论断映射表、核验队列、验收报告

## 离线复查（无需模型调用）
cd agent_source
uv sync                                                    # 恢复依赖
uv run pytest                                              # 28 项测试
uv run litreview --data-dir ../evidence_manifest check --scope corpus
# 期望输出：papers.jsonl 726 条当前记录（原始 1079 行）/ 有效证据 342（废止 7 条保留可追溯）/
#          检索运行 104 次；必需文件缺失或语料为空时该命令返回失败

## 在线复现（需要模型凭证）
export ANTHROPIC_BASE_URL=... ANTHROPIC_AUTH_TOKEN=... ANTHROPIC_DEFAULT_HAIKU_MODEL=...
uv run litreview evaluate                                  # 标准评估入口
# （评估会产生新的模型调用与费用；已有结果在 agent_source/evaluation/）

## LaTeX 重建
cd ../latex_source/paper && tectonic main.tex              # 综述（21 页）
cd ../agent_report && tectonic main.tex                    # 智能体说明
cd ../slides && tectonic main.tex                          # 幻灯片

模型凭证走环境变量（.env.example 列出变量名）；论文原档（sources/）与 HTTP
缓存不入包，证据清单含定位可溯源。
README

echo "提交包构建完成："
find "$SUB" -type f | wc -l | xargs echo "  文件数:"
du -sh "$SUB" | awk '{print "  大小: "$1}'
