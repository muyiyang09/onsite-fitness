# Langfuse 可观测性：痛点分析 + 面试题集

> 版本：v1.0 · 2026-09-02
> 用途：① Langfuse 接入的决策依据（为什么接 / 什么时候不接）；② 面试速记话术
> 配套：[06-Harness工程与评估 §3.4](./06-Harness工程与评估.md)（目标设计）、[12-面试速记话术](./12-面试速记话术.md)（背诵口径）
> 状态：✅ **代码已落地（2026-09-02）**，话术口径与代码现状一致，可放心背诵；改动清单见 §四。

---

## 0.5 30 秒极简版（面试前只背这一屏）

**定义一句话**：Langfuse = **AI 的行车记录仪**。

- 以前 LLM 答错 = 出车祸没记录仪，只能靠路边的公共监控（日志）远远猜：日志拍得到"车经过了"（节点跑了多久），拍不到"车内"（AI 看到了什么 prompt、说了什么、花了多少钱）。
- 痛点一句话：**还原不了现场**。拆开就 3 件事：① 看不到现场（prompt/输出被截断，审计只留 1000 字）；② 拼不出过程（多次 LLM 调用 + 重试的树状关系靠脑补）；③ 算不清钱（token 是按字数估的，不是真实账单）。
- 加它的理由一句话：**日志回答"快不快、挂没挂"，Langfuse 回答"AI 为什么这么答、花了多少钱"**——不是替代日志，是补一层。

**故事一口气**（回答任何"具体怎么用"的问题）：用户点踩 → 拿 request_id 搜出这趟记录 → 展开一棵树，每次调用的 prompt/输出/花费全在 → 一键加进评测集 → 改完 prompt 重跑回归。

**概念不用死记，从记录仪推**：

| 术语 | 记录仪类比 |
|---|---|
| Trace | 一次完整行程（一次请求） |
| Span | 行程中的一段路（一个图节点） |
| Generation | 行车录像本体（一次 LLM 调用，含画面+声音+油耗） |
| Score | 车主给这次行程打的分 |

被追问"为什么不用日志？"——公共监控看得到车流，拍不到车内。

---

## 0. 背诵口径（必读）

1. **现状口径（已与代码对齐）**：结构化日志 + request_id + 节点耗时 + MySQL 审计 + Prometheus 指标是**保底层**（Langfuse 关闭时唯一路径）；Langfuse 是 **LLM 语义层增强**（`LANGFUSE_ENABLED=true` + 装包后生效，未开启时全部 no-op）。面试表述："**可观测性我做了两层兜底：轻量日志层无条件可用，Langfuse 语义层按需开启，观测组件自身故障 fail-open 不连坐业务**"——这句比"我接了 Langfuse"更能体现设计能力。
2. **没有编造的收益数据**：别说"排查时间从 2 小时降到 5 分钟"这种没测过的数字。对比说定性事实：**"从 grep 日志拼时间戳，变成 UI 上点开一棵 trace 树"**。
3. 话术遵循「**结论 → 3 点展开 → 1 句反思**」，每段 150-250 字，60-90 秒口述。
4. [09-Agent面试题集](./09-Agent面试题集.md) / [12-面试速记话术](./12-面试速记话术.md) 中「无 Langfuse / 结构化日志替代」的旧表述以本文档为准更新口径。

---

## 一、用户痛点：把一条坏 case 排查一遍，就知道缺什么

场景：用户投诉"我产后恢复的需求，它给我推了个健美教练"。拿现有工具排查一次：

### 痛点 1：看得到耗时，看不到内容

[trace.py:38](../app/clients/trace.py) 只打一条 `node=extract_intent latency_ms=xxx`；[audit.py](../app/core/audit.py) 虽然存了 prompt/response，但**截断到 1000 字符**，而且结构化输出的 prompt 里拼着完整 JSON Schema + 检索上下文，1000 字根本不够。
**后果**：无法回答"LLM 当时到底看到了什么、吐了什么"，也就无法回答"为什么推了 A 不推 B"。

### 痛点 2：平铺日志拼不出调用树

`request_id` 串起来的是**平铺的行**。一次教练推荐 = 意图抽取 1 次 LLM + 理由生成 1 次 LLM（格式漂移时带修正提示最多重试 2 次）；评价摘要的 Map-Reduce 是**一次请求 N 次 LLM**。这些调用之间的嵌套、重试关系，只能 grep 出来对着时间戳脑补。

### 痛点 3：token 成本是估算值，不是真实账单

审计表里的 input/output_tokens 来自 [token_budget.py 的 `estimate_tokens()`](../app/middleware/token_budget.py)：`CJK 字符 1 字 ≈ 1 token` 的**启发式估算**，不是 API 返回的真实 `usage`。按用户/按功能的成本归因要自己写 SQL 聚 MySQL，聚合口径还全是估算值。

### 痛点 4：重试的中间态一闪而过

[llm.py 的 `achat_structured_with_retry`](../app/clients/llm.py) 在输出 JSON 漂移时会把错误喂回去重试——但每次失败的原始输出只在 `logger.warning` 里出现一行，重试成功后无从对比"第一次错哪了、修正提示有没有用"。

### 痛点 5：badcase → 离线 Eval 的回流是断的

[`/feedback`](../app/api/v1/recommend.py) 只往 `ai_eval_online` 表写 `request_id + action`。**想把这个 case 加进离线评测集，当时的完整输入（检索上下文、打分明细）根本没存**，拼不回来。线上反馈和离线评测之间缺一条"一键回流"的通路。

### 痛点 6：质量回归不可见

[metrics.py](../app/core/metrics.py) 全是次数/延迟计数器，**没有一个质量维度**。意图抽取某天突然抽错城市，唯一发现途径是用户投诉。质量没有变成"可看、可比、可告警"的数据。

> **一句话总结**：现有体系回答得了"服务挂没挂、慢不慢"（系统层），回答不了"这一次 LLM 为什么这么答"（语义层）——[06 §3.4](./06-Harness工程与评估.md) 早就把 Langfuse 列为目标设计，本文档给出接入理由与话术。

---

## 二、为什么要加 Langfuse：补的是「LLM 语义层」

### 2.1 三层可观测性，各管一层

| 层 | 回答的问题 | 现状 | Langfuse 接入后 |
|---|---|---|---|
| **系统层** Prometheus | 服务挂没挂？QPS/延迟/错误率？ | ✅ [metrics.py](../app/core/metrics.py) + `/metrics` | 不变（Langfuse 不替代它） |
| **文本层** JSON 日志 | 谁在什么时候干了什么？ | ✅ [logging.py](../app/core/logging.py) request_id 贯穿 | 不变（日志照打，排系统故障用） |
| **语义层** LLM Trace | 这一次 LLM 看到了什么 prompt？吐了什么？花了多少 token/钱？质量如何？ | ❌ 缺失，只有截断审计 | ✅ trace 树 + generation 明细 + usage/cost + score |

### 2.2 收益 → 痛点一一对应

1. **痛点 1/2** → 每次 LLM 调用自动记为 `generation`（完整 prompt/completion/真实 usage），节点 `span` 嵌套成树，UI 上直接展开回放。
2. **痛点 3** → 记录 API 返回的真实 `usage`，按模型单价自动算 cost，按 `user_id`/`session_id`/自定义 tag 聚合。
3. **痛点 4** → 重试的每一次都是独立 generation，历史全留。
4. **痛点 5** → trace 一键加入 Langfuse **dataset**，线上线下用同一套数据模型跑实验。
5. **痛点 6** → `score` API 把人工评分/LLM-as-judge 结果挂回 trace，质量变成可聚合数据。

### 2.3 代价与诚实边界（什么时候不值得接）

- **重依赖**：v3 自部署需要 PostgreSQL + ClickHouse + MinIO（v2 只要 PostgreSQL 但已停止新功能开发）；国内访问 Langfuse Cloud 网络慢——这正是 [trace.py](../app/clients/trace.py) 当初"先不上 Langfuse"的原因，**这个取舍今天依然成立**，所以接入必须遵循与审计同款的设计纪律：
  - **旁路上报**：异步批量，绝不阻断主流程；
  - **fail-open**：Langfuse 不可达只丢 trace 不报错，不让保护组件变成故障源；
  - **可采样**：低峰全采、高峰按采样率，停机前 flush 防丢尾。
- **不值得接的场景**：单体单 Agent、调用量小、没有质量追溯需求——JSON 日志就够。我们的触发条件是：三个 Agent × 多节点 × 多次 LLM 调用 × 要做成本归因与 Eval 闭环，日志层已经顶不住了。

---

## 三、面试题 + 口语化回答 + 知识点解释

> 格式：🎯 考察点 → 🗣️ 口语化回答（背诵）→ 📚 知识点解释（理解，防追问）。
> 顺序由浅入深：Q1-Q3 必背 🟢，Q4-Q7 建议背 🟡，Q8-Q9 加分项 🔴。

---

### Q1（🟢）你的项目可观测性是怎么做的？为什么还要加 Langfuse？

🎯 考察点：体系化思维 + 知道自己工具链的边界，不堆砌名词。

🗣️ **口语化回答**：

> 我的可观测性分**三层**。**系统层**用 Prometheus 抓 `/metrics`，看 QPS、延迟、错误率；**文本层**是结构化 JSON 日志，`request_id` 用 contextvars 贯穿全链路，节点耗时也打在日志里；**合规层**每次 LLM 调用旁路写 MySQL 审计表，记 prompt、response 和 token。
>
> 但上线排查坏 case 时我发现了**三层都覆盖不了的盲区**：一次推荐里有多次 LLM 调用，还带格式漂移重试，日志只能看到"哪个节点跑了多久"，**看不到 LLM 当时的完整 prompt 和输出**——审计表还截断到 1000 字符。也就是说系统能回答"慢不慢"，回答不了"**为什么这么答**"。
>
> 所以我加了 Langfuse 做**第四层：LLM 语义层**——每次 LLM 调用自动记 generation，节点记成 span 拼成树，真实 usage 和成本自动算，还能一键把坏 case 加进评测集。**反思**：观测要分层选工具，而不是一把锤子敲所有钉子。

📚 **知识点解释**：

- **可观测性三支柱**（metrics / logs / traces）来自传统微服务，但 LLM 应用多出一个维度：**模型内部不可见，输入输出就是全部真相**。传统 trace（如 SkyWalking）记录的是"函数调用链"，而 LLM 语义层 trace 记录的是"prompt → completion → usage → 质量评分"，后者是 AI 特有需求。
- **Langfuse 的定位**：开源 LLM 工程平台，核心四件事——Tracing（trace/span/generation）、Prompt 管理（版本化 + 服务端拉取）、Evaluation（人工/模型评分 + 数据集）、成本分析。竞品：LangSmith（商业闭源、绑 LangChain 生态）、Phoenix（Arize，偏 eval）。
- **为什么不用审计表替代**：审计表是**合规件**（保留记录），不是**调查工具**（无 UI 回放、无嵌套结构、截断存储）。两者目的不同，共存而不是替代。

---

### Q2（🟢）Langfuse、Prometheus、ELK 三层怎么分工？只用日志行不行？

🎯 考察点：能不能讲清楚每层的不可替代性，而不是"都上"。

🗣️ **口语化回答**：

> 分工按"**回答什么问题**"划：Prometheus 回答**聚合面**——错误率有没有涨、P99 延迟多少，代价是只有数字没有明细；ELK/JSON 日志回答**明细面**——单条请求发生了什么，代价是平铺无结构、聚合检索成本高；Langfuse 回答**LLM 语义面**——一次请求的 prompt/输出/token/评分，天然是**树结构**。
>
> 只用日志行不行？**小项目行**，我之前就是纯日志方案。但两个硬伤：一是**基数问题**——我想算"每个用户今天花了多少钱"，日志要把全量明细拉出来再聚合，而 trace 系统写入时就带维度索引；二是**结构问题**——多 Agent 链路的调用树，日志要用时间戳脑补，trace 系统里 span 父子关系是显式的。
>
> **反思**：分层不是为了简历好看，是每层都在替下一层挡掉它不擅长的问题。

📚 **知识点解释**：

- **基数（cardinality）**：Prometheus 处理高基数标签（如 user_id）会内存爆炸，所以"按用户算钱"不能放指标层——这正是审计表/trace 的活。理解基数边界是监控选型的基本功。
- **trace 的树结构 vs 日志的流结构**：Langfuse 里 trace（一次请求）→ span（一个节点/阶段）→ generation（一次 LLM 调用）是**显式父子关系**；日志要靠 request_id + 时间戳**事后重建**，LLM 多调用场景下重建成本极高。
- **保留策略差异**：日志/trace 量大，通常 7-30 天滚动；审计表按合规要求长留。Langfuse 自部署可配数据保留期。

---

### Q3（🟢）讲讲 Langfuse 的数据模型：Trace、Span、Generation、Score？

🎯 考察点：是否真的用过，而非只知道名字。

🗣️ **口语化回答**：

> 四个核心概念。**Trace** 对应一次完整请求，我按 `request_id` 建，这样从我的日志能跳到 trace、从 trace 能跳回审计表。**Observation** 是 trace 下的节点，分三种：**Span** 是一段有起止的处理过程，我给 LangGraph 的每个节点开一个 span；**Generation** 是一次 LLM 调用，Langfuse 对它有特殊处理——记模型名、完整 prompt/completion、真实 token usage，还能自动算成本；**Event** 是瞬时事件，无耗时。
>
> 嵌套关系是：trace → span → generation，父子的**时间线天然对齐**，展开一棵树就能看到"意图抽取节点里那次 LLM 调用长什么样"。最后是 **Score**：把人工评分或 LLM-as-judge 的结果挂到 trace 或单个 generation 上，质量就能聚合对比了。
>
> **反思**：trace 树的价值在于"**回放一次请求**"，这也是我选 request_id 当 trace 根的原因。

📚 **知识点解释**：

- **v2 → v3 的一个关键变化**：v2 是 SDK 自带的数据模型；v3 改为**基于 OpenTelemetry** 构建——trace/span 直接对应 OTel 的 span 概念，generation 是在 span 上附加 LLM 语义属性。好处是能接任何 OTel 生态（OTLP 导入），坏处是自部署要带 ClickHouse（存 span 数据）。
- **Generation 的专用字段**：`model`、`input`/`output`（支持 messages 结构）、`usage`（prompt/completion/total tokens，支持按 token 明细缓存计费）、`model_parameters`（temperature 等）。**成本表**按 `model + usage` 自动换算。
- **Score 类型**：`numeric` / `categorical` / `boolean`，来源可以是 API 上报（人工/算法）或 Langfuse 内置 LLM-as-judge 评估器（基于 eval template），支持在线（写入时）与离线（dataset 实验）两类挂载。

---

### Q4（🟡）LangGraph 的链路你是怎么埋点的？说说集成方案。

🎯 考察点：工程落地细节——装饰器统一注入、异步上下文传播。

🗣️ **口语化回答**：

> 我做了**两层埋点**。**入口层**：FastAPI 的四个 AI 端点函数套一个 span 装饰器，以 `request_id` 建根 trace，并打上 `user_id`、session、模型名等元数据——从日志跳 trace 就靠这个 id。**节点层**：所有图节点本来就统一经过 `trace_node` 耗时装饰器，我在这一个地方把 span 埋进去，**业务节点代码零改动**——十几个节点全部自动有 trace。
>
> **LLM 调用层**：项目用 LiteLLM 统一路由，所以不用逐个调用点埋——给 LiteLLM 挂 `success_callback`/`failure_callback`，每次 completion 自动上报 generation，拿到的是 API 返回的**真实 usage** 而不是我原来估算的 token。
>
> 两个工程细节：节点是异步的，span 的父子关系靠 **OTel context 在 asyncio task 间继承**（asyncio.Task 创建时会复制 contextvars），所以嵌套关系不用手动传；停机时要 **flush**，不然尾巴上的 trace 会丢。
>
> **反思**：埋点要收口到基础设施层（装饰器/客户端封装），散在业务代码里必漏。

📚 **知识点解释**：

- **为什么要统一装饰器收口**：项目里 14 个节点全部 `@trace_node(...)`（见 [recommend_coach.py](../app/graphs/recommend_coach.py) 等三个图），单点改造即全量生效——这正是当初把超时兜底、耗时统计都收口在 `trace_node` 的红利。散装埋点的典型事故：新节点忘埋、异常路径漏 `end_span`。
- **异步上下文传播**：OTel/Langfuse v3 的当前 span 存在 **contextvar** 里；`asyncio.create_task` 会**复制创建时刻的 context**，所以父 span 未关闭期间派生的子任务能继承父 span。注意坑：如果父协程先返回（span 关闭）而后台任务还在跑，子 span 会脱挂到错误父节点——长后台任务要显式传 context。
- **LiteLLM 集成**：`litellm.success_callback = ["langfuse"]`（读 `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST` 环境变量），completion/acompletion 的每次调用自动生成 generation，含 usage/cost。与 LangChain 生态的 `CallbackHandler` 是两套等价方案，选哪个看项目走哪个客户端。
- **flush 语义**：SDK 上报是**内存队列 + 后台批量发送**；进程退出若不 flush，队列里未发送的 trace 丢失。所以在 FastAPI lifespan 的 shutdown 段调用 flush（与现有"优雅停机关连接池"同一位置）。

---

### Q5（🟢）trace 上报会不会拖慢主流程？怎么控制接入本身的成本？

🎯 考察点：可观测组件的可靠性设计——很多人栽在"监控把自己拖挂"。

🗣️ **口语化回答**：

> 三条纪律，和我项目里限流/熔断的 **fail-open** 原则一脉相承。**第一，异步旁路**：上报走 SDK 内部的内存队列 + 后台批量发送，主流程只是往队列塞一条，微秒级；**第二，fail-open**：Langfuse 不可达、上报超时，只丢 trace 打告警日志，绝不阻塞请求也绝不抛错——宁可少观测，不能挂服务；**第三，可采样**：低峰全采，高峰按采样率（环境变量可配），坏 case 用 request_id 强制采样。
>
> 还有一个容易被忽略的点：**停机 flush**。优雅停机时先 flush 再关连接池，不然队列尾巴上的 trace 全丢。以及成本上，Langfuse 存的是文本，量大了存储不小，所以要配**数据保留期**，审计要长留的进 MySQL 审计表，职责分开。
>
> **反思**：可观测组件的 SLA 必须低于业务组件——它是配角，挂了不能连坐。

📚 **知识点解释**：

- **批量上报（batching）**：SDK 攒一批（如每 500ms 或每 N 条）一次网络发送，摊薄开销；对齐 OTel **BatchSpanProcessor** 的行为。反面是 **SimpleSpanProcessor**（同步逐条发送），只适合调试。
- **采样策略**：**头部采样**（head sampling，进来就掷骰子，实现简单但可能丢关键样本）vs **尾部采样**（tail sampling，攒一批后按规则挑——错误请求、慢请求 100% 保留，正常请求抽 1%，需要收集端支持）。LLM 场景还有"**指定 trace 强制保留**"：按 traceId 白名单采样，用于还原用户投诉的具体请求。
- **降级设计的项目呼应**：本项目缓存/限流/Token 预算全部 fail-open（Redis 挂了放行而非全拦，见 [config.py 注释](../app/config.py)）——Langfuse 上报遵循同一纪律，面试里把这两处串起来讲，能体现设计一致性。

---

### Q6（🟡）线上发现一个坏 case，你怎么让它回流到离线 Eval？说说闭环。

🎯 考察点：线上线下评估闭环——Agent 工程化的分水岭问题。

🗣️ **口语化回答**：

> 我的闭环分四步。**第一步捕获**：用户在小程序上点踩，`/feedback` 接口把 `action=dislike + request_id` 写进 `ai_eval_online` 表——这是线上 ground truth 的源头。**第二步还原**：拿 request_id 去 Langfuse 查那棵 trace，当时的完整输入输出都在——用户原话、抽取的意图、检索召回的候选、每次 LLM 调用的 prompt 和输出，**不用再靠日志脑补**。**第三步入集**：把这个 case 一键加进 Langfuse dataset，或者导出成我离线 eval runner 的 JSON 用例。**第四步回归**：改 prompt 或换模型后，拿 dataset 重跑离线评测，看这个 case 修了、别的 case 没退化，才算真修好。
>
> 之前断在哪？审计表截断 1000 字符，检索上下文根本没存，**想入集都拼不回来**——这就是我接 Langfuse 的直接动因之一。
>
> **反思**：没有回流闭环，线上反馈就只是一条数据库记录，永远变不成回归用例。

📚 **知识点解释**：

- **Langfuse Dataset 机制**：dataset（集合）→ dataset item（单条输入+期望输出+元数据）→ run（跑一轮实验）；每次 run 记录模型输出 + 评分，**版本间可 diff**。等价于离线 eval 的"用例库 + 回归报告"。
- **连续评估闭环（continuous eval loop）**：线上信号（点踩、转人工、投诉）→ 归因（trace 回放）→ 入集（dataset）→ 实验（prompt/模型/参数变更）→ 发布。面试中画出这个环，比罗列"我用了 Langfuse"高一个档次。
- **项目呼应**：离线 eval 基建在 [app/eval/](../app/eval/)（runner/judge/metrics，19/20 通过率）；接了 Langfuse 后，`judge.py` 的 LLM-as-judge 结果也可以通过 score API 挂回 trace，实现"离线评分线上可查"。

---

### Q7（🟡）token 成本怎么归因和治理？

🎯 考察点：从"能跑"到"能算账"——商业化视角。

🗣️ **口语化回答**：

> 分**记账**和**治理**两半。**记账**：接入前我的审计表 token 是 `estimate_tokens` 估的——CJK 一字一 token 的启发式，**不是真实账单**；接入后 Langfuse 记 API 返回的真实 usage，按模型单价自动算成本，我打上 `user_id`、`session_id`、功能 tag，按用户/按功能聚合就是一条 SQL 的事。**治理**三招：一是**缓存**，相同 query 24 小时命中直接返回、不花一分钱 token，配合 singleflight 防击穿；二是**预算硬控**，token_budget 中间件做了单请求 / 单用户日 / 全局日三级上限；三是**模型分层**，便宜模型做路由和意图抽取，贵模型只做理由生成。
>
> **反思**：成本治理的前提是"**账记得准**"——用估算值做治理决策，等于拿体温计量血压。

📚 **知识点解释**：

- **usage 的来源**：OpenAI 兼容 API 的 `response.usage`（prompt_tokens / completion_tokens）；注意 LiteLLM 会做**多供应商归一化**，Langfuse 从回调里拿到的已是标准结构。流式场景 usage 在最后一个 chunk（需开 `stream_options.include_usage`）。
- **成本计算**：Langfuse 维护模型单价表（支持自定义价格覆盖），`cost = Σ(token_type × unit_price)`；缓存命中（prompt caching）可按"缓存读/写"不同价计算。
- **预算中间件的项目细节**：三级限额 + **fail-open**（Redis 挂了放行），见 [token_budget.py](../app/middleware/token_budget.py)；治理动作与观测数据分开存——预算计数在 Redis（实时扣减），成本分析在 Langfuse（事后归因）。

---

### Q8（🔴）Langfuse 你打算用云还是自部署？v2 和 v3 有什么区别？

🎯 考察点：部署选型 + 对版本演进的了解（加分项，答不好也不扣分）。

🗣️ **口语化回答**：

> 我的结论是**先用云验证、数据敏感再自部署**。云版本零运维、功能最新；但两个现实约束：国内访问网络不稳定，以及平台数据出境合规。真要自部署得认清楚 **v3 的部署成本涨了**：v2 是单体应用加一个 PostgreSQL 就能跑；v3 重构到 **OpenTelemetry + ClickHouse**，要带 ClickHouse、MinIO、PostgreSQL 好几个组件，换来了大数据量下的查询性能和 OTel 生态兼容，但小团队自部署的运维负担明显变重。
>
> 所以我的决策树是：**开发/演示用云**；生产看两条线——数据是否敏感、调用量是否大到云费用可感；中间态还有折中，比如只上报脱敏后的 trace。
>
> **反思**：自部署不是免费的，运维成本也是成本，选型要连人一起算。

📚 **知识点解释**：

- **v2 → v3 架构差异**：v2 单体（Next.js 服务 + PostgreSQL）；v3 拆为 web 服务 + worker，span 数据进 **ClickHouse**（列存，海量 trace 聚合查询快），对象存储用 S3/MinIO，接入标准 **OTLP** 端点。官方已将新特性集中在 v3，v2 停止新功能开发。
- **数据合规要点**：PII 处理（Langfuse 支持 input/output 脱敏钩子与掩码规则）、数据驻留（自部署 = 数据不出内网）、审计要求（本项目审计表已覆盖合规格，Langfuse 只承担调查职能）。
- **网络现实**：国内访问 Langfuse Cloud 延迟高且不稳，SDK 的批量上报可容忍，但 UI 查询体验差——这是国内自部署的主要动机，与 [trace.py](../app/clients/trace.py) 原注释"国内自部署成本高"对应。

---

### Q9（🔴）什么项目不值得上 Langfuse？说说你的反方向判断。

🎯 考察点：技术判断力的反面论证——会不会说"不"。

🗣️ **口语化回答**：

> 三种情况我不会上。**第一，单体单 Agent**：一次请求就一次 LLM 调用，JSON 日志加 request_id 完全够，trace 树的收益撑不起组件成本；**第二，调用量小**：一天几百次调用，grep 日志十秒钟的事，上平台是杀鸡用牛刀；**第三，团队没有消费场景**：没人天天看 trace、没人做成本归因和 Eval 回流，数据存了就是坟场。
>
> 我项目之前**没接**就是这个判断——所以先把结构化日志、审计表、Prometheus 三件套做扎实，它们覆盖了 80% 的需求。现在触发条件到了：三个 Agent、多节点、多 LLM 调用、要做成本归因和 Eval 闭环，才升级方案。
>
> **反思**：选型的成熟标志不是"什么都上"，而是**知道什么时候上、什么时候不上**。

📚 **知识点解释**：

- **观测成熟度阶梯**：print → 结构化日志 → 指标 → LLM trace 平台。跳级（第一天就上全家桶）的常见后果：工具维护成本吃掉开发时间，而数据没人消费。
- **"数据坟场"问题**：观测平台的价值 = 数据量 × 消费频次；只写不读的系统是纯成本。判断标准是"过去一周它帮过谁解决什么问题"。
- **与项目叙事的一致性**：本项目多个文档（[06](./06-Harness工程与评估.md)、[12](./12-面试速记话术.md)）反复强调"轻量降级优先、目标设计明确"——本问答正是这一工程哲学在可观测性上的应用，面试串讲时能形成统一的个人风格标签。

---

## 四、落地清单（✅ 已完成，2026-09-02）

> litellm 1.55.3 兼容矩阵验证结论：其内置 langfuse callback **只兼容 v2 SDK**（依赖 `langfuse.model.CreateTrace/CreateGeneration`，v3 已移除）。因此 **LLM 层不走 litellm callback**，改在 llm.py 收口点用 v3 `@observe` 记 generation——litellm 版本不动，还顺带保证 usage 归因的模型名口径与 `LLM_MODEL` 一致。

实际改动（业务代码零改动，全部收口在基础设施层）：

| 文件 | 改动 |
|---|---|
| [pyproject.toml](../pyproject.toml) | 可选 extra `langfuse = ["langfuse>=3.0,<4"]`（v3 SDK，未装包时全链路 no-op） |
| [config.py](../app/config.py) | `LANGFUSE_ENABLED / PUBLIC_KEY / SECRET_KEY / HOST / SAMPLE_RATE` 五项配置，默认关 |
| [langfuse_client.py](../app/clients/langfuse_client.py) **（新增）** | 唯一封装点：`init_langfuse`（注入 env + 取全局 client）/ `flush_langfuse` / `observe_span` 装饰器工厂 / `update_trace_meta` / `update_current_generation`；四层 no-op 降级 |
| [trace.py](../app/clients/trace.py) | `trace_node` 内接 `observe_span("node.xxx")`——兑现原文件预留的钩子注释 |
| [llm.py](../app/clients/llm.py) | `chat / achat` 套 generation，`_record_generation` 上报 litellm 响应的**真实 usage** + request_id |
| 四个 AI 端点（recommend / review_summary / cert_review(含 resume) / chat） | root trace + `update_trace_meta`（user_id / session_id=thread_id / request_id / tags） |
| [main.py](../app/main.py) | lifespan 启动 `init_langfuse()`，停机 `flush_langfuse()` |
| [.env.example](../.env.example) | LANGFUSE 配置块 + 启用步骤注释 |

设计纪律（与审计/限流同款）：**旁路异步上报、fail-open（Langfuse 不可达只丢 trace）、可采样（LANGFUSE_SAMPLE_RATE）、停机 flush 防丢尾**。

验证：
- `pytest` 关态 67 passed（默认 LANGFUSE_ENABLED=false，未装包场景由 no-op 装饰器覆盖）；
- 开态冒烟 [scripts/smoke_langfuse.py](../scripts/smoke_langfuse.py)：假 key + 不可达 host 下，`app.main` 导入（FastAPI 接受装饰后端点签名）→ 三层 span 树（api → node → generation）→ 真实 usage 上报 → flush 不阻断停机，全部通过；
- 开态回归：`LANGFUSE_ENABLED=true` 跑全量 pytest 67 passed。

[06 §3.4](./06-Harness工程与评估.md) 已同步为落地版；§3.4.3（Prompt 抽到 Langfuse）仍为目标设计，当前 prompt 走本地 YAML 版本化。
