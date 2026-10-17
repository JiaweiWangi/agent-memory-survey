# 最终验收报告

验收日期：2026-10-17（v3：三轮外部核验与修复后，见 §0a/§0b）。本报告如实列出完成情况与剩余限制；"待真人"项不由智能体代签。

## 0a. 第三轮外部复验核验结果（v3 新增，2026-10-17）

| 复验问题 | 核验结论 | 实际修改 | 验证依据 |
|---|---|---|---|
| references.bib 仍留错误 arXiv（W0003:2307.08909 / W0004:2305.10250） | 成立 | bibgen 重生成：W0003 eprint=2305.10250、W0004 eprint=2303.11366 | `grep -A6 "W0003," paper/references.bib`；包内 latex_source 同步一致 |
| research_matrix.jsonl 仍把艾宾浩斯/15 用户/194 问题归 Reflexion | 成立（矩阵生成于修正前未重跑） | matrix 从修正后阅读卡重生成：W0003=遗忘曲线、W0004=反思缓冲+Ω 上限；methods_table 同步 | `data/derived/research_matrix.jsonl` W0003/W0004 行 |
| 核验队列保留错误编号 | 成立（队列文件为修正前生成） | review_queue 重生成 | `docs/human_review_queue.md` W0003/W0004 行 |
| 身份检查仍放行 Reflexion 标题+MemoryBank PDF | 成立（v1 按词半数命中，通用词即可凑满） | v2 规则：首显著词必须命中+显著词过半+通用词黑名单 | 3 项 identity 回归测试（含两种真实错配被拒、正确配对不误拒）；`check --scope identity` 39/40（仅 W0056 无 PDF） |
| reading_cards.py 等流程仍读全部证据 | 成立（4 处直接 read_jsonl） | 全部改用 load_valid_evidence（废止感知） | `grep -rn 'read_jsonl.*evidence.jsonl' src/` 归零；测试 21/21 |
| M4-03/A 编造 S102 判成功；M4-03/C 过度确定判成功；M4-01/C 缺动作判成功 | 全部成立 | 判分 v2（事实+动作+来源+确定性）重评已存储输出（未重跑）：multirun A 0/3、B 3/3、C 1/3；合计 A 2/12、B 12/12、C 9/12；B 最好、C 优势结论从全部材料撤回 | `evaluation/report.md` v5；results.jsonl scored_by=structured_v2；4 项判分回归测试（含防过严合格样例） |
| README 评测命令仍为旧单阶段 | 成立 | CLI evaluate 改标准入口（R1/S2/H3 单阶段 + M4 两阶段 + v2 判分）；README 同步 | `src/litreview_agent/cli.py` evaluate 分支；README 评测段 |
| 谱系图节点遮挡 | 成立 | TikZ 图改为关系表（12 条有据边 + 依据列 + "仅提到不视为继承"说明） | review.pdf 第 8 页 `tab:genealogy` 表格完整呈现 |
| 基准表超出右边界 | 成立 | longtable 列宽适配（1.1+0.6+5.4+6.8cm < 版心宽） | review.pdf 第 14–15 页基准表"主要发现"列完整可读 |
| 正文仍称 39 篇 343 条证据 | 成立（生成时注入的漏斗文本） | concepts.tex 改"核心池证据 139 条 + 辅助池 203 条（不进入正文引用链）" | review.pdf 第 5 页 |
| submission 缺 papers/evidence/claims/reviews 四文件 | 成立 | 打包脚本补 6 个 JSONL（papers/evidence/claims/reviews/search_runs/memory_events，含 7 条废止记录） | 独立临时目录 `/tmp/submission_verify` 验证：文件齐全、JSONL 可读、废止记录在内、W0003/W0004 最新绑定正确、三份 PDF 与最终编译版字节一致（cmp）、agent_source 源码离线可编译（py_compile）；包 92 文件 3.5M |

## 0b. 第二轮外部审查核验结果（v2，2026-10-17）

| 审查问题 | 核验结论 | 处置 |
|---|---|---|
| W0003/W0004 论文身份错配（气候论文证据混入） | **确认成立**（2307.08909=physics.ao-ph 气候论文；2305.10250=MemoryBank 被错绑 Reflexion） | 记录修正（W0003→2305.10250、W0004→2303.11366）；7 条污染证据经 reviews.jsonl 废止（原记录保留）；两篇重新提取证据与阅读卡；conclusion.tex 错配句修正；全核心池身份核验（40 项，39 通过 + W0056 无 PDF 已知）；批处理加入前置身份校验 + `check --scope identity`（决策 D-6） |
| multirun "3/3 成功"不成立（无真实跨运行） | **确认成立且更严重**（C 条件实际输出"查无记录"仍被计为成功） | 重做为真实两阶段实验（阶段1持久化→新实例→阶段2恢复）；全量 36 行按任务完成口径重审：A 3/12、B 12/12、C 11/12；**撤回"C 优于 B"结论**；"人工复核确认"不实表述改为"智能体侧核查"（决策 D-7）；旧结果归档未覆盖 |
| 摘要占位 | 确认 | 已基于真实发现撰写（含 F1 0.417/0.468、9.8% 等可回查数字） |
| 未转义 % 静默删内容 | 确认（evaluation 2 处、update_reliability 18 处） | 全部转义；成品 PDF 抽查确认被吞内容（"94% 的评估问题"等）已呈现 |
| 谱系图节点重叠 | 确认（同年同层节点同坐标完全重叠） | 重排为同年同层横向展开（v2） |
| 方法表 40 行溢出 | 确认 | 改 longtable 跨页 |
| conclusion 缺 RQ1、RQ4/RQ5 编号与协议错位 | 确认 | 补 RQ1 小节；RQ4/RQ5 标题对齐冻结协议编号 |
| "记忆更新与可靠性"章节标题缺失 | 确认（早前围栏清理误删 \section 行） | 已补回，成品 PDF 验证 |
| 证据数口径 343 vs 核心池实际 | 确认（核心池有效证据 139 条，343 为含辅助池全库数） | 漏斗图/说明/验收报告/讲稿统一改为分层口径（核心 139 + 辅助 203 = 有效 342） |
| taxonomy 末句截断 | **成立**（v2 曾误判"不成立"——当时只查了文件末段，漏检第 27 行段落中间的截断句；本轮复验纠正该记录） | 截断句按本章内容补全；顺带修正同段悬空引用"图 1(d)"（指 RecMem 论文自身的图，非本文图表） | 成品 PDF 第 8 页"如何组织与演化……是否可信"完整呈现；`grep -n 如何组织与演 paper/sections/taxonomy.tex` 现为完整句 |
| 关键论断可追溯性 | 部分成立（原 claims.jsonl 仅 7 条不足以覆盖正文） | 新建关键论断映射表 `data/derived/claims_map.md`：20 项核心论断全部映射到文献+页码定位+摘录+适用条件（20/20 成功） |

## 1. 课程硬性要求核验

| 要求 | 状态 | 证据 |
|---|---|---|
| ≥30 篇文献的综述 | ✅ **39 项独立研究正文实际引用**（`\cite` 命令统计，非 bib 条目计数） | `paper/main.pdf` 18 页；`paper/references.bib`；检查器输出 |
| 三人一组 | ⚠️ 结构就绪，**待成员署名**：分工表已设计（EXECUTION_PLAN §10.1），贡献记录 `docs/contribution_log.md` 待真实填写 | 成员 A/B/C 占位 |
| 设计智能体完成综述 | ✅ 完整实现 + 真实运行 | `src/litreview_agent/`（10 模块）；`runs/` 34 个运行目录全程日志 |
| 幻觉控制 | ✅ 逐字验证拦截 360 次（258 协调器 + 102 批处理），0 条被拒摘录入库；独立抽查 4/4 | `runs/*/events.jsonl`；`data/evidence.jsonl` 349 条记录（有效 342：核心池 139 + 辅助池 203；7 条错配证据已废止）全带定位 |
| 人工验证 | ⚠️ **核验包就绪、真人核验未完成**（不可替代项）；另有关键论断映射表 `data/derived/claims_map.md`（20 项论断→文献→页码→条件）供复核 | `docs/human_review_queue.md`（40 文献 + 45 边界 + 7 claims） |
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

12 冻结案例 × 3 条件（36/36 真实运行，multirun 为真实两阶段：阶段1持久化→新实例→阶段2恢复）。**当前结论（v5 报告 + v3 结构化判分，替换早期所有版本）**：任务完成度 A 无记忆 2/12、B 上下文注入 12/12、C 结构化记忆 9/12——B 最好；C 的"优势"结论已全部撤回，其剩余实证为跨运行持久化可行（M4-02 真实恢复）与本项目 342 条有效证据运行其上（工程实证）。~~早期版本"C 编造最少、跨会话恢复与跨运行任务全过"的表述已失效~~（multirun 原单阶段设计无真实持久化且判分仅关键词命中，见 D-7/D-8/D-11）。判分经历三轮修正（D-7 重做两阶段 → D-8 结构化判分 → D-11 对象绑定/内容相符性），误判输出全部固化为回归测试；受污染的早期结果归档于 `results_*.jsonl.bak` 未计入。

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


## 0-4. 第四轮独立验收核验结果（GPT-6.1 Sol，2026-10-17）

| 复验问题 | 核验结论 | 实际修改 | 验证依据 |
|---|---|---|---|
| coordinator._evidence() 仍读原始库，废止证据可能进入生产路径 | 成立（submit_claim 也仅查 ID 存在） | _evidence 改 load_valid_evidence；submit_claim 显式拒绝废止 ID（区分"不存在"与"已废止"两种错误） | 真实 7 条废止 ID 端到端验证：list_evidence 展示 0 条、覆盖统计不计入、submit_claim 明确拒绝；2 项 coordinator 级回归测试（test_coordinator_hides_invalidated_evidence / rejects_claim_on_invalidated） |
| 谱系表把"比较/批评基准"写成"以该基准评测" | 成立（3 条边错标性质，2 条边无证据） | 12 条边逐条对照证据裁定：LongMemEval→LoCoMo、LongMemEval→MemoryBank、HaluMem→LongMemEval 改为"比较／讨论"；Canonicalization→LongMemEval、A-Mem→Mem0 无证据删除；10 条保留边均附原文定位；单元格 LaTeX 特殊字符转义修复 | `data/derived/genealogy.json` nature/basis 字段；review.pdf 第 8 页表 1（"以该基准评测"仅在有使用证据处出现） |
| 判分器仍放行三类明显错误（999/888/777 编造、队列颠倒、claim 内容相反） | 成立 | 判分 v3：M4-01 数字-对象绑定核对（分隔符容错 ：/=/共/有）；M4-02 邻近窗口（±15字符）角色绑定防颠倒；M4-03 主张与 claim 内容相符性检查；无法可靠判断时输出 needs_human_review 不默认成功 | 8 个构造案例 + 2 个真实误拒修复全部通过；4 项新回归测试；重评存储输出（未调模型）终值不变：A 2/12、B 12/12、C 9/12 |
| 提交包 README 复现命令未指定数据目录，空目录返回成功 | 成立 | check_corpus 加必需文件/非空检查（缺失即失败并说明原因，exit=1）；README 与提交包 README 写明 `--data-dir ../evidence_manifest` 与期望输出 | 独立临时目录 `/tmp/sub_verify_final`：uv sync + 28 项测试通过；corpus check 读包内数据（726 当前记录/342 有效/104 检索运行/废止 7 条保留）；空目录 exit=1 并打印缺失原因 |


## 0-5. 第五轮收尾核验（GPT-6.1 Sol 复验后，2026-10-17）

| 项目 | 核验结论 | 修改内容 | 实际验证结果 | 剩余人工事项 |
|---|---|---|---|---|
| M4-03 仍可放行明显错误（"猫狗照片/天气预报"判成功） | 成立（错误词黑名单可被任意编造绕过） | 判分改保守三态（D-13）：确定性错误（编造标识/过度确定/虚构评分）判失败；其余 M4-03 一律 needs_human_review 不默认成功；三态互斥，待核验不计入成功/失败 | 重评已存储输出（零模型调用）：multirun A 0成功/3失败/0待核、B 2/0/1、C 1/2/0；**12 案例合计（成功/失败/待核验）：A 2/10/0、B 11/0/1、C 9/3/0**——替换此前"A 2/12、B 12/12、C 9/12"成功率口径；3 项新回归测试 + 2 项旧测试更新三态预期，31/31 通过 | M4-03/B 输出列入人工核验待办（评分依据=阶段1记忆原文，见 evaluation/report.md §2） |
| 方法分类表"评测对象"列超出页面 | 成立（列宽合计 15.3cm 溢出版心，第 6 页行宽 73-74 字符 vs 正文 61） | 列宽缩至 13.2cm、角色列截短、p 列自然换行（D-14）；未缩小字号 | review.pdf 第 6–8 页：最长行 58 字符 ≤ 正文宽 61；17 类分类值（长期任务成功率/攻击鲁棒性/更新正确性/验证过滤/程序性经验等）按列字符序验证全部完整呈现 | 无 |

**口径声明**：本报告与 evaluation/report.md v6、agent_report、幻灯片、讲稿中的评估数字均为三态口径；"待核验"不由 Agent 代签，不计入成功率。
