# 大模型智能体的长期记忆：组织、更新与可靠性评测综述

学术写作课程作业项目：三人小组 + 文献综述智能体。

- 综述主题：LLM 智能体跨会话外部记忆的组织、更新与可靠性评测
- 状态入口：`PROGRESS.md`（阶段验收 G0–G7、数量看板、问题清单）
- 执行规范：`EXECUTION_PLAN.md`；研究协议：`docs/protocol.md`（冻结）
- 交接指令：`AGENT_HANDOFF.md`；决策记录：`docs/decisions.md`

## 环境

- Python：uv 管理（`uv sync` 按 `uv.lock` 恢复，Python 3.12）
- LaTeX：`tectonic`（brew 安装）；PDF 提取：poppler（pdftotext/pdfinfo）
- 模型凭证：环境变量 `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` /
  `ANTHROPIC_DEFAULT_HAIKU_MODEL`（见 `.env.example`；值不入库）
- 检索源：OpenAlex（主）、Crossref、arXiv API（节流 ≥3s）、Semantic Scholar（增益）

## 常用命令

```bash
cd Acdamic-Writing-Class-Task
uv sync                                  # 恢复依赖
uv run pytest                            # 不变量测试（去重/记忆/引用/重启）
uv run litreview check --scope corpus    # 语料计数与不变量检查

# 研究流程（按阶段）
uv run litreview run --stage discovery       # G1：多源检索 + 去重
uv run litreview run --stage screen [--max N]# G3：题名+摘要批量筛选
uv run litreview run --stage trace           # G3：引文追踪（前向+经典）
uv run litreview run --stage evidence        # G2：协调器回合（工具循环）
uv run litreview run --stage evidence_batch  # G3：批量证据提取（可续跑）
uv run litreview run --stage draft           # G2：带引用短草稿 + 引用检查
uv run litreview run --stage matrix          # G3：研究矩阵（六维分类）
uv run litreview run --stage review_queue    # 生成人工核验包

uv run litreview bibgen                     # papers.jsonl → paper/references.bib
uv run litreview evaluate                   # 标准评估入口（D-8）：
                                           #   R1/S2/H3 九案例单阶段 + M4 三案例
                                           #   两阶段（阶段1持久化→重启→阶段2恢复）
                                           #   结构化判分（事实/动作/来源/确定性）

# LaTeX 构建
cd paper && tectonic main.tex               # 综述
cd agent_report && tectonic main.tex        # 智能体说明
```

## 数据与可追溯性

| 文件 | 内容 |
|---|---|
| `data/search_runs.jsonl` | 每次检索（含失败与未完整分页） |
| `data/papers.jsonl` | 候选文献（work_id 归并；追加事件式更新） |
| `data/abstracts.jsonl` | 题名摘要侧车 |
| `data/evidence.jsonl` | 证据（逐字摘录 + 页级定位 + 条件/局限 + 核验状态） |
| `data/claims.jsonl` | 陈述（direct/synthesis/hypothesis × 章节） |
| `data/reviews.jsonl` | 核验记录（真人写入，智能体不代填） |
| `data/memory_events.jsonl` | 研究记忆（四类 × 双状态 × supersedes 链） |
| `runs/<id>/events.jsonl` | 运行日志（工具调用/模型用量/决策理由/失败） |

反幻觉核心：证据摘录提交时做逐字签名验证（剔除空白/连字符排版差异后的
连续子串匹配），改写与拼接被拒；证据库中每条摘录可回查到 `sources/` 存档
PDF 的指定页。

## 目录

```
paper/          综述 LaTeX 工程
agent_report/   智能体设计说明（LaTeX）
slides/         汇报材料（G6）
src/litreview_agent/  智能体源码
data/           研究数据（JSONL，入库）
sources/        论文 PDF 存档（不入库，本地保留）
runs/           运行日志（入库）
evaluation/     评估案例/规则/结果
docs/           协议、环境、可行性、决策、核验队列
```

## 限制说明

- 真人核验、成员姓名、计时排练未完成前，交付状态保持"待核验"（见
  `PROGRESS.md` §4）；
- 摘录验证保证逐字性，不保证解释无过度引申——语义核验需真人；
- 评估为小样本演示性评估，不构成方法优劣的统计证据；最终结果与判分方法见
  `evaluation/report.md`（v5：B 上下文注入 12/12 最好，C 结构化记忆 9/12）。
