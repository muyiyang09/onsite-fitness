# AI 微服务开发文档 · #06 Harness 工程（Eval + Trace + Prompt 管理）

> 版本：v1.0 · 2026-08-26
> **文档分类**：落地指南（Guideline） · **强制性**：建议遵循 · **用途**：建立可量化、可观测、可迭代的 Agent 评估与可观测体系
> 前置阅读：[#02 §8 可观测性](./02-Agent工程能力地图.md) · [#02 §10 评估与迭代](./02-Agent工程能力地图.md) · [#05 商业化加固](./05-商业化加固.md)
> 涉及文件：`app/eval/`（新增）/ `app/clients/trace.py`（新增）/ `app/prompts/`（新增）/ `tests/eval/`（新增）

---

## 0. 文档说明

### 0.1 目标

把 Agent 从「凭感觉改 prompt」升级到「**量化评估 + 全链路可观测 + Prompt 版本化**」，建立可持续迭代的工程化体系：

1. **Eval 数据集 + Metric**：20+ 标注样例，3 类 metric，量化每次改动
2. **Trace 全链路**：节点级耗时 / token / 错误，Langfuse 自部署
3. **Prompt 管理**：从代码常量抽到独立配置，支持版本化 + A/B
4. **LLM-as-Judge**：用强模型评判输出质量
5. **反馈回流**：用户点击/下单成在线 eval 集

### 0.2 范围与边界

| 项 | 是否改动 |
|---|---|
| 业务逻辑 | ❌ 不动 |
| 节点实现 | ⚠️ 加 trace 装饰器（不改逻辑） |
| Prompt 文本 | ✅ 抽到独立文件 |
| 测试目录 | ✅ 新增 tests/eval/ |

---

## 1. 现状回顾

| 维度 | 现状 | 缺口 |
|---|---|---|
| 离线测试 | 1 个 smoke test，4 条 query，仅断言结构 | 无 Eval 集 / 无 metric |
| 可观测 | `logging.basicConfig` | 无 trace / 无 span / 无 metrics |
| Prompt 管理 | `SYSTEM_NODE1` 等硬编码常量 | 无版本 / 无 A/B / 无 few-shot 池 |
| 反馈回流 | `used_mock` 字段仅本地 | 无在线 eval |

---

## 2. 设计思路

### 2.1 Eval 不是测试

**关键认知**：Eval ≠ 单元测试。

| 维度 | 单元测试 | Eval |
|---|---|---|
| 目的 | 验证"代码对不对" | 量化"AI 表现好不好" |
| 输入 | 确定性 case | 标注的 ground truth |
| 期望 | 精确匹配 | 允许一定误差 |
| 通过条件 | assert True | score ≥ threshold |
| 触发时机 | CI 每次 push | 改 prompt / 改模型 / 定期回归 |

Eval 不要求 100% 通过，而是给一个 baseline 分数，每次改动后对比。**baseline 涨了 = 改对了**。

### 2.2 分节点评估 vs 端到端评估

| 评估层级 | 优点 | 缺点 |
|---|---|---|
| 端到端 | 简单 | 失败时定位不到哪个节点出问题 |
| **分节点** | 可定位 | 设计成本高 |
| 混合（推荐） | 兼顾 | - |

**本项目推荐分节点**：
- Node1 Intent 抽取：字段级准确率
- Node2 召回：Recall@K / nDCG@K
- Node3 推荐理由：可读性 + 含数据 + 不空泛
- 端到端：用户满意度（在线）

### 2.3 LLM-as-Judge 的边界

| 场景 | 用 LLM-as-Judge | 用规则 |
|---|---|---|
| 推荐理由可读性 | ✅ 适合 | ❌ 规则难定义 |
| Top-K 命中 | ❌ 浪费 | ✅ 直接对比 coach_ids |
| Intent 字段准确 | ⚠️ 可以但慢 | ✅ 字段名匹配 |
| 推荐理由含数据 | ⚠️ 可以 | ✅ 关键词匹配（教练名/价格/评分） |

**原则**：能用规则的用规则，规则难定义的用 LLM-as-Judge。LLM-as-Judge 用便宜模型（deepseek-chat / gpt-4o-mini）即可，不用上 GPT-4。

### 2.4 Trace 三层结构

```
Trace（一次请求）
├── Span: extract_intent
│   ├── Span: chat_structured
│   │   └── Span: acompletion (LLM 调用)
│   └── event: retry 1/2
├── Span: retrieve_and_rank
│   ├── Span: bm25_search
│   ├── Span: vector_search
│   └── Span: rerank
└── Span: generate_reason
    └── Span: chat
```

---

## 3. 落地方案

### 3.1 Eval 数据集

```yaml
# tests/eval/dataset.yaml（新增）
- id: eval_001
  name: 产后恢复+预算+时段
  query: "望京，预算 200 以内，想产后恢复，周末上午"
  expected_intent:
    city_name: "北京市"
    district: "望京"
    specialization: "产后恢复"
    max_price: 200
    time_slot_contains: "周末"
  expected_coach_ids_subset: [1, 3]  # 至少包含这些 coach 之一
  tags: [happy_path, 产后]

- id: eval_002
  name: 减脂+金牌教练
  query: "想找金牌教练上门减脂塑形，要求评分高，在北京朝阳区"
  expected_intent:
    level: 4
    specialization: "减脂塑形"
    city_name: "北京市"
    district: "朝阳区"
  expected_coach_ids_subset: [1]
  tags: [happy_path, 减脂]

# ... 共 20+ 条
```

### 3.2 Metric 实现

```python
# app/eval/metrics.py（新增）
"""三类 metric：Intent 准确率 / Top-K 命中率 / 理由可读性"""

from typing import Any


def intent_field_accuracy(predicted: dict, expected: dict, fields: list[str] = None) -> float:
    """IntentExtraction 字段级准确率（0~1）。
    非空字段匹配 = 1，不匹配 = 0，期望为 None 时不计入。
    """
    fields = fields or [
        "city_name",
        "district",
        "specialization",
        "level",
        "max_price",
        "time_slot",
        "male_only",
    ]
    correct, total = 0, 0
    for f in fields:
        exp = expected.get(f)
        if exp is None:
            continue  # 期望为 None 不计入
        total += 1
        pred = predicted.get(f)
        if f == "time_slot":
            # 时段模糊匹配：期望值是关键词，命中即算对
            if isinstance(exp, str) and exp.lower() in str(pred or "").lower():
                correct += 1
        elif pred == exp:
            correct += 1
    return correct / total if total else 1.0


def topk_hit_ratio(predicted_ids: list[int], expected_subset: list[int]) -> float:
    """Top-K 命中率：期望的教练 ID 至少有一个在 Top-K 中。
    返回 0~1，命中 1 个 = 1，全 miss = 0。
    """
    if not expected_subset:
        return 1.0
    hit = any(eid in predicted_ids for eid in expected_subset)
    return 1.0 if hit else 0.0


def reason_quality_score(reason: str, candidates: list[dict]) -> dict:
    """推荐理由质量分（0~100）。返回 {score, details}。
    规则门控：
      - 长度 30~200 字
      - 含 ≥2 位教练名
      - 不含空泛词
    """
    details = {}
    if 30 <= len(reason) <= 200:
        details["length"] = 20
    else:
        details["length"] = 0
    names_in = sum(1 for c in candidates if c.get("name", "") in reason)
    details["coach_names"] = min(40, names_in * 20)
    empty_words = ["很专业", "很棒", "非常好", "推荐"]
    has_empty = any(w in reason for w in empty_words)
    details["no_empty"] = 20 if not has_empty else 0
    details["data_richness"] = (
        20
        if any(str(c.get("rating")) in reason or str(c.get("price")) in reason for c in candidates)
        else 0
    )
    return {"score": sum(details.values()), "details": details}
```

### 3.3 Eval 运行器

```python
# app/eval/runner.py（新增）
"""Eval 运行器：跑数据集 + 算 metric + 输出报告"""

import yaml
from pathlib import Path
from rich.console import Console
from rich.table import Table
from app.graphs.recommend_coach import RECOMMEND_GRAPH
from app.schemas.coach_recommend import RecommendResult
from app.eval.metrics import intent_field_accuracy, topk_hit_ratio, reason_quality_score

console = Console()


async def run_eval(dataset_path: str = "tests/eval/dataset.yaml") -> dict:
    cases = yaml.safe_load(Path(dataset_path).read_text(encoding="utf-8"))
    results = []
    for case in cases:
        try:
            state_out = await RECOMMEND_GRAPH.ainvoke({"user_query": case["query"], "top_n": 3})
            result = RecommendResult.model_validate(state_out["result"])
        except Exception as exc:
            results.append(
                {"id": case["id"], "name": case["name"], "error": str(exc), "pass": False}
            )
            continue

        intent_acc = intent_field_accuracy(
            result.intent.model_dump(), case.get("expected_intent", {})
        )
        hit = topk_hit_ratio(result.coach_ids, case.get("expected_coach_ids_subset", []))
        rq = reason_quality_score(
            result.recommend_reason, [c.model_dump() for c in result.candidates]
        )
        passed = intent_acc >= 0.6 and hit >= 1.0 and rq["score"] >= 60

        results.append(
            {
                "id": case["id"],
                "name": case["name"],
                "intent_acc": intent_acc,
                "topk_hit": hit,
                "reason_score": rq["score"],
                "pass": passed,
            }
        )

    # 汇总
    total = len(results)
    passed = sum(1 for r in results if r.get("pass"))
    avg_intent = sum(r.get("intent_acc", 0) for r in results) / total
    avg_reason = sum(r.get("reason_score", 0) for r in results) / total
    return {
        "passed": passed,
        "total": total,
        "pass_rate": passed / total,
        "avg_intent_acc": avg_intent,
        "avg_reason_score": avg_reason,
        "details": results,
    }


async def main():
    report = await run_eval()
    tbl = Table("ID", "Name", "Intent Acc", "TopK Hit", "Reason Score", "Pass")
    for r in report["details"]:
        tbl.add_row(
            r.get("id", "-"),
            r.get("name", "-"),
            f"{r.get('intent_acc', 0):.2f}",
            f"{r.get('topk_hit', 0):.2f}",
            f"{r.get('reason_score', 0):.0f}",
            "✓" if r.get("pass") else "✗",
        )
    console.print(tbl)
    console.print(
        f"\n[bold]通过率：{report['passed']}/{report['total']} ({report['pass_rate']:.0%})[/]"
    )
    console.print(f"平均 Intent 准确率：{report['avg_intent_acc']:.2f}")
    console.print(f"平均理由质量分：{report['avg_reason_score']:.0f}")
```

### 3.4 Langfuse Trace 接入

> ✅ **已落地（v1.0，2026-09-02）**。本节原为「目标设计」草稿，实际落地与草稿有三处关键差异，以 [13-Langfuse接入与面试题](./13-Langfuse接入与面试题.md) 为准：
> 1. **LLM 层不走 litellm callback**：litellm==1.55.3 的 langfuse 集成只兼容 v2 SDK（`langfuse.model.CreateTrace/CreateGeneration`，v3 已移除）；改为在 [llm.py](../app/clients/llm.py) 收口点用 v3 `@observe` 记 generation，从 litellm 响应取**真实 usage**（替代 estimate_tokens 估算）。
> 2. **SDK 用 v3**（OTel 内核），可选依赖 `pip install -e ".[langfuse]"`，未装包/未配置时全链路 no-op。
> 3. **埋点收口三处，业务代码零改动**：API 端点 root trace（`observe_span("api.xxx")`）→ 节点 span（[trace.py](../app/clients/trace.py) 的 `trace_node` 统一注入）→ LLM generation（[llm.py](../app/clients/llm.py)）。纪律与审计一致：旁路异步上报、fail-open、可采样（LANGFUSE_SAMPLE_RATE）、停机 flush。

#### 3.4.1 部署 Langfuse

```yaml
# docker-compose.yml 新增（v2 单体示例：只要 PostgreSQL，最轻；注意 v2 已停止新功能开发，
# v3 自部署需要 ClickHouse + MinIO + PostgreSQL 全家桶，小团队建议先用云版验证）
langfuse:
  image: langfuse/langfuse:2
  ports: ["3000:3000"]
  environment:
    - DATABASE_URL=postgresql://langfuse:langfuse@postgres-langfuse:5432/langfuse
    - NEXTAUTH_SECRET=your-secret
    - SALT=your-secret
    - NEXTAUTH_URL=http://localhost:3000
  depends_on: [postgres-langfuse]
  restart: unless-stopped

postgres-langfuse:
  image: postgres:15
  environment:
    - POSTGRES_USER=langfuse
    - POSTGRES_PASSWORD=langfuse
    - POSTGRES_DB=langfuse
  volumes: ["lf-pg:/var/lib/postgresql/data"]

volumes:
  lf-pg:
```

#### 3.4.2 接入 Langfuse（已落地版）

```python
# app/clients/langfuse_client.py（已落地）——唯一封装点，四层 no-op 降级：
#   未启用(env) / 未装包 / 未配 key / 运行时异常 → 全部静默降级为纯日志 trace
init_langfuse()      # lifespan 启动时调用：注入 LANGFUSE_* 环境变量 + 取全局 client
flush_langfuse()     # lifespan 停机时调用：flush 内存队列防丢 trace 尾巴

observe_span("api.recommend-coach")                    # API 端点：root trace
observe_span("node.extract_intent")                    # 图节点：span（trace_node 统一注入）
observe_span("llm.acompletion", as_type="generation")  # LLM 调用：generation

update_trace_meta(user_id=..., session_id=thread_id, metadata={"request_id": ...})
update_current_generation(output=..., model=..., usage={"input": p, "output": c, ...})
```

启用：`.env` 里 `LANGFUSE_ENABLED=true` + `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST`（见 [.env.example](../.env.example)）。

#### 3.4.3 Prompt 抽到 Langfuse（⏳ 目标设计：当前 prompt 走本地 YAML 版本化，见 §3.5）

```python
# 直接在 Langfuse UI 创建 prompt，代码侧 fetch
SYSTEM_NODE1 = _langfuse.get_prompt("recommend_node1_intent_extraction", label="production").prompt
```

### 3.5 Prompt 版本化管理

#### 3.5.1 抽到独立文件

```
ai-service/
└── app/
    └── prompts/
        ├── recommend_node1_intent.yaml
        ├── recommend_node3_reason.yaml
        └── cert_review_v1.yaml  # 后续证书审核用
```

```yaml
# app/prompts/recommend_node1_intent.yaml
name: recommend_node1_intent_extraction
version: "1.2.0"
label: production
template: |
  你是一个「上门私教教练推荐」的结构化意图抽取器。
  只根据用户一句话，输出 JSON：
    - city_name/district：用户提到的服务城市 / 商圈；
    ...
variables: []
metadata:
  changelog:
    - version: "1.0.0"
      date: "2026-08-20"
      change: "初始版本"
    - version: "1.1.0"
      date: "2026-08-23"
      change: "增加 male_only 字段"
    - version: "1.2.0"
      date: "2026-08-26"
      change: "增加 specialization_tags 数组"
```

#### 3.5.2 Prompt 加载器

```python
# app/prompts/loader.py（新增）
import yaml
from pathlib import Path

_loaded: dict[str, dict] = {}


def load_prompt(name: str, version: str = None) -> str:
    """加载 prompt 模板。version 留空取 label=production。"""
    if name not in _loaded:
        path = Path(__file__).parent / f"{name}.yaml"
        _loaded[name] = yaml.safe_load(path.read_text(encoding="utf-8"))
    p = _loaded[name]
    if version:
        # 找指定版本
        if p.get("version") != version:
            raise ValueError(f"prompt {name} 无版本 {version}")
    return p["template"]


# 节点内使用
SYSTEM_NODE1 = load_prompt("recommend_node1_intent")
```

### 3.6 LLM-as-Judge

```python
# app/eval/judge.py（新增）
"""LLM-as-Judge：用便宜模型评判推荐理由质量"""

from app.clients.llm import achat

JUDGE_PROMPT = """你是推荐理由质量评估员。请给以下理由打分（0~100），按维度评：
1. 个性化：是否结合用户具体目标
2. 数据支撑：是否含评分/价格/擅长领域
3. 差异化：是否点出至少 2 位教练的不同卖点
4. 简洁度：是否 100 字以内
5. 口语化：是否真诚自然，无硬广

用户目标：{user_goal}
候选教练：{candidates}
推荐理由：{reason}

输出 JSON：{"score": int, "details": {维度: int}, "feedback": str}
"""


async def judge_reason(user_goal: str, candidates: list, reason: str) -> dict:
    text = await achat(
        [
            {
                "role": "system",
                "content": JUDGE_PROMPT.format(
                    user_goal=user_goal, candidates=candidates, reason=reason
                ),
            },
        ]
    )
    return json.loads(text)
```

### 3.7 在线反馈回流

```python
# app/main.py 新增
@app.post("/v1/ai/feedback", tags=["AI"])
async def feedback(payload: FeedbackIn, request: Request):
    """用户对推荐结果反馈（点赞/点踩/下单）→ 写入 ai_eval_online 表"""
    await afetch_all(
        "INSERT INTO ai_eval_online (request_id, user_id, action, coach_id, "
        "feedback, created_at) VALUES (:rid, :uid, :act, :cid, :fb, NOW())",
        {
            "rid": payload.request_id,
            "uid": request.headers.get("x-user-id"),
            "act": payload.action,
            "cid": payload.coach_id,
            "fb": payload.feedback,
        },
    )
    return {"ok": True}
```

定时任务聚合在线反馈 → 更新 eval 数据集：

```python
# 周一聚合任务：把上周有点击/下单的 query 加入 eval 集
async def _weekly_eval_update():
    rows = await afetch_all("""
        SELECT request_id, user_id, query, action, coach_id
        FROM ai_eval_online
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        AND action IN ('order', 'like')
    """)
    # 写入 tests/eval/online_dataset.yaml
    ...
```

---

## 4. 落地步骤

| 步骤 | 文件 | 改动 |
|---|---|---|
| 1 | `tests/eval/dataset.yaml` | 写 20 条标注 case |
| 2 | `app/eval/metrics.py` | 实现 3 类 metric |
| 3 | `app/eval/runner.py` | Eval 运行器 + 报告 |
| 4 | `app/prompts/*.yaml` | 把硬编码 prompt 抽出 |
| 5 | `app/prompts/loader.py` | Prompt 加载器 |
| 6 | `app/clients/trace.py` | Langfuse 接入 + trace_node 装饰器 |
| 7 | `app/eval/judge.py` | LLM-as-Judge |
| 8 | `app/main.py` | 节点加装饰器 + /v1/ai/feedback 端点 |
| 9 | `sql/ai_eval_online.sql` | 反馈表 |
| 10 | `docker-compose.yml` | 加 Langfuse + PG |
| 11 | `tests/eval/test_regression.py` | CI 回归测试 |

---

## 5. 验收标准

### 5.1 Eval 验收

- 数据集 20 条 case，覆盖 happy path / 边界 / 兜底
- 3 类 metric 都跑通
- 当前 baseline：通过率 ≥ 80%，Intent 准确率 ≥ 0.7

### 5.2 Trace 验收

- Langfuse UI 能看到每次请求的节点级 span
- 含 input / output / 耗时 / token
- 改 prompt 后能在 Langfuse 对比新旧版本

### 5.3 Prompt 管理验收

- 改 prompt 不动业务代码（只改 yaml）
- changelog 完整
- 改完跑 eval 回归

### 5.4 反馈回流验收

- 点赞/点踩/下单 → 入 ai_eval_online 表
- 周一定时聚合入 eval 集

---

## 6. 关键设计决策回顾

| 决策点 | 选择 | 理由 |
|---|---|---|
| Eval 性质 | 量化指标 + baseline 对比 | 不是断言对错，是量化趋势 |
| 评估粒度 | 分节点 + 端到端混合 | 兼顾定位与简明 |
| LLM-as-Judge 模型 | deepseek-chat | 便宜模型够用，不上 GPT-4 |
| Trace 工具 | Langfuse 自部署 | 开源、数据自主、与 LangGraph 集成好 |
| Prompt 管理 | YAML 文件 + Langfuse | 简单可读，未来上 Langfuse 版本化 |
| 反馈回流 | 显式 + 隐式 | 点赞显式，下单隐式 |

---

## 7. 学习要点小结

1. **Eval ≠ 单元测试**：量化趋势而非断言对错
2. **分节点评估定位准**：失败时知道哪个节点出问题
3. **能用规则不用 LLM-as-Judge**：规则明确且免费
4. **Trace 三层结构**：Trace / Span / Event，对应请求/节点/子调用
5. **Prompt 抽到独立文件**：改 prompt 不动业务代码
6. **在线反馈回流**：用户点击/下单才是真 ground truth
7. **Langfuse 自部署**：数据自主，不依赖第三方云
