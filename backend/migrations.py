"""
Migraciones ligeras para SQLite.
Se ejecutan automáticamente al arrancar el servidor; son idempotentes.
"""
from sqlalchemy import text
from backend.database import engine


def _column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return any(row[1] == column for row in rows)


def run():
    with engine.begin() as conn:
        if not _column_exists(conn, "productos", "costo"):
            conn.execute(text("ALTER TABLE productos ADD COLUMN costo FLOAT"))
            print("[migration] Columna 'costo' añadida a productos")
