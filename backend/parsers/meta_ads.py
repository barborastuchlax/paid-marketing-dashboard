import csv
import pandas as pd
import io
from backend.models import NormalizedCampaign

COLUMN_MAP = {
    'campaign name': 'campaign_name',
    'campaign': 'campaign_name',
    'impressions': 'impressions',
    'clicks (all)': 'clicks',
    'link clicks': 'clicks',
    'clicks': 'clicks',
    'ctr (all)': 'ctr',
    'ctr (link click-through rate)': 'ctr',
    'ctr': 'ctr',
    'cpc (all)': 'avg_cpc',
    'cpc (cost per link click)': 'avg_cpc',
    'avg. cpc': 'avg_cpc',
    'average cpc': 'avg_cpc',
    'cpc': 'avg_cpc',
    'amount spent': 'spend',
    'amount spent (usd)': 'spend',
    'total spent': 'spend',
    'spend': 'spend',
    'cost': 'spend',
    'cost per result': 'cost_per_conversion',
    'cost per action type': 'cost_per_conversion',
    'cost per lead': 'cost_per_conversion',
    'results': 'conversions',
    'conversions': 'conversions',
    'leads': 'leads',
    'purchases': 'purchases',
    'website purchases': 'purchases',
    'purchase roas': 'roas',
    'website purchase roas': 'roas',
    'conversion rate': 'conversion_rate',
    'conversion value': 'conversion_value',
    'purchase value': 'conversion_value',
    'website purchases conversion value': 'conversion_value',
    'ad name': 'headline',
    'headline': 'headline',
    'body': 'description',
    'primary text': 'description',
    'description': 'description',
    'ad creative body': 'description',
    'ad creative link title': 'headline',
    'reach': 'reach',
    'frequency': 'frequency',
    'cpm (cost per 1,000 impressions)': 'cpm',
    'cpm': 'cpm',
}


def clean_numeric(val) -> float:
    if isinstance(val, pd.Series):
        val = val.iloc[0] if len(val) > 0 else 0
    try:
        if pd.isna(val):
            return 0.0
    except (ValueError, TypeError):
        pass
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
    # Try multiple encodings — Meta exports can be UTF-8, UTF-8-BOM, or UTF-16
    for encoding in ('utf-8-sig', 'utf-16', 'latin-1'):
        try:
            text = file_content.decode(encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        text = file_content.decode('utf-8', errors='replace')

    # Find the header row (Meta exports sometimes have metadata rows at the top)
    lines = text.strip().split('\n')
    header_row = 0
    for i, line in enumerate(lines):
        lower = line.lower()
        if ('campaign' in lower or 'campaign name' in lower) and \
           ('impressions' in lower or 'clicks' in lower or 'spend' in lower or 'cost' in lower or 'amount spent' in lower):
            header_row = i
            break

    # Auto-detect delimiter (comma vs tab)
    sample = lines[header_row] if header_row < len(lines) else lines[0]
    dialect = csv.Sniffer().sniff(sample, delimiters=',\t;|')
    sep = dialect.delimiter

    df = pd.read_csv(io.StringIO(text), skiprows=header_row, sep=sep)
    df.columns = df.columns.str.strip()

    # Map columns — exact match first, then prefix/contains fallback for
    # currency-suffixed columns like "Amount Spent (EUR)", "CPC (Cost per Link Click) (EUR)"
    PREFIX_RULES = [
        ('amount spent', 'spend'),
        ('total spent', 'spend'),
        ('cost per result', 'cost_per_conversion'),
        ('cost per action type', 'cost_per_conversion'),
        ('cost per lead', 'cost_per_conversion'),
        ('cpc (all)', 'avg_cpc'),
        ('cpc (cost per link click)', 'avg_cpc'),
        ('cpm (cost per 1,000 impressions)', 'cpm'),
        ('website purchases conversion value', 'conversion_value'),
        ('purchase value', 'conversion_value'),
        ('conversion value', 'conversion_value'),
    ]
    col_mapping = {}
    for col in df.columns:
        key = col.lower().strip()
        if key in COLUMN_MAP:
            col_mapping[col] = COLUMN_MAP[key]
        else:
            # Fallback: check if the column starts with a known prefix
            for prefix, target in PREFIX_RULES:
                if key.startswith(prefix):
                    col_mapping[col] = target
                    break

    df = df.rename(columns=col_mapping)

    # Remove duplicate columns (e.g. both "Results" and "Conversions" mapping to "conversions")
    df = df.loc[:, ~df.columns.duplicated(keep='first')]

    if 'campaign_name' not in df.columns:
        raise ValueError("Could not find 'Campaign Name' column in Meta Ads CSV. Please ensure your export includes campaign names.")

    df = df.dropna(subset=['campaign_name'])

    # Clean numeric columns
    numeric_cols = ['impressions', 'clicks', 'spend', 'conversions',
                    'conversion_value', 'ctr', 'avg_cpc',
                    'cost_per_conversion', 'conversion_rate',
                    'leads', 'purchases']

    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)

    # If no conversions column but leads or purchases exist, use them
    has_convs = 'conversions' in df.columns and float(df['conversions'].sum()) > 0
    if not has_convs:
        if 'purchases' in df.columns and df['purchases'].sum() > 0:
            df['conversions'] = df['purchases']
        elif 'leads' in df.columns and df['leads'].sum() > 0:
            df['conversions'] = df['leads']

    # Normalize CTR — detect if it's already a decimal or a percentage
    if 'ctr' in df.columns:
        max_ctr = df['ctr'].max()
        if max_ctr > 1:  # likely percentages that weren't caught
            df['ctr'] = df['ctr'] / 100.0

    # Capture ad copy before aggregation
    copy_data = {}
    if 'headline' in df.columns or 'description' in df.columns:
        for _, row in df.iterrows():
            cname = str(row['campaign_name'])
            if cname not in copy_data:
                copy_data[cname] = {'headline': '', 'description': ''}
            if 'headline' in df.columns and not copy_data[cname]['headline']:
                val = str(row.get('headline', '')).strip()
                if val and val.lower() not in ('nan', '--', ''):
                    copy_data[cname]['headline'] = val
            if 'description' in df.columns and not copy_data[cname]['description']:
                val = str(row.get('description', '')).strip()
                if val and val.lower() not in ('nan', '--', ''):
                    copy_data[cname]['description'] = val

    # Aggregate by campaign (Meta exports can have daily rows)
    sum_cols = {c: 'sum' for c in ['impressions', 'clicks', 'spend', 'conversions', 'conversion_value'] if c in df.columns}
    if sum_cols:
        grouped = df.groupby('campaign_name', as_index=False).agg(sum_cols)
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

        cname = str(row['campaign_name'])
        headline = copy_data.get(cname, {}).get('headline', '')
        description = copy_data.get(cname, {}).get('description', '')

        campaigns.append(NormalizedCampaign(
            campaign_name=cname,
            channel='meta_ads',
            impressions=impr,
            clicks=clicks,
            spend=spend,
            conversions=convs,
            conversion_value=conv_val,
            ctr=ctr,
            avg_cpc=avg_cpc,
            cost_per_conversion=cpa,
            conversion_rate=conv_rate,
            headline=headline,
            description=description,
        ))

    return campaigns
