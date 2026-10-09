function initAddChannel() {
    const form = document.getElementById('add-channel-form');
    if (!form) return;
    const input = document.getElementById('channel-input');
    const btn = document.getElementById('add-channel-btn');
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = input.value.trim();
        if (!username) return;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Adding…';
        try {
            const resp = await fetch('/api/channels', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username }),
            });
            const data = await resp.json();
            if (data.ok) {
                showToast(`Channel @${data.channel.username} added!`, 'success');
                input.value = '';
                setTimeout(() => window.location.reload(), 800);
            } else {
                showToast(data.error || 'Failed to add channel', 'error');
            }
        } catch (err) {
            showToast(`Error: ${err.message}`, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = 'Add Channel';
        }
    });
}
function initDigest() {
    const btn = document.getElementById('generate-digest-btn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
        const username = btn.dataset.channel;
        if (!username) return;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner"></span> Generating…';
        const contentEl = document.getElementById('digest-content');
        try {
            const resp = await fetch(`/api/channels/${username}/digest`);
            const data = await resp.json();
            if (data.digest) {
                contentEl.textContent = data.digest;
                contentEl.classList.remove('digest-section__placeholder');
            } else {
                contentEl.textContent = data.error || 'AI digest unavailable.';
                contentEl.classList.add('digest-section__placeholder');
            }
        } catch (err) {
            contentEl.textContent = 'Failed to generate digest.';
            contentEl.classList.add('digest-section__placeholder');
        } finally {
            btn.disabled = false;
            btn.textContent = '🔄 Generate Digest';
        }
    });
}
function showToast(message, type = 'info') {
    document.querySelectorAll('.toast').forEach(t => t.remove());
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}
function initCharts() {
    initViewsChart();
    initSubscribersChart();
    initPostMetricsChart();
}
function initViewsChart() {
    const el = document.getElementById('views-chart');
    if (!el) return;
    const rawData = el.dataset.views;
    if (!rawData) return;
    const data = JSON.parse(rawData);
    if (!data.length) return;
    new Chart(el, {
        type: 'bar',
        data: {
            labels: data.map(d => d.date),
            datasets: [{
                label: 'Total Views',
                data: data.map(d => d.views),
                backgroundColor: 'rgba(108, 99, 255, 0.5)',
                borderColor: 'rgba(108, 99, 255, 1)',
                borderWidth: 1,
                borderRadius: 4,
            }],
        },
        options: chartOptions('Views per Day'),
    });
}
function initSubscribersChart() {
    const el = document.getElementById('subscribers-chart');
    if (!el) return;
    const rawData = el.dataset.subscribers;
    if (!rawData) return;
    const data = JSON.parse(rawData);
    if (!data.length) return;
    new Chart(el, {
        type: 'line',
        data: {
            labels: data.map(d => d.date ? d.date.split('T')[0] : ''),
            datasets: [{
                label: 'Subscribers',
                data: data.map(d => d.subscribers),
                borderColor: 'rgba(52, 211, 153, 1)',
                backgroundColor: 'rgba(52, 211, 153, 0.1)',
                tension: 0.3,
                fill: true,
                pointRadius: 3,
            }],
        },
        options: chartOptions('Subscribers'),
    });
}
function initPostMetricsChart() {
    const el = document.getElementById('post-metrics-chart');
    if (!el) return;
    const rawData = el.dataset.metrics;
    if (!rawData) return;
    const data = JSON.parse(rawData);
    if (!data.length) return;
    new Chart(el, {
        type: 'line',
        data: {
            labels: data.map(d => d.date ? d.date.split('T')[0] : ''),
            datasets: [{
                label: 'Views',
                data: data.map(d => d.views),
                borderColor: 'rgba(108, 99, 255, 1)',
                backgroundColor: 'rgba(108, 99, 255, 0.1)',
                tension: 0.3,
                fill: true,
                pointRadius: 3,
            }],
        },
        options: chartOptions('Views Over Time'),
    });
}
function chartOptions(title) {
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            title: { display: false },
        },
        scales: {
            x: {
                grid: { color: 'rgba(45, 50, 80, 0.5)' },
                ticks: { color: '#6b6f85', maxTicksLimit: 8, font: { size: 11 } },
            },
            y: {
                grid: { color: 'rgba(45, 50, 80, 0.5)' },
                ticks: { color: '#6b6f85', font: { size: 11 } },
                beginAtZero: true,
            },
        },
    };
}
document.addEventListener('DOMContentLoaded', () => {
    initAddChannel();
    initDigest();
    initCharts();
});