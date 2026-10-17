# 选题可行性报告（G1）

执行日期：2026-10-17。全部计数来自 `data/search_runs.jsonl`、`data/papers.jsonl` 的实际记录，可用 `uv run litreview check --scope corpus` 复核。

## 1. 结论

**选题可行**：候选数量、正文可获取性、RQ 覆盖均显著超过 G1 验收线，且更新与可靠性分支研究活跃。扩展到正文实际引用 ≥30 篇的路径明确（见 §5）。

## 2. 检索执行记录

| 来源 | 状态 | 说明 |
|---|---|---|
| OpenAlex | ✅ 产出主力 | 11 个检索式（五组概念）× 每式 2 页 × 25 条 + 种子核验 6 次；page 翻页（cursor 翻页现需 API key，实测规避） |
| Crossref | ✅ 可用 | RQ3/RQ4/RQ5 重点补检 3 式 × 20 条；正式出版记录为主，与 OpenAlex 覆盖互补 |
| arXiv API | ⚠️ 暂时限流 | 适配器已实现（节流 3.5s + 退避）；早前探测触发 IP 级封锁，持续 429。封锁解除后用于预印本定向补检；**不影响正文获取**（arxiv.org/abs、/html、/pdf 三通道均 200） |
| Semantic Scholar | ⚠️ 429 限流 | 共享 IP 限流，仅增益源，不阻塞 |

检索运行共 66 次记录（含 17 次失败——主要是 arXiv 429 与 OpenAlex cursor 政策错误，全部如实入档）。

## 3. 数量与覆盖（2026-10-17 实测）

| 指标 | 数值 | G1 验收线 |
|---|---|---|
| 去重后独立研究（work_id） | **494** | ≥20 |
| 正文已验证可读（PDF 下载 + 提取成功） | **16**（另有 213 项有 arXiv 通道待按需下载） | ≥12 |
| 涉及更新或可靠性（题名级确认） | **更新 1+ / 可靠性 10+**（RQ3/RQ4 抽验池内） | ≥4 |
| 种子论文核验 | **6/6**（Generative Agents、MemGPT、MemoryBank、Reflexion、LoCoMo、LongMemEval 全部命中并记录元数据） | — |

RQ 覆盖（题名/摘要启发式初步标注，待模型正式标注）：RQ1 ≥83、RQ2 ≥328、RQ3 ≥204、RQ4 ≥199、RQ5 ≥311 条候选。五个 RQ 均有充分候选，无结构性空白。

年份分布：2020–2022 共 9 项、2023 起 424 项（2026 年 348 项）——领域极新且活跃，"前沿问题"定位成立；早期经典（Generative Agents 2023 等）经种子核验保留。

## 4. 初步分类（工作假设，待正文阅读修订）

按 EXECUTION_PLAN §2.4 维度，当前候选池的天然聚类：

- **组织与表示（RQ2）**：上下文工程型（MemGPT 分页）、图结构（Selective Forgetting 的图框架、知识图谱索引）、分层/摘要型（MemoryBank Ebbinghaus 遗忘曲线）、经验型（Reflexion 语言化经验）。
- **更新与遗忘（RQ3）**：reconsolidation（检索驱动再巩固）、selective forgetting、memory canonicalization、时序知识冲突。
- **可靠性（RQ4）**：记忆投毒攻击（prompt persistence attacks、poisoning attack/defense、forged reasoning traces）、provenance（Agent Zero Memory、provenance laundering）、可信巩固（TRUSTMEM）。
- **评测（RQ5）**：LongMemEval（ICLR 2025）、LoCoMo（ACL 2024）、IFCMemoryBench、cost-aware evaluation。

## 5. 扩展到正文引用 ≥30 篇的路径

1. **已验证 16 篇直接进入阅读**（覆盖全 5 个 RQ，全部有页级可定位 PDF）。
2. **213 项 arXiv 通道候选**按 RQ 缺口逐批下载筛选（预估筛出 25–35 篇高质量项）。
3. **引文追踪**：对已验证据（LongMemEval、MemGPT、survey）用 OpenAlex referenced_works/cited_by 前后向追踪，补齐方法谱系早期节点（Voyager、RecurrentGPT、RET-LLM 等）。
4. **arXiv API 解封后**做预印本定向检索（arXiv 独有覆盖）。
5. 筛选按 `docs/protocol.md` §4 理由码记录，宁缺毋滥：目标 35–45 项纳入、≥30 项正文实际引用。

## 6. 风险与限制

- OpenAlex 检索相关度对 2026 年预印本有偏（数量大、质量分层），纳入筛选需更严格（G3 执行）。
- arXiv API 封锁未解除前，预印本发现依赖 OpenAlex/Crossref 的镜像索引（二者均收录 arXiv DOI，实测无遗漏迹象）。
- 启发式 RQ 标注仅为可行性估计，正式标注在 G2 由模型按摘要+正文完成，人工复核。
