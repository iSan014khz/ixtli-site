import hashlib
import io
import json
import os
import uuid

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

from backend.database import get_db
from backend.models import Carga, Venta, Producto

from backend.schemas.carga import MapeoColumnas, ResultadoCarga

router = APIRouter(prefix="/cargas", tags=["cargas"])

TEMP_DIR = "temp"
COLUMNAS_REQUERIDAS = {"fecha", "producto_nombre", "cantidad"}



# ── Helpers ────────────────────────────────────────────────────────────────────

def _leer_archivo(ruta: str) -> pd.DataFrame:
    ext = ruta.rsplit(".", 1)[-1].lower()
    if ext in ("xlsx", "xls"):
        return pd.read_excel(ruta)
    return pd.read_csv(ruta)


def _leer_headers_y_previa(contenido: bytes, extension: str):
    buf = io.BytesIO(contenido)
    if extension in ("xlsx", "xls"):
        headers = pd.read_excel(buf, nrows=0)
        buf.seek(0)
        previa = pd.read_excel(buf, nrows=3)
    else:
        headers = pd.read_csv(buf, nrows=0)
        buf.seek(0)
        previa = pd.read_csv(buf, nrows=3)
    return headers, previa


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/previa-carga")
async def previa(archivo: UploadFile = File(...)):
    """Recibe el archivo, guarda en temp/ con UUID y devuelve columnas + primeras 5 filas"""
    extension = archivo.filename.rsplit(".", 1)[-1].lower()
    if extension not in ("xlsx", "xls", "csv"):
        raise HTTPException(
            status_code=400,
            detail="Formato no soportado. Solo se aceptan .xlsx, .xls o .csv"
        )

    contenido = await archivo.read()
    headers_df, previa_df = _leer_headers_y_previa(contenido, extension)

    archivo_id = str(uuid.uuid4())
    os.makedirs(TEMP_DIR, exist_ok=True)
    ruta_temp = os.path.join(TEMP_DIR, f"{archivo_id}.{extension}")
    with open(ruta_temp, "wb") as f:
        f.write(contenido)

    return {
        "archivo_id": archivo_id,
        "nombre_original": archivo.filename,
        "columnas_detectadas": headers_df.columns.tolist(),
        "vista_previa": previa_df.fillna("").to_dict(orient="records"),
        "columnas_sistema": {
            "requeridas": sorted(COLUMNAS_REQUERIDAS),
            "opcionales": ["precio_unitario", "precio_total", "categoria"]
        }
    }


@router.post("/confirmar-carga", status_code=201, response_model=ResultadoCarga)
def confirmar(datos: MapeoColumnas, db: Session = Depends(get_db)):
    """Aplica el mapeo, valida columnas, detecta solapamiento, inserta ventas y registra la carga"""

    # 1. Localizar archivo temporal (buscar cualquier extensión guardada)
    ruta_temp = None
    for ext in ("xlsx", "xls", "csv"):
        candidato = os.path.join(TEMP_DIR, f"{datos.archivo_id}.{ext}")
        if os.path.exists(candidato):
            ruta_temp = candidato
            break
    if not ruta_temp:
        raise HTTPException(status_code=404, detail="Archivo temporal no encontrado. Vuelve a hacer el preview")

    # 2. Leer archivo y calcular hash (anti-duplicados)
    with open(ruta_temp, "rb") as f:
        raw = f.read()
    hash_md5 = hashlib.md5(raw).hexdigest()

    existe = db.execute(
        text("SELECT 1 AS ok FROM cargas WHERE hash_md5 = :h LIMIT 1"),
        {"h": hash_md5},
    ).mappings().first()
    if existe:
        raise HTTPException(status_code=409, detail="Este archivo ya fue importado anteriormente")

    # 3. Cargar en DataFrame y aplicar mapeo de columnas
    df = _leer_archivo(ruta_temp)
    df = df.rename(columns=datos.mapeo)

    # 4. Validar columnas requeridas
    faltantes = COLUMNAS_REQUERIDAS - set(df.columns)
    if faltantes:
        raise HTTPException(
            status_code=422,
            detail=f"Columnas requeridas faltantes tras el mapeo: {sorted(faltantes)}"
        )

    # 5. Normalizar
    # dayfirst=False para que fechas ISO (YYYY-MM-DD) y con T se parseen correctamente.
    # Para formatos ambiguos (DD/MM/YYYY), el usuario debe asegurarse de usar
    # separadores inequívocos o incluir el año primero.
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=False, errors="coerce")
    filas_invalidas = df["fecha"].isna().sum()
    df = df.dropna(subset=["fecha", "producto_nombre", "cantidad"])
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce").fillna(0).astype(int)

    if "precio_unitario" in df.columns:
        df["precio_unitario"] = pd.to_numeric(df["precio_unitario"], errors="coerce")
    if "precio_total" in df.columns:
        df["precio_total"] = pd.to_numeric(df["precio_total"], errors="coerce")

    # Calcular precio_total si no viene y hay precio_unitario
    if "precio_unitario" in df.columns and "precio_total" not in df.columns:
        df["precio_total"] = df["precio_unitario"] * df["cantidad"]

    # 6. Detectar solapamiento: fechas del archivo ya cubiertas por una Carga previa
    fecha_min = df["fecha"].min().date()
    fecha_max = df["fecha"].max().date()

    solapamiento = db.execute(
        text(
            """
            SELECT nombre_original, periodo_desde, periodo_hasta
            FROM cargas
            WHERE periodo_desde <= :hasta AND periodo_hasta >= :desde
            LIMIT 1
            """
        ),
        {"desde": str(fecha_min), "hasta": str(fecha_max)},
    ).mappings().first()
    if solapamiento:
        raise HTTPException(
            status_code=409,
            detail=(
                f"El rango {fecha_min} – {fecha_max} solapa con la carga '{solapamiento['nombre_original']}' "
                f"({solapamiento['periodo_desde']} – {solapamiento['periodo_hasta']})"
            )
        )

    # 7. Insertar ventas
    ventas_insertadas = 0
    for _, fila in df.iterrows():
        prod = db.execute(
            text("SELECT id FROM productos WHERE nombre = :n LIMIT 1"),
            {"n": str(fila["producto_nombre"])},
        ).mappings().first()
        db.execute(
            text(
                """
                INSERT INTO ventas (producto_id, producto_nombre, cantidad, precio_unitario, precio_total, fecha)
                VALUES (:producto_id, :producto_nombre, :cantidad, :precio_unitario, :precio_total, :fecha)
                """
            ),
            {
                "producto_id": prod["id"] if prod else None,
                "producto_nombre": str(fila["producto_nombre"]),
                "cantidad": int(fila["cantidad"]),
                "precio_unitario": fila.get("precio_unitario") if "precio_unitario" in df.columns else None,
                "precio_total": fila.get("precio_total") if "precio_total" in df.columns else None,
                "fecha": fila["fecha"].to_pydatetime(),
            },
        )
        ventas_insertadas += 1

    # 8. Registrar la carga
    db.execute(
        text(
            """
            INSERT INTO cargas
              (archivo_id, hash_md5, nombre_original, filas_importadas, filas_ignoradas,
               periodo_desde, periodo_hasta, mapeo_aplicado, fecha_upload)
            VALUES
              (:archivo_id, :hash_md5, :nombre_original, :filas_importadas, :filas_ignoradas,
               :periodo_desde, :periodo_hasta, :mapeo_aplicado, :fecha_upload)
            """
        ),
        {
            "archivo_id": datos.archivo_id,
            "hash_md5": hash_md5,
            "nombre_original": datos.nombre_archivo or datos.archivo_id,
            "filas_importadas": ventas_insertadas,
            "filas_ignoradas": int(filas_invalidas),
            "periodo_desde": str(fecha_min),
            "periodo_hasta": str(fecha_max),
            "mapeo_aplicado": json.dumps(datos.mapeo, ensure_ascii=False),
            "fecha_upload": datetime.now(),
        },
    )
    db.commit()

    # 9. Borrar temporal
    os.remove(ruta_temp)

    return {
        "ok": True,
        "filas_importadas": ventas_insertadas,
        "filas_ignoradas": int(filas_invalidas),
        "periodo": {"desde": str(fecha_min), "hasta": str(fecha_max)},
        "solapamiento_resultado": False
    }


@router.get("/historial")
def historial(db: Session = Depends(get_db)):
    """Lista todos los uploads registrados, ordenados por fecha descendente"""
    rows = db.execute(
        text(
            """
            SELECT id, nombre_original, fecha_upload, filas_importadas, filas_ignoradas, periodo_desde, periodo_hasta
            FROM cargas
            ORDER BY fecha_upload DESC, id DESC
            """
        )
    ).mappings().all()

    out = []
    for r in rows:
        d = dict(r)
        fu = d.get("fecha_upload")
        if fu is None:
            d["fecha_upload"] = None
        elif isinstance(fu, str):
            # SQLite puede devolver TEXT
            try:
                d["fecha_upload"] = datetime.fromisoformat(fu.replace("Z", "")).strftime("%Y-%m-%d %H:%M")
            except ValueError:
                d["fecha_upload"] = fu[:16] if len(fu) >= 16 else fu
        else:
            d["fecha_upload"] = fu.strftime("%Y-%m-%d %H:%M")
        out.append(d)
    return out
