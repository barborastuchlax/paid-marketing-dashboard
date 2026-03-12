import pandas as pd
import io
import re
from backend.models import NormalizedCampaign

COLUMN_MAP = {
    'campaign': 'campaign_name',
    'campaign name': 'campaign_name',
    'ad group': 'ad_group',
    'impressions': 'impressions',
    'impr.': 'impressions',
    'clicks': 'clicks',
    'ctr': 'ctr',
    'avg. cpc': 'avg_cpc',
    'average cpc': 'avg_cpc',
    'cost': 'spend',
    'amount spent': 'spend',
    'spend': 'spend',
    'conversions': 'conversions',
    'cost / conv.': 'cost_per_conversion',
    'cost/conv.': 'cost_per_conversion',
    'conv. rate': 'conversion_rate',
    'conversion rate': 'conversion_rate',
    'conv. value': 'conversion_value',
    'conversion value': 'conversion_value',
    'total conv. value': 'conversion_value',
    'all conv.': 'all_conversions',
    'view-through conv.': 'view_through_conversions',
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


def find_header_row(content: str) -> int:
    """Google Ads exports often have metadata rows before the actual table."""
    lines = content.split('\n')
    for i, line in enumerate(lines):
        lower = line.lower()
        if 'campaign' in lower and ('impressions' in lower or 'clicks' in lower or 'cost' in lower):
            return i
    return 0


def parse(file_content: bytes) -> list[NormalizedCampaign]:
    text = file_content.decode('utf-8-sig')
    header_row = find_header_row(text)

    df = pd.read_csv(io.StringIO(text), skiprows=header_row)
    df.columns = df.columns.str.strip()

    # Map columns
    col_mapping = {}
    for col in df.columns:
        key = col.lower().strip()
        if key in COLUMN_MAP:
            col_mapping[col] = COLUMN_MAP[key]

    df = df.rename(columns=col_mapping)

    if 'campaign_name' not in df.columns:
        raise ValueError("Could not find 'Campaign' column in Google Ads CSV. Please ensure your export includes campaign names.")

    # Drop total/summary rows
    df = df[~df['campaign_name'].astype(str).str.lower().isin(['total', 'totals', ''])]
    df = df.dropna(subset=['campaign_name'])

    # Clean numeric columns
    numeric_cols = ['impressions', 'clicks', 'spend', 'conversions',
                    'conversion_value', 'ctr', 'avg_cpc',
                    'cost_per_conversion', 'conversion_rate']

    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)

    # Aggregate by campaign
    agg_cols = {c: 'sum' for c in ['impressions', 'clicks', 'spend', 'conversions', 'conversion_value'] if c in df.columns}
    if agg_cols:
        grouped = df.groupby('campaign_name', as_index=False).agg(agg_cols)
    else:
        grouped = df[['campaign_name']].drop_duplicates()
        for c in ['impressions', 'clicks', 'spend', 'conversions', 'conversion_value']:
            if c not in grouped.columns:
                grouped[c] = 0

    campaigns = []
    for _, row in grouped.iterrows():
        impr = int(row.get('impressions', 0))
        clicks = int(row.get('clicks', 0))
        spend = float(row.get('spend', 0))
        convs = float(row.get('conversions', 0))
        conv_val = float(row.get('conversion_value', 0))

        ctr = clicks / impr if impr > 0 else 0.0
        avg_cpc = spend / clicks if clicks > 0 else 0.0
        cpa = spend / convs if convs > 0 else 0.0
        conv_rate = convs / clicks if clicks > 0 else 0.0

        campaigns.append(NormalizedCampaign(
            campaign_name=str(row['campaign_name']),
            channel='google_ads',
            impressions=impr,
            clicks=clicks,
            spend=spend,
            conversions=convs,
            conversion_value=conv_val,
            ctr=ctr,
            avg_cpc=avg_cpc,
            cost_per_conversion=cpa,
            conversion_rate=conv_rate,
        ))

    return campaigns
