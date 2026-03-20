"""
Migraciones ligeras para SQLite.
Se ejecutan automáticamente al arrancar el servidor; son idempotentes.
"""
from sqlalchemy import text
from backend.database import engine


def existe_columna(consulta, tabla: str, columna: str) -> bool:
    """Verifica si una columna existe en una tabla"""
    rows = consulta.execute(text(f"PRAGMA table_info({tabla})")).fetchall()
    return any(row[1] == columna for row in rows)


def agregar_columna_costo():
    """Agrega una columna 'costo' a la tabla 'productos'"""
    with engine.begin() as consulta:
        if not existe_columna(consulta, "productos", "costo"):
            consulta.execute(text("ALTER TABLE productos ADD COLUMN costo FLOAT"))
            print("[migration] Columna 'costo' añadida a productos")
