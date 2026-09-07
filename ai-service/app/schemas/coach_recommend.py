"""教练推荐相关 Pydantic Schema：
IntentExtraction（Node 1 输出：用户自然语言 → 结构化筛选条件）
CoachCandidate   （Node 2 输出：候选教练 + 各项子打分 + 综合分）
RecommendResult  （Graph 最终输出：Top3 教练 + 总推荐理由 + 标签）
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Node 1：用户意图抽取（用户说一句话 → 结构化筛选条件）
# ---------------------------------------------------------------------------
class IntentExtraction(BaseModel):
    """从用户自然语言中抽取出的「教练筛选 + 需求画像」结构化条件。

    字段与现有 MySQL coach / course 表一一对应，Node 2 直接按该字段做 SQL 过滤。
    未抽取到的字段保持 None（Node 2 会把 None 视为"不限制"）。
    """

    model_config = ConfigDict(extra="ignore")

    city_name: str | None = Field(
        default=None,
        description="服务城市，中文全称，如 '北京市'。如果只提到区也反推所属城市。",
    )
    district: str | None = Field(
        default=None,
        description="区县 / 商圈，如 '朝阳区'、'望京'、'科技园'。不限制则为 null。",
    )
    specialization: str | None = Field(
        default=None,
        description="主要训练目标：减脂塑形 / 增肌训练 / 拉伸放松 / 产后恢复 / 运动康复 等",
    )
    specialization_tags: list[str] = Field(
        default_factory=list,
        description="更细的子标签：['减脂','体态矫正','孕产恢复','青少年体能'] 等",
    )
    level: Literal[1, 2, 3, 4] | None = Field(
        default=None,
        description="期望教练等级：1=初级 2=中级 3=高级 4=金牌。没提则 null（不限）。",
    )
    min_rating: float | None = Field(
        default=None, ge=0.0, le=5.0, description="期望最低评分（0~5）。"
    )
    max_price: float | None = Field(default=None, ge=0, description="单次课程预算上限（元）。")
    time_slot: str | None = Field(
        default=None,
        description="期望时段，如 '周末上午'、'工作日晚上'、'每天 09:00-10:00'。",
    )
    male_only: bool | None = Field(
        default=None, description="是否要求男教练：True/False/None（用户没提则不限）。"
    )
    user_goal: str | None = Field(
        default=None,
        description="用户一句话目标摘要，用于 Node 3 生成个性化推荐理由。如 '3 个月减 10 斤备婚'。",
    )


# ---------------------------------------------------------------------------
# Node 2：候选教练打分结果
# ---------------------------------------------------------------------------
class CoachCandidate(BaseModel):
    """Node 2 输出的一个候选教练 + 各项子打分。"""

    coach_id: int = Field(description="教练 ID，对应 MySQL coach.id")
    name: str = Field(description="教练姓名")
    level: int = Field(description="教练等级：1 初 / 2 中 / 3 高 / 4 金")
    rating: float = Field(description="评分 0~5")
    service_radius_km: float = Field(description="服务半径 KM")
    city_name: str
    bio: str = Field(default="", description="教练简介/擅长（bio），用于生成差异化推荐理由。")
    specialization: str | None = Field(
        default=None, description="匹配课程分类（展示用「擅长领域」标签）。"
    )
    course_name: str | None = Field(
        default=None, description="匹配到的课程名称（同类教练相同，用于展示/下单）。"
    )
    price: float = Field(description="匹配课程的参考单价（元）。教练不直接定价，价格来自课程目录。")
    distance_km_est: float | None = Field(
        default=None, description="估算距离（KM）。若 district 抽不到则为 null。"
    )
    schedule_match_ratio: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="用户时段要求与 coach_schedule 空闲时段匹配比例（0~1）。",
    )
    # ---- 各项子打分 0~100（价格维度已移除：价格在教练间无价差，见项目决策）----
    score_rating: int = Field(ge=0, le=100, description="评分分")
    score_level: int = Field(ge=0, le=100, description="等级分")
    score_match: int = Field(
        ge=0, le=100, description="specialization / 标签与用户目标的语义匹配度"
    )
    score_distance: int = Field(
        ge=0, le=100, description="距离分（越近越高），未知距离给 60 中位分。"
    )
    score_schedule: int = Field(ge=0, le=100, description="档期匹配分")
    # ---- 综合分 0~100（Node 2 内部算好加权）----
    score_total: float = Field(ge=0, le=100)


# ---------------------------------------------------------------------------
# Graph 最终输出：给小程序 / Java 后端的契约
# ---------------------------------------------------------------------------
class RecommendResult(BaseModel):
    """教练推荐 Graph 最终输出（HTTP Response）。"""

    model_config = ConfigDict(extra="ignore")

    user_query: str = Field(description="用户原始查询，透传回去便于前端调试")
    intent: IntentExtraction = Field(description="Node 1 抽取出的结构化条件，前端可选展示。")

    candidates: list[CoachCandidate] = Field(
        description="按 score_total 降序排列的候选教练，默认返回 Top3。",
        min_length=0,
        max_length=5,
    )
    coach_ids: list[int] = Field(
        default_factory=list,
        description="与 candidates 对应的 coach_id 列表，为方便后端直接用做二次查询。",
    )
    recommend_reason: str = Field(
        default="",
        description="Node 3 生成的 2~3 句自然语言推荐理由。如：'为你推荐李教练，评分5.0（金牌），专注减脂8年，且在你预算内'。",
    )
    matched_course_name: str | None = Field(
        default=None, description="为用户匹配到的参考课程名（用于展示/下单）。"
    )
    matched_course_price: float | None = Field(
        default=None, description="参考课程单价（元），预算过滤后的价格。"
    )
    over_budget: bool = Field(
        default=False, description="参考课程是否超出用户预算（超预算时建议前端提示）。"
    )
    used_mock: bool = Field(
        default=False, description="是否走了离线 mock 分支（没配 LLM Key 时 True）。"
    )
