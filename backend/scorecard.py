from backend.models import MetricGrade, ScorecardResult


def _lerp(value: float, low: float, high: float, score_low: int, score_high: int) -> int:
    """Linear interpolation between score bands."""
    if high == low:
        return score_high
    t = (value - low) / (high - low)
    t = max(0.0, min(1.0, t))
    return int(score_low + t * (score_high - score_low))


def score_to_grade(score: int) -> tuple[str, str]:
    if score >= 90: return 'A+', 'Exceptional'
    if score >= 85: return 'A', 'Excellent'
    if score >= 80: return 'A-', 'Very Strong'
    if score >= 75: return 'B+', 'Strong'
    if score >= 70: return 'B', 'Good'
    if score >= 65: return 'B-', 'Above Average'
    if score >= 60: return 'C+', 'Average'
    if score >= 55: return 'C', 'Below Average'
    if score >= 50: return 'C-', 'Needs Work'
    if score >= 40: return 'D', 'Poor'
    return 'F', 'Critical'


def score_roas(roas: float | None) -> MetricGrade:
    if roas is None:
        return MetricGrade(value=None, grade='N/A', score=0, label='No conversion value data')

    if roas >= 5.0:
        s = _lerp(roas, 5.0, 8.0, 90, 100)
    elif roas >= 4.0:
        s = _lerp(roas, 4.0, 5.0, 82, 90)
    elif roas >= 3.0:
        s = _lerp(roas, 3.0, 4.0, 72, 82)
    elif roas >= 2.0:
        s = _lerp(roas, 2.0, 3.0, 58, 72)
    elif roas >= 1.0:
        s = _lerp(roas, 1.0, 2.0, 40, 58)
    else:
        s = _lerp(roas, 0.0, 1.0, 15, 40)

    grade, label = score_to_grade(s)
    return MetricGrade(value=round(roas, 2), grade=grade, score=s, label=label)


def score_ctr(ctr: float | None, channel: str = 'blended') -> MetricGrade:
    if ctr is None:
        return MetricGrade()

    ctr_pct = ctr * 100  # convert to percentage

    if channel == 'linkedin_ads':
        # LinkedIn benchmarks are lower
        if ctr_pct >= 1.0:
            s = _lerp(ctr_pct, 1.0, 2.0, 88, 98)
        elif ctr_pct >= 0.6:
            s = _lerp(ctr_pct, 0.6, 1.0, 72, 88)
        elif ctr_pct >= 0.3:
            s = _lerp(ctr_pct, 0.3, 0.6, 55, 72)
        else:
            s = _lerp(ctr_pct, 0.0, 0.3, 25, 55)
    else:
        # Google / blended benchmarks
        if ctr_pct >= 3.5:
            s = _lerp(ctr_pct, 3.5, 6.0, 88, 98)
        elif ctr_pct >= 2.5:
            s = _lerp(ctr_pct, 2.5, 3.5, 72, 88)
        elif ctr_pct >= 1.5:
            s = _lerp(ctr_pct, 1.5, 2.5, 55, 72)
        else:
            s = _lerp(ctr_pct, 0.0, 1.5, 25, 55)

    grade, label = score_to_grade(s)
    return MetricGrade(value=round(ctr_pct, 2), grade=grade, score=s, label=label)


def score_cpa(cpa: float | None, avg_ltv: float = 0) -> MetricGrade:
    if cpa is None or cpa <= 0:
        return MetricGrade(value=None, grade='N/A', score=0, label='No conversions')

    if avg_ltv > 0:
        ratio = cpa / avg_ltv
        if ratio < 0.2:
            s = _lerp(ratio, 0.0, 0.2, 100, 90)
        elif ratio < 0.33:
            s = _lerp(ratio, 0.2, 0.33, 90, 75)
        elif ratio < 0.5:
            s = _lerp(ratio, 0.33, 0.5, 75, 60)
        elif ratio < 1.0:
            s = _lerp(ratio, 0.5, 1.0, 60, 35)
        else:
            s = _lerp(ratio, 1.0, 2.0, 35, 10)
    else:
        # Without LTV, use absolute benchmarks (general B2B/B2C mix)
        if cpa < 20:
            s = 92
        elif cpa < 50:
            s = _lerp(cpa, 20, 50, 78, 92)
        elif cpa < 100:
            s = _lerp(cpa, 50, 100, 62, 78)
        elif cpa < 200:
            s = _lerp(cpa, 100, 200, 45, 62)
        else:
            s = _lerp(cpa, 200, 500, 20, 45)

    grade, label = score_to_grade(s)
    return MetricGrade(value=round(cpa, 2), grade=grade, score=s, label=label)


def score_conversion_rate(cr: float | None) -> MetricGrade:
    if cr is None:
        return MetricGrade()

    cr_pct = cr * 100

    if cr_pct >= 8:
        s = _lerp(cr_pct, 8, 15, 90, 98)
    elif cr_pct >= 5:
        s = _lerp(cr_pct, 5, 8, 76, 90)
    elif cr_pct >= 3:
        s = _lerp(cr_pct, 3, 5, 62, 76)
    elif cr_pct >= 1:
        s = _lerp(cr_pct, 1, 3, 42, 62)
    else:
        s = _lerp(cr_pct, 0, 1, 20, 42)

    grade, label = score_to_grade(s)
    return MetricGrade(value=round(cr_pct, 2), grade=grade, score=s, label=label)


def score_ltv_cac(ratio: float | None) -> MetricGrade:
    if ratio is None:
        return MetricGrade(value=None, grade='N/A', score=0, label='LTV not provided')

    if ratio >= 5:
        s = _lerp(ratio, 5, 8, 92, 98)
    elif ratio >= 4:
        s = _lerp(ratio, 4, 5, 83, 92)
    elif ratio >= 3:
        s = _lerp(ratio, 3, 4, 72, 83)
    elif ratio >= 2:
        s = _lerp(ratio, 2, 3, 52, 72)
    elif ratio >= 1:
        s = _lerp(ratio, 1, 2, 32, 52)
    else:
        s = _lerp(ratio, 0, 1, 10, 32)

    grade, label = score_to_grade(s)
    return MetricGrade(value=round(ratio, 2), grade=grade, score=s, label=label)


def generate_scorecard(metrics: dict, avg_ltv: float = 0) -> ScorecardResult:
    summary = metrics['summary']

    grades = {}
    weights = {}

    # ROAS
    roas_grade = score_roas(summary.blended_roas)
    grades['roas'] = roas_grade
    if roas_grade.score > 0:
        weights['roas'] = 25

    # CPA
    cpa_grade = score_cpa(summary.blended_cpa, avg_ltv)
    grades['cpa'] = cpa_grade
    if cpa_grade.score > 0:
        weights['cpa'] = 25

    # CTR
    ctr_grade = score_ctr(summary.blended_ctr)
    grades['ctr'] = ctr_grade
    if ctr_grade.score > 0:
        weights['ctr'] = 15

    # Conversion Rate
    cr_grade = score_conversion_rate(summary.blended_conversion_rate)
    grades['conversion_rate'] = cr_grade
    if cr_grade.score > 0:
        weights['conversion_rate'] = 20

    # LTV:CAC
    ltv_cac_grade = score_ltv_cac(metrics.get('ltv_cac_ratio'))
    grades['ltv_cac_ratio'] = ltv_cac_grade
    if ltv_cac_grade.score > 0:
        weights['ltv_cac_ratio'] = 15

    # Calculate weighted overall score
    total_weight = sum(weights.values())
    if total_weight > 0:
        overall_score = sum(
            grades[k].score * (w / total_weight)
            for k, w in weights.items()
        )
        overall_score = int(round(overall_score))
    else:
        overall_score = 0

    overall_grade, _ = score_to_grade(overall_score)

    return ScorecardResult(
        overall_grade=overall_grade,
        overall_score=overall_score,
        grades=grades,
    )
