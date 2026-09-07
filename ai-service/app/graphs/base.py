"""BaseGraph：所有工作流图的公共基类与工具函数。

这里故意只引入「langgraph StateGraph + START/END」与消息 reducer，
不引入任何 LangChain Core 的链式组件，把 LangChain 当零件超市用、只取有用的。
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, TypedDict, TypeVar

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

T = TypeVar("T")


# =============================================================================
# 节点执行兜底（§6.30 死循环防护）：asyncio.wait_for 强制终止挂起/死循环节点。
# 超时抛 asyncio.TimeoutError，由上层 graph 统一捕获降级；配合各图已有的
# refine_count / reason_attempts 等循环硬上限，双保险保证图必终止。
# =============================================================================
def invoke_node(
    node: Callable[[dict[str, Any]], Awaitable[Any]],
    state: dict[str, Any],
    timeout: float | None = None,
) -> Awaitable[Any]:
    from app.config import settings

    return asyncio.wait_for(node(state), timeout or settings.graph_node_timeout)


# =============================================================================
# 公共消息 reducer：推荐 Graph 目前不做多轮对话，但保留消息字段方便以后扩展。
# 用法：在自定义 State 中声明 messages: Annotated[list[BaseMessage], add_messages]
#       节点返回 {"messages": [AIMessage(...)]} 即可完成增量追加，无需自己 merge。
# =============================================================================
MessagesState = Annotated[list[BaseMessage], add_messages]


# =============================================================================
# 节点路由辅助：把「节点写一个分支字段 → 路由函数只返回分支 key → add_conditional_edges
# 配 key -> node 映射」的固定模式抽出来，避免拓扑歧义（经验 1635788）。
# =============================================================================
class ConditionalRouter:
    """用法：

    class MyState(TypedDict):
        branch: str

    router = ConditionalRouter(
        state_field="branch",
        mapping={
            "A": "node_a",
            "B": "node_b",
            "stop": END,
        },
        default=END,
    )

    builder.add_conditional_edges("root", router.route, router.edges())
    """

    # 兜底 key：route() 返回的是「分支 key」，而非目标节点名；未知 key 归到 default 目标。
    _DEFAULT_KEY = "__default__"

    def __init__(self, state_field: str, mapping: dict[str, str], default: Any = END) -> None:
        self.state_field = state_field
        self.mapping = mapping
        self.default = default

    def route(self, state: dict[str, Any]) -> Any:
        key = state.get(self.state_field)
        return key if key in self.mapping else self._DEFAULT_KEY

    def edges(self) -> dict[str, Any]:
        # add_conditional_edges 的 path_map：分支 key → 目标节点；额外挂上兜底 key。
        return {**self.mapping, self._DEFAULT_KEY: self.default}


# =============================================================================
# 消息辅助：统一把用户输入包成 HumanMessage。
# 对外的 State 一般只存 user_query 字符串，节点内部再转消息对象。
# =============================================================================
def to_human(query: str) -> list[BaseMessage]:
    return [HumanMessage(content=query)]


__all__ = [
    "MessagesState",
    "StateGraph",
    "START",
    "END",
    "Annotated",
    "TypedDict",
    "ConditionalRouter",
    "to_human",
    "invoke_node",
]
