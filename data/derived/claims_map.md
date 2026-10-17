# 关键论断映射表（v2，审查后重建）

正文核心论断 → 支撑文献 → 原文定位与摘录 → 适用条件。全部映射自`data/evidence.jsonl` 有效证据（7 条错配证据已废止剔除）。

| # | 论断（正文位置） | 文献 | 原文定位 | 摘录（截断） | 适用条件 |
|---|---|---|---|---|---|
| 1 | 图结构记忆 token F1 0.417 低于扁平向量基线 0.468（配对 Δ=-0.050）（摘要发现1 / 结论RQ2 / 挑战 / 幻灯片7） | W0034 | pdf:p1 Abstract | On LongMemEval, the graph does not out- perform a flat vector baseline at a matched candid | LongMemEval 基准；单一小提取模型；候选生成预算=5 个检索根；500 问题配对 bootstrap |
| 2 | 选择性遗忘一次移除 9.8% 节点与 9.5% 存储字节，token F1 +0.001（CI 含 0），judged （摘要发现2 / 结论RQ3 / 幻灯片7） | W0034 | pdf:p1 Abstract | Applied once to a persistent 27,021-node graph, it removes 9.8% of nodes and 9.5% of store | persistent 27,021-node graph；一次剪枝；LongMemEval；加权得分=recency/访 |
| 3 | REALM 再巩固在 LoCoMo 75.97%（比最强基线 +7.17pp）、LongMemEval 65.11%（结论RQ3 / 更新可靠性节） | W0012 | pdf:p1 Abstract | REALM achieves an average accuracy of 75.97% on LoCoMo and 65.11% on LongMemEval, outperfo | LoCoMo 和 LongMemEval 基准；REALM 框架。 |
| 4 | HiGMem 将平均检索轮数从 A-Mem 的 99.84 降至 8.09（LoCoMo10）（结论RQ2） | W0030 | pdf:p4 Table 2 | Compared with A-Mem, HiGMem
retrieves an order of magnitude fewer turns on average (8.09 v | LoCoMo10 benchmark；K 为最终证据集中的轮数；Precision@K 与 Recall@K 均在问题级 |
| 5 | Memory Worth 估计 10,000 回合后与真实效用秩相关 ρ=0.89±0.02（结论RQ3） | W0199 | pdf:p2 Abstract | after
10,000 episodes, the Spearman rank-correlation
between Memory Worth and true utiliti | 控制的合成环境，真实效用已知；20 个独立种子。 |
| 6 | LoCoMo 基准规模约 16K tokens / 588.2 turns / 27.2 sessions（MSC 的 （评测节 / 结论RQ5） | W0005 | pdf:p2 Table 1 | Table 1: Statistics of L O C O M O compared to existing dialog datasets. The average lengt | L O C O M O 数据集：gpt-3.5-turbo 生成 + 人工验证编辑 |
| 7 | LoCoMo 94% 评估问题仅需 ≤2 个此前会话（LongMemEval 85%）——偏浅层检索（评测节 / 结论RQ5 / 幻灯片8） | W0171 | pdf:p2 §1 | In LoCoMo (Maharana et al., 2024), 94% of the evaluation questions require grounding evide | LoCoMo 和 LongMemEval 的评估问题集；Memora 论文作者的分析。 |
| 8 | 依赖任务成功率 0.00→0.55–1.00；嵌入检索更新场景 0.30–0.95；代理仅 55% 时间对正确检索值行动（评测节 / 结论RQ5 / 幻灯片7） | W0031 | pdf:p1 Abstract | Across 23,440 scored episodes ($42.57), a two-generation pilot on gpt-4.1-mini and a
prere | gpt-4.1-mini 两代 pilot + GPT-4.1 / Claude Haiku 4.5 三模型 × 三种子 |
| 9 | 幻觉检测率沿 4 阶段流水线 72.0%→50.9% 单调下降；边界门控使生存率 58.4%→16.2%（更新可靠性节 / 结论RQ4） | W0688 | pdf:p1 §Abstract | We
formalize this as the hallucination snowball effect,
a first-order Markov process over  | 4-agent LangGraph pipeline (Researcher→Analyst→Writer→Review |
| 10 | 来源感知记忆 LongMemEval 95.60%（+0.73）、LoCoMo 93.60%（+1.10）；成本差约 3（更新可靠性节 / 结论RQ4） | W0010 | pdf:p1 Abstract | On two public benchmarks the system sets a new state of the art: 95.60% on LongMemEval
and | LongMemEval 与 LoCoMo 两个公共长期对话记忆基准 |
| 11 | MemPoison 绕过选择性记忆机制，攻击成功率最高 0.95（结论RQ4） | W0319 | pdf:p1 §1 Introduction | Evaluations across different agent domains
and memory mechanisms show MemPoison achieves a | 需结合 §5 的评估设置；此处未说明具体数据集、记忆机制类别或触发条件 |
| 12 | 记忆防御的良性代价：核心准确率 -4.4 点，33.6% 合法记忆被误隔离（结论RQ4 / 幻灯片7） | W0312 | pdf:p1 Abstract | The reranker is different: it lowers core accuracy by 4.4 points (95% CI [-9.0,0.05], boot | 完全良性 LoCoMo 对话流量；与未防御基线同一内存后端、检索配置和冻结判断器；五次对话、每组三次重复 |
| 13 | Mem0 图记忆整体得分仅比基础版高约 2%（LoCoMo LLM-as-a-Judge 相对 +26%）（脉络节 / 结论RQ2） | W0682 | pdf:p1 Abstract | Notably, Mem0 achieves 26% relative improvements in the LLM-as-a-Judge metric over OpenAI, | LOCOMO benchmark; LLM-as-a-Judge metric; GPT-4o-mini as infe |
| 14 | Synapse 扩散激活 LoCoMo 加权 F1 40.5 > Zep 39.7 > AriGraph 33.7（结论RQ2） | W0099 | pdf:p5 Table 1 | S YNAPSE establishes a
new state-of-the-art with a weighted average F1
of 40.5 (calculated | LoCoMo benchmark；GPT-4o-mini；排除对抗类别计算加权 F1 |
| 15 | MemoryBank 以艾宾浩斯遗忘曲线设计记忆强度衰减更新（结论（基础机制段）） | W0003 | pdf:p1 Abstract | To mimic anthropomorphic behaviors and selectively preserve memory, MemoryBank incorporate | MemoryBank 框架，适用于配备该机制的长时交互场景。 |
| 16 | Reflexion 语言化自反在 HumanEval 达 91% pass@1（结论（基础机制段）） | W0004 | pdf:p1 Abstract | Reflexion achieves a
91% pass@1 accuracy on the HumanEval coding benchmark, surpassing the | HumanEval, pass@1, GPT-4 backbone |
| 17 | 记忆规范化：情感一致性 +0.050（CI [0.013,0.086]）多重比较校正后不显著——作者定性为探索性（结论RQ3） | W0077 | pdf:p1 Abstract | We find a significant uncorrected improvement
in cross-model emotional consistency for ful | n=176 合成记忆对象，三个下游模型家族，配对准随机测试，六项比较的多重校正 |
| 18 | HaluMem：现有系统倾向在抽取与更新阶段产生并累积幻觉，向问答传播（结论RQ5） | W0261 | pdf:p1 Abstract | Existing evaluations of memory hallucinations are primarily end-to-end
question answering, | — |
| 19 | 检索可采纳性：Top-20 anchor recall 0.432→0.533（元数据参照），相似度评测降 98.3%（更新可靠性节） | W0690 | pdf:p1 Abstract | Top-20 anchor recall increases from
0.432 to 0.533, 80% recall feasibility from 0.237 to 0 | RHELM和MemOps两个公开长期记忆基准的冻结排名，共3,767个查询；top-20设置；所有发布锚点位于可信查询命 |
| 20 | Memora/Mem-Gallery/MemBench 补齐遗忘、多模态、层级维度（ACL 2025/2026）（评测节） | W0171 | pdf:p1 Table 1 | Memora introduces substantially
higher consolidation and mutation requirements across
week | Memora Weekly/Monthly/Quarterly 设置；对比基准：PerLTQA、MemDaily、LOC |

映射成功 20/20。