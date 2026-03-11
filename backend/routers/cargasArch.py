import hashlib
import io
import json
import os
import uuid
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Carga, Venta, Producto
from datetime import datetime

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

    if db.query(Carga).filter(Carga.hash_md5 == hash_md5).first():
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
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
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

    solapamiento = db.query(Carga).filter(
        Carga.periodo_desde <= str(fecha_max),
        Carga.periodo_hasta >= str(fecha_min)
    ).first()
    if solapamiento:
        raise HTTPException(
            status_code=409,
            detail=(
                f"El rango {fecha_min} – {fecha_max} solapa con la carga '{solapamiento.nombre_original}' "
                f"({solapamiento.periodo_desde} – {solapamiento.periodo_hasta})"
            )
        )

    # 7. Insertar ventas
    ventas_insertadas = 0
    for _, fila in df.iterrows():
        producto = db.query(Producto).filter(Producto.nombre == fila["producto_nombre"]).first()
        venta = Venta(
            producto_id=producto.id if producto else None,
            producto_nombre=str(fila["producto_nombre"]),
            cantidad=int(fila["cantidad"]),
            precio_unitario=fila.get("precio_unitario") if "precio_unitario" in df.columns else None,
            precio_total=fila.get("precio_total") if "precio_total" in df.columns else None,
            fecha=fila["fecha"].to_pydatetime()
        )
        db.add(venta)
        ventas_insertadas += 1

    # 8. Registrar la carga
    carga = Carga(
        archivo_id=datos.archivo_id,
        hash_md5=hash_md5,
        nombre_original=datos.nombre_archivo or datos.archivo_id,
        filas_importadas=ventas_insertadas,
        filas_ignoradas=int(filas_invalidas),
        periodo_desde=str(fecha_min),
        periodo_hasta=str(fecha_max),
        mapeo_aplicado=json.dumps(datos.mapeo, ensure_ascii=False)
    )
    db.add(carga)
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
    cargas = db.query(Carga).order_by(Carga.fecha_upload.desc()).all()
    return [{
        "id": c.id,
        "nombre_original": c.nombre_original,
        "fecha_upload": c.fecha_upload.strftime("%Y-%m-%d %H:%M") if c.fecha_upload else None,
        "filas_importadas": c.filas_importadas,
        "filas_ignoradas": c.filas_ignoradas,
        "periodo_desde": c.periodo_desde,
        "periodo_hasta": c.periodo_hasta
    } for c in cargas]
