from backend.models import NormalizedCampaign, ChannelMetrics


def compute_channel_metrics(campaigns: list[NormalizedCampaign]) -> ChannelMetrics:
    if not campaigns:
        return ChannelMetrics()

    total_impressions = sum(c.impressions for c in campaigns)
    total_clicks = sum(c.clicks for c in campaigns)
    total_spend = sum(c.spend for c in campaigns)
    total_conversions = sum(c.conversions for c in campaigns)
    total_conv_value = sum(c.conversion_value for c in campaigns)

    return ChannelMetrics(
        total_spend=round(total_spend, 2),
        total_conversions=round(total_conversions, 2),
        total_clicks=total_clicks,
        total_impressions=total_impressions,
        blended_cpa=round(total_spend / total_conversions, 2) if total_conversions > 0 else None,
        blended_ctr=round(total_clicks / total_impressions, 4) if total_impressions > 0 else None,
        blended_roas=round(total_conv_value / total_spend, 2) if total_spend > 0 and total_conv_value > 0 else None,
        blended_conversion_rate=round(total_conversions / total_clicks, 4) if total_clicks > 0 else None,
        cpm=round((total_spend / total_impressions) * 1000, 2) if total_impressions > 0 else None,
        avg_cpc=round(total_spend / total_clicks, 2) if total_clicks > 0 else None,
        conversion_value=round(total_conv_value, 2),
    )


def calculate_all_metrics(
    campaigns: list[NormalizedCampaign],
    avg_ltv: float = 0,
    monthly_revenue: float = 0,
) -> dict:
    # Split by channel
    google = [c for c in campaigns if c.channel == 'google_ads']
    linkedin = [c for c in campaigns if c.channel == 'linkedin_ads']

    summary = compute_channel_metrics(campaigns)
    by_channel = {}
    if google:
        by_channel['google_ads'] = compute_channel_metrics(google)
    if linkedin:
        by_channel['linkedin_ads'] = compute_channel_metrics(linkedin)

    # Per-campaign data
    by_campaign = []
    for c in campaigns:
        by_campaign.append({
            'campaign_name': c.campaign_name,
            'channel': c.channel,
            'impressions': c.impressions,
            'clicks': c.clicks,
            'spend': round(c.spend, 2),
            'conversions': round(c.conversions, 2),
            'conversion_value': round(c.conversion_value, 2),
            'ctr': round(c.ctr, 4),
            'avg_cpc': round(c.avg_cpc, 2),
            'cpa': round(c.cost_per_conversion, 2),
            'conversion_rate': round(c.conversion_rate, 4),
            'roas': round(c.conversion_value / c.spend, 2) if c.spend > 0 and c.conversion_value > 0 else None,
            'spend_share': round(c.spend / summary.total_spend, 4) if summary.total_spend > 0 else 0,
            'cpm': round((c.spend / c.impressions) * 1000, 2) if c.impressions > 0 else None,
        })

    # Sort by spend descending
    by_campaign.sort(key=lambda x: x['spend'], reverse=True)

    # CAC and LTV:CAC
    cac = summary.blended_cpa
    ltv_cac_ratio = round(avg_ltv / cac, 2) if cac and avg_ltv > 0 else None

    # MER
    mer = round(monthly_revenue / summary.total_spend, 2) if summary.total_spend > 0 and monthly_revenue > 0 else None

    return {
        'summary': summary,
        'by_channel': by_channel,
        'by_campaign': by_campaign,
        'cac': cac,
        'ltv_cac_ratio': ltv_cac_ratio,
        'mer': mer,
    }
