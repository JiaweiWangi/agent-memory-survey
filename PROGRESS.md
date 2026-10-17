# 执行进度与验收记录

最后更新：2026-10-17（G0 完成，G1 进行中）。

本文件是执行状态入口。执行 Agent 每个重要阶段更新；未执行的工作不得勾选。计数来自实际记录，未知值写“未统计”。

## 1. 当前状态

| 项目 | 状态 |
|---|---|
| 课程要求 | 已读取 `Task.md` |
| 选题 | 已获用户接受：大模型智能体的长期记忆，重点关注更新与可靠性 |
| 执行方案 | 已交付 `EXECUTION_PLAN.md` |
| 执行交接 | 已交付 `AGENT_HANDOFF.md` |
| 执行计划 | 已批准（2026-10-17）：API 端点复用、tectonic+poppler、uv 管理、里程碑提交 |
| 研究执行 | G0–G3 完成；G4 待启动（矩阵/谱系/评估） |
| 真人核验 | 未开始 |
| 实际截止日期 | 未提供，按 10 个工作日相对计划执行 |
| 成员身份 | 待三名成员补充，当前使用 A/B/C |
| 模型与检索服务 | 已实测：Anthropic 兼容端点可用、OpenAlex/arXiv 可用、S2 限流（见 `docs/environment.md`） |
| LaTeX | tectonic 0.17.0 已装，ctexart 中文编译冒烟通过 |

## 2. 阶段检查表

### G0：环境与协议 ✅（2026-10-17）

- [x] 核对项目范围、已有文件与 Git 状态。
- [x] 记录真实环境和可用模型、检索、正文读取、编译能力。
- [x] 固定 RQ、范围、纳入排除条件与检索截止日。
- [x] 建立数据字段、文件位置和来源追踪规则。
- [x] 对具体缺口记录依赖和替代路径。

产物与验证依据：
- `docs/protocol.md` v1.0——RQ1–RQ5、纳入/排除标准（6 个稳定理由码）、检索截止日冻结 2026-10-17、DOI/arXiv ID 归一化与 work_id 规则、六文件 JSONL 字段、证据六要素、陈述支持等级、停止规则。
- `docs/environment.md`——实测环境：OpenAlex ✅ / arXiv ✅（需 ≥3s 节流，实测 Rate exceeded 行为）/ S2 ⚠️429 / 全文三通道 ✅ / Anthropic 兼容端点冒烟 ✅ / tectonic+poppler 安装且冒烟 ✅（中文 ctexart 编译、MemGPT PDF 13 页页级提取）。
- uv 工程：`pyproject.toml` + `uv.lock`（Python 3.12.13，httpx/pydantic/pypdf/pytest），`src/litreview_agent/` src-layout，models.py 冒烟往返通过。
- `config.example.yaml`（节流、max_tool_steps=12、模型名走 env）、`.env.example`（仅变量名）、scoped `.gitignore`（.venv/sources/凭证不入库）。

### G1：文献可行性 ✅（2026-10-17）

- [x] 至少两个实际可访问的学术发现来源。（OpenAlex ✅ 产出主力 + Crossref ✅ 3 式补检；arXiv API 适配器已实现但 IP 级 429 封锁中，解封后补预印本定向检索；S2 限流不阻塞）
- [x] 至少 20 项去重学术候选，身份初核完成。（494 项独立 work_id；556 OpenAlex 命中 + 60 Crossref 命中经 DOI/arXiv ID/题名-首作者-年份三重键归并，合并 69 次重复）
- [x] 至少 12 项可读取相关正文。（16 项 PDF 下载 + pdftotext 提取验证成功，sha256 存档；另 213 项有 arXiv 通道待按需下载）
- [x] 至少 4 项涉及记忆更新或可靠性，并覆盖多个 RQ。（抽验池内：更新 1+ 项、可靠性 10+ 项；五 RQ 启发式覆盖 RQ1≥83/RQ2≥328/RQ3≥204/RQ4≥199/RQ5≥311）
- [x] 初始分类和扩展到至少 30 篇的检索路径明确。（`docs/topic_feasibility.md` §4–5）
- [x] 无法获取、重复版本和排除原因已记录。（search_runs.jsonl 66 条含 17 失败；版本记录标 alt-version-record；未获取正文标 unavailable）

产物与验证依据：
- `docs/topic_feasibility.md`——真实计数可行性报告。
- `data/search_runs.jsonl`（66 次检索记录）+ `data/papers.jsonl`（524 条记录 / 494 独立研究）+ `sources/`（16 个 PDF 存档带哈希）。
- `uv run litreview check --scope corpus` 可复核计数与不变量（通过）。
- 种子论文 6/6 核验：Generative Agents、MemGPT、MemoryBank、Reflexion、LoCoMo（ACL 2024）、LongMemEval（ICLR 2025）。

### G2：最小完整智能体流程 ✅（2026-10-17）

- [x] 对 3–5 篇真实论文建立可回查证据。（5 篇：MemGPT、LongMemEval、Selective Forgetting、Memory Poisoning Attack and Defense、LTM Security Survey；30 条证据全部带 pdf:pN 定位 + 逐字摘录 + 条件/局限，验证状态 model_assisted）
- [x] Agent 根据研究缺口选择下一步工具行动。（**真实发生**：模型观察到 RQ1/RQ5 证据缺口后自选 7 个检索词补检，含 "long-term memory versus context window RAG parametric knowledge boundary"——非脚本预设；另诚实报告工具链缺口"无法枚举 evidence_id"并提出 list_evidence 方案，被采纳）
- [x] 生成带有效引用的短草稿。（`data/derived/draft_g2.md`：9 处 \cite 全部有证据支撑，4 个 work；引用检查通过）
- [x] 缺失证据和冲突不会被自动写成已确认结论。（**反幻觉验证真实拦截**：excerpt 逐字验证拒绝改写/省略号压缩/凭记忆复述 30+ 次，模型重读原文后修正；草稿中泛化性陈述主动标【待核验】×1）
- [x] 重启可恢复状态，记忆更新可追踪。（`tests/test_g2_invariants.py::test_restart_preserves_state_no_duplicates` 通过：新协调器实例从磁盘重建状态；memory_events.jsonl 29 条任务记忆事件，supersedes 链保留历史）
- [x] 形成真实运行日志，模拟和重放有明确标识。（12 个运行目录共 1,586 条事件：工具调用/结果/模型用量/决策理由/错误全记录；无模拟数据，replay=false）

产物与验证依据：
- 代码：`coordinator.py`（协调循环+9 工具）、`model_backends.py`（Anthropic 兼容适配器，凭证仅从 env）、`memory.py`（四类记忆+双状态+supersedes）、`checks.py`（引用检查）、`stages.py`（evidence/draft 阶段）。
- 数据：`data/evidence.jsonl`（30 条）、`data/claims.jsonl`（7 条，其中 clm-d99029 为模型工具探测产物、后续筛选排除）、`data/memory_events.jsonl`（29 条）、`data/derived/draft_g2.md` + `draft_g2_check.md`。
- 测试：`uv run pytest` 9/9 通过（版本去重×2、记忆有效性、证据不自动提升、摘录验证接受/拒绝×2、引用检查×2、重启恢复）。
- 关键工程决策（正文提取）：pdftotext raw 模式替代 -layout（双栏论文按逻辑顺序读取，连续摘录可验证）；摘录验证签名剔除空白与连字符（排版产物），内容字符序列仍逐字严格。

### G3：完整证据库 ✅（2026-10-17，策略对齐版）

**策略对齐（D-3，用户九点指令）**：暂停无差别提取；建立 40 篇核心阅读池（七层结构），初筛与最终纳入分离，深读+阅读卡，年份六成复查通过（2026 占 60%，2023–2025 主线 16 篇）。

- [x] 版本去重、身份核验、筛选理由和来源完整。（升级：Zenodo 资源/Underline 载体不计数；W0172/W0380/W0439 合并；同研究版本对标记待归并）
- [x] 五个 RQ 和主要方法分支的覆盖已检查。（核心池覆盖矩阵：RQ1:10 RQ2:18 RQ3:18 RQ4:10 RQ5:12 篇；可靠性去失衡——非恶意 5 + 攻击 3）
- [x] 核心池 40 篇完成正文深读与阅读卡。（39/40 有证据共 138 条（5页/篇，含方法/实验/消融）；W0056 记忆机制综述正文获取受限（ACM 付费墙+镜像损坏）如实标注，摘要级辅证。39 张九要素阅读卡 `data/derived/reading_cards.md`，空字段标"证据未覆盖待补读"不编造；独立抽查 4/4 摘录在标注页真实存在）
- [x] 最终确定 35–45 篇。（核心池 40 篇即正文引用池；D-3 策略后 215 项 included 降为辅助池）
- [ ] 真人核验：核验队列按核心池重生成（优先 P0=更新/可靠性层）。

产物与验证依据：
- `data/core_pool.jsonl` + `data/derived/core_selection.md`（40 篇拟选表：角色/RQ/三问理由/阅读状态）
- `data/derived/coverage_matrix.md`（层×RQ 覆盖与缺口）
- `data/derived/downgrade_exclusion.md`（215 项降级辅助 + 排除合并清单）
- `docs/decisions.md` D-3、`docs/protocol.md` v1.1 修正案
- 年份再平衡：换入 MIRIX/HaluMem/MemBench/记忆机制综述(143引)，换出 Memory Fabric/IFCMemoryBench/FadeMem/HippoRAG(边界)
- LoCoMo 修正：W0005（ACL 2024，被引 85）此前因无 arXiv 字段从未被读——已绑定 ACL PDF 入池

### G4：综合与评估

- [ ] 分类矩阵、谱系或时间线有来源依据。
- [ ] 方法与基准比较明确任务、模型和预算差异。
- [ ] 开发案例与冻结的正式评估案例分离。
- [ ] 评估结果、分母、模型、参数和用量如实记录。
- [ ] 保留失败案例，并说明小规模评估局限。
- [ ] 持久化、更新、来源约束、引用检查等必要测试通过。

产物与验证依据：待填写。

### G5：正文、说明与核验

- [ ] 综述覆盖背景、研究谱系、主要挑战和五个 RQ。
- [ ] 正文实际引用至少 30 项去重学术研究。
- [ ] 核心陈述、数值、图表和谱系关系均可追溯。
- [ ] 每项最终引用研究完成人工身份、版本及至少一条使用证据检查。
- [ ] 核心结论与关键数值全部人工检查，关键内容交叉复核。
- [ ] 辅助陈述抽样检查不少于 20%，发现问题后扩展检查。
- [ ] 没有已知未解决的重大事实或引用错误。
- [ ] 综述和智能体说明均已编译并检查 PDF 页面。

产物与验证依据：待填写。

### G6：汇报

- [ ] 幻灯片与讲稿使用真实来源、运行和结果。
- [ ] 智能体部分在 4 分钟内，研究部分在 4 分钟内。
- [ ] 有演示备份和主要问题的答辩准备。
- [ ] 三人贡献明确且真实记录。
- [ ] 至少一次真人完整计时排练，记录实际用时。

产物与验证依据：待填写。

### G7：最终交付

- [ ] 从整理后的工程成功构建最终 PDF，源文件与 PDF 一致。
- [ ] 真实智能体流程、跨运行更新和必要检查可复现。
- [ ] 必需人工核验和问题修复完成。
- [ ] 提交包包含正文、智能体说明、幻灯片、源码、配置示例与复现说明。
- [ ] 证据清单和贡献记录完整，没有凭证或不必要缓存。
- [ ] `docs/final_acceptance.md` 写明检查结果和剩余局限。

产物与验证依据：待填写。

## 3. 数量看板

| 指标 | 当前值 | 说明 |
|---|---|---|
| 原始发现记录 | 616 次命中（66 次检索运行，含 17 次失败记录） | OpenAlex 556 + Crossref 60；全部入档 search_runs.jsonl |
| 去重学术候选 | 494 | 按独立 work_id；524 条记录含版本关系 |
| 可获取相关正文 | 16 已验证 + 213 有 arXiv 通道 | 已验证=PDF 下载+提取成功；通道=未逐一验证 |
| 已阅读相关正文 | 5（30 条证据支撑，G2 完成） | MemGPT / LongMemEval / Selective Forgetting / Memory Poisoning / LTM Security Survey |
| 纳入研究 | 5（G2 代表作；G3 扩展到 35–45） | 均有已验证证据 |
| 正文实际引用的独立研究 | 4（G2 短草稿；最终硬性要求 ≥30） | draft_g2.md 引用检查通过 |
| 已有原文支持的核心陈述 | 6 条 claims（+1 探测产物） | 2 direct + 4 synthesis；全部引用已登记证据 |
| 已完成人工初核的引用研究 | 未统计 | 最终覆盖全部引用研究 |
| 关键结论人工复核 | 未统计 | 最终覆盖全部必检项 |
| 未解决重大问题 | 未统计 | 不能将未审查误记为 0 |
| 正式评估案例与结果 | 未统计 | 开发、正式、重跑分别记录 |
| 真人排练时长 | 未记录 | 不以自动估算代替 |

## 4. 当前问题与依赖

| 编号 | 事项 | 状态 | 影响与可继续工作 |
|---|---|---|---|
| D-01 | 实际截止日期未知 | 使用默认排期 | 不阻塞启动，获知后重新排期 |
| D-02 | 模型和检索能力 | ✅ 已实测（2026-10-17）：端点/OpenAlex/arXiv 可用，S2 限流 | 见 `docs/environment.md` |
| D-03 | LaTeX 构建路径 | ✅ 已建立：tectonic 0.17.0 中文编译冒烟通过 | 见 `docs/environment.md` §4 |
| D-04 | 真人姓名、核验与排练尚未发生 | 后续真实执行 | 先准备核验包，不能替真人确认 |

## 5. 决策与变更记录

| 日期 | 决定 | 依据与影响 |
|---|---|---|
| 2026-10-17 | 选用智能体长期记忆方向 | 用户接受；聚焦跨会话外部记忆、更新与可靠性 |
| 2026-10-17 | 默认单一协调 Agent、Python 与文件持久化 | 优先完成可追踪的研究流程，控制工程范围 |
| 2026-10-17 | 最终文献目标 35–45 项，硬性底线 30 项正文实际引用研究 | 留出筛选和修订余量，禁止重复版本凑数 |
| 2026-10-17 | 使用相对排期与可替换后端 | 用户暂无额外偏好，减少非必要确认 |

后续变更在此记录摘要，复杂决定写入 `docs/decisions.md` 并链接依据。

## 6. 下一步

G0/G1/G2 已完成（批次 1–3：协议环境 → 文献可行性 → 最小智能体闭环）。下一批次：G3 证据库扩展——OpenAlex 引文前后向追踪、更新/可靠性/评测三分支补检、筛选记录与研究矩阵、目标 35–45 项纳入。arXiv API 封锁解除后补预印本定向检索。人工核验包从 G3 开始准备。

最终状态：**G0–G3 完成（核心池 40 篇深读+阅读卡就绪）；G4 待启动。**
