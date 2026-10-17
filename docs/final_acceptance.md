# 最终验收报告

验收日期：2026-10-17。本报告如实列出完成情况与剩余限制；"待真人"项不由智能体代签。

## 1. 课程硬性要求核验

| 要求 | 状态 | 证据 |
|---|---|---|
| ≥30 篇文献的综述 | ✅ **39 项独立研究正文实际引用**（`\cite` 命令统计，非 bib 条目计数） | `paper/main.pdf` 18 页；`paper/references.bib`；检查器输出 |
| 三人一组 | ⚠️ 结构就绪，**待成员署名**：分工表已设计（EXECUTION_PLAN §10.1），贡献记录 `docs/contribution_log.md` 待真实填写 | 成员 A/B/C 占位 |
| 设计智能体完成综述 | ✅ 完整实现 + 真实运行 | `src/litreview_agent/`（10 模块）；`runs/` 34 个运行目录全程日志 |
| 幻觉控制 | ✅ 逐字验证拦截 360 次（258 协调器 + 102 批处理），0 条被拒摘录入库；独立抽查 4/4 | `runs/*/events.jsonl`；`data/evidence.jsonl` 343 条全带定位 |
| 人工验证 | ⚠️ **核验包就绪、真人核验未完成**（不可替代项） | `docs/human_review_queue.md`（40 文献 + 45 边界 + 7 claims） |
| 8 分钟汇报（4+4） | ⚠️ 材料完成、**真人计时排练未做** | `slides/main.pdf` 9 页；`slides/speaker_notes.md`（含计时表待填） |
| LaTeX 提交 | ✅ 三份文档 tectonic 编译 0 错误 | 综述 18 页 / 智能体说明 4 页 / 幻灯片 9 页 |

## 2. 研究质量核验（对照 EXECUTION_PLAN §12.3）

1. **引用数**：39 ≥ 30 ✓；全部引用可解析（0 未定义）✓
2. **身份/版本核验**：机器侧完成（DOI/arXiv ID 归并、多载体合并、资源记录排除）；**人工侧待办**（40 项队列）
3. **真人核验记录**：`data/reviews.jsonl` 尚无记录——待成员按队列填写
4. **真实流程复现**：协调器回合（缺口驱动 + 诚实失败两次决策演示）与跨运行恢复测试可复现（`uv run litreview run --stage evidence`；`tests/` 12/12）
5. **自动检查**：pytest 12/12；引用/计数/记忆不变量检查器全过
6. **PDF 检查**：编译通过且结构完整；**逐页人工检查待做**
7. **汇报分段**：讲稿按 4+4 结构编写；**计时待排练**
8. **提交包**：见 §4

## 3. 智能体评估摘要（详见 agent_report）

12 冻结案例 × 3 条件（36/36 真实运行）：结构化记忆（C）编造最少（1 vs A/B 各 3）、跨会话恢复与跨运行任务全过；已知混杂（C 用工具循环）与小样本局限如实报告。两次实现修复（D-4/D-5）均记录并全量重跑，污染结果归档未计入。

## 4. 提交包结构

```
submission/
  review.pdf              综述（18 页）
  agent_report.pdf        智能体设计说明（4 页）
  presentation.pdf        幻灯片（9 页）
  latex_source/           三工程源文件 + 参考文献 + 图表
  agent_source/           智能体源码 + 测试 + 配置样例 + 评估材料
  evidence_manifest/      文献清单/证据清单/阅读卡/研究矩阵/核验队列
  README.md               复现说明
```

原始论文 PDF（sources/，68 个）与 HTTP 缓存不入分享包（协议 §12.2）；证据清单保留标识、定位与摘录，可溯源性不变。

## 5. 剩余限制（如实）

1. **真人核验未发生**——文献身份/版本/使用证据 40 项、核心结论交叉复核、≥20% 辅助陈述抽样，全部待三名成员完成前，交付状态为"待核验草稿"，不宣称 G5/G7 通过。
2. **W0056（记忆机制综述，143 引）正文获取受限**（ACM 付费墙、镜像损坏）——未进入正文引用；摘要级信息在核验队列中标注。
3. **语义正确性**：逐字验证保证"摘录真实存在"，不证明"解释无过度引申"——阅读卡的模型解释字段全部标"待人工复核"。
4. **评估为演示性小样本**，不构成方法优劣的统计证据。
5. **arXiv API 曾有 IP 限流**：检索期间以 OpenAlex/Crossref 为主源（均已满足多源要求），失败记录如实入档。
6. **汇报排练与成员姓名**：待真人完成。

## 6. 复现

```bash
cd Acdamic-Writing-Class-Task
uv sync && uv run pytest                    # 12/12
uv run litreview check --scope corpus      # 语料计数
cd paper && tectonic main.tex              # 综述
cd ../agent_report && tectonic main.tex    # 说明
cd ../slides && tectonic main.tex          # 幻灯片
```

模型凭证走环境变量（`.env.example`）；全程用量记录于 `runs/*/events.jsonl` 与 `data/derived/evidence_batch_usage.jsonl`。
