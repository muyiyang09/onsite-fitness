"""轻量指标（可观测性 · 监控）：内存计数器 + Prometheus 文本格式导出。

设计（为什么不用 prometheus-client 重依赖）：
  - 指标种类少（llm/tool/cache/error/latency），手工维护计数器即可；
  - 输出 Prometheus 文本格式（`name value`），Prometheus/Grafana 直接 scrape `/metrics`；
  - 进程内计数，多副本各自统计、由 Prometheus 聚合（标准做法）。

指标（对应 #10 §1.7.3）：
  - llm_calls_total / llm_latency_ms：LLM 调用次数 + 耗时
  - tool_calls_total：工具调用次数
  - cache_hit_total / cache_miss_total：缓存命中/未命中
  - graph_latency_ms：整图耗时
  - error_total：错误次数
"""

from __future__ import annotations

import threading
from collections import defaultdict

_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)
_latency: dict[str, list[float]] = defaultdict(list)  # name -> [count, total_ms]


def incr(name: str, value: int = 1) -> None:
    with _lock:
        _counters[name] += value


def observe(name: str, value_ms: float) -> None:
    """记录一次耗时（ms），导出为 name_count / name_sum。"""
    with _lock:
        rec = _latency.setdefault(name, [0, 0.0])
        rec[0] += 1
        rec[1] += value_ms


def render() -> str:
    """渲染 Prometheus 文本格式。"""
    with _lock:
        lines: list[str] = []
        for name in sorted(_counters):
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {_counters[name]}")
        for name in sorted(_latency):
            cnt, total = _latency[name]
            lines.append(f"# TYPE {name}_count counter")
            lines.append(f"{name}_count {cnt}")
            lines.append(f"# TYPE {name}_sum gauge")
            lines.append(f"{name}_sum {total:.2f}")
        return "\n".join(lines) + ("\n" if lines else "")


__all__ = ["incr", "observe", "render"]
