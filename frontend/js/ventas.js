/* ══ Ixtli — ventas.js ══════════════════════════════════════════════════════ */

const $ = id => document.getElementById(id);
let productosCache = [];

// ── Cargar tabla de ventas ────────────────────────────────────────────────────
async function loadVentas(desde, hasta) {
    const tbody   = $('ventasTbody');
    const subtitle = $('tblSubtitle');
    tbody.innerHTML = `<tr><td colspan="6" class="empty">Cargando…</td></tr>`;

    let url = '/ventas/';
    if (desde && hasta) url += `?desde=${desde}&hasta=${hasta}`;

    try {
        const data = await API.get(url);

        // KPIs del período
        const total = data.reduce((s, v) => s + (v.precio_total || 0), 0);
        const avg   = data.length ? total / data.length : 0;
        $('kTotal').textContent = fmt.money(total);
        $('kTotalMeta').textContent = desde ? `${desde} → ${hasta}` : 'todo el historial';
        $('kCount').textContent = fmt.num(data.length);
        $('kAvg').textContent   = fmt.money(avg);

        if (desde && hasta) {
            subtitle.textContent = `${data.length} ventas entre ${desde} y ${hasta}`;
        } else {
            subtitle.textContent = `${data.length} ventas en total`;
        }

        if (!data.length) {
            tbody.innerHTML = `<tr><td colspan="6" class="empty">Sin ventas en el período</td></tr>`;
            return;
        }

        tbody.innerHTML = data.map(v => `
            <tr>
                <td class="td-muted">#${v.id}</td>
                <td style="font-weight:500">${v.producto_nombre}</td>
                <td>${fmt.num(v.cantidad)}</td>
                <td>${v.precio_unitario != null ? fmt.money(v.precio_unitario) : '<span class="td-muted">—</span>'}</td>
                <td style="font-weight:600;color:var(--accent-hi)">${v.precio_total != null ? fmt.money(v.precio_total) : '<span class="td-muted">—</span>'}</td>
                <td class="td-muted">${fmt.date(v.fecha)}</td>
            </tr>`).join('');
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty" style="color:var(--red)">${e.message}</td></tr>`;
        console.error('Ventas:', e);
    }
}

// ── Cargar productos para el modal ────────────────────────────────────────────
async function loadProductosSelect() {
    if (productosCache.length) return;
    try {
        productosCache = await API.get('/productos/');
        const sel = $('fProducto');
        sel.innerHTML = '<option value="">Seleccionar producto…</option>' +
            productosCache.map(p =>
                `<option value="${p.id}" data-precio="${p.precio_venta || ''}" data-stock="${p.stock_actual}">${p.nombre} (stock: ${p.stock_actual})</option>`
            ).join('');
    } catch(e) { console.error('Productos select:', e); }
}

// ── Modal nueva venta ─────────────────────────────────────────────────────────
$('btnNuevaVenta')?.addEventListener('click', async () => {
    await loadProductosSelect();
    $('fCantidad').value = '1';
    $('fPrecio').value = '';
    $('fFecha').value = '';
    openModal('modalBg');
});

$('modalClose')?.addEventListener('click', () => closeModal('modalBg'));
$('btnCancelar')?.addEventListener('click', () => closeModal('modalBg'));

$('fProducto')?.addEventListener('change', e => {
    const opt = e.target.selectedOptions[0];
    const precio = opt?.dataset.precio;
    if (precio) $('fPrecio').placeholder = `Precio sugerido: $${precio}`;
    else $('fPrecio').placeholder = 'Se usa el precio del producto';
});

$('btnGuardar')?.addEventListener('click', async () => {
    const productoId = parseInt($('fProducto').value);
    const cantidad   = parseInt($('fCantidad').value);
    const precio     = parseFloat($('fPrecio').value) || undefined;
    const fecha      = $('fFecha').value || undefined;

    if (!productoId) { flash('flashModal', 'Selecciona un producto', 'err'); return; }
    if (!cantidad || cantidad < 1) { flash('flashModal', 'La cantidad debe ser mayor a 0', 'err'); return; }

    const btn = $('btnGuardar');
    btn.disabled = true; btn.textContent = 'Guardando…';

    try {
        const body = { producto_id: productoId, cantidad };
        if (precio)  body.precio_unitario = precio;
        if (fecha)   body.fecha = fecha;

        await API.post('/ventas/', body);
        closeModal('modalBg');
        flash('flashBanner', 'Venta registrada correctamente', 'ok');
        productosCache = []; // reset cache (stock cambió)
        loadVentas($('fDesde').value || undefined, $('fHasta').value || undefined);
    } catch(e) {
        flash('flashModal', e.message, 'err');
    } finally {
        btn.disabled = false; btn.textContent = 'Registrar';
    }
});

// ── Filtros ───────────────────────────────────────────────────────────────────
$('btnFiltrar')?.addEventListener('click', () => {
    const desde = $('fDesde').value;
    const hasta = $('fHasta').value;
    if (desde && !hasta || !desde && hasta) {
        flash('flashBanner', 'Debes indicar ambas fechas', 'err'); return;
    }
    loadVentas(desde || undefined, hasta || undefined);
});

$('btnLimpiar')?.addEventListener('click', () => {
    $('fDesde').value = '';
    $('fHasta').value = '';
    loadVentas();
});

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => loadVentas());
