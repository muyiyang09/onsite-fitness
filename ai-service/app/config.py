"""配置中心：基于 pydantic-settings 的强类型配置。
通过 .env 文件或环境变量加载，避免把密钥硬编码进代码。
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_checkpointer_backend() -> str:
    """prod 环境（SERVICE_ENV=prod）默认 redis；开发机可零依赖跑 memory。"""
    import os

    return "redis" if os.getenv("SERVICE_ENV") == "prod" else "memory"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # —— LLM（通过 LiteLLM 路由，支持 DeepSeek / 通义 / OpenAI 等）——
    llm_model: str = Field(
        default="deepseek/deepseek-chat",
        description="LiteLLM 模型标识，如 deepseek/deepseek-chat / qwen/qwen-plus / openai/gpt-4o-mini",
    )
    llm_api_key: str = Field(default="", description="对应供应商的 API Key")
    llm_base_url: str | None = Field(
        default=None,
        description="自定义兼容端点。留空时 LiteLLM 会根据模型名选择官方端点。",
    )
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    llm_timeout: int = Field(default=60, description="单次 LLM 请求超时（秒）")
    llm_max_retries: int = Field(default=2, description="LiteLLM 内部重试次数")
    # §6.30 死循环防护：单节点最大执行秒数，超时 asyncio.wait_for 强制终止。
    # 需 > 最坏节点耗时（llm_timeout=60 × 重试），用 300s 做安全网，不误杀慢节点。
    graph_node_timeout: int = Field(default=300, description="单节点最大执行秒数，超时强制终止")

    # —— MySQL（只读，查 coach/course 等现有表）——
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "onsite_fitness"
    # —— MySQL 连接池（#05 上线加固：显式配池，避免默认 5 连接被打满）——
    mysql_pool_size: int = Field(default=20, description="连接池常驻连接数")
    mysql_max_overflow: int = Field(default=10, description="池满后可临时超出的连接数")
    mysql_pool_timeout: int = Field(default=30, description="获取连接超时（秒）")

    # —— Redis（推荐结果缓存，可选）——
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 1
    redis_password: str | None = None

    # —— 混合检索（#04 RAG 升级）——
    # 设计：混合检索是「加强」不是「替代」——BM25 便宜且离线可跑，默认开；
    # 向量/重排依赖 bge-m3 / FlagEmbedding 重模型，国内下载困难，默认关、留开关待接入。
    hybrid_retrieval_enabled: bool = Field(
        default=True,
        description="是否启用混合检索（BM25+RRF 升级语义匹配维度；关闭则完全退回 #03 子串匹配）",
    )
    reranker_enabled: bool = Field(
        default=False,
        description="是否启用 Cross-Encoder 重排（依赖 bge-reranker 重模型，默认关）",
    )
    bm25_top_k: int = Field(default=50, description="BM25 召回条数")
    rrf_k: int = Field(default=60, description="RRF 平滑常数（业界经验值）")
    rrf_top_k: int = Field(default=30, description="RRF 融合后取前 N 进入重排/打分")

    # —— 向量召回 / 重排模型（预留：重依赖未装时自动降级为 BM25 单路）——
    embedding_model: str = Field(
        default="BAAI/bge-m3", description="Embedding 模型名（HuggingFace）"
    )
    embedding_device: str = Field(default="cpu", description="cpu / cuda / mps")
    embedding_use_fp16: bool = Field(default=True)
    # 向量库：Milvus 单后端（生产唯一）。pymilvus 未装 / Milvus 不可达时，向量召回降级为 BM25 单路
    milvus_uri: str = Field(
        default="http://127.0.0.1:19530",
        description="Milvus 连接 URI，如 http://127.0.0.1:19530；Zilliz 云用 https://xxx.zillizcloud.com",
    )
    milvus_token: str = Field(
        default="", description="Milvus 认证 token（本地部署留空；Zilliz 云用 apikey）"
    )
    milvus_database: str = Field(default="default", description="Milvus 数据库名")
    milvus_collection: str = Field(default="ai_vector_coach", description="向量 collection 名")
    milvus_dim: int = Field(default=1024, description="向量维度（bge-m3=1024）")
    vector_skip_initial_upsert: bool = Field(
        default=False, description="启动时是否跳过 upsert（已建索引时 True 加速启动）"
    )
    reranker_model: str = Field(default="BAAI/bge-reranker-v2-m3", description="Reranker 模型名")
    reranker_device: str = Field(default="cpu", description="cpu / cuda / mps")
    reranker_use_fp16: bool = Field(default=True)

    # —— 商业化加固（#05）：限流 / Token 预算 / 熔断 / 缓存 ——
    # 设计：这些管控都依赖 Redis。Redis 不可用时一律「fail-open」——放过流量而非全拦，
    # 避免「保护组件本身故障」把整个服务打挂（见各中间件的降级注释）。
    rl_global_per_min: int = Field(default=100, description="全局每分钟限流")
    rl_ip_per_min: int = Field(default=30, description="单 IP 每分钟限流")
    rl_user_per_min: int = Field(default=10, description="单用户每分钟限流")
    token_per_request_limit: int = Field(default=10000, description="单次请求输入 token 上限")
    token_user_daily_limit: int = Field(default=100000, description="单用户单日 token 上限")
    token_global_daily_limit: int = Field(default=1000000, description="全局单日 token 上限")
    cb_fail_threshold: int = Field(default=5, description="LLM 连续失败 N 次触发熔断")
    cb_reset_timeout: int = Field(default=60, description="熔断开路后多久进入半开试探（秒）")
    cache_enabled: bool = Field(
        default=True, description="是否启用推荐结果缓存（相同 query 24h 复用）"
    )
    cache_ttl: int = Field(default=86400, description="缓存 TTL（秒），默认 24h")

    # —— MCP 工具层（#07，默认关：单 Agent 单进程直接调用够用）——
    mcp_enabled: bool = Field(default=False, description="是否启用 MCP 工具层（跨语言/外部 LLM）")
    mcp_server_port: int = Field(default=18001, description="MCP Server 端口")
    mcp_server_url: str = Field(default="http://localhost:18001/mcp", description="MCP Server URL")

    # —— Langfuse LLM 可观测性（#13，默认关：LLM 语义层 trace，未装包/未配置时全链路 no-op）——
    # 设计纪律与审计一致：旁路异步上报、fail-open（Langfuse 不可达只丢 trace 不影响主流程）。
    # 开启需先装可选依赖：pip install -e ".[langfuse]"
    langfuse_enabled: bool = Field(
        default=False, description="是否启用 Langfuse（LLM trace/cost/eval 闭环）"
    )
    langfuse_public_key: str = Field(
        default="", description="Langfuse Public Key（项目 Settings → API Keys）"
    )
    langfuse_secret_key: str = Field(default="", description="Langfuse Secret Key")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse 地址：云 https://cloud.langfuse.com / 自部署 http://localhost:3000",
    )
    langfuse_sample_rate: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="trace 采样率（0~1）；高峰期可调低，坏 case 按 request_id 强制查",
    )

    # —— 多 Agent（#08）——
    review_summary_enabled: bool = Field(default=True, description="是否启用评价摘要 Agent")
    cert_review_enabled: bool = Field(default=True, description="是否启用证书审核 Agent")
    supervisor_enabled: bool = Field(
        default=False, description="统一入口 Supervisor（默认关，直接调子 Agent）"
    )
    hitl_enabled: bool = Field(
        default=False, description="是否启用 HITL 人工介入（证书审核最终确认，默认关）"
    )

    # —— Checkpointer（上线加固：崩溃恢复 + 多副本共享状态 + DB 灾备）——
    checkpointer_backend: str = Field(
        default_factory=lambda: _default_checkpointer_backend(),
        pattern=r"^(memory|redis)$",
        description="Checkpointer 后端：memory(开发默认)/redis(prod 默认)。"
        "SERVICE_ENV=prod 时隐式切 redis，除非显式设置 CHECKPOINTER_BACKEND。",
    )
    checkpoint_ttl_minutes: int = Field(
        default=60, description="Checkpoint TTL（分钟），教练推荐/摘要 1h 足够"
    )
    checkpoint_db_fallback: bool = Field(
        default=True,
        description="是否启用 DB 灾备层（Redis miss 时从 DB 读 state + 回填 Redis，防雪崩/穿透/击穿）",
    )

    # —— HTTP 服务 ——
    service_host: str = "0.0.0.0"
    service_port: int = 18000
    service_env: str = Field(default="dev", pattern=r"^(dev|test|prod)$")

    # —— CORS（§6.31）：来源从 env 配置；credentials=True 时禁止 "*" ——
    cors_origins: str = Field(
        default="", description="CORS 允许来源（csv）；留空时 dev 默认 *，prod 需显式配置"
    )
    cors_allow_credentials: bool = Field(
        default=True, description="是否允许携带凭据；True 时禁止 allow_origins 含 *"
    )

    @property
    def mysql_dsn(self) -> str:
        pwd = f":{self.mysql_password}" if self.mysql_password else ""
        return (
            f"mysql+pymysql://{self.mysql_user}{pwd}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}"
                f"@{self.redis_host}:{self.redis_port}/{self.redis_db}"
            )
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
