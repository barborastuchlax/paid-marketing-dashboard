import os
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from typing import Optional

from backend.parsers import google_ads, linkedin_ads, meta_ads, linkedin_demographics
from backend.metrics import calculate_all_metrics
from backend.scorecard import generate_scorecard
from backend.recommendations import generate_recommendations
from backend.copy_analysis import analyze_copy

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Paid Marketing Dashboard")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/analyze")
async def analyze(
    google_ads_csv: Optional[UploadFile] = File(None),
    linkedin_ads_csv: Optional[UploadFile] = File(None),
    meta_ads_csv: Optional[UploadFile] = File(None),
    linkedin_demographics_csv: Optional[UploadFile] = File(None),
    creatives_csv: Optional[UploadFile] = File(None),
    avg_customer_ltv: float = Form(0),
    monthly_revenue: float = Form(0),
    ad_copy_text: str = Form(""),
):
    import traceback
    try:
        return await _analyze(google_ads_csv, linkedin_ads_csv, meta_ads_csv, linkedin_demographics_csv, creatives_csv, avg_customer_ltv, monthly_revenue, ad_copy_text)
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Internal error: {str(e)}", "trace": traceback.format_exc()},
        )


async def _analyze(google_ads_csv, linkedin_ads_csv, meta_ads_csv, linkedin_demographics_csv, creatives_csv, avg_customer_ltv, monthly_revenue, ad_copy_text=""):
    if not google_ads_csv and not linkedin_ads_csv and not meta_ads_csv:
        return JSONResponse(
            status_code=400,
            content={"error": "Please upload at least one CSV file (Google Ads, LinkedIn Ads, or Meta Ads)."},
        )

    campaigns = []
    errors = []

    if google_ads_csv and google_ads_csv.filename:
        try:
            content = await google_ads_csv.read()
            campaigns.extend(google_ads.parse(content))
        except Exception as e:
            errors.append(f"Google Ads CSV error: {str(e)}")

    if linkedin_ads_csv and linkedin_ads_csv.filename:
        try:
            content = await linkedin_ads_csv.read()
            campaigns.extend(linkedin_ads.parse(content))
        except Exception as e:
            errors.append(f"LinkedIn Ads CSV error: {str(e)}")

    if meta_ads_csv and meta_ads_csv.filename:
        try:
            content = await meta_ads_csv.read()
            campaigns.extend(meta_ads.parse(content))
        except Exception as e:
            errors.append(f"Meta Ads CSV error: {str(e)}")

    demographics = None
    if linkedin_demographics_csv and linkedin_demographics_csv.filename:
        try:
            content = await linkedin_demographics_csv.read()
            demographics = linkedin_demographics.parse(content)
        except Exception as e:
            errors.append(f"LinkedIn Demographics CSV error: {str(e)}")

    if not campaigns:
        return JSONResponse(
            status_code=400,
            content={"error": "No campaign data could be parsed. " + " ".join(errors)},
        )

    metrics = calculate_all_metrics(campaigns, avg_customer_ltv, monthly_revenue)
    scorecard = generate_scorecard(metrics, avg_customer_ltv)
    recommendations = generate_recommendations(metrics, avg_customer_ltv)

    # Parse creatives CSV if provided
    creatives_csv_content = None
    if creatives_csv and creatives_csv.filename:
        try:
            creatives_csv_content = await creatives_csv.read()
        except Exception as e:
            errors.append(f"Creatives CSV error: {str(e)}")

    # Copy analysis (runs if ad copy is available from CSVs, creatives CSV, or manual entry)
    copy_result = await analyze_copy(campaigns, ad_copy_text, creatives_csv_content)

    result = {
        "summary": metrics['summary'].model_dump(),
        "by_channel": {k: v.model_dump() for k, v in metrics['by_channel'].items()},
        "by_campaign": metrics['by_campaign'],
        "scorecard": scorecard.model_dump(),
        "recommendations": [r.model_dump() for r in recommendations],
        "cac": metrics['cac'],
        "ltv_cac_ratio": metrics['ltv_cac_ratio'],
        "mer": metrics['mer'],
        "demographics": demographics.model_dump() if demographics else None,
        "copy_analysis": copy_result.model_dump(),
        "warnings": errors if errors else None,
    }

    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
