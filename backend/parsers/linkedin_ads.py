import pandas as pd
import io
from backend.models import NormalizedCampaign

COLUMN_MAP = {
    'campaign name': 'campaign_name',
    'campaign': 'campaign_name',
    'campaign group': 'campaign_group',
    'campaign group name': 'campaign_group',
    'impressions': 'impressions',
    'clicks': 'clicks',
    'average ctr': 'ctr',
    'ctr': 'ctr',
    'average cpc': 'avg_cpc',
    'avg. cpc': 'avg_cpc',
    'total spent': 'spend',
    'amount spent': 'spend',
    'cost': 'spend',
    'spend': 'spend',
    'conversions': 'conversions',
    'external conversions': 'conversions',
    'cost per conversion': 'cost_per_conversion',
    'leads': 'leads',
    'lead form opens': 'lead_form_opens',
    'lead form completions': 'lead_form_completions',
    'total engagement': 'total_engagement',
    'engagement rate': 'engagement_rate',
    'conversion rate': 'conversion_rate',
    'conv. rate': 'conversion_rate',
}


def clean_numeric(val) -> float:
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = s.replace('$', '').replace('€', '').replace('£', '').replace(',', '')
    is_pct = s.endswith('%')
    s = s.replace('%', '').strip()
    if s in ('--', '-', '', 'N/A', 'n/a'):
        return 0.0
    try:
        v = float(s)
        if is_pct:
            v = v / 100.0
        return v
    except ValueError:
        return 0.0


def parse(file_content: bytes) -> list[NormalizedCampaign]:
    # Try multiple encodings — LinkedIn exports can be UTF-8, UTF-8-BOM, or UTF-16
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

    # Map columns
    col_mapping = {}
    for col in df.columns:
        key = col.lower().strip()
        if key in COLUMN_MAP:
            col_mapping[col] = COLUMN_MAP[key]

    df = df.rename(columns=col_mapping)

    if 'campaign_name' not in df.columns:
        raise ValueError("Could not find 'Campaign Name' column in LinkedIn Ads CSV. Please ensure your export includes campaign names.")

    df = df.dropna(subset=['campaign_name'])

    # Clean numeric columns
    numeric_cols = ['impressions', 'clicks', 'spend', 'conversions',
                    'ctr', 'avg_cpc', 'cost_per_conversion', 'conversion_rate',
                    'leads', 'lead_form_completions']

    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)

    # If no conversions column but leads exist, use lead_form_completions or leads
    if 'conversions' not in df.columns or df.get('conversions', pd.Series([0])).sum() == 0:
        if 'lead_form_completions' in df.columns:
            df['conversions'] = df['lead_form_completions']
        elif 'leads' in df.columns:
            df['conversions'] = df['leads']

    # Normalize CTR — detect if it's already a decimal or a percentage
    if 'ctr' in df.columns:
        max_ctr = df['ctr'].max()
        if max_ctr > 1:  # likely percentages that weren't caught
            df['ctr'] = df['ctr'] / 100.0

    # Aggregate by campaign (LinkedIn exports can have daily rows)
    sum_cols = {c: 'sum' for c in ['impressions', 'clicks', 'spend', 'conversions'] if c in df.columns}
    if sum_cols:
        grouped = df.groupby('campaign_name', as_index=False).agg(sum_cols)
    else:
        grouped = df[['campaign_name']].drop_duplicates()
        for c in ['impressions', 'clicks', 'spend', 'conversions']:
            if c not in grouped.columns:
                grouped[c] = 0

    campaigns = []
    for _, row in grouped.iterrows():
        impr = int(row.get('impressions', 0))
        clicks = int(row.get('clicks', 0))
        spend = float(row.get('spend', 0))
        convs = float(row.get('conversions', 0))

        ctr = clicks / impr if impr > 0 else 0.0
        avg_cpc = spend / clicks if clicks > 0 else 0.0
        cpa = spend / convs if convs > 0 else 0.0
        conv_rate = convs / clicks if clicks > 0 else 0.0

        campaigns.append(NormalizedCampaign(
            campaign_name=str(row['campaign_name']),
            channel='linkedin_ads',
            impressions=impr,
            clicks=clicks,
            spend=spend,
            conversions=convs,
            conversion_value=0.0,  # LinkedIn doesn't typically export conversion values
            ctr=ctr,
            avg_cpc=avg_cpc,
            cost_per_conversion=cpa,
            conversion_rate=conv_rate,
        ))

    return campaigns
