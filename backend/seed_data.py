"""
Seed de datos ficticios para probar todos los endpoints de analíticas.
Ejecutar desde la raíz del proyecto:
    python backend/seed_data.py

Genera:
- 18 productos con categorías variadas
- 90 días de historial de ventas con patrones realistas
- Algunos productos en stock crítico, alerta y vigilar
"""

import sys
import os
import random
from datetime import datetime, timedelta

# Asegura que la raíz del proyecto esté en el path para importar database y models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import engine, SessionLocal, Base
from backend.models import Producto, Venta

random.seed(42)

# ── Catálogo de productos ────────────────────────────────────────────────────────

PRODUCTOS = [
    # nombre                  categoria      precio_venta  stock_actual  stock_minimo  unidad    costo
    ("Coca-Cola 600ml",       "Bebidas",      18.0,         120,          20,           "pieza",  11.0),
    ("Agua 1L",               "Bebidas",       8.0,          80,          15,           "pieza",   4.5),
    ("Jugo Naranja 1L",       "Bebidas",      22.0,          35,          10,           "pieza",  14.0),
    ("Cerveza Modelo 355ml",  "Bebidas",      25.0,          60,          12,           "pieza",  16.0),
    ("Sabritas Original",     "Botanas",      16.0,          90,          15,           "pieza",   9.0),
    ("Doritos Nacho",         "Botanas",      18.0,          55,          10,           "pieza",  10.5),
    ("Chicharrón Barcel",     "Botanas",      14.0,           8,          10,           "pieza",   7.5),  # ALERTA
    ("Leche Lala 1L",         "Lácteos",      24.0,          45,          20,           "pieza",  17.0),
    ("Yogurt Fresa 1kg",      "Lácteos",      38.0,          12,          10,           "pieza",  26.0),
    ("Queso Oaxaca 400g",     "Lácteos",      62.0,           3,          10,           "pieza",  44.0),  # CRÍTICO
    ("Arroz Verde Valle 1kg", "Abarrotes",    28.0,          70,          15,           "pieza",  18.0),
    ("Frijol Negro 1kg",      "Abarrotes",    32.0,           4,          10,           "pieza",  21.0),  # CRÍTICO
    ("Azúcar Estándar 1kg",   "Abarrotes",    26.0,          50,          10,           "pieza",  16.5),
    ("Aceite 1L",             "Abarrotes",    48.0,          25,          10,           "pieza",  34.0),
    ("Detergente Roma 500g",  "Limpieza",     22.0,          30,          10,           "pieza",  13.0),
    ("Cloro 1L",              "Limpieza",     18.0,           6,          10,           "pieza",  10.5),  # ALERTA
    ("Marlboro Rojo",         "Cigarros",     68.0,          40,           8,           "pieza",  55.0),
    ("Delicados 20 cigarros", "Cigarros",     42.0,          22,           8,           "pieza",  34.0),
]

# Patrón de demanda por producto: (min_unidades_dia, max_unidades_dia)
DEMANDA = {
    "Coca-Cola 600ml":        (3, 12),
    "Agua 1L":                (2, 8),
    "Jugo Naranja 1L":        (1, 5),
    "Cerveza Modelo 355ml":   (2, 10),
    "Sabritas Original":      (3, 10),
    "Doritos Nacho":          (2, 8),
    "Chicharrón Barcel":      (1, 4),
    "Leche Lala 1L":          (2, 7),
    "Yogurt Fresa 1kg":       (1, 4),
    "Queso Oaxaca 400g":      (1, 3),
    "Arroz Verde Valle 1kg":  (2, 6),
    "Frijol Negro 1kg":       (2, 5),
    "Azúcar Estándar 1kg":    (1, 4),
    "Aceite 1L":              (1, 3),
    "Detergente Roma 500g":   (1, 4),
    "Cloro 1L":               (1, 3),
    "Marlboro Rojo":          (2, 8),
    "Delicados 20 cigarros":  (1, 5),
}


def crear_tablas():
    Base.metadata.create_all(bind=engine)
    print("[OK] Tablas creadas / verificadas")


def limpiar_datos(db):
    db.query(Venta).delete()
    db.query(Producto).delete()
    db.commit()
    print("[OK] Datos previos eliminados")


def insertar_productos(db) -> dict[str, Producto]:
    objetos = {}
    for nombre, categoria, precio, stock_actual, stock_minimo, unidad, costo in PRODUCTOS:
        p = Producto(
            nombre=nombre,
            categoria=categoria,
            precio_venta=precio,
            costo=costo,
            stock_actual=stock_actual,
            stock_minimo=stock_minimo,
            unidad=unidad,
        )
        db.add(p)
        objetos[nombre] = p

    db.commit()
    # Refrescamos para obtener los IDs asignados
    for p in objetos.values():
        db.refresh(p)

    print(f"[OK] {len(objetos)} productos insertados")
    return objetos


def insertar_ventas(db, productos: dict[str, Producto], dias: int = 90):
    hoy = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    ventas = []

    for offset in range(dias, -1, -1):
        fecha_base = hoy - timedelta(days=offset)
        # Fines de semana venden ~30% más
        es_finde = fecha_base.weekday() >= 5
        factor = 1.3 if es_finde else 1.0

        for nombre, producto in productos.items():
            minv, maxv = DEMANDA[nombre]
            # Algunos días sin ventas de ciertos productos (realismo)
            if random.random() < 0.08:
                continue

            cantidad = max(1, round(random.uniform(minv, maxv) * factor))
            precio_u = producto.precio_venta

            # Pequeña variación de precio (descuentos/redondeos)
            precio_u_real = round(precio_u * random.uniform(0.95, 1.02), 1)

            # Hora aleatoria del día (7am – 9pm)
            hora = random.randint(7, 20)
            minuto = random.randint(0, 59)
            fecha_venta = fecha_base.replace(hour=hora, minute=minuto)

            ventas.append(
                Venta(
                    producto_id=producto.id,
                    producto_nombre=nombre,
                    cantidad=cantidad,
                    precio_unitario=precio_u_real,
                    precio_total=round(precio_u_real * cantidad, 2),
                    fecha=fecha_venta,
                )
            )

    db.bulk_save_objects(ventas)
    db.commit()
    print(f"[OK] {len(ventas)} ventas generadas ({dias} dias de historial)")


def main():
    print("\n-- Iniciando seed de datos ----------------------------------")
    crear_tablas()

    db = SessionLocal()
    try:
        limpiar_datos(db)
        productos = insertar_productos(db)
        insertar_ventas(db, productos, dias=90)
    finally:
        db.close()

    print("\n-- Seed completado ------------------------------------------")
    print("   Endpoints listos para probar:")
    print("   GET /reportes/dashboard")
    print("   GET /reportes/ventas-por-periodo?agrupacion=semana")
    print("   GET /reportes/top-productos?limite=5")
    print("   GET /reportes/rotacion")
    print("   GET /reportes/ticket-promedio?agrupacion=mes")
    print("   GET /reportes/ventas-por-periodo?desde=2025-12-01&hasta=2026-01-31")
    print("-------------------------------------------------------------\n")


if __name__ == "__main__":
    main()
