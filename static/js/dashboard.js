/**
 * FinEdge Dashboard - Frontend JS
 * Real-time stock/crypto edge prediction dashboard
 */

const API = {
    dashboard: '/api/dashboard',
    watchlist: '/api/watchlist',
    signals: '/api/signals',
    latestSignals: '/api/signals/latest',
    refresh: '/api/refresh',
    status: '/api/status',
    price: (t) => `/api/price/${t}`,
    history: (t, d) => `/api/history/${t}?days=${d || 90}`,
    indicators: (t) => `/api/indicators/${t}`,
    signal: (t) => `/api/signal/${t}`,
    sentiment: (t) => `/api/sentiment/${t}`,
    model: (t) => `/api/model/${t}`,
    signalHistory: (t) => `/api/signal-history/${t}`,
    retrain: '/api/retrain',
};

let dashboardData = [];
let selectedTicker = null;
let priceChart = null;
let refreshTimer = null;
const AUTO_REFRESH_SEC = 300; // 5 minutes

// ═══════════════════════════════════════════
// Initialization
// ═══════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
    startAutoRefresh();
});

async function loadDashboard() {
    showLoading(true);
    try {
        const res = await fetch(API.dashboard);
        dashboardData = await res.json();
        renderTickerTape();
        renderSummary();
        renderSignalCards();
        showToast('Dashboard loaded', 'success');
    } catch (err) {
        console.error('Dashboard load failed:', err);
        showToast('Failed to load dashboard. Retrying...', 'error');
        // Retry after 10s
        setTimeout(loadDashboard, 10000);
    } finally {
        showLoading(false);
    }
}

// ═══════════════════════════════════════════
// Ticker Tape
// ═══════════════════════════════════════════

function renderTickerTape() {
    const track = document.getElementById('tickerTrack');
    if (!track || !dashboardData.length) return;

    const items = dashboardData.map(item => {
        const price = item.price;
        if (!price) return '';
        const isUp = price.change_pct >= 0;
        const arrow = isUp ? '▲' : '▼';
        const cls = isUp ? 'ticker-up' : 'ticker-down';
        return `
            <div class="ticker-item">
                <span class="ticker-symbol">${item.ticker}</span>
                <span class="ticker-price">$${price.price?.toFixed(2) || '—'}</span>
                <span class="ticker-change ${cls}">${arrow} ${Math.abs(price.change_pct || 0).toFixed(2)}%</span>
            </div>
        `;
    }).join('');

    // Duplicate for seamless scroll
    track.innerHTML = items + items;
}

// ═══════════════════════════════════════════
// Summary Cards
// ═══════════════════════════════════════════

function renderSummary() {
    const container = document.getElementById('summaryRow');
    if (!container) return;

    const total = dashboardData.length;
    const bullish = dashboardData.filter(d => d.edge_score > 25).length;
    const bearish = dashboardData.filter(d => d.edge_score < -25).length;
    const avgEdge = total ? (dashboardData.reduce((s, d) => s + (d.edge_score || 0), 0) / total).toFixed(1) : 0;
    const topPick = dashboardData.length ? dashboardData[0] : null;

    container.innerHTML = `
        <div class="summary-card">
            <div class="summary-label">Tracking</div>
            <div class="summary-value">${total}</div>
            <div class="summary-sub">Assets monitored</div>
        </div>
        <div class="summary-card">
            <div class="summary-label">Bullish</div>
            <div class="summary-value" style="color: var(--accent-green)">${bullish}</div>
            <div class="summary-sub">Buy/Strong Buy signals</div>
        </div>
        <div class="summary-card">
            <div class="summary-label">Bearish</div>
            <div class="summary-value" style="color: var(--accent-red)">${bearish}</div>
            <div class="summary-sub">Sell/Strong Sell signals</div>
        </div>
        <div class="summary-card">
            <div class="summary-label">Avg Edge Score</div>
            <div class="summary-value" style="color: ${avgEdge >= 0 ? 'var(--accent-cyan)' : 'var(--accent-red)'}">${avgEdge > 0 ? '+' : ''}${avgEdge}</div>
            <div class="summary-sub">Market sentiment</div>
        </div>
        <div class="summary-card">
            <div class="summary-label">Top Pick</div>
            <div class="summary-value" style="color: var(--accent-purple)">${topPick ? topPick.ticker : '—'}</div>
            <div class="summary-sub">${topPick ? `Edge: ${topPick.edge_score > 0 ? '+' : ''}${topPick.edge_score}` : 'N/A'}</div>
        </div>
    `;
}

// ═══════════════════════════════════════════
// Signal Cards
// ═══════════════════════════════════════════

function renderSignalCards() {
    const grid = document.getElementById('signalGrid');
    if (!grid) return;

    grid.innerHTML = dashboardData.map(item => {
        const signal = item.signal || 'N/A';
        const signalClass = signal.toLowerCase().replace(/\s+/g, '-');
        const badgeClass = `badge-${signalClass}`;
        const price = item.price || {};
        const isUp = (price.change_pct || 0) >= 0;
        const edgeScore = item.edge_score || 0;

        // Gauge calculation (edge -100 to +100 mapped to 0-100% width)
        const gaugePosition = ((edgeScore + 100) / 200) * 100;
        const gaugeColor = edgeScore > 25 ? 'var(--accent-green)' :
                          edgeScore < -25 ? 'var(--accent-red)' : 'var(--accent-yellow)';

        // Gauge fill: from center (50%) outward
        let gaugeLeft, gaugeWidth;
        if (edgeScore >= 0) {
            gaugeLeft = 50;
            gaugeWidth = (edgeScore / 100) * 50;
        } else {
            gaugeWidth = (Math.abs(edgeScore) / 100) * 50;
            gaugeLeft = 50 - gaugeWidth;
        }

        return `
            <div class="signal-card ${signalClass}" onclick="showDetail('${item.ticker}')">
                <div class="card-top">
                    <div>
                        <div class="card-ticker">${item.ticker}</div>
                        <div class="card-name">${item.name || item.ticker}</div>
                    </div>
                    <div class="card-badge ${badgeClass}">${signal}</div>
                </div>

                <div class="card-price-row">
                    <span class="card-price">$${price.price?.toFixed(2) || '—'}</span>
                    <span class="card-change ${isUp ? 'ticker-up' : 'ticker-down'}">
                        ${isUp ? '▲' : '▼'} ${Math.abs(price.change_pct || 0).toFixed(2)}%
                    </span>
                </div>

                <div class="edge-gauge">
                    <div class="gauge-label">
                        <span>-100</span>
                        <span>EDGE SCORE</span>
                        <span>+100</span>
                    </div>
                    <div class="gauge-bar">
                        <div class="gauge-center"></div>
                        <div class="gauge-fill" style="left:${gaugeLeft}%; width:${gaugeWidth}%; background:${gaugeColor}"></div>
                    </div>
                    <div class="gauge-value" style="color:${gaugeColor}">
                        ${edgeScore > 0 ? '+' : ''}${edgeScore}
                    </div>
                </div>

                <div class="score-breakdown">
                    <div class="score-item">
                        <div class="score-item-label">ML</div>
                        <div class="score-item-value" style="color:${item.ml_score >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">
                            ${item.ml_score > 0 ? '+' : ''}${(item.ml_score || 0).toFixed(0)}
                        </div>
                    </div>
                    <div class="score-item">
                        <div class="score-item-label">Technical</div>
                        <div class="score-item-value" style="color:${item.ta_score >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">
                            ${item.ta_score > 0 ? '+' : ''}${(item.ta_score || 0).toFixed(0)}
                        </div>
                    </div>
                    <div class="score-item">
                        <div class="score-item-label">Sentiment</div>
                        <div class="score-item-value" style="color:${item.sentiment_score >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}">
                            ${item.sentiment_score > 0 ? '+' : ''}${(item.sentiment_score || 0).toFixed(0)}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// ═══════════════════════════════════════════
// Detail Panel
// ═══════════════════════════════════════════

async function showDetail(ticker) {
    selectedTicker = ticker;
    const panel = document.getElementById('detailPanel');
    if (!panel) return;

    panel.classList.add('active');
    document.getElementById('detailTicker').textContent = ticker;

    // Fetch detailed data
    try {
        const [indicatorsRes, sentimentRes, modelRes, historyRes] = await Promise.all([
            fetch(API.indicators(ticker)),
            fetch(API.sentiment(ticker)),
            fetch(API.model(ticker)),
            fetch(API.history(ticker, 90)),
        ]);

        const indicators = await indicatorsRes.json();
        const sentiment = await sentimentRes.json();
        const model = await modelRes.json();
        const history = await historyRes.json();

        renderDetailStats(indicators);
        renderChart(ticker, history);
        renderNews(sentiment.details?.headlines || []);
    } catch (err) {
        console.error('Detail load failed:', err);
        showToast('Failed to load details', 'error');
    }
}

function closeDetail() {
    const panel = document.getElementById('detailPanel');
    if (panel) panel.classList.remove('active');
    selectedTicker = null;
}

function renderDetailStats(indicators) {
    const grid = document.getElementById('detailGrid');
    if (!grid) return;

    const stats = [
        { label: 'RSI (14)', value: indicators.RSI?.toFixed(1) || '—', color: rsiColor(indicators.RSI) },
        { label: 'MACD', value: indicators.MACD?.toFixed(4) || '—', color: indicators.MACD >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' },
        { label: 'MACD Histogram', value: indicators.MACD_Hist?.toFixed(4) || '—', color: indicators.MACD_Hist >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' },
        { label: 'Bollinger %B', value: indicators.BB_Pct?.toFixed(2) || '—' },
        { label: 'Stochastic %K', value: indicators.Stoch_K?.toFixed(1) || '—' },
        { label: 'ATR (14)', value: indicators.ATR?.toFixed(2) || '—' },
        { label: 'CCI (20)', value: indicators.CCI?.toFixed(1) || '—' },
        { label: 'Williams %R', value: indicators.Williams_R?.toFixed(1) || '—' },
        { label: 'Volume Ratio', value: indicators.Volume_Ratio?.toFixed(2) || '—' },
        { label: 'ROC (5d)', value: `${indicators.ROC_5?.toFixed(2) || '—'}%`, color: indicators.ROC_5 >= 0 ? 'var(--accent-green)' : 'var(--accent-red)' },
        { label: 'SMA 20', value: indicators.SMA_20?.toFixed(2) || '—' },
        { label: 'SMA 50', value: indicators.SMA_50?.toFixed(2) || '—' },
    ];

    grid.innerHTML = stats.map(s => `
        <div class="detail-stat">
            <div class="detail-stat-label">${s.label}</div>
            <div class="detail-stat-value" ${s.color ? `style="color:${s.color}"` : ''}>${s.value}</div>
        </div>
    `).join('');
}

function rsiColor(rsi) {
    if (!rsi) return '';
    if (rsi < 30) return 'var(--accent-green)';
    if (rsi > 70) return 'var(--accent-red)';
    return 'var(--accent-yellow)';
}

// ═══════════════════════════════════════════
// Price Chart (Canvas-based)
// ═══════════════════════════════════════════

function renderChart(ticker, history) {
    const canvas = document.getElementById('priceCanvas');
    if (!canvas || !history.length) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = 280 * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = '280px';
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = 280;
    const pad = { top: 20, right: 60, bottom: 30, left: 10 };
    const plotW = W - pad.left - pad.right;
    const plotH = H - pad.top - pad.bottom;

    const closes = history.map(h => h.close);
    const dates = history.map(h => h.date);
    const minP = Math.min(...closes) * 0.995;
    const maxP = Math.max(...closes) * 1.005;

    // Clear
    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = 'rgba(42, 48, 80, 0.4)';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
        const y = pad.top + (plotH / 4) * i;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(W - pad.right, y);
        ctx.stroke();

        // Price labels
        const price = maxP - ((maxP - minP) / 4) * i;
        ctx.fillStyle = '#64748b';
        ctx.font = '10px Inter, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('$' + price.toFixed(2), W - pad.right + 5, y + 4);
    }

    // Date labels
    const dateStep = Math.max(1, Math.floor(closes.length / 6));
    ctx.fillStyle = '#64748b';
    ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'center';
    for (let i = 0; i < closes.length; i += dateStep) {
        const x = pad.left + (i / (closes.length - 1)) * plotW;
        const d = dates[i];
        ctx.fillText(d?.substring(5) || '', x, H - 5);
    }

    // Gradient fill
    const gradient = ctx.createLinearGradient(0, pad.top, 0, H - pad.bottom);
    const isUp = closes[closes.length - 1] >= closes[0];
    if (isUp) {
        gradient.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
        gradient.addColorStop(1, 'rgba(16, 185, 129, 0.0)');
    } else {
        gradient.addColorStop(0, 'rgba(239, 68, 68, 0.25)');
        gradient.addColorStop(1, 'rgba(239, 68, 68, 0.0)');
    }

    // Draw filled area
    ctx.beginPath();
    for (let i = 0; i < closes.length; i++) {
        const x = pad.left + (i / (closes.length - 1)) * plotW;
        const y = pad.top + plotH - ((closes[i] - minP) / (maxP - minP)) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.lineTo(pad.left + plotW, H - pad.bottom);
    ctx.lineTo(pad.left, H - pad.bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    // Draw line
    ctx.beginPath();
    ctx.strokeStyle = isUp ? '#10b981' : '#ef4444';
    ctx.lineWidth = 2;
    for (let i = 0; i < closes.length; i++) {
        const x = pad.left + (i / (closes.length - 1)) * plotW;
        const y = pad.top + plotH - ((closes[i] - minP) / (maxP - minP)) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Latest price dot
    const lastX = pad.left + plotW;
    const lastY = pad.top + plotH - ((closes[closes.length - 1] - minP) / (maxP - minP)) * plotH;
    ctx.beginPath();
    ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
    ctx.fillStyle = isUp ? '#10b981' : '#ef4444';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(lastX, lastY, 8, 0, Math.PI * 2);
    ctx.strokeStyle = isUp ? 'rgba(16,185,129,0.3)' : 'rgba(239,68,68,0.3)';
    ctx.lineWidth = 2;
    ctx.stroke();
}

// ═══════════════════════════════════════════
// News Feed
// ═══════════════════════════════════════════

function renderNews(headlines) {
    const container = document.getElementById('newsFeed');
    if (!container) return;

    if (!headlines || !headlines.length) {
        container.innerHTML = '<div style="color:var(--text-muted);font-size:0.82rem;padding:1rem;">No recent news available</div>';
        return;
    }

    container.innerHTML = headlines.slice(0, 8).map(h => {
        const sentClass = h.sentiment > 0.1 ? 'positive' : h.sentiment < -0.1 ? 'negative' : 'neutral';
        return `
            <div class="news-item">
                <div class="news-sentiment ${sentClass}"></div>
                <div>
                    <div class="news-title">${escapeHtml(h.title)}</div>
                    <div class="news-meta">Sentiment: ${h.sentiment?.toFixed(3) || '0.000'} • ${h.label || 'NEUTRAL'}</div>
                </div>
            </div>
        `;
    }).join('');
}

// ═══════════════════════════════════════════
// Watchlist Management
// ═══════════════════════════════════════════

function showAddModal() {
    document.getElementById('addModal').classList.add('active');
    document.getElementById('tickerInput').value = '';
    document.getElementById('tickerInput').focus();
}

function closeAddModal() {
    document.getElementById('addModal').classList.remove('active');
}

async function addTicker() {
    const input = document.getElementById('tickerInput');
    const ticker = input.value.trim().toUpperCase();
    if (!ticker) return;

    const btn = document.getElementById('addBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Adding...';

    try {
        const res = await fetch(API.watchlist, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticker }),
        });
        const data = await res.json();
        if (data.error) {
            showToast(data.error, 'error');
        } else {
            showToast(`${ticker} added to watchlist`, 'success');
            closeAddModal();
            loadDashboard();
        }
    } catch (err) {
        showToast('Failed to add ticker', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '⚡ Add';
    }
}

async function removeTicker(ticker) {
    if (!confirm(`Remove ${ticker} from watchlist?`)) return;

    try {
        await fetch(`${API.watchlist}/${ticker}`, { method: 'DELETE' });
        showToast(`${ticker} removed`, 'info');
        closeDetail();
        loadDashboard();
    } catch (err) {
        showToast('Failed to remove ticker', 'error');
    }
}

// ═══════════════════════════════════════════
// Actions
// ═══════════════════════════════════════════

async function refreshAll() {
    const btn = document.getElementById('refreshBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Analyzing...';
    showToast('Running full analysis... This may take a minute on your PC', 'info');

    try {
        const res = await fetch(API.refresh, { method: 'POST' });
        const data = await res.json();
        showToast(`Analysis complete: ${data.signals} signals generated`, 'success');
        loadDashboard();
    } catch (err) {
        showToast('Refresh failed', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '⚡ Analyze';
    }
}

async function generateSignal(ticker) {
    showToast(`Generating signal for ${ticker}...`, 'info');
    try {
        const res = await fetch(API.signal(ticker));
        const data = await res.json();
        showToast(`${ticker}: ${data.signal} (Edge: ${data.edge_score})`, 'success');
        loadDashboard();
    } catch (err) {
        showToast('Signal generation failed', 'error');
    }
}

// ═══════════════════════════════════════════
// Auto Refresh
// ═══════════════════════════════════════════

function startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(() => {
        loadDashboard();
    }, AUTO_REFRESH_SEC * 1000);
}

// ═══════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════

function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    if (overlay) {
        overlay.classList.toggle('active', show);
    }
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Handle Enter key in modal
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        const modal = document.getElementById('addModal');
        if (modal?.classList.contains('active')) {
            addTicker();
        }
    }
    if (e.key === 'Escape') {
        closeAddModal();
        closeDetail();
    }
});

// Resize chart on window resize
window.addEventListener('resize', () => {
    if (selectedTicker) {
        fetch(API.history(selectedTicker, 90))
            .then(r => r.json())
            .then(h => renderChart(selectedTicker, h))
            .catch(() => {});
    }
});
