from backend.models import Recommendation


def generate_recommendations(metrics: dict, avg_ltv: float = 0) -> list[Recommendation]:
    recs = []
    summary = metrics['summary']
    by_channel = metrics['by_channel']
    by_campaign = metrics['by_campaign']
    ltv_cac_ratio = metrics.get('ltv_cac_ratio')

    campaigns_with_conversions = [c for c in by_campaign if c['conversions'] > 0]

    # 1. Cross-channel CPA disparity
    if len(by_channel) == 2:
        channels = list(by_channel.items())
        ch1_name, ch1 = channels[0]
        ch2_name, ch2 = channels[1]
        if ch1.blended_cpa and ch2.blended_cpa and ch1.blended_cpa > 0 and ch2.blended_cpa > 0:
            ratio = max(ch1.blended_cpa, ch2.blended_cpa) / min(ch1.blended_cpa, ch2.blended_cpa)
            if ratio > 1.5:
                expensive = ch1_name if ch1.blended_cpa > ch2.blended_cpa else ch2_name
                cheaper = ch2_name if expensive == ch1_name else ch1_name
                exp_cpa = max(ch1.blended_cpa, ch2.blended_cpa)
                chp_cpa = min(ch1.blended_cpa, ch2.blended_cpa)
                recs.append(Recommendation(
                    priority='high',
                    category='efficiency',
                    title=f'Reduce {_channel_label(expensive)} CPA',
                    detail=f'{_channel_label(expensive)} CPA (${exp_cpa:,.2f}) is {ratio:.1f}x higher than {_channel_label(cheaper)} (${chp_cpa:,.2f}). Consider shifting budget toward {_channel_label(cheaper)} or optimizing {_channel_label(expensive)} targeting and creatives.',
                    metric_ref='cpa',
                    affected_campaigns=[],
                    potential_impact=f'Could save ${(exp_cpa - chp_cpa) * by_channel[expensive].total_conversions:,.0f} at equal CPA',
                ))

    # 2. High-spend low-conversion campaigns
    for c in by_campaign:
        if summary.total_spend > 0 and summary.total_conversions > 0:
            spend_share = c['spend'] / summary.total_spend
            conv_share = c['conversions'] / summary.total_conversions if summary.total_conversions > 0 else 0
            if spend_share > 0.15 and conv_share < 0.05 and c['spend'] > 0:
                recs.append(Recommendation(
                    priority='high',
                    category='efficiency',
                    title=f'Review underperforming campaign: {c["campaign_name"][:40]}',
                    detail=f'This campaign uses {spend_share:.0%} of total budget but generates only {conv_share:.0%} of conversions. Consider pausing, restructuring audiences, or refreshing creatives.',
                    metric_ref='cpa',
                    affected_campaigns=[c['campaign_name']],
                    potential_impact=f'${c["spend"]:,.2f} at risk',
                ))

    # 3. ROAS below breakeven
    for c in by_campaign:
        if c.get('roas') is not None and c['roas'] < 1.0 and c['spend'] > 50:
            recs.append(Recommendation(
                priority='high',
                category='efficiency',
                title=f'Negative ROAS on: {c["campaign_name"][:40]}',
                detail=f'ROAS is {c["roas"]:.2f}x — you\'re spending more than you\'re earning. Evaluate if this campaign serves a brand awareness purpose; otherwise consider pausing.',
                metric_ref='roas',
                affected_campaigns=[c['campaign_name']],
                potential_impact=f'${c["spend"] - c["conversion_value"]:,.2f} in losses',
            ))

    # 4. Low CTR campaigns (compare within each channel)
    for ch_name, ch_metrics in by_channel.items():
        if ch_metrics.blended_ctr and ch_metrics.blended_ctr > 0:
            ch_avg_ctr = ch_metrics.blended_ctr
            ch_campaigns = [c for c in by_campaign if c['channel'] == ch_name]
            for c in ch_campaigns:
                if c['ctr'] < ch_avg_ctr * 0.5 and c['impressions'] > 1000:
                    recs.append(Recommendation(
                        priority='medium',
                        category='performance',
                        title=f'Low CTR: {c["campaign_name"][:40]}',
                        detail=f'CTR ({c["ctr"]*100:.2f}%) is less than half the {_channel_label(ch_name)} average ({ch_avg_ctr*100:.2f}%). Consider refreshing ad copy, testing new headlines, or tightening audience targeting.',
                        metric_ref='ctr',
                        affected_campaigns=[c['campaign_name']],
                    ))

    # 5. Good CTR but low conversion rate (landing page issue)
    if summary.blended_ctr and summary.blended_conversion_rate:
        for c in by_campaign:
            if (c['ctr'] > summary.blended_ctr and
                c['conversion_rate'] < summary.blended_conversion_rate * 0.5 and
                c['clicks'] > 50):
                recs.append(Recommendation(
                    priority='medium',
                    category='performance',
                    title=f'Landing page issue: {c["campaign_name"][:40]}',
                    detail=f'Good CTR ({c["ctr"]*100:.2f}%) but low conversion rate ({c["conversion_rate"]*100:.2f}%). People are clicking but not converting — review landing page experience, load speed, and offer relevance.',
                    metric_ref='conversion_rate',
                    affected_campaigns=[c['campaign_name']],
                ))

    # 6. High CPC campaigns (compare within each channel since cross-channel CPC varies naturally)
    for ch_name, ch_metrics in by_channel.items():
        if ch_metrics.avg_cpc and ch_metrics.avg_cpc > 0:
            ch_campaigns = [c for c in by_campaign if c['channel'] == ch_name]
            for c in ch_campaigns:
                if c['avg_cpc'] > ch_metrics.avg_cpc * 2 and c['clicks'] > 20:
                    tip = 'keyword quality scores and bid strategy' if ch_name == 'google_ads' else 'audience targeting and bid caps'
                    recs.append(Recommendation(
                        priority='medium',
                        category='performance',
                        title=f'High CPC: {c["campaign_name"][:40]}',
                        detail=f'CPC (${c["avg_cpc"]:.2f}) is more than 2x the {_channel_label(ch_name)} average (${ch_metrics.avg_cpc:.2f}). Review {tip}.',
                        metric_ref='cpa',
                        affected_campaigns=[c['campaign_name']],
                    ))

    # 7. LTV:CAC below 3:1
    if ltv_cac_ratio is not None and ltv_cac_ratio < 3.0:
        recs.append(Recommendation(
            priority='high',
            category='strategy',
            title='LTV:CAC ratio below healthy threshold',
            detail=f'Your LTV:CAC ratio is {ltv_cac_ratio:.1f}:1 (target: 3:1+). Either reduce acquisition costs through better targeting and optimization, or work on increasing customer lifetime value through retention and upsell programs.',
            metric_ref='ltv_cac_ratio',
        ))

    # 8. Channel concentration risk
    if len(by_channel) == 2:
        for ch_name, ch_metrics in by_channel.items():
            if summary.total_spend > 0:
                share = ch_metrics.total_spend / summary.total_spend
                if share > 0.80:
                    recs.append(Recommendation(
                        priority='low',
                        category='strategy',
                        title=f'Heavy reliance on {_channel_label(ch_name)}',
                        detail=f'{share:.0%} of your budget is on {_channel_label(ch_name)}. Consider testing more budget on the other channel to diversify risk and discover new audiences.',
                        metric_ref='spend',
                    ))
    elif len(by_channel) == 1:
        ch_name = list(by_channel.keys())[0]
        recs.append(Recommendation(
            priority='low',
            category='strategy',
            title='Single-channel risk',
            detail=f'All spend is on {_channel_label(ch_name)}. Consider testing the other platform to diversify your acquisition channels.',
            metric_ref='spend',
        ))

    # 9. Missing conversion value tracking
    has_conv_value = any(c['conversion_value'] > 0 for c in by_campaign)
    if not has_conv_value and campaigns_with_conversions:
        recs.append(Recommendation(
            priority='medium',
            category='strategy',
            title='Set up conversion value tracking',
            detail='No conversion values detected. Without value data, ROAS cannot be calculated and you\'re optimizing blind. Implement value-based conversion tracking to enable revenue-based optimization.',
            metric_ref='roas',
        ))

    # 10. Budget reallocation opportunity
    if len(campaigns_with_conversions) >= 2:
        best = min(campaigns_with_conversions, key=lambda c: c['cpa'])
        worst = max(campaigns_with_conversions, key=lambda c: c['cpa'])
        if best['cpa'] > 0 and worst['cpa'] / best['cpa'] > 2 and summary.total_spend > 0:
            best_share = best['spend'] / summary.total_spend
            if best_share < 0.25:
                recs.append(Recommendation(
                    priority='high',
                    category='budget',
                    title=f'Increase budget for top performer',
                    detail=f'"{best["campaign_name"][:35]}" has the best CPA (${best["cpa"]:,.2f}) but only {best_share:.0%} of budget. Meanwhile "{worst["campaign_name"][:35]}" has CPA of ${worst["cpa"]:,.2f}. Reallocating budget could significantly improve overall efficiency.',
                    metric_ref='cpa',
                    affected_campaigns=[best['campaign_name'], worst['campaign_name']],
                    potential_impact=f'Up to ${(worst["cpa"] - best["cpa"]) * worst["conversions"]:,.0f} in savings',
                ))

    # 11. Diminishing returns signal
    if campaigns_with_conversions:
        top_spender = max(campaigns_with_conversions, key=lambda c: c['spend'])
        if len(campaigns_with_conversions) > 1:
            cpas = [c['cpa'] for c in campaigns_with_conversions if c['conversions'] >= 10]
            if cpas and top_spender['conversions'] >= 10 and top_spender['cpa'] == max(cpas):
                recs.append(Recommendation(
                    priority='medium',
                    category='budget',
                    title=f'Possible saturation: {top_spender["campaign_name"][:40]}',
                    detail=f'Your highest-spend campaign also has the worst CPA (${top_spender["cpa"]:,.2f}), suggesting diminishing returns. Consider capping its budget and redistributing to better-performing campaigns.',
                    metric_ref='cpa',
                    affected_campaigns=[top_spender['campaign_name']],
                ))

    # Sort by priority
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    recs.sort(key=lambda r: priority_order.get(r.priority, 3))

    return recs


def _channel_label(channel: str) -> str:
    labels = {
        'google_ads': 'Google Ads',
        'linkedin_ads': 'LinkedIn Ads',
    }
    return labels.get(channel, channel)
