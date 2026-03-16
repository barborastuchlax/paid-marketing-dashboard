from pydantic import BaseModel
from typing import Optional


class NormalizedCampaign(BaseModel):
    campaign_name: str
    channel: str  # "google_ads", "linkedin_ads", or "meta_ads"
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: float = 0.0
    conversion_value: float = 0.0
    ctr: float = 0.0
    avg_cpc: float = 0.0
    cost_per_conversion: float = 0.0
    conversion_rate: float = 0.0
    # Ad copy fields (optional - populated if CSV contains them)
    headline: str = ""
    description: str = ""


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


class CopyAttribute(BaseModel):
    campaign_name: str
    channel: str = ""
    headline: str = ""
    description: str = ""
    hook_type: str = ""
    cta_type: str = ""
    tone: str = ""
    length_category: str = ""
    emotional_trigger: str = ""
    value_prop: str = ""
    ctr: Optional[float] = None
    conversion_rate: Optional[float] = None
    cpa: Optional[float] = None
    roas: Optional[float] = None
    spend: Optional[float] = None
    conversions: Optional[float] = None


class CopyPattern(BaseModel):
    attribute_type: str
    attribute_value: str
    avg_ctr: Optional[float] = None
    avg_conversion_rate: Optional[float] = None
    avg_cpa: Optional[float] = None
    sample_count: int = 0
    performance_label: str = ""


class CopyInsight(BaseModel):
    insight: str
    priority: str = "medium"
    supporting_data: str = ""


class CopyAnalysisResult(BaseModel):
    ads_analyzed: int = 0
    copy_attributes: list[CopyAttribute] = []
    patterns: list[CopyPattern] = []
    insights: list[CopyInsight] = []
    top_performing_copy: list[dict] = []
    recommendations: list[str] = []


class AnalysisResult(BaseModel):
    summary: ChannelMetrics
    by_channel: dict[str, ChannelMetrics]
    by_campaign: list[dict]
    scorecard: ScorecardResult
    recommendations: list[Recommendation]
    cac: Optional[float] = None
    ltv_cac_ratio: Optional[float] = None
    mer: Optional[float] = None


class DemographicEntry(BaseModel):
    value: str
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: float = 0.0
    ctr: float = 0.0


class DemographicsData(BaseModel):
    age: list[DemographicEntry] = []
    job_function: list[DemographicEntry] = []
    seniority: list[DemographicEntry] = []
    industry: list[DemographicEntry] = []
    company_size: list[DemographicEntry] = []
