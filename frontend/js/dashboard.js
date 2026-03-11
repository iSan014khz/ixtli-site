/* ══ Ixtli — dashboard.js ═══════════════════════════════════════════════════ */

// ── Chart.js defaults ─────────────────────────────────────────────────────────
Chart.defaults.color = '#37506a';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.font.size = 11;
const GRID = 'rgba(59,130,246,0.06)';
const TICK = '#37506a';

let chartV = null, chartT = null;

const $ = id => document.getElementById(id);

// ── KPI Cards ─────────────────────────────────────────────────────────────────
async function loadKPIs() {
    try {
        const d = await API.get('/reportes/dashboard');
        $('kVentas').textContent     = fmt.money(d.ventas_totales_hoy);
        $('kVentasMeta').textContent = `${fmt.num(d.num_transacciones_hoy)} transacciones hoy`;
        $('kTxs').textContent        = fmt.num(d.num_transacciones_hoy);
        $('kTicket').textContent     = fmt.money(d.ticket_promedio_hoy);
        $('kAlertas').textContent    = fmt.num(d.alertas_activas);
        const badge = $('sBadge');
        if (d.alertas_activas > 0) { badge.textContent = d.alertas_activas; badge.style.display = ''; }
        else { badge.style.display = 'none'; }
    } catch(e) {
        ['kVentas','kTxs','kTicket','kAlertas'].forEach(id => $(id) && ($(id).textContent = '—'));
        console.error('KPIs:', e);
    }
}

// ── Ventas por período ─────────────────────────────────────────────────────────
async function loadVentas(agrupacion = 'semana') {
    try {
        const data = await API.get(`/reportes/ventas-por-periodo?agrupacion=${agrupacion}`);

        if (chartV) { chartV.destroy(); chartV = null; }

        const ctx = $('ventasChart').getContext('2d');
        const grad = ctx.createLinearGradient(0, 0, 0, 240);
        grad.addColorStop(0,   'rgba(59,130,246,0.38)');
        grad.addColorStop(0.7, 'rgba(59,130,246,0.08)');
        grad.addColorStop(1,   'rgba(59,130,246,0.01)');

        chartV = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => d.periodo),
                datasets: [{
                    data: data.map(d => d.total),
                    borderColor: '#3b82f6', borderWidth: 2.5,
                    backgroundColor: grad, fill: true, tension: 0.42,
                    pointRadius: data.length > 50 ? 0 : 3.5,
                    pointBackgroundColor: '#3b82f6',
                    pointBorderColor: '#101827', pointBorderWidth: 2,
                    pointHoverRadius: 5,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#182236', borderColor: 'rgba(59,130,246,0.3)',
                        borderWidth: 1, padding: 10,
                        callbacks: {
                            label: c => ` ${fmt.money(c.parsed.y)}`,
                            title: c => c[0].label,
                        }
                    }
                },
                scales: {
                    x: { grid:{ color:GRID }, ticks:{ color:TICK, maxTicksLimit:10, maxRotation:0 } },
                    y: { grid:{ color:GRID }, ticks:{ color:TICK, callback: v => '$'+(v>=1000?(v/1000).toFixed(0)+'k':v) } }
                }
            }
        });
    } catch(e) { console.error('Ventas chart:', e); }
}

// ── Top productos ─────────────────────────────────────────────────────────────
async function loadTopProductos() {
    const c = $('topList');
    try {
        const data = await API.get('/reportes/top-productos?limite=8');
        if (!data.length) { c.innerHTML = '<div class="empty">Sin datos</div>'; return; }
        const max = data[0].cantidad_total;
        c.innerHTML = data.map(p => `
            <div class="prod-row">
                <div class="prod-rank ${p.posicion <= 3 ? 'hi' : ''}">#${p.posicion}</div>
                <div class="prod-name" title="${p.producto}">${p.producto}</div>
                <div class="prod-bar-bg">
                    <div class="prod-bar-fill" style="width:${Math.round(p.cantidad_total/max*100)}%"></div>
                </div>
                <div class="prod-qty">${fmt.num(p.cantidad_total)}</div>
            </div>`).join('');
    } catch(e) { c.innerHTML = '<div class="empty">Error al cargar</div>'; console.error(e); }
}

// ── Ticket promedio ───────────────────────────────────────────────────────────
async function loadTicket(agrupacion = 'dia') {
    try {
        const data = await API.get(`/reportes/ticket-promedio?agrupacion=${agrupacion}`);

        if (chartT) { chartT.destroy(); chartT = null; }

        const ctx = $('ticketChart').getContext('2d');
        const grad = ctx.createLinearGradient(0, 0, 0, 200);
        grad.addColorStop(0,   'rgba(6,182,212,0.32)');
        grad.addColorStop(0.7, 'rgba(6,182,212,0.07)');
        grad.addColorStop(1,   'rgba(6,182,212,0.01)');

        chartT = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.map(d => d.periodo),
                datasets: [{
                    data: data.map(d => d.ticket_promedio),
                    borderColor: '#06b6d4', borderWidth: 2.5,
                    backgroundColor: grad, fill: true, tension: 0.42,
                    pointRadius: data.length > 50 ? 0 : 3.5,
                    pointBackgroundColor: '#06b6d4',
                    pointBorderColor: '#101827', pointBorderWidth: 2,
                    pointHoverRadius: 5,
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: '#182236', borderColor: 'rgba(6,182,212,0.3)',
                        borderWidth: 1, padding: 10,
                        callbacks: { label: c => ` ${fmt.money(c.parsed.y)}` }
                    }
                },
                scales: {
                    x: { grid:{ color:GRID }, ticks:{ color:TICK, maxTicksLimit:8, maxRotation:0 } },
                    y: { grid:{ color:GRID }, ticks:{ color:TICK, callback: v => '$'+(v>=1000?(v/1000).toFixed(0)+'k':v) } }
                }
            }
        });
    } catch(e) { console.error('Ticket chart:', e); }
}

// ── Alertas de stock ──────────────────────────────────────────────────────────
async function loadAlertas() {
    const c = $('alertasList');
    try {
        const data = await API.get('/productos/alertas');
        if (!data.length) { c.innerHTML = '<div class="empty">✅ Todos los productos sobre el mínimo</div>'; return; }
        c.innerHTML = data.map(a => `
            <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid var(--border)">
                <div style="font-size:13px;font-weight:500;flex:1">${a.nombre}</div>
                <div style="font-size:11.5px;color:var(--text-3);white-space:nowrap">${a.stock_actual}/${a.stock_minimo}</div>
                <span class="badge red">−${a.stock_minimo - a.stock_actual}</span>
            </div>`).join('');
    } catch(e) { c.innerHTML = '<div class="empty">Error al cargar</div>'; console.error(e); }
}

// ── Rotación / Stock crítico ──────────────────────────────────────────────────
async function loadRotacion() {
    try {
        const data = await API.get('/reportes/rotacion');
        const criticos = data.filter(p => p.dias_stock_estimados !== null && p.dias_stock_estimados <= 3);
        const alertas  = data.filter(p => p.dias_stock_estimados !== null && p.dias_stock_estimados > 3  && p.dias_stock_estimados <= 7);
        const vigilar  = data.filter(p => p.dias_stock_estimados !== null && p.dias_stock_estimados > 7  && p.dias_stock_estimados <= 30);

        const renderItems = (items, cls) => !items.length
            ? `<div class="s-empty">Sin productos aquí</div>`
            : items.map(p => `
                <div class="stock-item">
                    <div class="stock-item-name" title="${p.nombre}">${p.nombre}</div>
                    <div class="stock-item-meta">
                        <span>Stock: ${p.stock_actual}</span>
                        <span class="s-dias ${cls}">${p.dias_stock_estimados}d</span>
                    </div>
                </div>`).join('');

        $('colC').innerHTML = renderItems(criticos, 'critico');
        $('colA').innerHTML = renderItems(alertas,  'alerta');
        $('colV').innerHTML = renderItems(vigilar,  'vigilar');
    } catch(e) {
        $('stockCols').innerHTML = '<div class="empty">Error al cargar rotación</div>';
        console.error(e);
    }
}

// ── Tab listeners ─────────────────────────────────────────────────────────────
$('vTabs')?.addEventListener('click', e => {
    const b = e.target.closest('.ptab'); if (!b) return;
    $('vTabs').querySelectorAll('.ptab').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    loadVentas(b.dataset.v);
});

$('tTabs')?.addEventListener('click', e => {
    const b = e.target.closest('.ptab'); if (!b) return;
    $('tTabs').querySelectorAll('.ptab').forEach(x => x.classList.remove('active'));
    b.classList.add('active');
    loadTicket(b.dataset.t);
});

// ── Refresh ───────────────────────────────────────────────────────────────────
async function loadAll() {
    const up = $('lastUp');
    if (up) up.textContent = 'cargando…';
    await Promise.allSettled([
        loadKPIs(), loadVentas('semana'), loadTopProductos(),
        loadTicket('dia'), loadAlertas(), loadRotacion(),
    ]);
    if (up) up.textContent = fmt.now();
}

$('refreshBtn')?.addEventListener('click', async () => {
    const btn = $('refreshBtn');
    btn.textContent = '↻ Cargando…'; btn.disabled = true;
    await loadAll();
    btn.textContent = '↻ Actualizar'; btn.disabled = false;
});

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', loadAll);
