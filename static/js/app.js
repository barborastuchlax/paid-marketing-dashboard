// ===== Global State =====
let analysisData = null;
let chartInstances = [];

// ===== Helpers =====
function fmt(n, decimals = 0) {
    if (n == null) return 'N/A';
    return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
function fmtCurrency(n) {
    if (n == null) return 'N/A';
    if (Math.abs(n) >= 1000) return '$' + fmt(n, 0);
    return '$' + fmt(n, 2);
}
function fmtPct(n) {
    if (n == null) return 'N/A';
    return (n * 100).toFixed(2) + '%';
}
function fmtPctRaw(n) {
    if (n == null) return 'N/A';
    return n.toFixed(2) + '%';
}
function channelLabel(ch) {
    return ch === 'google_ads' ? 'Google Ads' : ch === 'linkedin_ads' ? 'LinkedIn Ads' : ch;
}
function channelTagClass(ch) {
    return ch === 'google_ads' ? 'google' : 'linkedin';
}
function gradeClass(grade) {
    if (!grade || grade === 'N/A') return 'grade-na';
    const l = grade[0].toUpperCase();
    if (l === 'A') return 'grade-a';
    if (l === 'B') return 'grade-b';
    if (l === 'C') return 'grade-c';
    if (l === 'D') return 'grade-d';
    return 'grade-f';
}
function destroyCharts() {
    chartInstances.forEach(c => c.destroy());
    chartInstances = [];
}

// ===== File Upload Logic =====
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('upload-form');
    const googleInput = document.getElementById('google-csv');
    const linkedinInput = document.getElementById('linkedin-csv');
    const googleDrop = document.getElementById('google-drop');
    const linkedinDrop = document.getElementById('linkedin-drop');

    // Advanced settings toggle
    const advToggle = document.getElementById('advanced-toggle');
    const advContent = document.getElementById('advanced-content');
    if (advToggle && advContent) {
        advToggle.addEventListener('click', () => {
            advToggle.classList.toggle('open');
            advContent.classList.toggle('open');
        });
    }

    // File input change handlers
    googleInput.addEventListener('change', () => updateFileLabel(googleInput, 'google-file-name', 'google-drop'));
    linkedinInput.addEventListener('change', () => updateFileLabel(linkedinInput, 'linkedin-file-name', 'linkedin-drop'));

    // Drag and drop
    [['google-drop', googleInput], ['linkedin-drop', linkedinInput]].forEach(([id, input]) => {
        const zone = document.getElementById(id);
        zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                updateFileLabel(input, id === 'google-drop' ? 'google-file-name' : 'linkedin-file-name', id);
            }
        });
    });

    // Form submit
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const errEl = document.getElementById('upload-error');
        errEl.classList.add('hidden');

        const googleFile = googleInput.files[0];
        const linkedinFile = linkedinInput.files[0];

        if (!googleFile && !linkedinFile) {
            errEl.textContent = 'Please upload at least one CSV file.';
            errEl.classList.remove('hidden');
            return;
        }

        const btn = document.getElementById('analyze-btn');
        btn.disabled = true;
        document.getElementById('btn-text').classList.add('hidden');
        document.getElementById('btn-loading').classList.remove('hidden');

        const formData = new FormData();
        if (googleFile) formData.append('google_ads_csv', googleFile);
        if (linkedinFile) formData.append('linkedin_ads_csv', linkedinFile);
        formData.append('avg_customer_ltv', document.getElementById('ltv-input').value || '0');
        formData.append('monthly_revenue', document.getElementById('revenue-input').value || '0');

        try {
            const res = await fetch('/api/analyze', { method: 'POST', body: formData });
            const data = await res.json();

            if (!res.ok) {
                errEl.textContent = data.error || 'Analysis failed. Please check your CSV format.';
                errEl.classList.remove('hidden');
                return;
            }

            analysisData = data;
            showResults();
        } catch (err) {
            errEl.textContent = 'Network error. Please try again.';
            errEl.classList.remove('hidden');
        } finally {
            btn.disabled = false;
            document.getElementById('btn-text').classList.remove('hidden');
            document.getElementById('btn-loading').classList.add('hidden');
        }
    });

    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
        });
    });

    // New analysis
    document.getElementById('new-analysis-btn').addEventListener('click', () => {
        destroyCharts();
        analysisData = null;
        document.getElementById('upload-section').classList.remove('hidden');
        document.getElementById('results-section').classList.add('hidden');
    });
});

function updateFileLabel(input, nameId, zoneId) {
    const nameEl = document.getElementById(nameId);
    const zone = document.getElementById(zoneId);
    if (input.files.length) {
        nameEl.textContent = input.files[0].name;
        zone.classList.add('has-file');
    } else {
        nameEl.textContent = 'No file chosen';
        zone.classList.remove('has-file');
    }
}

function showResults() {
    destroyCharts();
    document.getElementById('upload-section').classList.add('hidden');
    document.getElementById('results-section').classList.remove('hidden');

    // Reset to dashboard tab
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    document.querySelector('[data-tab="dashboard"]').classList.add('active');
    document.getElementById('tab-dashboard').classList.add('active');

    renderDashboard(analysisData);
    renderReport(analysisData);
    renderScorecard(analysisData);
    renderRecommendations(analysisData);
}
