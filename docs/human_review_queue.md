# 人工核验队列（真人任务）

生成时间：2026-10-17T09:44:34+00:00。本清单由核验包生成器从真实数据产生；
所有条目状态为**待核验**。核验结果由成员写入 `data/reviews.jsonl`，
格式见 `docs/protocol.md` §7；不要在本文件直接打勾——以 reviews.jsonl 为准。

## 1. 文献核验（核心阅读池：40 项）

每项需要：① 身份核验（题名/作者/年份/venue/DOI 与正式记录一致）；
② 版本核验（预印本 vs 正式版，主引用版本正确，证据页码绑定读取版本）；
③ 抽查 ≥1 条使用证据（excerpt 与所指标记页是否逐字一致、interpretation 无过度引申）。

| 优先级 | work | 层 | 题名（截断） | 年份 | 证据数 | 核验要点 |
|---|---|---|---|---|---|---|
| P0 | W0010 | L5-非恶意可靠性 | Agent Zero Memory: Provenance-Aware Long-Term Memory for | 2026 | 4 | 单版本 |
| P0 | W0011 | L3-更新遗忘 | Preference-Aware Memory Update for Long-Term LLM Agents | 2026 | 3 | 单版本 |
| P0 | W0012 | L3-更新遗忘 | Retrieval-Driven Memory Reconsolidation for Long-Term LL | 2026 | 4 | 单版本 |
| P0 | W0034 | L3-更新遗忘 | Selective Forgetting: A Graph-Based Memory Framework for | 2026 | 4 | 单版本 |
| P0 | W0076 | L6-安全投毒 | Memory Poisoning Attack and Defense on Memory Based LLM- | 2026 | 2 | 单版本 |
| P0 | W0077 | L3-更新遗忘 | Memory Canonicalization: A Framework and Benchmark for C | 2026 | 2 | 单版本 |
| P0 | W0178 | L3-更新遗忘 | Forget to Improve: On-Device LLM-Agent Continual Learnin | 2026 | 2 | 单版本 |
| P0 | W0180 | L3-更新遗忘 | What Should an Agent Forget? Separating What Is Stored f | 2026 | 3 | 单版本 |
| P0 | W0199 | L3-更新遗忘 | When to Forget: A Memory Governance Primitive | 2026 | 4 | 单版本 |
| P0 | W0207 | L5-非恶意可靠性 | What to Keep, What to Forget: A Rate--Distortion View of | 2026 | 4 | 单版本 |
| P0 | W0261 | L5-非恶意可靠性 | HaluMem: Evaluating Hallucinations in Memory Systems of  | 2025 | 4 | 单版本 |
| P0 | W0312 | L6-安全投毒 | The Price of Safety: Benign-Case Utility and Token Overh | 2026 | 2 | 单版本 |
| P0 | W0319 | L6-安全投毒 | MemPoison: Bypassing Selective Memory Mechanisms to Plan | 2026 | 3 | 单版本 |
| P0 | W0688 | L5-非恶意可靠性 | The Hallucination Snowball: Modeling Error Propagation a | 2026 | 3 | 单版本 |
| P0 | W0690 | L5-非恶意可靠性 | The Right Memory in the Wrong Context: Verifying Retriev | 2026 | 4 | 单版本 |
| P1 | W0001 | L1-基础系统 | Generative Agents: Interactive Simulacra of Human Behavi | 2023 | 2 | 单版本 |
| P1 | W0002 | L1-基础系统 | MemGPT: Towards LLMs as Operating Systems | 2023 | 7 | 单版本 |
| P1 | W0003 | L1-基础系统 | MemoryBank: Enhancing Large Language Models with Long-Te | 2024 | 4 | 单版本；arXiv:2307.08909 |
| P1 | W0004 | L1-基础系统 | Reflexion: language agents with verbal reinforcement lea | 2023 | 3 | 单版本；arXiv:2305.10250 |
| P1 | W0005 | L4-评测 | Evaluating Very Long-Term Conversational Memory of LLM A | 2024 | 3 | 单版本 |
| P1 | W0006 | L4-评测 | LongMemEval: Benchmarking Chat Assistants on Long-Term I | 2024 | 6 | 单版本 |
| P1 | W0028 | L2-组织检索 | Mem++: Non-Destructive Memory for Long-Term Organization | 2026 | 4 | 单版本 |
| P1 | W0030 | L2-组织检索 | HiGMem: A Hierarchical and LLM-Guided Memory System for  | 2026 | 2 | 3 版本记录 |
| P1 | W0031 | L4-评测 | When Does Memory Help? A Cost-Aware Evaluation of Long-T | 2026 | 3 | 单版本 |
| P1 | W0099 | L2-组织检索 | Synapse: Empowering LLM Agents with Episodic-Semantic Me | 2026 | 6 | 2 版本记录 |
| P1 | W0105 | L2-组织检索 | MIRIX: Multi-Agent Memory System for LLM-Based Agents | 2025 | 4 | 单版本 |
| P1 | W0107 | L2-组织检索 | RecMem: Recurrence-based Memory Consolidation for Effici | 2026 | 3 | 3 版本记录 |
| P1 | W0171 | L4-评测 | From Recall to Forgetting: Benchmarking Long-Term Memory | 2026 | 3 | 3 版本记录 |
| P1 | W0222 | L2-组织检索 | SodaMem: Evidence-Grounded Temporal Graph Memory for LLM | 2026 | 4 | 单版本 |
| P1 | W0379 | L4-评测 | Mem-Gallery: Benchmarking Multimodal Long-Term Conversat | 2026 | 2 | 3 版本记录 |
| P1 | W0434 | L4-评测 | MemBuilder: Reinforcing LLMs for Long-Term Memory Constr | 2026 | 2 | 单版本 |
| P1 | W0618 | L1-基础系统 | ExpeL: LLM Agents Are Experiential Learners | 2024 | 2 | 单版本；arXiv:2308.10144 |
| P1 | W0680 | L1-基础系统 | RET-LLM: Towards a General Read-Write Memory for Large L | 2023 | 5 | 单版本 |
| P1 | W0681 | L1-基础系统 | A-Mem: Agentic Memory for LLM Agents | 2025 | 4 | 单版本；arXiv:2502.12110 |
| P1 | W0682 | L1-基础系统 | Mem0: Building Production-Ready AI Agents with Scalable  | 2025 | 1 | 单版本；arXiv:2504.19413 |
| P1 | W0684 | L2-组织检索 | Zep: A Temporal Knowledge Graph Architecture for Agent M | 2025 | 4 | 单版本 |
| P1 | W0691 | L4-评测 | MemBench: Towards More Comprehensive Evaluation on the M | 2025 | 2 | 单版本 |
| P2 | W0039 | L7-综述与边界 | A Survey on Long-Term Memory Security in LLM Agents: Att | 2026 | 11 | 单版本 |
| P2 | W0056 | L7-综述与边界 | A Survey on the Memory Mechanism of Large Language Model | 2025 | 0 | 单版本 |
| P2 | W0140 | L7-综述与边界 | Cognitive Architectures for Language Agents | 2023 | 5 | 单版本 |

## 2. 边界判定复核（模型判定，建议真人裁决）

- **W0116**（pending）：HeLa-Mem: Hebbian Learning and Associative Memory for LLM Agents — 理由：uncertain | 无摘要，标题涉及Hebbian学习与联想记忆，待正文确定是否与LLM跨会话记忆直接相关。
- **W0134**（pending）：Self-Evolving World Models for LLM Agent Planning — 理由：uncertain | 重点在世界模型的规划与演化，未见明显跨会话/跨任务外部记忆机制，正文进一步确认。
- **W0145**（pending）：MAGMA: A Multi-Graph based Agentic Memory Architecture for AI Agents — 理由：uncertain | 无摘要，标题涉及多图Agentic记忆架构，需正文确认是否针对LLM长期记忆。
- **W0167**（pending）：Episodic Memory Model For Embodied Conversational Agents — 理由：uncertain | 摘要提及 ECA 架构，但无法确认是否涉及基于 LLM 的跨会话外部记忆机制，还是传统符号或规则式记忆。
- **W0182**（excluded）：The mitigating effect of repeated memory reactivations on forgetting — 理由：out_of_scope | 人类记忆再激活与遗忘研究，非 LLM。
- **W0185**（excluded）：Forgetting Enhances Episodic Control With Structured Memories — 理由：out_of_scope | 人工重审：哺乳动物大脑遗忘神经科学，非 LLM 记忆系统
- **W0198**（excluded）：Optimal forgetting: Semantic compression of episodic memories — 理由：out_of_scope | 人类情景记忆语义压缩研究，非 LLM。
- **W0211**（excluded）：Online Class-incremental Continual Learning with Maximum Entropy Memor — 理由：out_of_scope | 持续学习中的记忆更新，非 LLM 跨会话记忆机制。
- **W0219**（excluded）：MemoReason: Evaluating the Effect of Parametric Memory on Contextual R — 理由：out_of_scope | 研究参数化记忆对上下文推理的影响，不涉及跨会话外部记忆机制。
- **W0221**（pending）：PRISM: Probing Reasoning, Instruction, and Source Memory in LLM Halluc — 理由：uncertain | 无摘要，标题涉及LLM幻觉中的源记忆探测，需正文判断是否涉及外部记忆系统。
- **W0225**（pending）：Enhancing Group Recommendation with Memory-Augmented Reasoning in LLM  — 理由：uncertain | 摘要显示将交互历史作为动态记忆建模，但能否构成清晰的长期外部记忆机制需正文确认。
- **W0234**（excluded）：SEEK: Steering LLM Reasoning for RAG via Internal Reasoning Sketches — 理由：out_of_scope | 关注RAG推理过程而非跨会话外部记忆机制。
- **W0235**（pending）：From Recognition to Understanding: Unlocking Cognitive Time Series Rea — 理由：uncertain | 关注时间序列推理与LLM的结合，与跨会话记忆边界不清。
- **W0241**（excluded）：Ideological Bias in LLMs' Economic Causal Reasoning — 理由：out_of_scope | 研究LLM经济因果推理中的意识形态偏差，与记忆机制无关。
- **W0250**（excluded）：Beyond Math: Stories as a Testbed for Memorization-Constrained Reasoni — 理由：out_of_scope | 研究LLM记忆化对推理的影响，并非跨会话外部记忆系统。
- **W0253**（excluded）：Semiotic logical hexagon theory for LLM logical reasoning — 理由：out_of_scope | 关于逻辑推理的符号学理论，与LLM外部记忆无关。
- **W0257**（excluded）：Enabling Memory Safety of C Programs using LLMs — 理由：out_of_scope | 使用LLM改进C程序内存安全，与LLM智能体跨会话记忆无关。
- **W0279**（excluded）：A Multitask, Multilingual, Multimodal Evaluation of ChatGPT on Reasoni — 理由：out_of_scope | ChatGPT多任务评测，不涉及长期记忆机制或评测。
- **W0343**（excluded）：TextSeal: A Localized LLM Watermark for Provenance & Distillation Prot — 理由：out_of_scope | LLM输出水印用于来源保护，与跨会话外部记忆无直接关联。
- **W0350**（excluded）：On the Reliability of LLM-Based Vulnerability Patching Benchmarks — 理由：out_of_scope | 关注LLM漏洞修补基准的可靠性，与智能体外记忆机制无关。
- **W0354**（excluded）：Know the Normal, Track the Attack: Context-Grounded and Stateful LLM I — 理由：out_of_scope | 系统溯源入侵检测的LLM叙事生成，非LLM智能体记忆研究。
- **W0355**（excluded）：TRACES: A Benchmark for Epistemic Reliability in Scientific Reasoning  — 理由：out_of_scope | 评测LLM科研推理的认知可靠性，不涉及跨会话外部记忆的可靠性。
- **W0357**（excluded）：Cache the Encoder Within:Compact, Reusable Memory across LLM Queries — 理由：out_of_scope | 研究编码器缓存复用以降查询成本，不涉及LLM智能体的跨会话记忆组织。
- **W0377**（excluded）：LadderEdit: Edit-Level Residual Compression for Memory-Efficient Lifel — 理由：out_of_scope | 终身编辑模型权重的LoRA压缩，属模型编辑而非外部记忆系统。
- **W0429**（pending）：RealMem: Benchmarking LLMs in Real-World Memory-Driven Interaction — 理由：uncertain | 无摘要，标题涉及真实世界记忆驱动交互基准，需正文确认是否覆盖所有RQ。
- **W0437**（pending）：Beyond Continuity: Challenges of Context Switching in Multi-Turn Dialo — 理由：uncertain | 主题是对话中上下文切换而非跨会话外部记忆，但可能涉及记忆边界问题，需正文确认。
- **W0440**（excluded）：Poker Arena: Multi-Axis Profiling of Strategic Reasoning and Memory in — 理由：out_of_scope | 扑克竞技场评测战略推理与记忆能力，非跨会话外部记忆机制。
- **W0456**（excluded）：SOMA: Efficient Multi-turn LLM Serving via Small Language Model — 理由：out_of_scope | 面向多轮对话中的上下文服务优化，属上下文压缩/效率而非跨会话外部记忆机制。
- **W0495**（excluded）：Semantic and episodic contributions of long-term memory to working mem — 理由：out_of_scope | 研究人类长时记忆对工作记忆的贡献，非 LLM 记忆系统。
- **W0496**（excluded）：Explaining short-term memory phenomena with an integrated episodic/sem — 理由：out_of_scope | 用人类长时记忆框架解释短时记忆现象，属认知科学，非 LLM。
- **W0497**（excluded）：Neurofeedback training improves episodic and semantic long-term memory — 理由：out_of_scope | 神经反馈训练改善人类长时记忆，属于临床神经科学。
- **W0500**（excluded）：Strategic use of internal and external memory in everyday life: episod — 理由：out_of_scope | 人类日常记忆策略研究，与 LLM 记忆无关。
- **W0502**（excluded）：Episodic, semantic and procedural memory in a case of amnesia at an ea — 理由：out_of_scope | 人类失忆症案例研究，与 LLM 无关。
- **W0503**（excluded）：ACCOUNTING FOR EPISODIC, SEMANTIC AND PROCEDURAL MEMORY IN THE RECOMME — 理由：out_of_scope | 认知模型中的记忆研究，非 LLM 智能体记忆机制。
- **W0504**（excluded）：The semantic-episodic distinction and the history of long-term memory  — 理由：out_of_scope | 讨论人类记忆类型学的语义-情景区分历史，非 LLM 记忆。
- **W0506**（excluded）：An Episodic-Procedural Semantic Memory Model for Continuous Topologica — 理由：out_of_scope | 传感器建图的记忆模型，与 LLM 无关。
- **W0507**（excluded）：Reviewer #1 (Public Review): Episodic long-term memory formation durin — 理由：out_of_scope | 关于慢波睡眠中人类情景记忆形成，非 LLM 记忆研究。
- **W0526**（excluded）：Understanding the planning of LLM agents: A survey — 理由：out_of_scope | 综述LLM智能体的规划能力，不聚焦记忆组织、更新或评测。
- **W0534**（excluded）：MeMAT: Multi-agent transformer with deep long-term memory, short-term  — 理由：out_of_scope | 多智能体 Transformer 记忆架构，非 LLM 外部记忆系统研究。
- **W0547**（excluded）：Four-hour delayed memory recall for stories: Theoretical and clinical  — 理由：out_of_scope | 人工重审：人类记忆心理学研究，非 LLM 智能体（无摘要、标题与 venue 均指向人类被试）
- **W0550**（excluded）：ASSOCIATIONS AND FORGETTING IN LONG-TERM MEMORY — 理由：out_of_scope | 标题涉及人类长期记忆，未使用 LLM，与 LLM 智能体记忆无关。
- **W0553**（excluded）：Acquisition, Recall, and Forgetting of Verbal Information in Long-Term — 理由：out_of_scope | 涉及不同年龄个体的言语信息长期记忆，属于认知心理学研究，非 LLM 记忆系统。
- **W0685**（excluded）：Titans: Learning to Memorize at Test Time — 理由：out_of_scope | Titans研究测试时记忆架构与长序列建模，属于模型架构层面，非跨会话外部记忆系统。
- **W0687**（excluded）：MemoRAG: Boosting Long Context Processing with Global Memory-Enhanced  — 理由：out_of_scope | MemoRAG关注长上下文处理与检索增强，记忆用于单次查询内全局上下文，非跨会话智能体外部记忆。
- **W0689**（pending）：LLM as a Broken Telephone: Iterative Generation Distorts Information — 理由：uncertain | 迭代生成信息失真，可能与跨会话记忆迭代更新相关，但摘要未明确涉及智能体记忆机制。

## 3. Claims 复核（当前 7 条）

每条需回到证据定位核对：原文是否支持该陈述及其范围；
synthesis 类需核对全部引用证据与综合理由。

- **clm-d99029c6dc** [direct] 评测：探测：验证 submit_claim 是否返回证据 id 信息。…
- **clm-81192ffe3e** [synthesis] 引言：LLM 智能体长期记忆（LTM）被定义为跨会话的、可写的持久化记忆，且不能简单被扩展上下文窗口或 RAG 所取代，其引入带来了新的安全与可靠性挑战。…
  - ev-70dca24ae3: W0039 pdf:p1 Abstract
  - ev-8d280fd434: W0039 pdf:p1 §1
  - ev-31418bd5be: W0039 pdf:p1 Abstract
  - ev-855c37bb1f: W0039 pdf:p1 §1
  - ev-b3dff3cc9c: W0039 pdf:p2 §1
  - ev-a729ac6697: W0039 pdf:p1 Abstract/Introduction
- **clm-b650cb3c21** [direct] 脉络：MemGPT 将提示 token 分为系统指令、工作上下文与 FIFO 队列三个连续区段，并通过函数调用实现自主的、自引导的记忆读写与检索，为可写持久记忆提供了早期工程范式。…
  - ev-dd0a54c1bc: W0002 pdf:p2 §2.1 Main context
  - ev-c8f2e67be5: W0002 pdf:p2 §2
  - ev-9eb724bbaf: W0002 pdf:p2 2.1 Main context
  - ev-f7acbffa63: W0002 pdf:p1 Introduction
  - ev-9744219d78: W0002 pdf:p3
  - ev-60cb65b5a9: W0002 pdf:p2 2. MemGPT
- **clm-86d86c44e5** [synthesis] 脉络：随着 LLM 成为智能体系统骨干，记忆被重新定位为跨会话持久化（而不仅是对话内上下文），并通过图索引、向量库等外部结构组织，且在图索引与扁平向量基线下任务表现无显著差异。…
  - ev-9b1e7076d5: W0034 pdf:p2 Related Work 2.1
  - ev-36450aaaa1: W0034 pdf:p2 §2.1
  - ev-e5f5747e6f: W0034 pdf:p1 Abstract
- **clm-f04f6d72e6** [synthesis] 更新可靠性：记忆生命周期可分解为 Write、Store、Retrieve、Execute 等多个阶段，各阶段（如基于访问的保留策略、信任感知过滤与排名）既是更新/遗忘的入口，也是错误信息进入记忆并影响决策的潜在…
  - ev-fadb5bf279: W0039 pdf:p2
  - ev-095eeb706d: W0039 pdf:p4 §3.2 Store
  - ev-55aa09bce2: W0076 pdf:p9 6.2 Memory Sanitization
- **clm-0cb1895f67** [synthesis] 更新可靠性：更新与遗忘通过多种机制实现：MemGPT 的队列淘汰（flush 释放上下文空间）、LongMemEval 的图节点/边删除（一次性移除 9.8% 节点与 9.5% 边）、信任分数门槛控制记忆追加，以…
  - ev-9c2ecd9622: W0002 pdf:p3 queue manager / eviction
  - ev-04383921e8: W0034 pdf:p1 Abstract
  - ev-0d1302f74c: W0076 pdf:p8 6.1.1
  - ev-b2fc6c534a: W0039 pdf:p3 Figure 1
  - ev-119bca5547: W0039 pdf:p3 Figure 1
  - ev-3eab8e5621: W0039 pdf:p3 Figure 1
- **clm-da6c12eee3** [synthesis] 评测：LongMemEval 作为综合基准评估五项核心能力（信息抽取、多会话推理、时间推理、知识更新、拒绝回答），而既有 QA 类基准忽略了多项关键记忆能力，且近期长期记忆基准（如 LoCoMo）仍以 QA…
  - ev-ebdf08e2d6: W0006 pdf:p1 Abstract
  - ev-ec40d0b95a: W0006 pdf:p2 §2 Related Work
  - ev-d2c9f16872: W0006 pdf:p3 Table 1
  - ev-8ae13d366d: W0006 pdf:p3 Table 1 + p3 正文
  - ev-94e5c2ab5b: W0006 pdf:p1 Abstract

## 4. 汇总

- 文献核验任务：40 项（P0 优先：更新与可靠性分支）
- 边界复核：45 项
- Claims 复核：7 条
- 合计约 92 个核验任务；建议三人按 P0→P1→P2 分摊，
  同一人整理的关键部分由另一成员复核（EXECUTION_PLAN §5.4）。
