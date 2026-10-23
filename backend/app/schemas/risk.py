from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


RiskStatus = Literal["ok", "insufficient_data", "error"]


class RiskResult(BaseModel):
    model: str
    status: RiskStatus
    metric_value: float | None = None
    category: str | None = None
    alert_level: str | None = None
    explanation: str
    missing: list[str] = Field(default_factory=list)
    source: str
    disclaimer: str


class RiskSummaryResponse(BaseModel):
    results: list[RiskResult]
    ai_consent_required: bool = False
    message_code: str | None = None


class RiskSnapshotResponse(BaseModel):
    id: UUID
    patient_id: UUID
    model: str
    metric_value: float | None = None
    category: str
    alert_level: str
    trigger: str
    computed_at: datetime

    model_config = {"from_attributes": True}


class RiskHistoryResponse(BaseModel):
    snapshots: list[RiskSnapshotResponse]
    next_cursor: str | None = None
    trend: str
    ai_consent_required: bool = False
    message_code: str | None = None
