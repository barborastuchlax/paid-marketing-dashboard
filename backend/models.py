from pydantic import BaseModel
from typing import Optional


class NormalizedCampaign(BaseModel):
    campaign_name: str
    channel: str  # "google_ads" or "linkedin_ads"
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: float = 0.0
    conversion_value: float = 0.0
    ctr: float = 0.0
    avg_cpc: float = 0.0
    cost_per_conversion: float = 0.0
    conversion_rate: float = 0.0


class MetricGrade(BaseModel):
    value: Optional[float] = None
    grade: str = "N/A"
    score: int = 0
    label: str = "Insufficient Data"


class ScorecardResult(BaseModel):
    overall_grade: str
    overall_score: int
    grades: dict[str, MetricGrade]


class Recommendation(BaseModel):
    priority: str  # high, medium, low
    category: str  # efficiency, performance, strategy, budget
    title: str
    detail: str
    metric_ref: str
    affected_campaigns: list[str] = []
    potential_impact: str = ""


class ChannelMetrics(BaseModel):
    total_spend: float = 0
    total_conversions: float = 0
    total_clicks: int = 0
    total_impressions: int = 0
    blended_cpa: Optional[float] = None
    blended_ctr: Optional[float] = None
    blended_roas: Optional[float] = None
    blended_conversion_rate: Optional[float] = None
    cpm: Optional[float] = None
    avg_cpc: Optional[float] = None
    conversion_value: float = 0


class AnalysisResult(BaseModel):
    summary: ChannelMetrics
    by_channel: dict[str, ChannelMetrics]
    by_campaign: list[dict]
    scorecard: ScorecardResult
    recommendations: list[Recommendation]
    cac: Optional[float] = None
    ltv_cac_ratio: Optional[float] = None
    mer: Optional[float] = None
