/* ══ Ixtli — common.js ══════════════════════════════════════════════════════ */

// ── Formatters ────────────────────────────────────────────────────────────────
const fmt = {
    money : v => '$' + Number(v).toLocaleString('es-MX', { minimumFractionDigits:2, maximumFractionDigits:2 }),
    num   : v => Number(v).toLocaleString('es-MX'),
    date  : v => v ? new Date(v + (v.includes('T') ? '' : 'T12:00:00')).toLocaleDateString('es-MX', { day:'2-digit', month:'short', year:'numeric' }) : '—',
    time  : () => new Date().toLocaleTimeString('es-MX', { hour:'2-digit', minute:'2-digit' }),
    now   : () => new Date().toLocaleTimeString('es-MX', { hour:'2-digit', minute:'2-digit', second:'2-digit' }),
};

// ── API helper ────────────────────────────────────────────────────────────────
const API = {
    get: async path => {
        const r = await fetch(path);
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r.status}`); }
        return r.json();
    },
    post: async (path, body) => {
        const r = await fetch(path, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r.status}`); }
        return r.json();
    },
    patch: async (path, body) => {
        const r = await fetch(path, { method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r.status}`); }
        return r.json();
    },
    del: async path => {
        const r = await fetch(path, { method:'DELETE' });
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r.status}`); }
        return r.json();
    },
    upload: async (path, formData) => {
        const r = await fetch(path, { method:'POST', body:formData });
        if (!r.ok) { const e = await r.json().catch(() => ({})); throw new Error(e.detail || `HTTP ${r.status}`); }
        return r.json();
    },
};

// ── Sidebar ───────────────────────────────────────────────────────────────────
function initSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    const burger  = document.getElementById('burger');
    const sClose  = document.getElementById('sClose');
    if (!sidebar) return;

    const open  = () => { sidebar.classList.add('open');    overlay?.classList.add('show'); };
    const close = () => { sidebar.classList.remove('open'); overlay?.classList.remove('show'); };

    burger?.addEventListener('click', open);
    sClose?.addEventListener('click', close);
    overlay?.addEventListener('click', close);

    // Auto-mark active link based on current URL
    const path = window.location.pathname;
    sidebar.querySelectorAll('.s-link').forEach(l => {
        const href = l.getAttribute('href') || '';
        l.classList.toggle('active', href === path || (path === '/' && href === '/'));
    });
}

// ── Live clock ────────────────────────────────────────────────────────────────
function initClock(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const tick = () => el.textContent = fmt.time();
    tick(); setInterval(tick, 10000);
}

// ── Flash banner ─────────────────────────────────────────────────────────────
function flash(id, msg, type = 'ok', ms = 3500) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = msg;
    el.className = `alert-banner ${type} show`;
    setTimeout(() => el.classList.remove('show'), ms);
}

// ── Modal helpers ─────────────────────────────────────────────────────────────
function openModal(id)  { document.getElementById(id)?.classList.add('show'); }
function closeModal(id) { document.getElementById(id)?.classList.remove('show'); }

// ── Init all on page load ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    initClock('hTime');
});
