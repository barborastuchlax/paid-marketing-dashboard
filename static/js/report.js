function renderReport(data) {
    const container = document.getElementById('tab-report');
    const s = data.summary;
    const campaigns = data.by_campaign;
    const channels = Object.keys(data.by_channel);

    // Executive summary
    const numCampaigns = campaigns.length;
    const channelList = channels.map(channelLabel).join(' and ');
    let summaryText = `Across ${numCampaigns} campaign${numCampaigns > 1 ? 's' : ''} on ${channelList}, `;
    summaryText += `total spend was ${fmtCurrency(s.total_spend)} generating ${fmt(s.total_conversions)} conversions `;
    summaryText += `at a blended CPA of ${fmtCurrency(s.blended_cpa)}.`;

    if (s.blended_ctr != null) {
        summaryText += ` Overall CTR was ${(s.blended_ctr * 100).toFixed(2)}%`;
        if (s.blended_conversion_rate != null) {
            summaryText += ` with a ${(s.blended_conversion_rate * 100).toFixed(2)}% conversion rate`;
        }
        summaryText += '.';
    }

    if (data.ltv_cac_ratio != null) {
        summaryText += ` The LTV:CAC ratio is ${data.ltv_cac_ratio.toFixed(1)}:1${data.ltv_cac_ratio >= 3 ? ', which is healthy' : ', which is below the recommended 3:1 target'}.`;
    }

    if (s.blended_roas != null) {
        summaryText += ` ROAS stands at ${s.blended_roas.toFixed(2)}x.`;
    }

    let html = `
        <button class="btn-print" onclick="window.print()">Print Report</button>
        <div class="exec-summary">
            <h3>Executive Summary</h3>
            <p>${summaryText}</p>
        </div>`;

    // Channel comparison table
    if (channels.length >= 2) {
        html += `
        <div class="table-card">
            <h3>Channel Comparison</h3>
            <table>
                <thead>
                    <tr>
                        <th>Metric</th>
                        ${channels.map(ch => `<th class="text-right">${channelLabel(ch)}</th>`).join('')}
                        <th class="text-right">Blended</th>
                    </tr>
                </thead>
                <tbody>
                    <tr><td>Spend</td>${channels.map(ch => `<td class="text-right">${fmtCurrency(data.by_channel[ch].total_spend)}</td>`).join('')}<td class="text-right"><strong>${fmtCurrency(s.total_spend)}</strong></td></tr>
                    <tr><td>Impressions</td>${channels.map(ch => `<td class="text-right">${fmt(data.by_channel[ch].total_impressions)}</td>`).join('')}<td class="text-right"><strong>${fmt(s.total_impressions)}</strong></td></tr>
                    <tr><td>Clicks</td>${channels.map(ch => `<td class="text-right">${fmt(data.by_channel[ch].total_clicks)}</td>`).join('')}<td class="text-right"><strong>${fmt(s.total_clicks)}</strong></td></tr>
                    <tr><td>CTR</td>${channels.map(ch => `<td class="text-right">${data.by_channel[ch].blended_ctr != null ? (data.by_channel[ch].blended_ctr * 100).toFixed(2) + '%' : 'N/A'}</td>`).join('')}<td class="text-right"><strong>${s.blended_ctr != null ? (s.blended_ctr * 100).toFixed(2) + '%' : 'N/A'}</strong></td></tr>
                    <tr><td>Avg CPC</td>${channels.map(ch => `<td class="text-right">${fmtCurrency(data.by_channel[ch].avg_cpc)}</td>`).join('')}<td class="text-right"><strong>${fmtCurrency(s.avg_cpc)}</strong></td></tr>
                    <tr><td>Conversions</td>${channels.map(ch => `<td class="text-right">${fmt(data.by_channel[ch].total_conversions)}</td>`).join('')}<td class="text-right"><strong>${fmt(s.total_conversions)}</strong></td></tr>
                    <tr><td>CPA</td>${channels.map(ch => `<td class="text-right">${fmtCurrency(data.by_channel[ch].blended_cpa)}</td>`).join('')}<td class="text-right"><strong>${fmtCurrency(s.blended_cpa)}</strong></td></tr>
                    <tr><td>Conv. Rate</td>${channels.map(ch => `<td class="text-right">${data.by_channel[ch].blended_conversion_rate != null ? (data.by_channel[ch].blended_conversion_rate * 100).toFixed(2) + '%' : 'N/A'}</td>`).join('')}<td class="text-right"><strong>${s.blended_conversion_rate != null ? (s.blended_conversion_rate * 100).toFixed(2) + '%' : 'N/A'}</strong></td></tr>
                    <tr><td>ROAS</td>${channels.map(ch => `<td class="text-right">${data.by_channel[ch].blended_roas != null ? data.by_channel[ch].blended_roas.toFixed(2) + 'x' : 'N/A'}</td>`).join('')}<td class="text-right"><strong>${s.blended_roas != null ? s.blended_roas.toFixed(2) + 'x' : 'N/A'}</strong></td></tr>
                    <tr><td>CPM</td>${channels.map(ch => `<td class="text-right">${fmtCurrency(data.by_channel[ch].cpm)}</td>`).join('')}<td class="text-right"><strong>${fmtCurrency(s.cpm)}</strong></td></tr>
                </tbody>
            </table>
        </div>`;
    }

    // Campaign detail table
    html += `
    <div class="table-card">
        <h3>Campaign Details</h3>
        <table id="campaign-table">
            <thead>
                <tr>
                    <th data-sort="campaign_name">Campaign</th>
                    <th data-sort="channel">Channel</th>
                    <th data-sort="spend" class="text-right">Spend</th>
                    <th data-sort="impressions" class="text-right">Impressions</th>
                    <th data-sort="clicks" class="text-right">Clicks</th>
                    <th data-sort="ctr" class="text-right">CTR</th>
                    <th data-sort="avg_cpc" class="text-right">Avg CPC</th>
                    <th data-sort="conversions" class="text-right">Conv.</th>
                    <th data-sort="conversion_rate" class="text-right">Conv. Rate</th>
                    <th data-sort="cpa" class="text-right">CPA</th>
                    <th data-sort="roas" class="text-right">ROAS</th>
                </tr>
            </thead>
            <tbody>`;

    for (const c of campaigns) {
        html += `
                <tr>
                    <td title="${c.campaign_name}">${c.campaign_name.length > 35 ? c.campaign_name.slice(0, 33) + '...' : c.campaign_name}</td>
                    <td><span class="channel-tag ${channelTagClass(c.channel)}">${channelLabel(c.channel)}</span></td>
                    <td class="text-right">${fmtCurrency(c.spend)}</td>
                    <td class="text-right">${fmt(c.impressions)}</td>
                    <td class="text-right">${fmt(c.clicks)}</td>
                    <td class="text-right">${(c.ctr * 100).toFixed(2)}%</td>
                    <td class="text-right">${fmtCurrency(c.avg_cpc)}</td>
                    <td class="text-right">${fmt(c.conversions)}</td>
                    <td class="text-right">${(c.conversion_rate * 100).toFixed(2)}%</td>
                    <td class="text-right">${c.conversions > 0 ? fmtCurrency(c.cpa) : '-'}</td>
                    <td class="text-right">${c.roas != null ? c.roas.toFixed(2) + 'x' : '-'}</td>
                </tr>`;
    }

    html += `
            </tbody>
        </table>
    </div>`;

    container.innerHTML = html;

    // Sortable table
    setupSortableTable('campaign-table', campaigns);
}

function setupSortableTable(tableId, campaigns) {
    const table = document.getElementById(tableId);
    if (!table) return;
    let sortDir = {};

    table.querySelectorAll('thead th[data-sort]').forEach(th => {
        th.addEventListener('click', () => {
            const key = th.dataset.sort;
            sortDir[key] = !sortDir[key];
            const dir = sortDir[key] ? 1 : -1;

            const sorted = [...campaigns].sort((a, b) => {
                let va = a[key], vb = b[key];
                if (va == null) va = -Infinity;
                if (vb == null) vb = -Infinity;
                if (typeof va === 'string') return va.localeCompare(vb) * dir;
                return (va - vb) * dir;
            });

            const tbody = table.querySelector('tbody');
            tbody.innerHTML = '';
            for (const c of sorted) {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td title="${c.campaign_name}">${c.campaign_name.length > 35 ? c.campaign_name.slice(0, 33) + '...' : c.campaign_name}</td>
                    <td><span class="channel-tag ${channelTagClass(c.channel)}">${channelLabel(c.channel)}</span></td>
                    <td class="text-right">${fmtCurrency(c.spend)}</td>
                    <td class="text-right">${fmt(c.impressions)}</td>
                    <td class="text-right">${fmt(c.clicks)}</td>
                    <td class="text-right">${(c.ctr * 100).toFixed(2)}%</td>
                    <td class="text-right">${fmtCurrency(c.avg_cpc)}</td>
                    <td class="text-right">${fmt(c.conversions)}</td>
                    <td class="text-right">${(c.conversion_rate * 100).toFixed(2)}%</td>
                    <td class="text-right">${c.conversions > 0 ? fmtCurrency(c.cpa) : '-'}</td>
                    <td class="text-right">${c.roas != null ? c.roas.toFixed(2) + 'x' : '-'}</td>`;
                tbody.appendChild(tr);
            }
        });
    });
}
