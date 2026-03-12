function renderScorecard(data) {
    const container = document.getElementById('tab-scorecard');
    const sc = data.scorecard;

    const metricLabels = {
        roas: 'ROAS',
        cpa: 'CPA',
        ctr: 'CTR',
        conversion_rate: 'Conversion Rate',
        ltv_cac_ratio: 'LTV:CAC Ratio',
    };

    const metricFormatters = {
        roas: v => v != null ? v.toFixed(2) + 'x' : 'N/A',
        cpa: v => v != null ? '$' + v.toFixed(2) : 'N/A',
        ctr: v => v != null ? v.toFixed(2) + '%' : 'N/A',
        conversion_rate: v => v != null ? v.toFixed(2) + '%' : 'N/A',
        ltv_cac_ratio: v => v != null ? v.toFixed(1) + ':1' : 'N/A',
    };

    // Overall grade
    let html = `
        <div class="overall-grade-card">
            <div class="grade-circle ${gradeClass(sc.overall_grade)}">${sc.overall_grade}</div>
            <div class="grade-title">Overall Marketing Health</div>
            <div class="grade-subtitle">Score: ${sc.overall_score}/100</div>
        </div>`;

    // Individual metric grades
    html += '<div class="metric-grades">';
    for (const [key, grade] of Object.entries(sc.grades)) {
        const label = metricLabels[key] || key;
        const formatter = metricFormatters[key] || (v => v != null ? v.toString() : 'N/A');
        const gc = gradeClass(grade.grade);

        html += `
            <div class="metric-grade-card">
                <div class="metric-grade-header">
                    <span class="metric-grade-name">${label}</span>
                    <span class="grade-pill ${gc}">${grade.grade}</span>
                </div>
                <div class="metric-grade-value">${formatter(grade.value)}</div>
                <div class="progress-bar">
                    <div class="progress-fill ${gc}" style="width: ${grade.score}%"></div>
                </div>
                <div class="metric-grade-label">${grade.label} (${grade.score}/100)</div>
            </div>`;
    }
    html += '</div>';

    // Radar chart
    html += `
        <div class="chart-row">
            <div class="chart-card chart-full">
                <h3>Performance Radar</h3>
                <canvas id="chart-radar" style="max-height: 350px;"></canvas>
            </div>
        </div>`;

    // Channel comparison scorecard
    if (Object.keys(data.by_channel).length >= 2) {
        html += `
        <div class="table-card">
            <h3>Channel Scorecard Comparison</h3>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        ${Object.keys(data.by_channel).map(ch => `<th class="text-right">${channelLabel(ch)}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>CPA</td>
                        ${Object.values(data.by_channel).map(ch => `<td class="text-right">${fmtCurrency(ch.blended_cpa)}</td>`).join('')}
                    </tr>
                    <tr>
                        <td>CTR</td>
                        ${Object.values(data.by_channel).map(ch => `<td class="text-right">${ch.blended_ctr != null ? (ch.blended_ctr * 100).toFixed(2) + '%' : 'N/A'}</td>`).join('')}
                    </tr>
                    <tr>
                        <td>Conv. Rate</td>
                        ${Object.values(data.by_channel).map(ch => `<td class="text-right">${ch.blended_conversion_rate != null ? (ch.blended_conversion_rate * 100).toFixed(2) + '%' : 'N/A'}</td>`).join('')}
                    </tr>
                    <tr>
                        <td>Avg CPC</td>
                        ${Object.values(data.by_channel).map(ch => `<td class="text-right">${fmtCurrency(ch.avg_cpc)}</td>`).join('')}
                    </tr>
                    <tr>
                        <td>CPM</td>
                        ${Object.values(data.by_channel).map(ch => `<td class="text-right">${fmtCurrency(ch.cpm)}</td>`).join('')}
                    </tr>
                </tbody>
            </table>
        </div>`;
    }

    container.innerHTML = html;

    // Render radar chart
    const radarLabels = [];
    const radarData = [];
    for (const [key, grade] of Object.entries(sc.grades)) {
        if (grade.score > 0) {
            radarLabels.push(metricLabels[key] || key);
            radarData.push(grade.score);
        }
    }

    if (radarLabels.length >= 3) {
        chartInstances.push(new Chart(document.getElementById('chart-radar'), {
            type: 'radar',
            data: {
                labels: radarLabels,
                datasets: [
                    {
                        label: 'Your Score',
                        data: radarData,
                        backgroundColor: 'rgba(37, 99, 235, 0.15)',
                        borderColor: '#2563eb',
                        borderWidth: 2,
                        pointBackgroundColor: '#2563eb',
                    },
                    {
                        label: 'Target (80)',
                        data: radarLabels.map(() => 80),
                        backgroundColor: 'transparent',
                        borderColor: 'rgba(5, 150, 105, 0.4)',
                        borderWidth: 1,
                        borderDash: [5, 5],
                        pointRadius: 0,
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom' } },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: { stepSize: 20 },
                        grid: { color: 'rgba(0,0,0,0.06)' },
                    }
                }
            }
        }));
    }
}
