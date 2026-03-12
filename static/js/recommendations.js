function renderRecommendations(data) {
    const container = document.getElementById('tab-recommendations');
    const recs = data.recommendations;

    if (!recs || recs.length === 0) {
        container.innerHTML = `
            <div class="exec-summary">
                <h3>No Recommendations</h3>
                <p>Everything looks good! No specific issues detected based on the uploaded data.</p>
            </div>`;
        return;
    }

    // Group by priority
    const grouped = { high: [], medium: [], low: [] };
    recs.forEach(r => {
        if (grouped[r.priority]) grouped[r.priority].push(r);
    });

    const priorityLabels = { high: 'High Priority', medium: 'Medium Priority', low: 'Low Priority' };

    let html = '';

    // Quick wins section (first 3 high-priority items)
    if (grouped.high.length > 0) {
        html += `
        <div class="exec-summary" style="border-left: 4px solid #dc2626; margin-bottom: 24px;">
            <h3>Quick Wins</h3>
            <p>${grouped.high.slice(0, 3).map(r => r.title).join(' &bull; ')}</p>
        </div>`;
    }

    for (const [priority, items] of Object.entries(grouped)) {
        if (items.length === 0) continue;

        html += `
        <div class="recs-section">
            <div class="recs-section-title priority-${priority}">${priorityLabels[priority]} (${items.length})</div>`;

        for (const rec of items) {
            html += `
            <div class="rec-card priority-${rec.priority}">
                <div class="rec-header">
                    <span class="rec-title">${rec.title}</span>
                    <span class="rec-category">${rec.category}</span>
                </div>
                <div class="rec-detail">${rec.detail}</div>`;

            if (rec.affected_campaigns && rec.affected_campaigns.length > 0) {
                html += '<div class="rec-campaigns">';
                rec.affected_campaigns.forEach(c => {
                    html += `<span class="rec-campaign-tag">${c.length > 35 ? c.slice(0, 33) + '...' : c}</span>`;
                });
                html += '</div>';
            }

            if (rec.potential_impact) {
                html += `<div class="rec-impact">Potential impact: ${rec.potential_impact}</div>`;
            }

            html += '</div>';
        }

        html += '</div>';
    }

    container.innerHTML = html;
}
