# AI 微服务开发文档 · #07 MCP 工具层

> 版本：v1.0 · 2026-08-26
> **文档分类**：落地指南（Guideline） · **强制性**：建议遵循 · **用途**：用 MCP 协议抽象工具层，实现跨语言/跨 Agent 工具复用
> 前置阅读：[#02 §3 工具系统](./02-Agent工程能力地图.md) · [#04 RAG 混合检索](./04-RAG混合检索.md)
> 涉及文件：`app/mcp/`（新增）/ `app/clients/db.py` / `app/clients/bm25.py` / `app/clients/vectorstore.py` / `app/graphs/recommend_coach.py` / `app/config.py`

---

## 0. 文档说明

### 0.1 目标

把当前紧耦合的「节点函数直接 import db.py」改造为「**MCP 协议抽象的工具层**」，让工具：

1. **跨 Agent 复用**：recommend_coach / 评价摘要 / 证书审核 共享同一套工具
2. **跨语言复用**：Python Agent 可调 Spring Boot 暴露的 Java 工具
3. **可替换**：换工具实现（MySQL → ES）不改 Agent 代码
4. **可观测**：所有工具调用通过 MCP 协议统一审计

### 0.2 范围与边界

| 项 | 是否改动 |
|---|---|
| Agent 业务逻辑 | ❌ 不动 |
| 工具实现（DB 查询/BM25/向量） | ❌ 不动（包装成 MCP tool） |
| 节点调用方式 | ✅ 从直接 import 改走 MCP client |
| 新增组件 | MCP Server（Python + Java） |

---

## 1. 现状回顾

### 1.1 当前工具调用方式

```python
# app/graphs/recommend_coach.py 当前
from app.clients.db import fetch_all
from app.clients.bm25 import search as bm25_search
from app.clients.vectorstore import search as vector_search


def retrieve_and_rank(state):
    coaches = _fetch_coaches(city)  # 直接调 db.fetch_all
    bm25_results = bm25_search(query)  # 直接调
    vec_results = vector_search(query)  # 直接调
```

### 1.2 三大致命伤

| # | 问题 | 例子 |
|---|---|---|
| 1 | **紧耦合** | 节点代码与具体 client 实现（db/bm25/vectorstore）绑死，换实现要改节点 |
| 2 | **不可复用** | 评价摘要 Agent 也想查 coach，要重新写一遍调用 |
| 3 | **跨语言难** | 想调 Spring Boot 的"派单池查询"，要走 HTTP REST，不是工具语义 |

### 1.3 MCP 是什么

**MCP（Model Context Protocol）** 是 Anthropic 2024 年底推出的开放协议，标准化「LLM ↔ 工具」通信：

```
┌────────────┐     JSON-RPC      ┌──────────────┐
│  MCP Client│ ←─────────────► │  MCP Server  │
│ (LLM/Agent)│   tools/list     │ (Tool Provider)│
│            │   tools/call      │              │
└────────────┘                  └──────────────┘
```

| 概念 | 说明 |
|---|---|
| **Transport** | 通信方式：stdio（本地）/ SSE / streamable-http（远程） |
| **Tool** | 一个可调用的函数，含 name + description + JSON Schema |
| **Resource** | 可读的数据源（如配置文件） |
| **Prompt** | 可复用的 prompt 模板 |

主流支持 MCP 的客户端：Claude Desktop / Cursor / Cline / Continue.dev。

---

## 2. 设计思路

### 2.1 为什么不直接用 HTTP REST

| 方式 | 优点 | 缺点 |
|---|---|---|
| HTTP REST | 通用，已有工具 | 每个工具一个 endpoint，无统一发现机制 |
| gRPC | 高性能 | protobuf 强类型，工具变更需重新生成 |
| **MCP** | 标准协议，自带发现/调用/schema | 引入协议层 |

**关键认知**：MCP 不是替代 REST，而是把"工具调用"从"接口调用"升级为"协议语义"。LLM 通过 MCP 知道有哪些工具可用（`tools/list`），知道每个工具怎么调（JSON Schema），不用硬编码。

### 2.2 何时该上 MCP / 何时不必

| 场景 | 是否上 MCP |
|---|---|
| 单 Agent 单进程 | ❌ 直接函数调用够用 |
| **多 Agent 共享工具** | ✅ MCP 抽象 |
| **跨语言工具复用** | ✅ MCP 协议天然支持 |
| **想让外部 LLM（Claude/Cursor）调你工具** | ✅ MCP 唯一选择 |
| 工具数量 < 5 个 | ❌ 上 MCP 是过度设计 |

**本项目场景**：Phase 5 后有 3 个 Agent + 跨语言（Python ↔ Java），符合上 MCP 条件。

### 2.3 Transport 选型

| Transport | 适用 | 本项目选型 |
|---|---|---|
| **stdio** | 本地 CLI 工具、单进程内 | ✅ 开发期 |
| **SSE** | 远程、单向流 | - |
| **streamable-http** | 远程、双向、生产 | ✅ 生产期 |

### 2.4 同进程 vs 跨进程

```
方案 A：MCP Server 独立进程，Client 跨网络调用
  优点：独立部署、可被外部 LLM 调用
  缺点：网络开销

方案 B：MCP Server 同进程内嵌（in-process）
  优点：零网络开销
  缺点：仅本进程可用，无外部复用

本项目推荐：方案 A（生产） + 方案 B（开发/测试）
```

---

## 3. 落地方案

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                  ai-service (Python)                        │
│                                                             │
│   ┌──────────────────┐    ┌──────────────────────────┐    │
│   │ recommend_coach  │    │ review_summary           │    │
│   │ Agent            │    │ Agent (后续 #08)         │    │
│   └────────┬─────────┘    └──────────┬───────────────┘    │
│            │ MCP Client                │ MCP Client        │
│            ▼                           ▼                   │
│   ┌──────────────────────────────────────────────────┐     │
│   │   MCP Client 统一封装层                         │     │
│   │   - tools/list / tools/call                     │     │
│   │   - 缓存 schema / 重试 / 超时                    │     │
│   └─────────────────────┬──────────────────────────┘     │
│                         │                                  │
│            ┌────────────┴─────────────┐                  │
│            ▼                            ▼                   │
│   ┌──────────────────┐      ┌────────────────────┐       │
│   │ MCP Server       │      │ MCP Server         │       │
│   │ (Python 工具集)   │      │ (Java 工具集)      │       │
│   │ - fetch_coaches  │      │ - query_order      │       │
│   │ - bm25_search    │      │ - accept_dispatch  │       │
│   │ - vector_search  │      │ - update_status    │       │
│   │ - rerank         │      │ - query_dispatch   │       │
│   └──────────────────┘      └────────────────────┘       │
│            ▲                            ▲                   │
└────────────┼────────────────────────────┼──────────────────┘
             │ streamable-http              │ streamable-http
             │                              │
   ┌─────────┴────────┐         ┌──────────┴─────────┐
   │  Python MCP       │         │  Spring Boot       │
   │  :18001           │         │  :8080/mcp         │
   │  (本服务子进程)    │         │  (Java 后端)       │
   └──────────────────┘         └────────────────────┘
```

### 3.2 Python MCP Server

```python
# app/mcp/server.py（新增）
"""Python MCP Server：暴露教练推荐相关工具"""

from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServer
from mcp.types import Tool, TextContent
import json

app = Server("onsite-fitness-ai-tools")


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="fetch_coaches",
            description="按城市查询已审核教练列表。返回 coach_id/name/level/rating/bio 等。",
            inputSchema={
                "type": "object",
                "properties": {
                    "city_name": {"type": "string", "description": "城市名，如 '北京市'"},
                    "level_min": {"type": "integer", "description": "最低等级 1-4"},
                },
            },
        ),
        Tool(
            name="bm25_search",
            description="BM25 关键词召回教练。输入用户 query，返回 [(coach_id, score)]。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 50},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="vector_search",
            description="向量语义召回教练。输入自然语言，返回语义相关的 [(coach_id, similarity)]。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "default": 50},
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="rerank",
            description="Cross-Encoder 重排。输入 query + 候选 docs，返回精排后的 top N。",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "docs": {"type": "array", "items": {"type": "object"}},
                    "top_n": {"type": "integer", "default": 3},
                },
                "required": ["query", "docs"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "fetch_coaches":
        from app.clients.db import afetch_all

        sql = (
            "SELECT id, name, sex, level, rating, service_radius_km, city_name, bio "
            "FROM coach WHERE status = 1"
        )
        params = {}
        if arguments.get("city_name"):
            sql += " AND city_name = :city_name"
            params["city_name"] = arguments["city_name"]
        if arguments.get("level_min"):
            sql += " AND level >= :level"
            params["level"] = arguments["level_min"]
        rows = await afetch_all(sql, params)
        return [TextContent(type="text", text=json.dumps(rows, ensure_ascii=False, default=str))]

    elif name == "bm25_search":
        from app.clients.bm25 import search

        results = search(arguments["query"], arguments.get("top_k", 50))
        return [TextContent(type="text", text=json.dumps(results))]

    elif name == "vector_search":
        from app.clients.vectorstore import search as vsearch

        results = vsearch(arguments["query"], arguments.get("top_k", 50))
        return [TextContent(type="text", text=json.dumps(results))]

    elif name == "rerank":
        from app.clients.reranker import rerank as rrnk

        results = rrnk(arguments["query"], arguments["docs"], arguments.get("top_n", 3))
        return [TextContent(type="text", text=json.dumps(results, ensure_ascii=False, default=str))]

    raise ValueError(f"Unknown tool: {name}")


async def run_server():
    from mcp.server.streamable_http import StreamableHTTPServer

    server = StreamableHTTPServer(app, host="0.0.0.0", port=settings.mcp_server_port)
    await server.start_serve()
```

### 3.3 Python MCP Client（节点侧调用）

```python
# app/mcp/client.py（新增）
"""MCP Client：让 LangGraph 节点通过 MCP 调用工具，而非直接 import"""

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from app.config import settings
from functools import lru_cache
import json


@lru_cache
async def get_session() -> ClientSession:
    """惰性创建 MCP client session（同进程内连接本地 MCP Server）"""
    client_ctx = streamablehttp_client(settings.mcp_server_url)
    read, write, _ = await client_ctx.__aenter__()
    session = ClientSession(read, write)
    await session.initialize()
    return session


async def call_tool(name: str, arguments: dict) -> dict | list:
    """调用 MCP 工具。所有节点统一通过此函数调工具。"""
    session = await get_session()
    result = await session.call_tool(name, arguments)
    # MCP 返回 TextContent 列表
    text = result.content[0].text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


async def list_tools() -> list[dict]:
    """列出所有可用工具（启动时缓存 schema）"""
    session = await get_session()
    resp = await session.list_tools()
    return [
        {"name": t.name, "description": t.description, "schema": t.inputSchema} for t in resp.tools
    ]
```

### 3.4 节点改造（直接 import → MCP client）

```python
# app/graphs/recommend_coach.py 改造
# 原：from app.clients.db import fetch_all
# 原：from app.clients.bm25 import search as bm25_search
# 改：统一走 MCP client

from app.mcp.client import call_tool as mcp_call


async def retrieve_and_rank(state: RecommendState) -> dict[str, Any]:
    intent = state.get("intent") or {}
    user_query = state.get("user_query", "")

    # ---- 通过 MCP 调工具 ----
    coaches = await mcp_call(
        "fetch_coaches",
        {
            "city_name": intent.get("city_name"),
            "level_min": intent.get("level"),
        },
    )
    bm25_results = await mcp_call("bm25_search", {"query": user_query, "top_k": 50})
    vec_results = await mcp_call("vector_search", {"query": user_query, "top_k": 50})

    # ... 后续 RRF 融合 / Rerank 也通过 MCP 调 ...
    fused = _rrf_fuse(bm25_results, vec_results, top_k=30)
    reranked = await mcp_call(
        "rerank",
        {
            "query": user_query,
            "docs": [{"coach_id": cid, "text": ...} for cid, _ in fused[:30]],
            "top_n": 10,
        },
    )

    # ... 后续打分逻辑不变 ...
```

### 3.5 Spring Boot 端 MCP Server（Java）

让 Python Agent 能调 Java 工具（如下单、派单等）。

```java
// platform-backend/backend-server/.../mcp/McpServerController.java（新增）
@RestController
@RequestMapping("/mcp")
public class McpServerController {

    @PostMapping("/tools/list")
    public Map<String, Object> listTools() {
        return Map.of("tools", List.of(
            Map.of(
                "name", "query_order",
                "description", "查询订单状态",
                "inputSchema", Map.of(
                    "type", "object",
                    "properties", Map.of(
                        "order_id", Map.of("type", "integer")
                    ),
                    "required", List.of("order_id")
                )
            ),
            Map.of(
                "name", "accept_dispatch",
                "description", "教练抢单",
                "inputSchema", Map.of(...)
            ),
            Map.of(
                "name", "query_dispatch_pool",
                "description", "查询派单池",
                "inputSchema", Map.of(...)
            )
        ));
    }

    @PostMapping("/tools/call")
    public Map<String, Object> callTool(@RequestBody Map<String, Object> body) {
        String name = (String) body.get("name");
        Map<String, Object> args = (Map<String, Object>) body.get("arguments");

        switch (name) {
            case "query_order":
                Long orderId = ((Number) args.get("order_id")).longValue();
                Orders order = orderService.getById(orderId);
                return Map.of("content", List.of(Map.of(
                    "type", "text", "text", JSON.toJSONString(order)
                )));
            case "accept_dispatch":
                // ... 教练抢单逻辑
            case "query_dispatch_pool":
                // ... 派单池查询
            default:
                throw new IllegalArgumentException("Unknown tool: " + name);
        }
    }
}
```

### 3.6 跨语言工具复用

Python Agent 调 Java 工具：

```python
# Python Agent 调 Java 暴露的 MCP 工具
async def some_node(state):
    # 调 Java 端 MCP Server（http://localhost:8080/mcp）
    order = await mcp_call(
        "query_order", {"order_id": 12345}, server_url="http://spring-boot:8080/mcp"
    )
```

需要 MCP client 支持多 server 路由：

```python
# app/mcp/client.py 扩展
_sessions: dict[str, ClientSession] = {}


async def call_tool(name: str, arguments: dict, server: str = "python") -> dict:
    """server: 'python' / 'java'"""
    url = {
        "python": settings.mcp_python_url,  # http://localhost:18001
        "java": settings.mcp_java_url,  # http://spring-boot:8080/mcp
    }[server]
    if server not in _sessions:
        # 创建 session
        ...
    session = _sessions[server]
    result = await session.call_tool(name, arguments)
    return json.loads(result.content[0].text)
```

### 3.7 配置项

```python
# app/config.py 新增
mcp_enabled: bool = Field(default=False, description="是否启用 MCP 工具层")
mcp_server_port: int = Field(default=18001, description="本服务 MCP Server 端口")
mcp_python_url: str = Field(default="http://localhost:18001/mcp")
mcp_java_url: str = Field(default="http://localhost:8080/mcp")
mcp_timeout: int = Field(default=30, description="MCP 工具调用超时")
```

```bash
# .env.example 新增
MCP_ENABLED=false
MCP_SERVER_PORT=18001
MCP_PYTHON_URL=http://localhost:18001/mcp
MCP_JAVA_URL=http://localhost:8080/mcp
MCP_TIMEOUT=30
```

### 3.8 依赖

```toml
# pyproject.toml 新增
"mcp==1.2.0",            # MCP 官方 Python SDK
"mcp-cli==0.1.0",        # 可选：CLI 调试工具
```

---

## 4. 落地步骤

| 步骤 | 文件 | 改动 |
|---|---|---|
| 1 | `pyproject.toml` | 加 mcp 依赖 |
| 2 | `app/config.py` | 加 5 个 MCP 配置项 |
| 3 | `.env.example` | 加 5 个环境变量 |
| 4 | `app/mcp/server.py` | 新建 Python MCP Server |
| 5 | `app/mcp/client.py` | 新建 MCP Client（含多 server 路由） |
| 6 | `app/graphs/recommend_coach.py` | 节点改走 mcp_call |
| 7 | `app/main.py` | 启动时同时起 MCP Server（同一进程或子进程） |
| 8 | `platform-backend/.../mcp/McpServerController.java` | Java 端 MCP Server |
| 9 | `docker-compose.yml` | 暴露 MCP 端口 |
| 10 | 测试：用 Claude Desktop 连本地 MCP Server 验证 |

---

## 5. 验收标准

### 5.1 功能验收

- `tools/list` 返回 4 个 Python 工具 + 3 个 Java 工具
- `tools/call fetch_coaches` 返回教练 JSON
- `tools/call bm25_search query="减脂"` 返回 top 50
- 节点走 MCP 后业务结果与之前一致（不回归）

### 5.2 跨语言验收

- Python Agent 能调 `query_order` 查 Java 后端订单
- Claude Desktop 连 MCP Server 后能查教练 / 查订单

### 5.3 性能验收

- MCP 协议开销 < 5ms（本地 stdio）/ < 20ms（HTTP）
- 与直接 import 相比总耗时增加 < 10%

### 5.4 可观测验收

- 所有 MCP 调用入审计日志
- Langfuse trace 能看到 MCP call span

---

## 6. 关键设计决策回顾

| 决策点 | 选择 | 理由 |
|---|---|---|
| 何时上 MCP | 多 Agent + 跨语言 | 单 Agent 单进程不上 MCP |
| Transport | stdio（开发）+ streamable-http（生产） | 业内标准 |
| Server 部署 | 同进程内嵌（开发）+ 独立进程（生产） | 平衡性能与可复用 |
| 工具粒度 | 单一职责 | 一个工具干一件事，便于复用 |
| 多 server 路由 | 按 server 名路由 | Python / Java 分开 |
| 兜底 | MCP 失败回退直接 import | 不让协议层挂了业务全挂 |

---

## 7. 后续衔接

| 后续文档 | 与 #07 的关系 |
|---|---|
| #08 双 Agent | 评价摘要 + 证书审核都复用本 MCP 工具层 |
| 评价摘要 Agent | 调 `fetch_reviews` 工具（新增） |
| 证书审核 Agent | 调 `query_certificate` + `verify_national_cert` 工具（新增） |

---

## 8. 学习要点小结

1. **MCP 是协议不是框架**：标准化 LLM ↔ 工具通信，与具体语言无关
2. **何时上 MCP**：多 Agent 共享工具 + 跨语言复用 + 让外部 LLM 调你工具
3. **不何时上 MCP**：单 Agent 单进程，过度设计
4. **Transport 选型**：本地 stdio，远程 streamable-http
5. **工具单一职责**：一个工具干一件事，便于跨 Agent 复用
6. **跨语言天然支持**：Python / Java / Node 各自实现 MCP Server，client 无感
7. **保留直接 import 兜底**：协议层失败不能让业务全挂
