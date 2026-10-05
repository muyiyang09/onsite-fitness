"""离线验证脚本：不启动 FastAPI，直接 invoke LangGraph。

目的：
  1. 不需要填 API Key，直接 Mock 跑通，快速验证 Graph 拓扑 + 状态流转 + Pydantic 契约；
  2. 装完依赖后的冒烟测试（参考 get_job 项目的 eval 思路）。

运行：
    cd ai-service
    set AI_MOCK=1        # Windows PowerShell：$env:AI_MOCK=1
    python -m tests.test_recommend
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# 让 pytest 之外也能直接跑：确保 ai-service 根目录在 sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 强制 mock 模式（不依赖 API Key 也能跑通图）
os.environ.setdefault("AI_MOCK", "1")

# Windows 控制台默认 GBK，rich 输出 Unicode（✓/✗/中文）会抛 UnicodeEncodeError。
# 强制 UTF-8 输出，并让 rich 跳过 legacy GBK 渲染器（必须在 Console() 构造前设置）。
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console  # type: ignore  # noqa: E402
from rich.panel import Panel  # noqa: E402
from rich.table import Table  # noqa: E402

from app.graphs.recommend_coach import RECOMMEND_GRAPH  # noqa: E402
from app.schemas.coach_recommend import RecommendResult  # noqa: E402

console = Console()

TEST_CASES: list[dict[str, str]] = [
    {
        "name": "产后恢复 + 预算 + 时段",
        "query": "我家住望京，预算 200 以内，想产后恢复，最好周末上午",
    },
    {
        "name": "减脂塑形 + 金牌教练",
        "query": "想找金牌教练上门减脂塑形，要求评分高，在北京朝阳区",
    },
    {
        "name": "增肌 + 便宜优先",
        "query": "男生想增肌，预算有限，150块钱一次以内，工作日晚上有时间",
    },
    {
        "name": "纯开放目标（兜底）",
        "query": "想找个教练上门上课",
    },
]


def run_one(name: str, query: str) -> RecommendResult:
    state_out = asyncio.run(
        RECOMMEND_GRAPH.ainvoke(
            {"user_query": query, "top_n": 3},
            config={"configurable": {"thread_id": f"smoke-{name}"}},
        )
    )
    return RecommendResult.model_validate(state_out["result"])


def main() -> int:
    console.print(
        Panel.fit(
            "[bold cyan]上门体育 · 教练推荐 Graph 离线冒烟测试[/]\n"
            "AI_MOCK=1 · 运行 4 条样例 · 验证 State/Node/Edge/Pydantic 全链路",
            title="LangGraph Smoke Test",
            border_style="cyan",
        )
    )

    passed = 0
    for case in TEST_CASES:
        name, query = case["name"], case["query"]
        try:
            result = run_one(name, query)
        except Exception as exc:  # noqa: BLE001
            console.print(f"[red]✗ FAILED[/] {name}: {exc!r}")
            continue

        # Pydantic 契约：candidates 非空、coach_ids 对齐、综合分降序
        c_cnt = len(result.candidates)
        ids_match = [c.coach_id for c in result.candidates] == result.coach_ids
        sorted_ok = all(
            result.candidates[i].score_total >= result.candidates[i + 1].score_total
            for i in range(len(result.candidates) - 1)
        )
        ok = c_cnt > 0 and ids_match and sorted_ok
        mark = "[bold green]✓ PASS[/]" if ok else "[bold red]✗ FAIL[/]"
        passed += 1 if ok else 0

        console.print()
        console.rule(f"[{mark}] {name}")
        console.print(f"[dim]Query:[/] {query}")
        console.print(
            f"[dim]City :[/] {result.intent.city_name!r}   "
            f"[dim]Dist :[/] {result.intent.district!r}   "
            f"[dim]Spec :[/] {result.intent.specialization!r}   "
            f"[dim]MaxPrice :[/] {result.intent.max_price!r}   "
            f"[dim]Level :[/] {result.intent.level!r}   "
            f"[dim]Tags :[/] {result.intent.specialization_tags}"
        )

        tbl = Table(
            "Rank", "Coach", "Level", "Rating", "Price", "Match", "Total", header_style="bold"
        )
        for i, c in enumerate(result.candidates, 1):
            lv = ["初级", "中级", "高级", "金牌"][c.level - 1]
            tbl.add_row(
                f"#{i}",
                f"{c.name} (id={c.coach_id})",
                lv,
                f"{c.rating:.1f}",
                f"¥{c.price:.0f}",
                f"{c.score_match}",
                f"{c.score_total:.1f}",
            )
        console.print(tbl)
        console.print(f"[bold yellow]💬 推荐理由[/]：{result.recommend_reason}")
        console.print(f"[dim]used_mock={result.used_mock}  coach_ids={result.coach_ids}[/]")
        if not ids_match:
            console.print("[red]错误：candidates.coach_id 与 coach_ids 不一致[/]")
        if not sorted_ok:
            console.print("[red]错误：candidates 未按 score_total 降序[/]")

    total = len(TEST_CASES)
    console.print()
    console.print(
        Panel.fit(
            f"[bold]结果：{passed}/{total} 通过[/]",
            border_style="green" if passed == total else "red",
        )
    )
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
