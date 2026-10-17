# 核心阅读池（拟选 40 篇）

按用户策略构建（docs/decisions.md D-3）：每篇回答三问（解决什么问题 /
承担什么作用 / 提供什么不同）；分层为参考结构，每篇计一个主要角色。
状态为拟选；正文审读（阅读卡）后才最终定稿 35–45 篇。

## L1-基础系统（8 篇）

| work | 题名（截断） | 年份 | 发表 | 角色 | RQ | 阅读 |
|---|---|---|---|---|---|---|
| W0001 | Generative Agents: Interactive Simulacra of Hu | 2023 | ACM Symposium on User In | 奠基范式 | RQ1,RQ2 | 已读(证据2条) |
| W0002 | MemGPT: Towards LLMs as Operating Systems | 2023 | arXiv (Cornell Universit | 虚拟上下文管理 | RQ1,RQ2 | 已读(证据7条) |
| W0003 | MemoryBank: Enhancing Large Language Models wi | 2024 | Proceedings of the AAAI  | 遗忘引入 | RQ3 | 已读(证据4条) |
| W0004 | Reflexion: language agents with verbal reinfor | 2023 | neural information proce | 语言化经验 | RQ2,RQ1 | 已读(证据3条) |
| W0680 | RET-LLM: Towards a General Read-Write Memory f | 2023 | arXiv (Cornell Universit | 读写式记忆 | RQ2,RQ3 | 已读(证据5条) |
| W0618 | ExpeL: LLM Agents Are Experiential Learners | 2024 | Proceedings of the AAAI  | 经验池 | RQ2 | 已读(证据2条) |
| W0681 | A-Mem: Agentic Memory for LLM Agents | 2025 | neural information proce | 动态组织 | RQ2,RQ3 | 已读(证据4条) |
| W0682 | Mem0: Building Production-Ready AI Agents with | 2025 | Frontiers in artificial  | 生产级记忆操作 | RQ2,RQ3,RQ5 | 已读(证据1条) |

- **W0001 奠基范式**：记忆流+新近度/重要度/相关度三因子检索+反思生成高层记忆；后续几乎所有智能体记忆工作引用此范式。作用：组织与检索层的起点。差异：首次把'记忆流'作为智能体基础设施。
- **W0002 虚拟上下文管理**：把上下文窗口当内存、外部存储当磁盘的 OS 隐喻，self-editing 记忆。作用：上下文工程路线代表。差异：以分页/中断机制解决容量，而非检索质量。
- **W0003 遗忘引入**：Ebbinghaus 遗忘曲线做记忆强度衰减+每日更新。作用：遗忘机制的早期代表（AAAI 2024）。差异：首个把认知遗忘曲线用于 LLM 助理记忆。
- **W0004 语言化经验**：失败后生成语言化自我反思存入情景记忆供后续尝试。作用：经验记忆代表。边界：任务级重试记忆，非助理跨会话记忆——须在正文明确区分。
- **W0680 读写式记忆**：DB 管理员隐喻：非参数记忆先检索后改写。作用：可写外部记忆的早期结构化方案。差异：显式读写操作而非追加式日志。
- **W0618 经验池**：跨任务积累成功轨迹并提炼 insights（AAAI 2024）。作用：程序性经验记忆。差异：从轨迹到规则的抽象层。
- **W0681 动态组织**：Zettelkasten 式笔记：新记忆触发邻接链接与记忆演化。作用：动态组织代表。差异：记忆自组织更新，区别于固定 schema。
- **W0682 生产级记忆操作**：ADD/UPDATE/DELETE/NOOP 四操作的记忆管理管线+评估。作用：工程化更新路线。差异：把更新建模为显式操作决策。

## L2-组织检索（7 篇）

| work | 题名（截断） | 年份 | 发表 | 角色 | RQ | 阅读 |
|---|---|---|---|---|---|---|
| W0684 | Zep: A Temporal Knowledge Graph Architecture f | 2025 | arXiv (Cornell Universit | 时间知识图谱 | RQ2,RQ3 | 已读(证据4条) |
| W0028 | Mem++: Non-Destructive Memory for Long-Term Or | 2026 | arXiv (Cornell Universit | 非破坏性组织 | RQ2,RQ3 | 已读(证据4条) |
| W0099 | Synapse: Empowering LLM Agents with Episodic-S | 2026 | arXiv | 情景-语义分层 | RQ1,RQ2 | 已读(证据6条) |
| W0030 | HiGMem: A Hierarchical and LLM-Guided Memory S | 2026 | arXiv (Cornell Universit | 分层图记忆 | RQ2 | 已读(证据2条) |
| W0107 | RecMem: Recurrence-based Memory Consolidation  | 2026 | arXiv (Cornell Universit | 递归巩固 | RQ2,RQ3 | 已读(证据3条) |
| W0222 | SodaMem: Evidence-Grounded Temporal Graph Memo | 2026 | arXiv (Cornell Universit | 证据锚定时间图 | RQ2,RQ4 | 已读(证据4条) |
| W0105 | MIRIX: Multi-Agent Memory System for LLM-Based | 2025 | arXiv (Cornell Universit | 多类型记忆系统 | RQ1,RQ2 | 已读(证据4条) |

- **W0684 时间知识图谱**：对话事件实时构建带时间有效期的实体关系图。作用：时间感知组织。差异：图结构+时间元数据，区别于向量库。
- **W0028 非破坏性组织**：写入不破坏原始记录，读取时按查询物化视图。作用：解决'保留原始 vs 结构化'权衡。差异：读时选择范式。
- **W0099 情景-语义分层**：情景记忆(trail)与语义记忆分层。作用：记忆类型学实现。差异：显式区分两类记忆及其转换。
- **W0030 分层图记忆**：LLM 引导的分层图组织。作用：分层表示代表。差异：层间抽象与 LLM 判断结合。
- **W0107 递归巩固**：递归巩固替代每条交互调用 LLM。作用：效率维度。差异：解决 eager 固化的 token 成本问题。
- **W0222 证据锚定时间图**：证据锚定的时间图记忆。作用：组织与可追溯结合。差异：记忆条目绑定证据来源。
- **W0105 多类型记忆系统**：情景/语义/程序性等多类型记忆的多智能体管理系统（2025）。作用：记忆类型学系统实现。差异：六类记忆显式分型与并行 worker 架构，区别于单一记忆流。

## L3-更新遗忘（7 篇）

| work | 题名（截断） | 年份 | 发表 | 角色 | RQ | 阅读 |
|---|---|---|---|---|---|---|
| W0034 | Selective Forgetting: A Graph-Based Memory Fra | 2026 | arXiv (Cornell Universit | 图记忆选择性遗忘 | RQ3,RQ5 | 已读(证据4条) |
| W0199 | When to Forget: A Memory Governance Primitive | 2026 | arXiv (Cornell Universit | 遗忘治理原语 | RQ3,RQ5 | 已读(证据4条) |
| W0180 | What Should an Agent Forget? Separating What I | 2026 | arXiv (Cornell Universit | 存储/使用分离 | RQ3 | 已读(证据3条) |
| W0011 | Preference-Aware Memory Update for Long-Term L | 2026 | arXiv | 偏好演变更新 | RQ3 | 已读(证据3条) |
| W0178 | Forget to Improve: On-Device LLM-Agent Continu | 2026 | arXiv (Cornell Universit | 预算策展遗忘 | RQ3 | 已读(证据2条) |
| W0012 | Retrieval-Driven Memory Reconsolidation for Lo | 2026 | arXiv (Cornell Universit | 检索驱动再巩固 | RQ3,RQ1 | 已读(证据4条) |
| W0077 | Memory Canonicalization: A Framework and Bench | 2026 | arXiv (Cornell Universit | 版本规范化 | RQ3,RQ5 | 已读(证据2条) |

- **W0034 图记忆选择性遗忘**：图记忆上的一次性剪枝：27,021 节点图移除 9.8% 节点/9.5% 字节而 token F1 基本不变。作用：遗忘的实证效果。差异：图粒度遗忘及成本-效果测量。
- **W0199 遗忘治理原语**：记忆价值(MW)指标+遗忘决策原语；过时记忆 MW 0.17 vs 专家记忆 0.77。作用：何时遗忘的可操作判据。差异：治理视角而非机制视角。
- **W0180 存储/使用分离**：区分'存了什么'与'检索时用什么'。作用：遗忘的作用域澄清。差异：遗忘决策从写入移到使用点。
- **W0011 偏好演变更新**：用户偏好变化的记忆更新。作用：冲突信息的一类真实场景。差异：偏好漂移 vs 事实失效的区分。
- **W0178 预算策展遗忘**：设备端预算约束下的持续学习与遗忘。作用：资源约束维度。差异：遗忘作为性能手段。
- **W0012 检索驱动再巩固**：检索时触发记忆再巩固（认知科学机制）。作用：更新的认知理论路径。差异：再巩固 vs 重写。
- **W0077 版本规范化**：记忆条目版本混乱的规范化框架+基准。作用：更新一致性。差异：把'同一事实多版本'显式定义为研究对象。

## L4-评测（7 篇）

| work | 题名（截断） | 年份 | 发表 | 角色 | RQ | 阅读 |
|---|---|---|---|---|---|---|
| W0005 | Evaluating Very Long-Term Conversational Memor | 2024 | Annual Meeting of the As | 超长期对话QA | RQ5 | 已读(证据3条) |
| W0006 | LongMemEval: Benchmarking Chat Assistants on L | 2024 | arXiv (Cornell Universit | 五能力维度 | RQ5,RQ3 | 已读(证据6条) |
| W0171 | From Recall to Forgetting: Benchmarking Long-T | 2026 | arXiv (Cornell Universit | 召回vs遗忘 | RQ5,RQ3 | 已读(证据3条) |
| W0379 | Mem-Gallery: Benchmarking Multimodal Long-Term | 2026 | arXiv (Cornell Universit | 多模态评测 | RQ5,RQ1 | 已读(证据2条) |
| W0434 | MemBuilder: Reinforcing LLMs for Long-Term Mem | 2026 | arXiv (Cornell Universit | 记忆构建评测 | RQ5,RQ2 | 已读(证据2条) |
| W0691 | MemBench: Towards More Comprehensive Evaluatio | 2025 | arXiv | 综合记忆评测 | RQ5 | 已读(证据2条) |
| W0031 | When Does Memory Help? A Cost-Aware Evaluation | 2026 | arXiv (Cornell Universit | 成本感知评测 | RQ5,RQ2 | 已读(证据3条) |

- **W0005 超长期对话QA**：LoCoMo 基准（ACL 2024，被引85）：超长对话+多类型 QA。作用：评测层锚点。差异：会话跨度(35轮/最高26K token)远超此前基准。
- **W0006 五能力维度**：ICLR 2025：信息抽取/多会话推理/时间推理/知识更新/拒绝回答五维度。作用：能力分类学。差异：知识更新与拒绝首次入基准。
- **W0171 召回vs遗忘**：ACL Findings 2026：同时评测记忆与遗忘。作用：补齐评测缺口。差异：遗忘正确性作为一等指标。
- **W0379 多模态评测**：ACL 2026：多模态长期对话记忆基准。作用：模态边界。差异：多模态记忆组织与检索。
- **W0434 记忆构建评测**：ACL 2026：RL 构建长期记忆+属性评测。作用：构建质量评测。差异：评'怎么写'而非'怎么用'。
- **W0691 综合记忆评测**：LLM 智能体记忆的综合评测基准（2025）。作用：评测维度系统化。差异：QA+开放域对话双通道，覆盖检索与推理。
- **W0031 成本感知评测**：记忆收益与成本的联合评测。作用：公平比较框架。差异：成本纳入指标而非只看准确率。

## L5-非恶意可靠性（5 篇）

| work | 题名（截断） | 年份 | 发表 | 角色 | RQ | 阅读 |
|---|---|---|---|---|---|---|
| W0688 | The Hallucination Snowball: Modeling Error Pro | 2026 | arXiv (Cornell Universit | 错误传播 | RQ4 | 已读(证据3条) |
| W0690 | The Right Memory in the Wrong Context: Verifyi | 2026 | arXiv (Cornell Universit | 检索可采纳性 | RQ4,RQ3 | 已读(证据4条) |
| W0207 | What to Keep, What to Forget: A Rate--Distorti | 2026 | arXiv (Cornell Universit | 压缩信息损失 | RQ4,RQ3 | 已读(证据4条) |
| W0261 | HaluMem: Evaluating Hallucinations in Memory S | 2025 | arXiv (Cornell Universit | 记忆幻觉评测 | RQ4,RQ5 | 已读(证据4条) |
| W0010 | Agent Zero Memory: Provenance-Aware Long-Term  | 2026 | arXiv (Cornell Universit | 来源感知 | RQ4 | 已读(证据4条) |

- **W0688 错误传播**：错误经状态转移传播的建模（雪球效应）。作用：可靠性核心问题——错误如何进入并放大。差异：传播动力学视角。
- **W0690 检索可采纳性**：记忆内容正确但上下文不适配（admissibility）的验证。作用：错误使用维度。差异：'检索对了但用错'这一被忽视的失效模式。
- **W0207 压缩信息损失**：率失真理论视角看记忆压缩的信息损失。作用：摘要失真的理论刻画。差异：给出压缩-保真的形式框架。
- **W0261 记忆幻觉评测**：记忆系统幻觉的专项评测基准（2025）。作用：错误写入/错误检索的直接测量。差异：把'记忆导致的幻觉'与'模型幻觉'分离量化。
- **W0010 来源感知**：来源感知的长期记忆。作用：来源丢失防线。差异：provenance 作为记忆一等公民。

## L6-安全投毒（3 篇）

| work | 题名（截断） | 年份 | 发表 | 角色 | RQ | 阅读 |
|---|---|---|---|---|---|---|
| W0076 | Memory Poisoning Attack and Defense on Memory  | 2026 | arXiv (Cornell Universit | 攻防综合 | RQ4 | 已读(证据2条) |
| W0319 | MemPoison: Bypassing Selective Memory Mechanis | 2026 | arXiv (Cornell Universit | 选择性绕过后门 | RQ4 | 已读(证据3条) |
| W0312 | The Price of Safety: Benign-Case Utility and T | 2026 | arXiv (Cornell Universit | 防御成本 | RQ4,RQ2 | 已读(证据2条) |

- **W0076 攻防综合**：记忆投毒攻击面+防御模块（信任过滤+复合门槛）。作用：安全分支代表。差异：攻防对照的完整实证。
- **W0319 选择性绕过后门**：绕过选择性记忆机制植入后门。作用：攻击与防御机制共同演化例证。差异：对记忆筛选机制本身的攻击。
- **W0312 防御成本**：记忆防护的良性场景效用损失与 token 开销。作用：安全的代价维度。差异：防御本身的负外部性。

## L7-综述与边界（3 篇）

| work | 题名（截断） | 年份 | 发表 | 角色 | RQ | 阅读 |
|---|---|---|---|---|---|---|
| W0140 | Cognitive Architectures for Language Agents | 2023 | arXiv (Cornell Universit | 概念框架 | RQ1 | 已读(证据5条) |
| W0039 | A Survey on Long-Term Memory Security in LLM A | 2026 | arXiv (Cornell Universit | 安全综述 | RQ4,RQ1 | 已读(证据11条) |
| W0056 | A Survey on the Memory Mechanism of Large Lang | 2025 | ACM Transactions on Info | 记忆机制综述 | RQ1,RQ2 | 待正文审读 |

- **W0140 概念框架**：CoALA：LLM 智能体认知架构统一框架（决策/记忆/学习模块）。作用：概念地图与术语对齐。差异：把记忆放进完整认知架构而非孤立组件。
- **W0039 安全综述**：6 阶段记忆生命周期安全框架。作用：可靠性的系统化图谱。差异：攻击/防御按生命周期阶段组织。
- **W0056 记忆机制综述**：LLM 智能体记忆机制综述（2025，被引143）。作用：机制分类图谱与本文分类的对照基准。差异：本综述聚焦更新与可靠性纵深，与其广度互补。
