"""
Genera CSVs/XLSX de prueba para el endpoint de importación de Ixtli
y opcionalmente los sube al API de forma automática.

Uso:
    python scripts/generar_csvs.py                          # solo genera archivos
    python scripts/generar_csvs.py --upload                 # genera + sube al API
    python scripts/generar_csvs.py --upload --url http://localhost:8000
    python scripts/generar_csvs.py --upload --solo ventas_formato_pos.csv

Archivos generados (en test_csvs/):
  1. ventas_formato_limpio.csv   - columnas exactas del sistema, sin necesidad de mapeo
  2. ventas_formato_excel.csv    - nombres como exportaría Excel (Fecha, Producto, Cant., Precio)
  3. ventas_formato_pos.csv      - estilo sistema de punto de venta externo (date, item, qty, price)
  4. ventas_mes_completo.xlsx    - Excel con un mes completo de datos
  5. ventas_con_errores.csv      - filas con errores intencionales para probar la tolerancia a fallos
"""

import argparse
import csv
import os
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# ── Intentar importar dependencias opcionales ─────────────────────────────────
try:
    import requests
    REQUESTS_OK = True
except ImportError:
    REQUESTS_OK = False

try:
    import openpyxl
    OPENPYXL_OK = True
except ImportError:
    OPENPYXL_OK = False

# ── Configuración ─────────────────────────────────────────────────────────────
random.seed(99)

SALIDA = Path("test_csvs")

PRODUCTOS = [
    ("Coca-Cola 600ml",       18.0,  11.0),
    ("Agua 1L",                8.0,   4.5),
    ("Jugo Naranja 1L",       22.0,  14.0),
    ("Cerveza Modelo 355ml",  25.0,  16.0),
    ("Sabritas Original",     16.0,   9.0),
    ("Doritos Nacho",         18.0,  10.5),
    ("Leche Lala 1L",         24.0,  17.0),
    ("Arroz Verde Valle 1kg", 28.0,  18.0),
    ("Frijol Negro 1kg",      32.0,  21.0),
    ("Marlboro Rojo",         68.0,  55.0),
    ("Detergente Roma 500g",  22.0,  13.0),
    ("Aceite 1L",             48.0,  34.0),
]

# Rango base: empezamos mañana para no solapar con historial ya importado
HOY      = date.today()
MANANA   = HOY + timedelta(days=1)


# ── Helpers ───────────────────────────────────────────────────────────────────

def fecha_str(d: date, fmt="%Y-%m-%d") -> str:
    return d.strftime(fmt)


def generar_ventas(fecha_inicio: date, fecha_fin: date, hora_min=8, hora_max=20):
    """Genera filas de ventas diarias para el rango dado."""
    filas = []
    delta = (fecha_fin - fecha_inicio).days + 1
    for offset in range(delta):
        dia = fecha_inicio + timedelta(days=offset)
        es_finde = dia.weekday() >= 5
        factor = 1.3 if es_finde else 1.0
        for nombre, precio, _ in PRODUCTOS:
            if random.random() < 0.10:    # 10% de días sin ese producto
                continue
            cantidad  = max(1, round(random.randint(2, 12) * factor))
            precio_u  = round(precio * random.uniform(0.97, 1.02), 1)
            hora      = random.randint(hora_min, hora_max - 1)
            minuto    = random.randint(0, 59)
            filas.append({
                "fecha":          datetime(dia.year, dia.month, dia.day, hora, minuto),
                "producto":       nombre,
                "cantidad":       cantidad,
                "precio_unitario": precio_u,
                "precio_total":   round(precio_u * cantidad, 2),
            })
    return filas


def escribir_csv(ruta: Path, filas: list[dict], columnas: list[tuple]):
    """
    columnas: lista de (nombre_en_csv, clave_en_fila, formato_fecha)
    """
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([c[0] for c in columnas])
        for fila in filas:
            row = []
            for nombre_csv, clave, fmt_fecha in columnas:
                val = fila[clave]
                if isinstance(val, datetime) and fmt_fecha:
                    val = val.strftime(fmt_fecha)
                row.append(val)
            writer.writerow(row)
    return ruta


def escribir_xlsx(ruta: Path, filas: list[dict], columnas: list[tuple], hoja="Ventas"):
    if not OPENPYXL_OK:
        print("  [!] openpyxl no instalado, saltando XLSX")
        return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = hoja
    ws.append([c[0] for c in columnas])
    for fila in filas:
        row = []
        for _, clave, fmt_fecha in columnas:
            val = fila[clave]
            if isinstance(val, datetime) and fmt_fecha:
                val = val.strftime(fmt_fecha)
            row.append(val)
        ws.append(row)
    wb.save(ruta)
    return ruta


def sep():
    print("-" * 60)


# ── Generadores de cada archivo ───────────────────────────────────────────────

def generar_formato_limpio():
    """Columnas exactas del sistema, fechas ISO con T (sin necesidad de mapeo)."""
    inicio = MANANA + timedelta(days=60)
    fin    = inicio + timedelta(days=6)
    filas  = generar_ventas(inicio, fin)
    ruta   = SALIDA / "ventas_formato_limpio.csv"
    # Usar formato ISO con T para que dayfirst=True no cause confusion
    escribir_csv(ruta, filas, [
        ("fecha",           "fecha",          "%Y-%m-%dT%H:%M:%S"),
        ("producto_nombre", "producto",        None),
        ("cantidad",        "cantidad",        None),
        ("precio_unitario", "precio_unitario", None),
        ("precio_total",    "precio_total",    None),
    ])
    return ruta, {}, f"{fecha_str(inicio)} al {fecha_str(fin)}", len(filas)


def generar_formato_excel():
    """Encabezados como los exportaria Excel en espanol."""
    inicio = MANANA + timedelta(days=70)
    fin    = inicio + timedelta(days=6)
    filas  = generar_ventas(inicio, fin)
    ruta   = SALIDA / "ventas_formato_excel.csv"
    escribir_csv(ruta, filas, [
        ("Fecha",    "fecha",          "%d/%m/%Y"),
        ("Producto", "producto",        None),
        ("Cant.",    "cantidad",        None),
        ("Precio",   "precio_unitario", None),
        ("Total",    "precio_total",    None),
    ])
    mapeo = {
        "Fecha":    "fecha",
        "Producto": "producto_nombre",
        "Cant.":    "cantidad",
        "Precio":   "precio_unitario",
        "Total":    "precio_total",
    }
    return ruta, mapeo, f"{fecha_str(inicio)} al {fecha_str(fin)}", len(filas)


def generar_formato_pos():
    """Estilo exportacion de sistema POS externo en ingles."""
    inicio = MANANA + timedelta(days=80)
    fin    = inicio + timedelta(days=6)
    filas  = generar_ventas(inicio, fin)
    ruta   = SALIDA / "ventas_formato_pos.csv"
    escribir_csv(ruta, filas, [
        ("transaction_date", "fecha",          "%Y-%m-%dT%H:%M"),
        ("item_name",        "producto",        None),
        ("qty_sold",         "cantidad",        None),
        ("unit_price",       "precio_unitario", None),
    ])
    mapeo = {
        "transaction_date": "fecha",
        "item_name":        "producto_nombre",
        "qty_sold":         "cantidad",
        "unit_price":       "precio_unitario",
    }
    return ruta, mapeo, f"{fecha_str(inicio)} al {fecha_str(fin)}", len(filas)


def generar_mes_completo_xlsx():
    """Excel con un mes completo (~30 dias) de datos."""
    inicio = MANANA + timedelta(days=90)
    fin    = inicio + timedelta(days=29)
    filas  = generar_ventas(inicio, fin)
    ruta   = SALIDA / "ventas_mes_completo.xlsx"
    result = escribir_xlsx(ruta, filas, [
        ("Fecha",            "fecha",          "%Y-%m-%d %H:%M"),
        ("Nombre Producto",  "producto",        None),
        ("Unidades",         "cantidad",        None),
        ("Precio Unitario",  "precio_unitario", None),
        ("Total Venta",      "precio_total",    None),
    ])
    mapeo = {
        "Fecha":           "fecha",
        "Nombre Producto": "producto_nombre",
        "Unidades":        "cantidad",
        "Precio Unitario": "precio_unitario",
        "Total Venta":     "precio_total",
    }
    return result, mapeo, f"{fecha_str(inicio)} al {fecha_str(fin)}", len(filas)


def generar_con_errores():
    """Filas con errores intencionales para probar la tolerancia a fallos."""
    inicio = MANANA + timedelta(days=125)
    fin    = inicio + timedelta(days=6)
    filas  = generar_ventas(inicio, fin)
    ruta   = SALIDA / "ventas_con_errores.csv"

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fecha", "producto_nombre", "cantidad", "precio_unitario"])
        for i, fila in enumerate(filas):
            row_fecha  = fila["fecha"].strftime("%Y-%m-%dT%H:%M:%S")
            row_prod   = fila["producto"]
            row_cant   = fila["cantidad"]
            row_precio = fila["precio_unitario"]

            if i % 21 == 0:   # fecha invalida
                row_fecha = "fecha-invalida"
            if i % 31 == 0:   # cantidad vacia
                row_cant = ""
            if i % 41 == 0:   # producto desconocido
                row_prod = "Producto Inventado XYZ"

            writer.writerow([row_fecha, row_prod, row_cant, row_precio])

    n_errores = (len(filas)//21) + (len(filas)//31) + (len(filas)//41)
    return ruta, {}, f"{fecha_str(inicio)} al {fecha_str(fin)}", len(filas), n_errores


# ── Upload al API ─────────────────────────────────────────────────────────────

def upload_archivo(ruta: Path, mapeo: dict, base_url: str) -> dict | None:
    if not REQUESTS_OK:
        print("  [!] Instala 'requests' para usar --upload:  pip install requests")
        return None
    if ruta is None or not ruta.exists():
        print(f"  [!] Archivo no encontrado: {ruta}")
        return None

    # 1. Paso previo
    print(f"  >> POST {base_url}/cargas/previa-carga")
    try:
        with open(ruta, "rb") as f:
            resp = requests.post(
                f"{base_url}/cargas/previa-carga",
                files={"archivo": (ruta.name, f, "multipart/form-data")},
                timeout=15,
            )
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] No se pudo conectar a {base_url}. Asegurate de que el servidor este corriendo.")
        return None
    if resp.status_code != 200:
        print(f"  [ERROR] previa-carga: {resp.status_code} - {resp.text[:200]}")
        return None

    data   = resp.json()
    archi_id = data["archivo_id"]
    cols     = data["columnas_detectadas"]
    print(f"  Columnas detectadas: {cols}")
    print(f"  Vista previa ({len(data['vista_previa'])} filas mostradas)")

    # Auto-mapeo si no se pasó mapeo manual
    mapeo_final = mapeo if mapeo else {c: c for c in cols}

    # 2. Confirmar
    print(f"  >> POST {base_url}/cargas/confirmar-carga")
    payload = {
        "archivo_id":    archi_id,
        "mapeo":         mapeo_final,
        "nombre_archivo": ruta.name,
    }
    resp2 = requests.post(
        f"{base_url}/cargas/confirmar-carga",
        json=payload,
        timeout=15,
    )
    if resp2.status_code in (200, 201):
        r = resp2.json()
        print(f"  [OK] Importadas: {r['filas_importadas']} ventas | Ignoradas: {r['filas_ignoradas']}")
        print(f"       Periodo: {r['periodo']['desde']} al {r['periodo']['hasta']}")
        return r
    else:
        print(f"  [ERROR] confirmar-carga: {resp2.status_code} - {resp2.text[:300]}")
        return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generador de CSVs de prueba para Ixtli")
    parser.add_argument("--upload",   action="store_true", help="Subir archivos al API tras generarlos")
    parser.add_argument("--reset",    action="store_true", help="Re-ejecutar seed_data antes de subir (limpia Cargas y Ventas previas)")
    parser.add_argument("--url",      default="http://localhost:8000", help="URL base del API (default: http://localhost:8000)")
    parser.add_argument("--solo",     default=None, help="Nombre de archivo para subir solo ese (ej: ventas_formato_pos.csv)")
    args = parser.parse_args()

    SALIDA.mkdir(exist_ok=True)

    print("\n== Ixtli - Generador de CSVs de prueba ==")
    sep()

    archivos = []

    # 1. Formato limpio
    ruta, mapeo, rango, n = generar_formato_limpio()
    print("[1] ventas_formato_limpio.csv")
    print(f"    Periodo : {rango}")
    print(f"    Filas   : {n}")
    print("    Mapeo   : (ninguno necesario - columnas exactas del sistema)")
    archivos.append((ruta, mapeo, "ventas_formato_limpio.csv"))
    sep()

    # 2. Formato Excel
    ruta, mapeo, rango, n = generar_formato_excel()
    print("[2] ventas_formato_excel.csv")
    print(f"    Periodo : {rango}")
    print(f"    Filas   : {n}")
    print(f"    Mapeo   : {mapeo}")
    archivos.append((ruta, mapeo, "ventas_formato_excel.csv"))
    sep()

    # 3. Formato POS
    ruta, mapeo, rango, n = generar_formato_pos()
    print("[3] ventas_formato_pos.csv")
    print(f"    Periodo : {rango}")
    print(f"    Filas   : {n}")
    print(f"    Mapeo   : {mapeo}")
    archivos.append((ruta, mapeo, "ventas_formato_pos.csv"))
    sep()

    # 4. Excel mes completo
    ruta, mapeo, rango, n = generar_mes_completo_xlsx()
    if ruta:
        print("[4] ventas_mes_completo.xlsx")
        print(f"    Periodo : {rango}")
        print(f"    Filas   : {n}")
        print(f"    Mapeo   : {mapeo}")
        archivos.append((ruta, mapeo, "ventas_mes_completo.xlsx"))
    else:
        print("[4] ventas_mes_completo.xlsx OMITIDO (instala openpyxl)")
    sep()

    # 5. Con errores
    ruta, mapeo, rango, n, n_err = generar_con_errores()
    print("[5] ventas_con_errores.csv")
    print(f"    Periodo : {rango}")
    print(f"    Filas   : {n} ({n_err} con errores intencionales)")
    print("    Mapeo   : (ninguno - columnas exactas del sistema)")
    archivos.append((ruta, mapeo, "ventas_con_errores.csv"))
    sep()

    print(f"\nArchivos guardados en: {SALIDA.resolve()}\n")

    # ── Reset (seed) ──────────────────────────────────────────────────────────
    if args.reset:
        print("\n== Reiniciando BD con seed_data ==")
        import subprocess
        resultado = subprocess.run(
            [sys.executable, "-m", "backend.seed_data"],
            capture_output=True, text=True,
        )
        print(resultado.stdout.strip())
        if resultado.returncode != 0:
            print("[ERROR] seed_data fallo:")
            print(resultado.stderr[:400])
        sep()

    # ── Upload ────────────────────────────────────────────────────────────────
    if args.upload:
        print(f"\n== Subiendo al API: {args.url} ==")
        sep()
        for ruta, mapeo, nombre in archivos:
            if args.solo and nombre != args.solo:
                continue
            print(f"\nArchivo: {nombre}")
            upload_archivo(ruta, mapeo, args.url)
            sep()
        print("\nUpload completado.")
    else:
        print("Tip: usa --upload para subirlos automaticamente al API")
        print("     python scripts/generar_csvs.py --upload")
        print("     python scripts/generar_csvs.py --upload --reset       # limpia BD antes de subir")
        print("     python scripts/generar_csvs.py --upload --solo ventas_formato_pos.csv\n")


if __name__ == "__main__":
    main()
