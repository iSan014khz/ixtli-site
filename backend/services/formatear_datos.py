import pandas as pd
import os
import hashlib

cols_obligatorias = {"fecha", "producto", "unidad", "precio"}

def normalizar_datos(df: pd.DataFrame) -> pd.DataFrame:
    # Normalizamos fechas
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True, errors="coerce")
    
    # Limpiamos texto y formateamos
    df["producto"] = df["producto"].astype(str).str.strip().str.title()
    
    # Convertimos cantidada a int y validamos
    df["unidad"] = pd.to_numeric(df["unidad"], errors="coerce")
    
    # Convertimos precio a float y validamos
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    
    # Calculamos el día de la semana
    df["dia_semana"] = df["fecha"].dt.dayofweek
    df["dia_semana"] = df["dia_semana"].map({
        0: "Lunes",
        1: "Martes",
        2: "Miércoles",
        3: "Jueves",
        4: "Viernes",
        5: "Sábado",
        6: "Domingo"
    })
    
    # Columnas opcionales
    if "costo" not in df.columns:
        df["costo"] = "Sin costo"
    if "categoria" not in df.columns:
        df["categoria"] = "Sin categoria"
    
    return df

def hash_archivo(contenido: bytes) -> str:
    return hashlib.md5(contenido).hexdigest()

def guardar_archivo(contenido: bytes, archivo_id: str) -> None:
    os.makedirs(f"temp", exist_ok=True)
    with open(f"temp/{archivo_id}", "wb") as f:
        f.write(contenido)

def leer_archivo(archivo_id: str) -> bytes:
    with open(f"temp/{archivo_id}", "rb") as f:
        return f.read()

    