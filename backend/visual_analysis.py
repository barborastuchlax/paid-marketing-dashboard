import json
import os
import base64
from backend.models import (
    VisualAttribute, VisualPattern, VisualInsight, VisualAnalysisResult,
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

VISUAL_ANALYSIS_PROMPT = """You are an expert creative strategist and performance marketing analyst specializing in ad creative analysis.

Analyze the following ad creatives (images and/or video thumbnails) from paid marketing campaigns. Each creative is labeled with its campaign name and performance metrics.

Campaign data with visuals:
{campaigns_json}

For each visual creative, classify:
1. visual_style: One of: minimal, bold_graphic, photographic, illustration, video_thumbnail, text_heavy, product_focused, lifestyle, abstract, meme_style
2. color_scheme: One of: bright_vibrant, dark_moody, neutral_corporate, warm_tones, cool_tones, high_contrast, monochrome, brand_colors, pastel, neon
3. imagery_type: One of: people_faces, people_action, product_only, product_in_use, abstract_shapes, icons_graphics, screenshot, landscape, data_chart, text_only
4. text_overlay: One of: none, headline_only, headline_subtext, full_copy, cta_only, minimal_badge, stats_numbers
5. cta_visual: One of: button, text_link, arrow, banner, none, implied, overlay
6. composition: One of: centered, rule_of_thirds, left_aligned, split_layout, full_bleed, framed, layered, asymmetric
7. brand_presence: One of: logo_prominent, logo_subtle, brand_colors_only, no_branding, watermark
8. emotional_feel: One of: trustworthy, exciting, calming, urgent, professional, playful, premium, relatable, bold, inspiring

Then analyze patterns:
- Which visual styles correlate with the highest CTR?
- Which color schemes drive the best conversion rates?
- Which imagery types lead to the lowest CPA?
- How do text overlays impact performance?
- For video thumbnails: what elements drive clicks?
- Cross-channel comparisons if multiple channels present.

Provide 3-5 actionable insights about visual creative performance.

Respond with ONLY valid JSON in this exact format:
{{
    "visual_classifications": [
        {{
            "campaign_name": "exact campaign name",
            "visual_style": "...",
            "color_scheme": "...",
            "imagery_type": "...",
            "text_overlay": "...",
            "cta_visual": "...",
            "composition": "...",
            "brand_presence": "...",
            "emotional_feel": "...",
            "description": "Brief 1-sentence description of what the creative shows"
        }}
    ],
    "patterns": [
        {{
            "attribute_type": "visual_style|color_scheme|imagery_type|text_overlay|cta_visual|composition|emotional_feel",
            "attribute_value": "the specific value",
            "avg_ctr_pct": 2.5,
            "avg_conversion_rate_pct": 4.1,
            "sample_count": 3,
            "performance_label": "top_performer|average|underperformer"
        }}
    ],
    "insights": [
        {{
            "insight": "Clear, actionable insight about visual creative performance",
            "priority": "high|medium|low",
            "supporting_data": "Brief data point supporting this insight"
        }}
    ],
    "recommendations": [
        "Specific visual creative recommendation 1",
        "Specific visual creative recommendation 2"
    ]
}}"""


async def analyze_visuals(
    visuals_data: list[dict],
    campaign_metrics: dict,
) -> VisualAnalysisResult:
    """Analyze visual ad creatives using Claude Vision API.

    visuals_data: list of {campaign_name, image_base64, media_type, video_url}
    campaign_metrics: dict mapping campaign_name -> {ctr, conversion_rate, cpa, spend, ...}
    """
    if not visuals_data:
        return VisualAnalysisResult(
            visuals_analyzed=0,
            insights=[VisualInsight(
                insight="No visual creatives uploaded. Drag screenshots onto campaign rows in the Report tab to analyze your ad visuals.",
                priority="high",
            )],
        )

    if not ANTHROPIC_API_KEY:
        return VisualAnalysisResult(
            visuals_analyzed=0,
            insights=[VisualInsight(
                insight="Visual analysis requires an Anthropic API key. Please set ANTHROPIC_API_KEY.",
                priority="high",
            )],
        )

    # Build campaign info for the prompt
    campaigns_info = []
    for v in visuals_data:
        cname = v['campaign_name']
        metrics = campaign_metrics.get(cname, {})
        info = {
            'campaign_name': cname,
            'channel': metrics.get('channel', ''),
            'has_image': bool(v.get('image_base64')),
            'has_video_link': bool(v.get('video_url')),
            'ctr_pct': metrics.get('ctr_pct'),
            'conversion_rate_pct': metrics.get('conversion_rate_pct'),
            'cpa': metrics.get('cpa'),
            'spend': metrics.get('spend'),
            'conversions': metrics.get('conversions'),
        }
        campaigns_info.append(info)

    # Build Claude messages with images
    content_blocks = []

    # Add text prompt
    prompt_text = VISUAL_ANALYSIS_PROMPT.format(
        campaigns_json=json.dumps(campaigns_info, indent=2)
    )
    content_blocks.append({"type": "text", "text": prompt_text})

    # Add images
    for v in visuals_data:
        if v.get('image_base64'):
            # Add label for this image
            content_blocks.append({
                "type": "text",
                "text": f"\n--- Creative for campaign: {v['campaign_name']} ---"
            })
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": v.get('media_type', 'image/png'),
                    "data": v['image_base64'],
                }
            })
        elif v.get('video_url'):
            content_blocks.append({
                "type": "text",
                "text": f"\n--- Video creative for campaign: {v['campaign_name']} (link: {v['video_url']}) - Please analyze based on context and performance data ---"
            })

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": content_blocks}],
        )

        response_text = message.content[0].text
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]

        result_data = json.loads(response_text.strip())
    except Exception as e:
        return VisualAnalysisResult(
            visuals_analyzed=len(visuals_data),
            insights=[VisualInsight(
                insight=f"Visual analysis error: {str(e)}",
                priority="high",
            )],
        )

    # Build VisualAttribute objects
    classifications = {c['campaign_name']: c for c in result_data.get('visual_classifications', [])}
    visual_attributes = []
    for v in visuals_data:
        cname = v['campaign_name']
        cls = classifications.get(cname, {})
        metrics = campaign_metrics.get(cname, {})

        visual_attributes.append(VisualAttribute(
            campaign_name=cname,
            channel=metrics.get('channel', ''),
            has_image=bool(v.get('image_base64')),
            has_video=bool(v.get('video_url')),
            video_url=v.get('video_url', ''),
            visual_style=cls.get('visual_style', ''),
            color_scheme=cls.get('color_scheme', ''),
            imagery_type=cls.get('imagery_type', ''),
            text_overlay=cls.get('text_overlay', ''),
            cta_visual=cls.get('cta_visual', ''),
            composition=cls.get('composition', ''),
            brand_presence=cls.get('brand_presence', ''),
            emotional_feel=cls.get('emotional_feel', ''),
            creative_description=cls.get('description', ''),
            ctr=metrics.get('ctr_pct'),
            conversion_rate=metrics.get('conversion_rate_pct'),
            cpa=metrics.get('cpa'),
            spend=metrics.get('spend'),
            conversions=metrics.get('conversions'),
        ))

    # Build patterns
    patterns = []
    for p in result_data.get('patterns', []):
        patterns.append(VisualPattern(
            attribute_type=p.get('attribute_type', ''),
            attribute_value=p.get('attribute_value', ''),
            avg_ctr=p.get('avg_ctr_pct'),
            avg_conversion_rate=p.get('avg_conversion_rate_pct'),
            sample_count=p.get('sample_count', 0),
            performance_label=p.get('performance_label', ''),
        ))

    # Build insights
    insights = []
    for i in result_data.get('insights', []):
        insights.append(VisualInsight(
            insight=i.get('insight', ''),
            priority=i.get('priority', 'medium'),
            supporting_data=i.get('supporting_data', ''),
        ))

    # Top performing visuals (by CTR)
    top_visuals = sorted(
        [a for a in visual_attributes if a.ctr is not None],
        key=lambda a: a.ctr or 0,
        reverse=True,
    )[:5]

    return VisualAnalysisResult(
        visuals_analyzed=len(visuals_data),
        visual_attributes=visual_attributes,
        patterns=patterns,
        insights=insights,
        top_performing_visuals=[v.model_dump() for v in top_visuals],
        recommendations=result_data.get('recommendations', []),
    )
