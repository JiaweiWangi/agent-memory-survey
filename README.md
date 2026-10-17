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
uv run litreview check --scope corpus    # 语料计数与不变量检查（默认 data/）

# 从提交包离线复查（不依赖原项目目录；数据在 evidence_manifest/）：
cd submission/agent_source
uv run litreview --data-dir ../evidence_manifest check --scope corpus
# → 期望：papers.jsonl 726 条当前记录 / 有效证据 342（废止 7 条保留）/ 检索运行 104 次

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

## 从零重新生成一份综述（完整流程）

> 端到端约 1.5–2 小时纯机器时间（含必要的人工策展决策点共约半天）。
> 产出会与当前版本**不同**（检索结果随时间变化、模型输出有随机性），
> 但流程约束不变：逐字验证、引用检查、身份核验照样执行。

### 第 0 步：准备与备份（必须）

```bash
cd Acdamic-Writing-Class-Task
uv sync

# 凭证检查（无输出说明未配置，需要先 export 三变量，见 .env.example）
env | grep -q ANTHROPIC_BASE_URL && echo OK || echo "缺凭证"

# ⚠️ 数据文件是追加式的：重跑会追加新记录、与现有结果混淆。
# 重生产前务必备份（保留当前干净状态可随时回退/对照）：
cp -r data  data_backup_$(date +%m%d)
cp -r paper paper_backup_$(date +%m%d)
```

网络依赖：OpenAlex/Crossref/arXiv 可达（无需 API key）；arXiv 有 ≥3s 节流属正常。

### 第 1 步：检索与去重（~8 分钟）

```bash
uv run litreview run --stage discovery
```

11 组检索式（覆盖五个 RQ）× OpenAlex/Crossref + 6 篇种子论文核验 + 三重键
去重。产出 `data/papers.jsonl`（候选库）与 `data/search_runs.jsonl`（每次
检索的完整记录，含失败）。

### 第 2 步：两轮筛选（~25 分钟）

```bash
uv run litreview run --stage screen --max 300   # 第一轮：题名+摘要初筛
uv run litreview run --stage trace              # 引文前向追踪 + 经典补检
uv run litreview run --stage screen             # 第二轮：筛新候选
```

初筛只决定"值得读全文"。模型判 uncertain 的条目需要人工裁决（约 15 项，
每项 1–2 分钟）。

### 第 3 步：核心池构建（人工策展环节，1–2 小时）

这是**必须由人做**的决策（`src/litreview_agent/selection.py` 的
SELECTION 清单）：从初筛通过的候选中选出约 40 篇核心阅读池，分七层
（基础系统/组织检索/更新遗忘/评测/非恶意可靠性/安全投毒/综述边界），
**每篇回答三问**：解决什么具体问题？在本文承担什么作用？相比已选论文
提供什么不同？"标题相关/能下载/发表新"不构成入选理由。

修改 SELECTION 后重建三件套（拟选表/覆盖矩阵/降级清单）：

```bash
uv run python -m litreview_agent.selection
```

### 第 4 步：核心池深读与证据提取（~25–30 分钟，本流程大头上）

```bash
uv run litreview run --stage evidence_batch
```

每篇：下载 PDF（sha256 存档 `sources/`）→ **身份核验**（首页必须匹配记录
题名，防错配）→ pdftotext 提取 5 页（含方法/实验/消融）→ 模型提取 2–4 条
证据 → **每条摘录逐字签名验证**（改写/省略/拼接被拒，实测拦截率约 25%）。
断点续跑：再次执行同命令自动跳过已有证据的论文。

### 第 5 步：阅读卡与矩阵（~5 分钟）

```bash
uv run python -m litreview_agent.reading_cards   # 或见下方调用方式
uv run litreview run --stage matrix
uv run litreview run --stage review_queue        # 生成人工核验包
```

每篇核心论文一张九要素阅读卡（问题/机制/更新/评测/发现/局限/关系/章节/
定位），证据未覆盖的字段如实标注"待补读"，不编造。

### 第 6 步：生成正文与编译（~15 分钟）

```bash
# 七节正文（素材=阅读卡+证据；生成后自动跑引用检查，无证据引用会被拦）
uv run python -m litreview_agent.paper_writing

# 后处理：RQ 定义强制替换为协议冻结版（模型会擅自改写）、标题层级修正
uv run python scripts/postprocess_sections.py

# 参考文献生成 + 编译
uv run litreview bibgen
cd paper && tectonic main.tex
```

编译后**必须做成品检查**（编译成功 ≠ 内容完整）：

```bash
pdfinfo main.pdf | grep Pages        # 页数
pdftotext main.pdf - | grep "94"     # 抽查关键数字是否真的在 PDF 里
```

历史教训：模型会把 Markdown 残留（代码围栏/`**`/未转义 `%` 与 `$`）泄进
LaTeX 导致内容静默丢失——这类问题只能靠成品抽查发现。

### 第 7 步（可选）：评估与打包

```bash
uv run litreview evaluate            # 12 案例 × 3 条件（会产生模型调用费用）
./scripts/package_submission.sh      # 构建提交包（submission/）
```

### 耗时与产物汇总

| 场景 | 耗时 | 说明 |
|---|---|---|
| 完整重生产（纯机器） | 1.5–2 小时 | 第 1–2、4–6 步 |
| 含人工策展决策点 | 约半天 | 第 3 步选池 + uncertain 裁决 |
| 离线复现验证（零模型调用） | 5 分钟 | `uv run pytest && uv run litreview check --scope corpus && cd paper && tectonic main.tex` |

每一步的中间产物都在 `data/`（JSONL 追加式）与 `runs/`（运行日志）中，
重生产过程中可随时中断检查；全流程的决策依据见 `docs/decisions.md`。

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
