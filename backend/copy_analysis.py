import json
import os
import io
import pandas as pd
from backend.models import (
    NormalizedCampaign, CopyAttribute, CopyPattern,
    CopyInsight, CopyAnalysisResult,
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ANALYSIS_PROMPT = """You are an expert paid media copywriter and performance marketing analyst.

Analyze the following ad copy from paid marketing campaigns and their performance metrics.
For each ad, classify the copy attributes and then identify patterns that correlate with performance.

Here are the ads to analyze:

{ads_json}

For each ad, determine:
1. hook_type: One of: question, stat, bold_claim, pain_point, social_proof, benefit, curiosity, offer, story, none
2. cta_type: One of: urgency, soft, benefit_driven, direct, none
3. tone: One of: casual, professional, emotional, humorous, authoritative, conversational, aspirational
4. length_category: short (under 10 words total), medium (10-25 words), long (25+ words)
5. emotional_trigger: One of: fear, aspiration, curiosity, fomo, trust, empathy, excitement, relief, none
6. value_prop: One of: price, quality, convenience, exclusivity, results, innovation, community, time_saving, none

Then analyze patterns:
- Which hook types correlate with the highest CTR?
- Which tones drive the best conversion rates?
- Which emotional triggers lead to the lowest CPA?
- Any other notable patterns.

Provide 3-5 actionable insights about what's working and what should change.

Respond with ONLY valid JSON in this exact format:
{{
    "ad_classifications": [
        {{
            "campaign_name": "exact campaign name",
            "hook_type": "...",
            "cta_type": "...",
            "tone": "...",
            "length_category": "...",
            "emotional_trigger": "...",
            "value_prop": "..."
        }}
    ],
    "patterns": [
        {{
            "attribute_type": "hook_type|tone|cta_type|emotional_trigger|value_prop",
            "attribute_value": "the specific value",
            "avg_ctr_pct": 2.5,
            "avg_conversion_rate_pct": 4.1,
            "sample_count": 3,
            "performance_label": "top_performer|average|underperformer"
        }}
    ],
    "insights": [
        {{
            "insight": "Clear, actionable insight about the copy performance",
            "priority": "high|medium|low",
            "supporting_data": "Brief data point supporting this insight"
        }}
    ],
    "recommendations": [
        "Specific recommendation 1",
        "Specific recommendation 2"
    ]
}}"""

FREEFORM_PARSE_PROMPT = """You are a data extraction assistant. The user has pasted ad copy text in a free-form format. Extract structured ad copy data from it.

Here are the campaign names from their ad platform data:
{campaign_names}

Here is the text they pasted:
---
{raw_text}
---

Extract each ad's copy and try to match it to the campaign names above. If an ad doesn't clearly match a campaign, use whatever name/label was provided in the text.

Respond with ONLY valid JSON in this exact format:
{{
    "ads": [
        {{
            "campaign_name": "matched or provided campaign name",
            "headline": "the ad headline",
            "description": "the ad description/body copy"
        }}
    ]
}}"""


# ── Creatives CSV parser ──────────────────────────────────────────────────

CREATIVES_COLUMN_MAP = {
    'campaign': 'campaign_name',
    'campaign name': 'campaign_name',
    'campaign_name': 'campaign_name',
    'headline': 'headline',
    'headline 1': 'headline',
    'headlines': 'headline',
    'ad name': 'headline',
    'creative name': 'headline',
    'description': 'description',
    'description 1': 'description',
    'description line 1': 'description',
    'ad copy': 'description',
    'intro text': 'description',
    'introductory text': 'description',
    'body': 'description',
    'text': 'description',
    'primary text': 'description',
}


def _parse_creatives_csv(file_content: bytes) -> dict[str, dict]:
    """Parse a dedicated creatives CSV file. Returns {campaign_name: {headline, description}}."""
    result = {}
    for encoding in ('utf-8-sig', 'utf-16', 'latin-1'):
        try:
            text = file_content.decode(encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        text = file_content.decode('utf-8', errors='replace')

    df = pd.read_csv(io.StringIO(text))
    df.columns = df.columns.str.strip()

    col_mapping = {}
    for col in df.columns:
        key = col.lower().strip()
        if key in CREATIVES_COLUMN_MAP:
            col_mapping[col] = CREATIVES_COLUMN_MAP[key]

    df = df.rename(columns=col_mapping)

    if 'campaign_name' not in df.columns:
        raise ValueError("Creatives CSV must include a 'Campaign' or 'Campaign Name' column.")

    for _, row in df.iterrows():
        cname = str(row.get('campaign_name', '')).strip()
        if not cname or cname.lower() in ('nan', ''):
            continue

        headline = str(row.get('headline', '')).strip() if 'headline' in df.columns else ''
        description = str(row.get('description', '')).strip() if 'description' in df.columns else ''

        if headline.lower() == 'nan':
            headline = ''
        if description.lower() == 'nan':
            description = ''

        if headline or description:
            if cname not in result or (not result[cname].get('headline') and headline):
                result[cname] = {'headline': headline, 'description': description}

    return result


# ── Free-form text parser (AI-powered) ────────────────────────────────────

def _parse_freeform_with_ai(raw_text: str, campaign_names: list[str]) -> dict[str, dict]:
    """Use Claude to parse free-form ad copy text and match to campaigns."""
    if not raw_text or not raw_text.strip():
        return {}

    if not ANTHROPIC_API_KEY:
        return {}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        prompt = FREEFORM_PARSE_PROMPT.format(
            campaign_names=json.dumps(campaign_names),
            raw_text=raw_text,
        )

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]

        data = json.loads(response_text.strip())
        result = {}
        for ad in data.get('ads', []):
            cname = ad.get('campaign_name', '')
            if cname:
                result[cname] = {
                    'headline': ad.get('headline', ''),
                    'description': ad.get('description', ''),
                }
        return result
    except Exception:
        return {}


# ── Merge copy sources with campaign performance data ─────────────────────

def _merge_copy_with_campaigns(
    campaigns: list[NormalizedCampaign],
    copy_sources: list[dict[str, dict]],
) -> list[dict]:
    """Build ad data list with copy + performance metrics.

    copy_sources is a list of dicts (in priority order) mapping campaign names to {headline, description}.
    Later sources override earlier ones.
    """
    # Build merged copy lookup: CSV fields first, then each source in order
    merged = {}
    for c in campaigns:
        if c.headline or c.description:
            merged[c.campaign_name] = {'headline': c.headline, 'description': c.description}

    for source in copy_sources:
        for name, copy in source.items():
            # Exact match
            if name in merged:
                if copy.get('headline'):
                    merged[name]['headline'] = copy['headline']
                if copy.get('description'):
                    merged[name]['description'] = copy['description']
            else:
                # Try fuzzy match against campaign names
                matched = False
                for c in campaigns:
                    if name.lower() in c.campaign_name.lower() or c.campaign_name.lower() in name.lower():
                        if c.campaign_name not in merged:
                            merged[c.campaign_name] = {'headline': '', 'description': ''}
                        if copy.get('headline'):
                            merged[c.campaign_name]['headline'] = copy['headline']
                        if copy.get('description'):
                            merged[c.campaign_name]['description'] = copy['description']
                        matched = True
                        break
                if not matched and (copy.get('headline') or copy.get('description')):
                    merged[name] = copy

    # Build output list with performance data
    ads = []
    campaign_lookup = {c.campaign_name: c for c in campaigns}

    for name, copy in merged.items():
        if not copy.get('headline') and not copy.get('description'):
            continue

        c = campaign_lookup.get(name)
        roas = None
        if c and c.spend > 0 and c.conversion_value > 0:
            roas = round(c.conversion_value / c.spend, 2)

        ads.append({
            'campaign_name': name,
            'channel': c.channel if c else '',
            'headline': copy.get('headline', ''),
            'description': copy.get('description', ''),
            'ctr_pct': round(c.ctr * 100, 2) if c else None,
            'conversion_rate_pct': round(c.conversion_rate * 100, 2) if c else None,
            'cpa': round(c.cost_per_conversion, 2) if c and c.cost_per_conversion > 0 else None,
            'roas': roas,
            'spend': round(c.spend, 2) if c else None,
            'conversions': round(c.conversions, 2) if c else None,
        })

    return ads


# ── Main entry point ──────────────────────────────────────────────────────

async def analyze_copy(
    campaigns: list[NormalizedCampaign],
    manual_copy_text: str = "",
    creatives_csv_content: bytes = None,
) -> CopyAnalysisResult:
    """Analyze ad copy using Claude API and correlate with performance metrics."""
    copy_sources = []

    # Source 1: Creatives CSV
    if creatives_csv_content:
        try:
            creatives_data = _parse_creatives_csv(creatives_csv_content)
            if creatives_data:
                copy_sources.append(creatives_data)
        except Exception:
            pass

    # Source 2: Free-form text (AI-parsed if not pipe-delimited)
    if manual_copy_text and manual_copy_text.strip():
        # Check if it looks like pipe-delimited format (backward compat)
        lines = [l.strip() for l in manual_copy_text.strip().split('\n') if l.strip() and not l.strip().startswith('#')]
        is_pipe_format = all('|' in l for l in lines) if lines else False

        if is_pipe_format:
            parsed = {}
            for line in lines:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 2:
                    parsed[parts[0]] = {
                        'headline': parts[1] if len(parts) >= 2 else '',
                        'description': parts[2] if len(parts) >= 3 else '',
                    }
            if parsed:
                copy_sources.append(parsed)
        else:
            # Use AI to parse free-form text
            campaign_names = [c.campaign_name for c in campaigns]
            ai_parsed = _parse_freeform_with_ai(manual_copy_text, campaign_names)
            if ai_parsed:
                copy_sources.append(ai_parsed)

    ads = _merge_copy_with_campaigns(campaigns, copy_sources)

    if not ads:
        return CopyAnalysisResult(
            ads_analyzed=0,
            insights=[CopyInsight(
                insight="No ad copy found. To use Copy Analysis, upload a Creatives CSV, include headline/description columns in your ad platform exports, or paste your ad copy in the text area.",
                priority="high",
            )],
        )

    # Call Claude API for analysis
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        prompt = ANALYSIS_PROMPT.format(ads_json=json.dumps(ads, indent=2))

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]

        result_data = json.loads(response_text.strip())
    except Exception as e:
        return CopyAnalysisResult(
            ads_analyzed=len(ads),
            insights=[CopyInsight(
                insight=f"AI analysis unavailable: {str(e)}. Showing raw copy data only.",
                priority="high",
            )],
            copy_attributes=[
                CopyAttribute(
                    campaign_name=ad['campaign_name'],
                    channel=ad['channel'],
                    headline=ad['headline'],
                    description=ad['description'],
                    ctr=ad['ctr_pct'],
                    conversion_rate=ad['conversion_rate_pct'],
                    cpa=ad['cpa'],
                    roas=ad['roas'],
                    spend=ad['spend'],
                    conversions=ad['conversions'],
                ) for ad in ads
            ],
        )

    # Build CopyAttribute objects by merging AI classifications with performance data
    classifications = {c['campaign_name']: c for c in result_data.get('ad_classifications', [])}
    copy_attributes = []
    for ad in ads:
        cls = classifications.get(ad['campaign_name'], {})
        copy_attributes.append(CopyAttribute(
            campaign_name=ad['campaign_name'],
            channel=ad['channel'],
            headline=ad['headline'],
            description=ad['description'],
            hook_type=cls.get('hook_type', ''),
            cta_type=cls.get('cta_type', ''),
            tone=cls.get('tone', ''),
            length_category=cls.get('length_category', ''),
            emotional_trigger=cls.get('emotional_trigger', ''),
            value_prop=cls.get('value_prop', ''),
            ctr=ad['ctr_pct'],
            conversion_rate=ad['conversion_rate_pct'],
            cpa=ad['cpa'],
            roas=ad['roas'],
            spend=ad['spend'],
            conversions=ad['conversions'],
        ))

    # Build patterns
    patterns = []
    for p in result_data.get('patterns', []):
        patterns.append(CopyPattern(
            attribute_type=p.get('attribute_type', ''),
            attribute_value=p.get('attribute_value', ''),
            avg_ctr=p.get('avg_ctr_pct'),
            avg_conversion_rate=p.get('avg_conversion_rate_pct'),
            avg_cpa=p.get('avg_cpa'),
            sample_count=p.get('sample_count', 0),
            performance_label=p.get('performance_label', ''),
        ))

    # Build insights
    insights = []
    for i in result_data.get('insights', []):
        insights.append(CopyInsight(
            insight=i.get('insight', ''),
            priority=i.get('priority', 'medium'),
            supporting_data=i.get('supporting_data', ''),
        ))

    # Identify top performing copy (sorted by CTR)
    top_copy = sorted(
        [a for a in ads if a.get('ctr_pct') is not None],
        key=lambda a: a.get('ctr_pct', 0),
        reverse=True,
    )[:5]

    return CopyAnalysisResult(
        ads_analyzed=len(ads),
        copy_attributes=copy_attributes,
        patterns=patterns,
        insights=insights,
        top_performing_copy=top_copy,
        recommendations=result_data.get('recommendations', []),
    )
