/* ══ Ixtli — productos.js ═══════════════════════════════════════════════════ */

const $ = id => document.getElementById(id);
let todosProductos = [];
let editandoId = null;
let eliminandoId = null;

// ── Cargar productos ──────────────────────────────────────────────────────────
async function loadProductos() {
    try {
        todosProductos = await API.get('/productos/');
        popularCategorias();
        renderProductos();
        actualizarKPIs();
    } catch(e) {
        $('prodsGrid').innerHTML = `<div class="empty" style="color:var(--red)">${e.message}</div>`;
        console.error('Productos:', e);
    }
}

function popularCategorias() {
    const cats = [...new Set(todosProductos.map(p => p.categoria).filter(Boolean))].sort();
    const sel = $('fCateg');
    const current = sel.value;
    sel.innerHTML = '<option value="">Todas</option>' + cats.map(c => `<option value="${c}">${c}</option>`).join('');
    sel.value = current;
}

function renderProductos() {
    const grid       = $('prodsGrid');
    const catFiltro  = $('fCateg').value;
    const soloAlerta = $('fSoloAlertas').checked;

    let lista = todosProductos;
    if (catFiltro) lista = lista.filter(p => p.categoria === catFiltro);
    if (soloAlerta) lista = lista.filter(p => p.stock_actual < p.stock_minimo);

    if (!lista.length) {
        grid.innerHTML = '<div class="empty" style="grid-column:1/-1">Sin productos que mostrar</div>';
        return;
    }

    grid.innerHTML = lista.map(p => {
        const alerta  = p.stock_actual < p.stock_minimo;
        const stockCls = alerta ? 'color:var(--red)' : 'color:var(--green)';
        return `
            <div class="prod-card ${alerta ? 'alerta' : ''}">
                ${alerta ? '<span class="badge red" style="position:absolute;top:10px;right:10px;font-size:10px">⚠️ Alerta</span>' : ''}
                <div class="prod-card-name">${p.nombre}</div>
                <div class="prod-card-cat">${p.categoria || 'Sin categoría'}</div>
                <div class="prod-card-row"><span>Precio venta</span><span>${p.precio_venta != null ? fmt.money(p.precio_venta) : '—'}</span></div>
                ${p.costo != null ? `<div class="prod-card-row"><span>Costo</span><span>${fmt.money(p.costo)}</span></div>` : ''}
                ${p.costo != null && p.precio_venta ? (() => { const pct = ((p.precio_venta-p.costo)/p.precio_venta*100).toFixed(1); return `<div class="prod-card-row"><span>Margen</span><span style="color:var(--green);font-weight:700">${pct}%</span></div>`; })() : ''}
                <div class="prod-card-row"><span>Stock actual</span><span style="${stockCls}">${fmt.num(p.stock_actual)} ${p.unidad}</span></div>
                <div class="prod-card-row"><span>Stock mínimo</span><span>${p.stock_minimo} ${p.unidad}</span></div>
                <div class="prod-card-actions">
                    <button class="btn btn-ghost btn-sm" onclick="abrirEditar(${p.id})">✏️ Editar</button>
                    <button class="btn btn-danger btn-sm" onclick="abrirEliminar(${p.id},'${p.nombre.replace(/'/g,"\\'")}')">🗑</button>
                </div>
            </div>`;
    }).join('');
}

function actualizarKPIs() {
    const alertas = todosProductos.filter(p => p.stock_actual < p.stock_minimo).length;
    $('kTotal').textContent   = fmt.num(todosProductos.length);
    $('kAlertas').textContent = fmt.num(alertas);
    $('kOk').textContent      = fmt.num(todosProductos.length - alertas);
}

// ── Filtros ───────────────────────────────────────────────────────────────────
$('fCateg')?.addEventListener('change', renderProductos);
$('fSoloAlertas')?.addEventListener('change', renderProductos);

// ── Modal crear ───────────────────────────────────────────────────────────────
$('btnNuevo')?.addEventListener('click', () => {
    editandoId = null;
    $('modalTitle').textContent = 'Nuevo Producto';
    $('fNombre').value    = '';
    $('fCategoria').value = '';
    $('fUnidad').value    = 'pieza';
    $('fPrecio').value    = '';
    $('fCosto').value     = '';
    $('fStockMin').value  = '5';
    $('margenPreview').style.display = 'none';
    openModal('modalBg');
});

function calcularMargenPreview() {
    const precio = parseFloat($('fPrecio').value);
    const costo  = parseFloat($('fCosto').value);
    const prev   = $('margenPreview');
    const val    = $('margenVal');
    if (precio > 0 && costo >= 0 && costo < precio) {
        const pct = ((precio - costo) / precio * 100).toFixed(1);
        const unit = (precio - costo).toFixed(2);
        val.textContent = `${pct}% · $${unit} por unidad`;
        prev.style.display = '';
    } else {
        prev.style.display = 'none';
    }
}

$('fPrecio')?.addEventListener('input', calcularMargenPreview);
$('fCosto')?.addEventListener('input', calcularMargenPreview);

function abrirEditar(id) {
    const p = todosProductos.find(x => x.id === id);
    if (!p) return;
    editandoId = id;
    $('modalTitle').textContent = 'Editar Producto';
    $('fNombre').value    = p.nombre;
    $('fCategoria').value = p.categoria || '';
    $('fUnidad').value    = p.unidad;
    $('fPrecio').value    = p.precio_venta || '';
    $('fCosto').value     = p.costo || '';
    $('fStockMin').value  = p.stock_minimo;
    calcularMargenPreview();
    openModal('modalBg');
}

$('modalClose')?.addEventListener('click', () => closeModal('modalBg'));
$('btnCancelar')?.addEventListener('click', () => closeModal('modalBg'));

$('btnGuardar')?.addEventListener('click', async () => {
    const nombre    = $('fNombre').value.trim();
    const categoria = $('fCategoria').value.trim();
    const unidad    = $('fUnidad').value;
    const precio    = parseFloat($('fPrecio').value) || null;
    const costo     = parseFloat($('fCosto').value)  || null;
    const stockMin  = parseInt($('fStockMin').value)  || 5;

    if (!nombre) { flash('flashModal', 'El nombre es obligatorio', 'err'); return; }

    const btn = $('btnGuardar');
    btn.disabled = true; btn.textContent = 'Guardando…';

    try {
        if (editandoId) {
            await API.patch(`/productos/${editandoId}`, { nombre, categoria, precio_venta: precio, costo, stock_minimo: stockMin, unidad });
            flash('flashBanner', 'Producto actualizado', 'ok');
        } else {
            await API.post('/productos/', { nombre, categoria, precio_venta: precio, costo, stock_minimo: stockMin, unidad });
            flash('flashBanner', 'Producto creado', 'ok');
        }
        closeModal('modalBg');
        await loadProductos();
    } catch(e) {
        flash('flashModal', e.message, 'err');
    } finally {
        btn.disabled = false; btn.textContent = 'Guardar';
    }
});

// ── Modal eliminar ────────────────────────────────────────────────────────────
function abrirEliminar(id, nombre) {
    eliminandoId = id;
    $('deleteNombre').textContent = nombre;
    openModal('modalDelete');
}

$('btnCancelarDel')?.addEventListener('click', () => closeModal('modalDelete'));

$('btnConfirmarDel')?.addEventListener('click', async () => {
    if (!eliminandoId) return;
    const btn = $('btnConfirmarDel');
    btn.disabled = true; btn.textContent = 'Eliminando…';
    try {
        await API.del(`/productos/${eliminandoId}`);
        closeModal('modalDelete');
        flash('flashBanner', 'Producto eliminado', 'ok');
        await loadProductos();
    } catch(e) {
        flash('flashDelete', e.message, 'err');
    } finally {
        btn.disabled = false; btn.textContent = 'Sí, eliminar';
        eliminandoId = null;
    }
});

// ── Stock mínimo automático ───────────────────────────────────────────────────
let stockSugerencias = [];

async function cargarPreviewStock() {
    const ventana  = $('fVentana').value;
    const leadTime = $('fLeadTime').value;
    const tbody    = $('tblStockBody');
    tbody.innerHTML = `<tr><td colspan="6" class="empty">Calculando con pandas…</td></tr>`;

    try {
        stockSugerencias = await API.get(
            `/reportes/stock-minimo-sugerido?ventana_dias=${ventana}&lead_time_dias=${leadTime}`
        );
        renderStockTable();
    } catch(e) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty" style="color:var(--red)">${e.message}</td></tr>`;
    }
}

function renderStockTable() {
    const tbody = $('tblStockBody');
    if (!stockSugerencias.length) {
        tbody.innerHTML = `<tr><td colspan="6" class="empty">Sin datos</td></tr>`;
        return;
    }
    tbody.innerHTML = stockSugerencias.map(s => {
        const diff     = s.diferencia;
        const diffTxt  = diff === 0 ? '—' : (diff > 0 ? `+${diff}` : `${diff}`);
        const diffCls  = diff > 0 ? 'color:var(--yellow)' : diff < 0 ? 'color:var(--green)' : 'color:var(--text-3)';
        const sinDatos = s.sin_datos
            ? `<span class="badge blue">Sin historial</span>` : '';
        return `
            <tr>
                <td style="font-weight:500">${s.nombre} <span class="td-muted" style="font-size:11px">${s.categoria}</span></td>
                <td>${s.sin_datos ? '—' : `${s.avg_diario} u/día`}</td>
                <td>${s.sin_datos ? '—' : `±${s.std_diario}`}</td>
                <td>${s.stock_minimo_actual}</td>
                <td style="font-weight:700">${s.stock_minimo_sugerido} ${sinDatos}</td>
                <td style="font-weight:700;${diffCls}">${diffTxt}</td>
            </tr>`;
    }).join('');
}

$('btnAutoStock')?.addEventListener('click', async () => {
    openModal('modalStock');
    await cargarPreviewStock();
});

$('modalStockClose')?.addEventListener('click', () => closeModal('modalStock'));
$('btnCancelarStock')?.addEventListener('click', () => closeModal('modalStock'));
$('btnRecalcPreview')?.addEventListener('click', cargarPreviewStock);

$('btnAplicarStock')?.addEventListener('click', async () => {
    const ventana  = $('fVentana').value;
    const leadTime = $('fLeadTime').value;
    const btn      = $('btnAplicarStock');
    btn.disabled = true; btn.textContent = 'Aplicando…';

    try {
        const r = await API.post(
            `/productos/recalcular-stock-minimo?ventana_dias=${ventana}&lead_time_dias=${leadTime}`,
            {}
        );
        flash('flashStock', `✅ ${r.actualizados} productos actualizados correctamente`, 'ok', 4000);
        flash('flashBanner', `Stock mínimo recalculado para ${r.actualizados} productos`, 'ok');
        setTimeout(() => { closeModal('modalStock'); loadProductos(); }, 1800);
    } catch(e) {
        flash('flashStock', e.message, 'err');
    } finally {
        btn.disabled = false; btn.textContent = '✅ Aplicar a todos';
    }
});

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', loadProductos);
