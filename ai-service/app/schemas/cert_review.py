"""证书审核 Agent（#08-B）的 Pydantic 契约。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CertReviewIn(BaseModel):
    """证书审核请求：教练提交的证书信息。"""

    coach_id: int = Field(..., description="教练 ID")
    cert_type: str = Field(..., description="证书类型：国职 / 国际认证 / 急救证")
    cert_number: str = Field(..., description="证书编号")
    holder_name: str = Field(..., description="持有人姓名")
    image_url: str | None = Field(default=None, description="证书图片 URL（OCR 用）")


class CertificateFields(BaseModel):
    """OCR / LLM 抽取出的证书结构化字段。"""

    cert_type: str = Field(description="证书类型")
    cert_number: str = Field(description="证书编号")
    holder_name: str = Field(description="持有人姓名")
    expiry_date: str | None = Field(default=None, description="有效期，如 2027-06-30")


class VerificationItem(BaseModel):
    """单条核验结果。"""

    check: str = Field(description="核验项，如 编号格式 / 有效期 / 姓名匹配")
    passed: bool = Field(description="是否通过")
    detail: str = Field(default="", description="核验说明")


class CertReviewResult(BaseModel):
    """证书审核输出：抽取字段 + 核验结果 + 风险等级 + 建议。"""

    coach_id: int
    fields: CertificateFields
    verifications: list[VerificationItem] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = Field(description="风险等级")
    suggestion: Literal["approve", "reject", "manual_review"] = Field(
        description="Agent 建议：通过 / 拒绝 / 人工复核"
    )
    used_mock: bool = Field(default=False)
