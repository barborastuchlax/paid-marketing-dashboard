"""Quick integration test for the analyze endpoint."""
import json
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_analyze():
    with open('test_data/google_ads_sample.csv', 'rb') as g, \
         open('test_data/linkedin_ads_sample.csv', 'rb') as l:
        resp = client.post(
            '/api/analyze',
            files={
                'google_ads_csv': ('google.csv', g, 'text/csv'),
                'linkedin_ads_csv': ('linkedin.csv', l, 'text/csv'),
            },
            data={'avg_customer_ltv': '500', 'monthly_revenue': '80000'},
        )

    assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text}"
    data = resp.json()

    print("=== SUMMARY ===")
    print(json.dumps(data['summary'], indent=2))

    print("\n=== BY CHANNEL ===")
    for ch, m in data['by_channel'].items():
        print(f"\n{ch}:")
        print(json.dumps(m, indent=2))

    print(f"\n=== CAC: ${data['cac']:.2f} ===")
    print(f"=== LTV:CAC: {data['ltv_cac_ratio']:.1f}:1 ===")
    print(f"=== MER: {data['mer']:.2f} ===")

    print("\n=== SCORECARD ===")
    sc = data['scorecard']
    print(f"Overall: {sc['overall_grade']} ({sc['overall_score']}/100)")
    for k, g in sc['grades'].items():
        print(f"  {k}: {g['grade']} ({g['score']}/100) - {g['label']} - Value: {g['value']}")

    print(f"\n=== RECOMMENDATIONS ({len(data['recommendations'])}) ===")
    for r in data['recommendations']:
        print(f"  [{r['priority'].upper()}] {r['title']}")
        print(f"    {r['detail'][:100]}...")

    print("\n=== CAMPAIGNS ===")
    for c in data['by_campaign']:
        print(f"  {c['channel']}: {c['campaign_name']} | Spend: ${c['spend']:.0f} | CPA: ${c['cpa']:.2f} | CTR: {c['ctr']*100:.2f}%")

    print("\nAll tests passed!")

if __name__ == '__main__':
    test_analyze()
