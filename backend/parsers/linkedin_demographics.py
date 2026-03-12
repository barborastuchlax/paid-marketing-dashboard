import csv
import io

import pandas as pd

from backend.models import DemographicEntry, DemographicsData


# Mapping of raw dimension names (lowercased) to our canonical keys
DIMENSION_MAP = {
    "age": "age",
    "age range": "age",
    "member age": "age",
    "job function": "job_function",
    "member job function": "job_function",
    "seniority": "seniority",
    "member seniority": "seniority",
    "industry": "industry",
    "member industry": "industry",
    "company size": "company_size",
    "member company size": "company_size",
}

# Metric column aliases (lowercased) -> canonical name
METRIC_ALIASES = {
    "impressions": "impressions",
    "clicks": "clicks",
    "spend": "spend",
    "total spent": "spend",
    "amount spent": "spend",
    "cost": "spend",
    "conversions": "conversions",
    "external conversions": "conversions",
    "ctr": "ctr",
    "average ctr": "ctr",
}


def _clean_numeric(val) -> float:
    """Clean a raw cell value into a float, stripping currency symbols and percentages."""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = s.replace("$", "").replace("\u20ac", "").replace("\u00a3", "").replace(",", "")
    is_pct = s.endswith("%")
    s = s.replace("%", "").strip()
    if s in ("--", "-", "", "N/A", "n/a"):
        return 0.0
    try:
        v = float(s)
        if is_pct:
            v = v / 100.0
        return v
    except ValueError:
        return 0.0


def _decode(file_content: bytes) -> str:
    """Decode bytes trying common LinkedIn export encodings."""
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            return file_content.decode(encoding)
        except (UnicodeDecodeError, UnicodeError):
            continue
    return file_content.decode("utf-8", errors="replace")


def _find_header_and_sep(text: str):
    """Locate the header row index and detect the delimiter."""
    lines = text.strip().split("\n")
    header_row = 0
    for i, line in enumerate(lines):
        lower = line.lower()
        # For pivoted format look for "dimension" or "facet"; for flat look for known dimension names
        if any(kw in lower for kw in ("dimension", "facet", "impressions", "clicks")):
            header_row = i
            break

    sample = lines[header_row] if header_row < len(lines) else lines[0]
    dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    return header_row, dialect.delimiter


def _detect_format(df: pd.DataFrame):
    """Return 'pivoted' if the CSV uses Dimension/Facet columns, else 'flat'."""
    lower_cols = [c.lower().strip() for c in df.columns]
    if "dimension" in lower_cols or "facet" in lower_cols:
        return "pivoted"
    if "dimension value" in lower_cols or "facet value" in lower_cols:
        return "pivoted"
    return "flat"


def _resolve_col(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Return the first column name in *df* that matches one of *candidates* (case-insensitive)."""
    lower_map = {c.lower().strip(): c for c in df.columns}
    for c in candidates:
        if c in lower_map:
            return lower_map[c]
    return None


def _build_entry(row: pd.Series, value: str, metric_map: dict[str, str]) -> DemographicEntry:
    """Build a DemographicEntry from a DataFrame row."""
    impressions = int(_clean_numeric(row.get(metric_map.get("impressions", ""), 0)))
    clicks = int(_clean_numeric(row.get(metric_map.get("clicks", ""), 0)))
    spend = _clean_numeric(row.get(metric_map.get("spend", ""), 0))
    conversions = _clean_numeric(row.get(metric_map.get("conversions", ""), 0))
    ctr_raw = _clean_numeric(row.get(metric_map.get("ctr", ""), 0))
    # Compute CTR from impressions/clicks if raw value is missing
    ctr = ctr_raw if ctr_raw > 0 else (clicks / impressions if impressions > 0 else 0.0)
    return DemographicEntry(
        value=str(value).strip(),
        impressions=impressions,
        clicks=clicks,
        spend=round(spend, 2),
        conversions=round(conversions, 4),
        ctr=round(ctr, 6),
    )


def _build_metric_map(df: pd.DataFrame) -> dict[str, str]:
    """Map canonical metric names to actual column names found in df."""
    lower_map = {c.lower().strip(): c for c in df.columns}
    metric_map: dict[str, str] = {}
    for alias, canonical in METRIC_ALIASES.items():
        if alias in lower_map and canonical not in metric_map:
            metric_map[canonical] = lower_map[alias]
    return metric_map


def _parse_pivoted(df: pd.DataFrame) -> DemographicsData:
    """Parse a pivoted-format demographics CSV."""
    dim_col = _resolve_col(df, ["dimension", "facet"])
    val_col = _resolve_col(df, ["dimension value", "facet value"])
    if not dim_col or not val_col:
        raise ValueError(
            "Pivoted demographics CSV must contain 'Dimension'/'Facet' and "
            "'Dimension Value'/'Facet Value' columns."
        )

    metric_map = _build_metric_map(df)
    buckets: dict[str, list[DemographicEntry]] = {
        "age": [],
        "job_function": [],
        "seniority": [],
        "industry": [],
        "company_size": [],
    }

    for _, row in df.iterrows():
        raw_dim = str(row[dim_col]).strip().lower()
        canonical = DIMENSION_MAP.get(raw_dim)
        if canonical is None:
            continue
        value = row[val_col]
        if pd.isna(value) or str(value).strip() == "":
            continue
        entry = _build_entry(row, value, metric_map)
        buckets[canonical].append(entry)

    # Sort each bucket by impressions descending
    for key in buckets:
        buckets[key].sort(key=lambda e: e.impressions, reverse=True)

    return DemographicsData(**buckets)


def _parse_flat(df: pd.DataFrame) -> DemographicsData:
    """Parse a flat-format demographics CSV where dimension names are column headers."""
    metric_map = _build_metric_map(df)
    lower_map = {c.lower().strip(): c for c in df.columns}

    buckets: dict[str, list[DemographicEntry]] = {
        "age": [],
        "job_function": [],
        "seniority": [],
        "industry": [],
        "company_size": [],
    }

    # Figure out which dimension column is present
    dim_col_name: str | None = None
    dim_key: str | None = None
    for alias, canonical in DIMENSION_MAP.items():
        if alias in lower_map:
            dim_col_name = lower_map[alias]
            dim_key = canonical
            break

    if dim_col_name is None:
        # Try treating every non-metric column as a potential dimension
        metric_actual_cols = set(metric_map.values())
        for col in df.columns:
            low = col.lower().strip()
            if col not in metric_actual_cols and low in DIMENSION_MAP:
                dim_col_name = col
                dim_key = DIMENSION_MAP[low]
                break

    if dim_col_name and dim_key:
        for _, row in df.iterrows():
            value = row[dim_col_name]
            if pd.isna(value) or str(value).strip() == "":
                continue
            entry = _build_entry(row, value, metric_map)
            buckets[dim_key].append(entry)

        buckets[dim_key].sort(key=lambda e: e.impressions, reverse=True)
    else:
        # Multiple dimension columns present — process each one
        metric_actual_cols = set(metric_map.values())
        for col in df.columns:
            low = col.lower().strip()
            canonical = DIMENSION_MAP.get(low)
            if canonical is None:
                continue
            for _, row in df.iterrows():
                value = row[col]
                if pd.isna(value) or str(value).strip() == "":
                    continue
                entry = _build_entry(row, value, metric_map)
                buckets[canonical].append(entry)
            buckets[canonical].sort(key=lambda e: e.impressions, reverse=True)

    return DemographicsData(**buckets)


def parse(file_content: bytes) -> DemographicsData:
    """Parse a LinkedIn Demographics CSV (pivoted or flat) and return structured data."""
    text = _decode(file_content)
    header_row, sep = _find_header_and_sep(text)

    df = pd.read_csv(io.StringIO(text), skiprows=header_row, sep=sep)
    df.columns = df.columns.str.strip()

    fmt = _detect_format(df)
    if fmt == "pivoted":
        return _parse_pivoted(df)
    else:
        return _parse_flat(df)
