/* ══ Ixtli — importar.js ════════════════════════════════════════════════════ */

const $ = id => document.getElementById(id);

// Campos del sistema con su etiqueta y si son obligatorios
const CAMPOS = [
    { key:'fecha',            label:'Fecha',           required:true },
    { key:'producto_nombre',  label:'Nombre producto', required:true },
    { key:'cantidad',         label:'Cantidad',        required:true },
    { key:'precio_unitario',  label:'Precio unitario', required:false },
    { key:'precio_total',     label:'Precio total',    required:false },
    { key:'categoria',        label:'Categoría',       required:false },
];

let estado = {
    archivoId: null,
    nombreArchivo: null,
    columnasDetectadas: [],
};

// ── Stepper ───────────────────────────────────────────────────────────────────
function setStep(n) {
    [1,2,3].forEach(i => {
        const s = $(`step${i}`);
        s.classList.remove('active','done');
        if (i < n)  s.classList.add('done');
        if (i === n) s.classList.add('active');
    });
}

// ── Panel visibility ──────────────────────────────────────────────────────────
function showPanel(name) {
    ['Upload','Mapeo','Resultado'].forEach(p => {
        $(`panel${p}`).style.display = p.toLowerCase() === name ? '' : 'none';
    });
}

// ── Upload file ───────────────────────────────────────────────────────────────
async function handleFile(file) {
    if (!file) return;
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['csv','xlsx','xls'].includes(ext)) {
        flash('flashBanner', 'Formato no soportado. Usa .csv, .xlsx o .xls', 'err');
        return;
    }

    const btnSel = $('btnSeleccionar');
    btnSel.textContent = 'Subiendo…'; btnSel.disabled = true;
    $('dropZone').classList.add('drag-over');

    try {
        const fd = new FormData();
        fd.append('archivo', file);
        const data = await API.upload('/cargas/previa-carga', fd);

        estado.archivoId        = data.archivo_id;
        estado.nombreArchivo    = data.nombre_original || file.name;
        estado.columnasDetectadas = data.columnas_detectadas || [];

        renderPreview(data);
        renderMapping(data.columnas_detectadas || []);
        setStep(2);
        showPanel('mapeo');
    } catch(e) {
        flash('flashBanner', `Error al subir: ${e.message}`, 'err');
    } finally {
        btnSel.textContent = 'Seleccionar archivo'; btnSel.disabled = false;
        $('dropZone').classList.remove('drag-over');
    }
}

// ── Preview ───────────────────────────────────────────────────────────────────
function renderPreview(data) {
    const cols = data.columnas_detectadas || [];
    const rows = data.vista_previa || [];

    $('previewSub').textContent = `${cols.length} columnas detectadas · ${estado.nombreArchivo}`;

    $('previewHead').innerHTML = `<tr>${cols.map(c => `<th>${c}</th>`).join('')}</tr>`;
    $('previewBody').innerHTML = rows.map(row =>
        `<tr>${cols.map(c => `<td>${row[c] ?? ''}</td>`).join('')}</tr>`
    ).join('') || '<tr><td colspan="99" class="empty">Sin filas de vista previa</td></tr>';
}

// ── Mapping UI ────────────────────────────────────────────────────────────────
function renderMapping(cols) {
    const container = $('mappingRows');
    container.innerHTML = CAMPOS.map(campo => {
        // Auto-detect column (case insensitive match)
        const auto = cols.find(c => c.toLowerCase().includes(campo.key.split('_')[0])) || '';
        return `
            <select name="col_${campo.key}" style="background:var(--elevated);border:1px solid var(--border);border-radius:8px;padding:8px 10px;color:var(--text);font-size:12.5px;font-family:inherit;outline:none">
                <option value="">— sin mapear —</option>
                ${cols.map(c => `<option value="${c}" ${c === auto ? 'selected' : ''}>${c}</option>`).join('')}
            </select>
            <div style="text-align:center;color:var(--accent-hi);font-size:18px">→</div>
            <div style="font-size:13px;font-weight:500;padding:8px 0">
                ${campo.label}
                ${campo.required ? '<span style="color:var(--red);font-size:10px;font-weight:700"> *</span>' : '<span style="color:var(--text-3);font-size:10px"> opc</span>'}
            </div>`;
    }).join('');
}

// ── Confirmar importación ─────────────────────────────────────────────────────
$('btnConfirmar')?.addEventListener('click', async () => {
    const selects = $('mappingRows').querySelectorAll('select');
    const mapeo = {};

    let ok = true;
    CAMPOS.forEach((campo, i) => {
        const col = selects[i].value;
        if (col) mapeo[col] = campo.key;
        else if (campo.required) { ok = false; }
    });

    if (!ok) { flash('flashBanner', 'Debes mapear los campos obligatorios: fecha, nombre producto, cantidad', 'err'); return; }

    const btn = $('btnConfirmar');
    btn.disabled = true; btn.textContent = 'Importando…';

    try {
        const resultado = await API.post('/cargas/confirmar-carga', {
            archivo_id:    estado.archivoId,
            mapeo,
            nombre_archivo: estado.nombreArchivo,
        });
        renderResultado(resultado);
        setStep(3);
        showPanel('resultado');
        loadHistorial();
    } catch(e) {
        flash('flashBanner', `Error: ${e.message}`, 'err');
    } finally {
        btn.disabled = false; btn.textContent = 'Confirmar importación';
    }
});

// ── Resultado ─────────────────────────────────────────────────────────────────
function renderResultado(r) {
    $('resultBox').innerHTML = r.ok ? `
        <div class="result-box ok">
            <div style="font-size:16px;font-weight:700;color:var(--green)">✅ Importación exitosa</div>
            <div class="result-big" style="color:var(--green)">${fmt.num(r.filas_importadas)}</div>
            <div style="font-size:13px;color:var(--text-2)">ventas importadas</div>
            <div style="margin-top:12px;font-size:12px;color:var(--text-3)">
                Período: ${r.periodo?.desde || '—'} → ${r.periodo?.hasta || '—'}
                · ${r.filas_ignoradas} filas ignoradas
            </div>
        </div>` : `
        <div class="result-box err">
            <div style="font-size:16px;font-weight:700;color:var(--red)">❌ Error en la importación</div>
            <div style="font-size:13px;color:var(--text-2);margin-top:8px">Revisa el archivo e intenta de nuevo</div>
        </div>`;
}

// ── Volver al paso 1 ──────────────────────────────────────────────────────────
$('btnVolver')?.addEventListener('click', () => {
    setStep(1); showPanel('upload');
    $('fileInput').value = '';
});

$('btnOtraImportacion')?.addEventListener('click', () => {
    setStep(1); showPanel('upload');
    $('fileInput').value = '';
    estado = { archivoId:null, nombreArchivo:null, columnasDetectadas:[] };
});

// ── Drag & drop + click ───────────────────────────────────────────────────────
const dropZone = $('dropZone');
const fileInput = $('fileInput');

$('btnSeleccionar')?.addEventListener('click', e => { e.stopPropagation(); fileInput.click(); });
dropZone?.addEventListener('click', () => fileInput.click());

fileInput?.addEventListener('change', e => handleFile(e.target.files[0]));

dropZone?.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone?.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone?.addEventListener('drop', e => {
    e.preventDefault(); dropZone.classList.remove('drag-over');
    handleFile(e.dataTransfer.files[0]);
});

// ── Historial ─────────────────────────────────────────────────────────────────
async function loadHistorial() {
    const tbody = $('historialTbody');
    try {
        const data = await API.get('/cargas/historial');
        if (!data.length) { tbody.innerHTML = '<tr><td colspan="5" class="empty">Sin importaciones anteriores</td></tr>'; return; }
        tbody.innerHTML = data.map(c => `
            <tr>
                <td style="font-weight:500">${c.nombre_original || '—'}</td>
                <td class="td-muted">${c.fecha_upload || '—'}</td>
                <td><span class="badge green">${fmt.num(c.filas_importadas)}</span></td>
                <td class="td-muted">${c.filas_ignoradas}</td>
                <td class="td-muted">${c.periodo_desde || '—'} → ${c.periodo_hasta || '—'}</td>
            </tr>`).join('');
    } catch(e) {
        tbody.innerHTML = '<tr><td colspan="5" class="empty" style="color:var(--red)">Error al cargar historial</td></tr>';
    }
}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    setStep(1);
    showPanel('upload');
    loadHistorial();
});
