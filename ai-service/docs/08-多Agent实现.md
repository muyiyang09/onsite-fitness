# AI 微服务开发文档 · #08 评价摘要 + 证书审核 Agent 落地

> 版本：v1.0 · 2026-08-26
> **文档分类**：落地指南（Guideline） · **强制性**：建议遵循 · **用途**：用 #02~#07 全部基础设施落地第二、第三个 Agent
> 前置阅读：所有 #01~#07
> 涉及文件：`app/graphs/review_summary.py`（新增）/ `app/graphs/cert_review.py`（新增）/ `app/schemas/review_summary.py`（新增）/ `app/schemas/cert_review.py`（新增）/ `app/main.py`

---

## 0. 文档说明

### 0.1 目标

落地规划中的第二、第三个 Agent，把前 7 份文档建好的基础设施（Loop / RAG / 商业化加固 / Harness / MCP）综合应用一次：

| Agent | 编号 | 范式 | 关键能力 |
|---|---|---|---|
| 评价摘要 | #08-A | Plan-and-Execute + Reflection | 长期记忆（情景）+ RAG 召回历史评价 + 质量门控 |
| 证书审核 | #08-B | ReAct + HITL | 工具循环 + 人工介入 + Checkpointer |

### 0.2 范围与边界

| 项 | 是否改动 |
|---|---|
| 推荐教练 Agent | ❌ 不动 |
| Spring Boot 后端 | ⚠️ 加 MCP 工具 + 1 个审核端点 |
| 管理端 PC | ⚠️ 加审核界面（已存在） |
| ai-service | ✅ 新增 2 个 Graph |

---

## 1. Agent #08-A：评价摘要

### 1.1 业务场景

教练列表页 / 管理端教练详情页，需要展示"用户评价摘要"：

```
教练：李教练
评分：4.9 ⭐
最近 30 天评价（87 条）
摘要：「评价普遍称赞李教练的减脂指导专业、动作纠正到位。负面集中在
       时段调整不便（3 条），1 条投诉迟到达 30 分钟。建议优化排期系统。」
```

人工读 87 条评价不现实，让 Agent 自动批量处理 → 总结优缺点 + 标签化。

### 1.2 设计：Plan-and-Execute + Reflection

```
START
  │
  ▼
┌─────────────────────┐
│ Node 1: Plan       │  LLM 规划：分几批处理？每批几条？
│ (LLM 规划分批)      │  输入：评价总数 / 用户目标
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│ Node 2: Map         │  并行处理每批评价：
│ (批量打标签 + 抽要点)│  - 情感分类（正向/负向/中性）
│ ToolNode 循环       │  - 抽关键词（专业/迟到/动作纠正）
│                     │  - 抽场景（减脂/产后/拉伸）
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│ Node 3: Reduce      │  LLM 聚合：跨批结果合并
│ (LLM 汇总 + 标签)   │  - 优缺点聚合
│                     │  - 标签频次统计
└─────────────────────┘
  │
  ▼
┌─────────────────────┐
│ Node 4: Reflection  │  LLM 自评摘要质量
│ (质量门控)          │  - 含数据支撑？覆盖正负面？
└─────────────────────┘
  │ branch:
  │   self_refine → 回 Node 3 重写
  │   done → END
  ▼
 END
```

### 1.3 长期记忆接入（情景记忆）

每次评价摘要完成，把"用户评价 + 教练 ID + 摘要"写入向量库，作为情景记忆。下次同一教练有新评价时，召回历史摘要做对比：

```python
# app/graphs/review_summary.py

from app.mcp.client import call_tool as mcp_call
from app.clients.vectorstore import upsert_reviews  # 复用 #04 向量库

REVIEW_SUMMARY_STATE = TypedDict("ReviewSummaryState", total=False, ...)


async def plan_batches(state) -> dict:
    """Node 1：根据评价总数规划分批策略。"""
    coach_id = state["coach_id"]
    total = await mcp_call("count_reviews", {"coach_id": coach_id})

    # 分批策略：每批 20 条
    batch_size = 20
    batches = [{"offset": i, "limit": batch_size}
               for i in range(0, total, batch_size)]
    return {"batches": batches, "total": total}


async def process_batch(batch: dict, coach_id: int) -> dict:
    """Map 阶段：处理一批评价，抽标签 + 情感 + 要点。"""
    reviews = await mcp_call("fetch_reviews", {
        "coach_id": coach_id,
        "offset": batch["offset"], "limit": batch["limit"],
    })

    # 用 LLM 批量抽标签
    prompt = load_prompt("review_batch_extract")
    text = await achat([
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(reviews, ensure_ascii=False)},
    ])
    return json.loads(text)  # {sentiment_counts, keywords, scenarios, highlights}


async def map_batches(state) -> dict:
    """Node 2：并行处理所有批。"""
    batches = state["batches"]
    coach_id = state["coach_id"]
    # 并行调度
    results = await asyncio.gather(*[
        process_batch(b, coach_id) for b in batches
    ])
    return {"batch_results": results}


async def reduce_summary(state) -> dict:
    """Node 3：聚合所有批，生成最终摘要。"""
    batch_results = state["batch_results"]
    prompt = load_prompt("review_reduce_summary")
    text = await achat([
        {"role": "system", "content": prompt},
        {"role": "user", "content": json.dumps(batch_results, ensure_ascii=False)},
    ])
    summary = json.loads(text)
    return {"summary": summary, "reason_feedback": None, "branch": "to_reflection"}


async def reflect_quality(state) -> dict:
    """Node 4：质量门控。"""
    summary = state["summary"]
    retry = state.get("reason_retry_count", 0)

    # 规则门控：长度 / 含正负面 / 含数据
    ok = _check_summary_quality(summary)
    if not ok and retry < 2:
        return {"reason_retry_count": retry + 1,
                "reason_feedback": "摘要缺少负面评价或数据支撑",
                "branch": "self_refine"}
    return {"branch": "done"}


# Graph 编译
_builder = StateGraph(REVIEW_SUMMARY_STATE)
_builder.add_node("plan", plan_batches)
_builder.add_node("map", map_batches)
_builder.add_node("reduce", reduce_summary)
_builder.add_node("reflect", reflect_quality)
_builder.add_edge(START, "plan")
_builder.add_edge("plan", "map")
_builder.add_edge("map", "reduce")
_builder.add_conditional_edges("reduce",
    ConditionalRouter("branch", {"to_reflection": "reflect", "self_refine": "reduce"},
                       default="reflect").route)
_builder.add_conditional_edges("reflect",
    ConditionalRouter("branch", {"self_refine": "reduce", "done": END},
                       default=END).route)
REVIEW_SUMMARY_GRAPH = _builder.compile(checkpointer=RedisSaver(...))
```

### 1.4 HTTP 端点

```python
@app.post("/v1/ai/review-summary", tags=["AI"])
async def review_summary(payload: ReviewSummaryIn, request: Request):
    state_out = await REVIEW_SUMMARY_GRAPH.ainvoke(
        {
            "coach_id": payload.coach_id,
            "top_n": payload.top_n or 30,
        },
        config={"configurable": {"thread_id": f"review-{payload.coach_id}"}},
    )
    return ReviewSummaryResult.model_validate(state_out["summary"])


# 写入长期记忆（情景记忆）
@app.post("/v1/ai/review-summary/commit", tags=["AI"])
async def commit_summary(payload: CommitIn):
    """摘要完成后异步写入向量库，作为下次召回的历史。"""
    await upsert_reviews(
        [
            {
                "id": f"review_summary_{payload.coach_id}_{date}",
                "text": payload.summary_text,
                "metadata": {"coach_id": payload.coach_id, "type": "summary"},
            }
        ]
    )
    return {"ok": True}
```

---

## 2. Agent #08-B：证书审核

### 2.1 业务场景

教练入驻时上传证书（国职 / 国际认证 / 急救证），管理端审核：

```
教练：李教练
证书：[国职私教证 - 编号 GZ2024xxxx]
审核流程：
  1. OCR 识别证书文字
  2. 抽取关键字段（证书类型 / 编号 / 持有人 / 有效期）
  3. 比对国职库（调用国家体育总局查询接口，模拟）
  4. 风险标记（编号格式异常 / 有效期已过 / 与持有人不符）
  5. Agent 给出建议（通过 / 拒绝 / 人工复核）
  6. 管理员最终确认（HITL）
```

### 2.2 设计：ReAct + HITL

```
START
  │
  ▼
┌─────────────────────────────┐
│ Node 1: ocr                │  LLM/Tool 调用 OCR 工具
│ ToolNode: ocr_certificate  │  抽取证书文字
└─────────────────────────────┘
  │
  ▼
┌─────────────────────────────┐
│ Node 2: extract_fields      │  LLM 抽取关键字段
│ (LLM 结构化输出)             │  → CertificateFields
└─────────────────────────────┘
  │
  ▼
┌─────────────────────────────┐
│ Node 3: verify (ReAct Loop) │  LLM 自主决定调哪些工具：
│                             │   - verify_national_cert（国职库）
│ ToolNode 循环               │   - verify_expiry（有效期）
│ should_continue             │   - check_name_match（姓名匹配）
│                             │  循环直到 LLM 不再要工具
└─────────────────────────────┘
  │
  ▼
┌─────────────────────────────┐
│ Node 4: risk_assess         │  LLM 综合评估，给风险等级
│ (LLM 风险评估)              │  - low / medium / high
└─────────────────────────────┘
  │
  ▼
┌─────────────────────────────┐
│ Node 5: hitl_checkpoint     │  interrupt 暂停
│ (HITL interrupt)            │  等管理员最终决定
└─────────────────────────────┘
  │ branch:
  │   approved → END
  │   rejected → END
  │   more_info → 回 Node 3
  ▼
 END
```

### 2.3 ReAct 实现（核心难点）

```python
# app/graphs/cert_review.py
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, HumanMessage


# 定义工具（通过 MCP）
async def verify_national_cert(args):
    return await mcp_call("verify_national_cert", args, server="java")


async def verify_expiry(args):
    return await mcp_call("verify_expiry", args, server="python")


async def check_name_match(args):
    return await mcp_call("check_name_match", args, server="python")


TOOLS = [verify_national_cert, verify_expiry, check_name_match]
tool_node = ToolNode(TOOLS)


async def react_agent(state) -> dict:
    """ReAct Agent：让 LLM 自主决定调什么工具、调几次。"""
    messages = state["messages"]
    # 调 LLM，让其决定调工具还是给最终答案
    response = await achat_with_tools(
        messages=messages,
        tools=[t.schema for t in TOOLS],
        model=settings.llm_model,
    )
    # 如果 LLM 要求调工具 → 走 ToolNode
    # 如果 LLM 给最终答案 → 走下一步
    if response.tool_calls:
        return {"messages": [response], "branch": "to_tools"}
    return {"messages": [response], "branch": "to_risk"}


def should_continue(state) -> str:
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "to_tools"
    return "to_risk"


# Graph 编译
_builder = StateGraph(CertReviewState)
_builder.add_node("ocr", ocr_node)
_builder.add_node("extract_fields", extract_fields_node)
_builder.add_node("react_agent", react_agent)
_builder.add_node("tools", tool_node)
_builder.add_node("risk_assess", risk_assess_node)
_builder.add_node("hitl", hitl_checkpoint)

_builder.add_edge(START, "ocr")
_builder.add_edge("ocr", "extract_fields")
_builder.add_edge("extract_fields", "react_agent")
_builder.add_conditional_edges(
    "react_agent", should_continue, {"to_tools": "tools", "to_risk": "risk_assess"}
)
_builder.add_edge("tools", "react_agent")  # 工具结果回到 ReAct Agent
_builder.add_edge("risk_assess", "hitl")
_builder.add_conditional_edges(
    "hitl",
    ConditionalRouter(
        "branch", {"approved": END, "rejected": END, "more_info": "react_agent"}, default=END
    ).route,
)

CERT_REVIEW_GRAPH = _builder.compile(checkpointer=RedisSaver(...))
```

### 2.4 HITL 实现

```python
from langgraph.types import interrupt, Command


async def hitl_checkpoint(state) -> dict:
    """证书审核 HITL：暂停等管理员决定。"""
    fields = state["fields"]
    risk = state["risk_level"]
    verification_results = state["verification_results"]

    # interrupt 暂停 Graph，state 持久化到 Redis
    decision = interrupt(
        {
            "prompt": f"证书审核人工确认（风险等级：{risk}）",
            "fields": fields,
            "verification_results": verification_results,
            "risk_level": risk,
            "suggestion": state.get("suggestion"),
        }
    )

    # 管理员通过 /resume API 提交决定
    if decision.get("action") == "approve":
        return {"branch": "approved", "final_decision": "approved"}
    elif decision.get("action") == "reject":
        return {"branch": "rejected", "final_decision": "rejected"}
    else:  # more_info
        return {"branch": "more_info", "follow_up_query": decision.get("query")}


@app.post("/v1/ai/cert-review/{thread_id}/resume", tags=["AI"])
async def resume_cert_review(thread_id: str, decision: dict):
    """管理员人工确认。"""
    state_out = await CERT_REVIEW_GRAPH.ainvoke(
        Command(resume=decision),
        config={"configurable": {"thread_id": thread_id}},
    )
    return CertReviewResult.model_validate(state_out)
```

### 2.5 OCR 工具

```python
# 通过 MCP 暴露
@app.call_tool()
async def ocr_certificate(args: dict) -> list[TextContent]:
    """OCR 识别证书图片。"""
    image_url = args["image_url"]
    # 调 PaddleOCR / 云 OCR API
    text = await paddle_ocr(image_url)
    return [TextContent(type="text", text=text)]
```

---

## 3. 多 Agent 协作（Supervisor 模式）

### 3.1 总体架构

3 个 Agent 落地后，引入 Supervisor 统一调度：

```
            ┌──────────────────────────┐
            │  Supervisor Agent       │
            │  (路由 + Handoff)        │
            └──────────┬───────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼               ▼
   ┌─────────┐  ┌──────────┐  ┌──────────┐
   │recommend│  │  review  │  │   cert   │
   │  coach  │  │  summary │  │  review  │
   └─────────┘  └──────────┘  └──────────┘
```

### 3.2 Supervisor 实现

```python
# app/graphs/supervisor.py（新增）
"""Supervisor Agent：根据用户意图路由到子 Agent。"""

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command

SUPERVISOR_PROMPT = """你是体育外卖平台的 AI 调度员。
根据用户 query 决定路由到哪个 Agent：
- "推荐教练" / "找教练" / "产后恢复" 等 → recommend_coach
- "评价摘要" / "评价总结" / "教练评价怎么样" → review_summary
- "审核证书" / "证书验证" / "教练资质" → cert_review

输出 JSON: {"agent": "recommend_coach" | "review_summary" | "cert_review",
            "args": {...}}
"""


async def supervisor(state) -> dict:
    text = await achat(
        [
            {"role": "system", "content": SUPERVISOR_PROMPT},
            {"role": "user", "content": state["user_query"]},
        ]
    )
    decision = json.loads(text)
    return {"route": decision["agent"], "args": decision["args"]}


def route_to_agent(state) -> str:
    return state["route"]


_builder = StateGraph(SupervisorState)
_builder.add_node("supervisor", supervisor)
_builder.add_node("recommend_coach", recommend_agent_node)
_builder.add_node("review_summary", review_summary_agent_node)
_builder.add_node("cert_review", cert_review_agent_node)
_builder.add_edge(START, "supervisor")
_builder.add_conditional_edges(
    "supervisor",
    route_to_agent,
    {
        "recommend_coach": "recommend_coach",
        "review_summary": "review_summary",
        "cert_review": "cert_review",
    },
)
_builder.add_edge("recommend_coach", END)
_builder.add_edge("review_summary", END)
_builder.add_edge("cert_review", END)
SUPERVISOR_GRAPH = _builder.compile(checkpointer=RedisSaver(...))
```

### 3.3 HTTP 端点（统一入口）

```python
@app.post("/v1/ai/chat", tags=["AI"])
async def chat(payload: ChatIn, request: Request):
    """统一 AI 入口：Supervisor 路由到具体子 Agent。"""
    thread_id = payload.thread_id or f"chat-{uuid.uuid4()}"
    state_out = await SUPERVISOR_GRAPH.ainvoke(
        {
            "user_query": payload.query,
            "user_id": request.headers.get("x-user-id"),
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    return {"result": state_out.get("result"), "thread_id": thread_id}
```

---

## 4. 配置项

```python
# app/config.py 新增
review_summary_enabled: bool = Field(default=True)
cert_review_enabled: bool = Field(default=True)
supervisor_enabled: bool = Field(default=False, description="统一入口开关，默认关")
ocr_provider: str = Field(default="paddle", description="paddle / aliyun / tencent")
```

---

## 5. 落地步骤

| 步骤 | 文件 | 改动 |
|---|---|---|
| 1 | `app/schemas/review_summary.py` | 新建 schema |
| 2 | `app/schemas/cert_review.py` | 新建 schema |
| 3 | `app/graphs/review_summary.py` | 4 节点 Graph |
| 4 | `app/graphs/cert_review.py` | 5 节点 Graph + ReAct + HITL |
| 5 | `app/graphs/supervisor.py` | Supervisor 路由 |
| 6 | `app/mcp/server.py` | 加 ocr_certificate / verify_national_cert / count_reviews / fetch_reviews 工具 |
| 7 | `app/prompts/review_*.yaml` | 抽 prompt |
| 8 | `sky-take-out/.../mcp/...` | Java 端加 verify 工具 |
| 9 | `app/main.py` | 加 3 个端点 |
| 10 | `admin-web/src/views/...` | 管理端加审核界面（已存在，加 resume 调用） |

---

## 6. 验收标准

### 6.1 评价摘要 Agent

- 100 条评价 → 摘要 ≤ 200 字
- 含正负面 + 数据支撑（"3 条投诉"等具体数字）
- 触发 refine 时有日志
- 性能：100 条评价 < 30s（含分批 LLM 调用）

### 6.2 证书审核 Agent

- OCR 抽字段准确率 ≥ 90%
- ReAct 至少调 2 个工具（verify_national_cert + verify_expiry）
- HITL interrupt 后 /resume 能恢复
- 管理员 approve / reject 都能正确结束

### 6.3 Supervisor

- 三种意图路由准确率 ≥ 95%
- 路由后子 Agent 输出与直接调子 Agent 一致

---

## 7. 学习要点小结

1. **不同业务选不同范式**：摘要用 Plan-Execute，证书用 ReAct，没有银弹
2. **Plan-and-Execute 的 Map-Reduce 模式**：长任务必备，先规划再并行执行再聚合
3. **ReAct 用 LangGraph 的 ToolNode + should_continue**：标准模式，可观测
4. **HITL 必须 interrupt + Checkpointer**：暂停即持久化，可跨进程恢复
5. **Supervisor 模式让多 Agent 协作**：单一入口，路由分发
6. **每个 Agent 独立 thread_id**：状态隔离，避免互相污染
7. **长期记忆跨 Agent 共享**：评价摘要写入向量库，下次推荐时召回
