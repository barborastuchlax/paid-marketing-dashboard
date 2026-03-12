// Chart.js defaults
Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
Chart.defaults.font.size = 12;
Chart.defaults.color = '#6b7280';

const COLORS = {
    google: '#f59e0b',
    linkedin: '#3b82f6',
    palette: ['#2563eb', '#f59e0b', '#059669', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316', '#6366f1'],
};

function renderDashboard(data) {
    const container = document.getElementById('tab-dashboard');
    const s = data.summary;

    // KPI tiles
    let kpis = `
        <div class="kpi-row">
            <div class="kpi-tile">
                <div class="kpi-label">Total Spend</div>
                <div class="kpi-value">${fmtCurrency(s.total_spend)}</div>
                <div class="kpi-sub">${fmt(Object.keys(data.by_channel).length)} channel${Object.keys(data.by_channel).length > 1 ? 's' : ''}</div>
            </div>
            <div class="kpi-tile">
                <div class="kpi-label">Total Conversions</div>
                <div class="kpi-value">${fmt(s.total_conversions)}</div>
                <div class="kpi-sub">${fmt(s.total_clicks)} clicks</div>
            </div>
            <div class="kpi-tile">
                <div class="kpi-label">Blended CPA</div>
                <div class="kpi-value">${fmtCurrency(s.blended_cpa)}</div>
                <div class="kpi-sub">Cost per acquisition</div>
            </div>
            <div class="kpi-tile">
                <div class="kpi-label">Blended CTR</div>
                <div class="kpi-value">${s.blended_ctr != null ? (s.blended_ctr * 100).toFixed(2) + '%' : 'N/A'}</div>
                <div class="kpi-sub">${fmt(s.total_impressions)} impressions</div>
            </div>
            <div class="kpi-tile">
                <div class="kpi-label">ROAS</div>
                <div class="kpi-value">${s.blended_roas != null ? s.blended_roas.toFixed(2) + 'x' : 'N/A'}</div>
                <div class="kpi-sub">${s.blended_roas != null ? fmtCurrency(s.conversion_value) + ' revenue' : 'No value data'}</div>
            </div>`;

    if (data.ltv_cac_ratio != null) {
        kpis += `
            <div class="kpi-tile">
                <div class="kpi-label">LTV:CAC Ratio</div>
                <div class="kpi-value">${data.ltv_cac_ratio.toFixed(1)}:1</div>
                <div class="kpi-sub">${data.ltv_cac_ratio >= 3 ? 'Healthy' : 'Below target (3:1)'}</div>
            </div>`;
    }

    kpis += '</div>';

    // Charts
    let charts = '<div class="chart-row">';

    // Channel spend comparison (if 2 channels)
    if (Object.keys(data.by_channel).length >= 2) {
        charts += `
            <div class="chart-card">
                <h3>Spend & Conversions by Channel</h3>
                <canvas id="chart-channel-compare"></canvas>
            </div>
            <div class="chart-card">
                <h3>Spend Distribution</h3>
                <canvas id="chart-spend-dist"></canvas>
            </div>`;
    }

    charts += '</div><div class="chart-row">';

    // CPA by campaign
    charts += `
        <div class="chart-card">
            <h3>CPA by Campaign</h3>
            <canvas id="chart-cpa-campaign"></canvas>
        </div>
        <div class="chart-card">
            <h3>CTR by Campaign</h3>
            <canvas id="chart-ctr-campaign"></canvas>
        </div>`;

    charts += '</div>';

    // Conversion rate by campaign (full width)
    charts += `
        <div class="chart-row">
            <div class="chart-card chart-full">
                <h3>Conversion Rate by Campaign</h3>
                <canvas id="chart-conv-rate"></canvas>
            </div>
        </div>`;

    container.innerHTML = kpis + charts;

    // Render charts
    const campaigns = data.by_campaign;

    // Channel comparison
    if (Object.keys(data.by_channel).length >= 2) {
        const channelNames = Object.keys(data.by_channel).map(channelLabel);
        const channelSpends = Object.values(data.by_channel).map(c => c.total_spend);
        const channelConvValues = Object.values(data.by_channel).map(c => c.conversion_value || 0);
        const channelConvs = Object.values(data.by_channel).map(c => c.total_conversions);

        chartInstances.push(new Chart(document.getElementById('chart-channel-compare'), {
            type: 'bar',
            data: {
                labels: channelNames,
                datasets: [
                    { label: 'Spend', data: channelSpends, backgroundColor: '#ef4444', borderRadius: 4 },
                    { label: 'Conversions', data: channelConvs, backgroundColor: '#059669', borderRadius: 4 },
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: { y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } } },
            }
        }));

        // Spend distribution doughnut
        const chColors = Object.keys(data.by_channel).map(ch => ch === 'google_ads' ? COLORS.google : COLORS.linkedin);
        chartInstances.push(new Chart(document.getElementById('chart-spend-dist'), {
            type: 'doughnut',
            data: {
                labels: channelNames,
                datasets: [{ data: channelSpends, backgroundColor: chColors, borderWidth: 0 }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                cutout: '60%',
            }
        }));
    }

    // CPA by campaign (horizontal bar)
    const campaignsWithConv = campaigns.filter(c => c.conversions > 0);
    const cpaSorted = [...campaignsWithConv].sort((a, b) => b.cpa - a.cpa);
    const cpaColors = cpaSorted.map(c => c.channel === 'google_ads' ? COLORS.google : COLORS.linkedin);

    chartInstances.push(new Chart(document.getElementById('chart-cpa-campaign'), {
        type: 'bar',
        data: {
            labels: cpaSorted.map(c => c.campaign_name.length > 30 ? c.campaign_name.slice(0, 28) + '...' : c.campaign_name),
            datasets: [{ label: 'CPA ($)', data: cpaSorted.map(c => c.cpa), backgroundColor: cpaColors, borderRadius: 4 }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } } },
        }
    }));

    // CTR by campaign
    const ctrSorted = [...campaigns].sort((a, b) => b.ctr - a.ctr);
    const ctrColors = ctrSorted.map(c => c.channel === 'google_ads' ? COLORS.google : COLORS.linkedin);

    chartInstances.push(new Chart(document.getElementById('chart-ctr-campaign'), {
        type: 'bar',
        data: {
            labels: ctrSorted.map(c => c.campaign_name.length > 30 ? c.campaign_name.slice(0, 28) + '...' : c.campaign_name),
            datasets: [{ label: 'CTR (%)', data: ctrSorted.map(c => (c.ctr * 100).toFixed(2)), backgroundColor: ctrColors, borderRadius: 4 }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { x: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } } },
        }
    }));

    // Conversion rate by campaign
    const crSorted = [...campaignsWithConv].sort((a, b) => b.conversion_rate - a.conversion_rate);
    const crColors = crSorted.map((_, i) => COLORS.palette[i % COLORS.palette.length]);

    chartInstances.push(new Chart(document.getElementById('chart-conv-rate'), {
        type: 'bar',
        data: {
            labels: crSorted.map(c => c.campaign_name.length > 35 ? c.campaign_name.slice(0, 33) + '...' : c.campaign_name),
            datasets: [{ label: 'Conv. Rate (%)', data: crSorted.map(c => (c.conversion_rate * 100).toFixed(2)), backgroundColor: crColors, borderRadius: 4 }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: { y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } } },
        }
    }));
}
