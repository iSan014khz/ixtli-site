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
    """Agrega la columna 'costo' a productos si no existe"""
    with engine.begin() as consulta:
        if not existe_columna(consulta, "productos", "costo"):
            consulta.execute(text("ALTER TABLE productos ADD COLUMN costo FLOAT"))
            print("[migration] Columna 'costo' añadida a productos")


def crear_trigger_duplicado_carga():
    """Crea trigger que previene cargas duplicadas por hash MD5"""
    with engine.begin() as con:
        con.execute(text("""
            CREATE TRIGGER IF NOT EXISTS verificar_duplicado_carga
            BEFORE INSERT ON cargas
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'duplicado')
                WHERE EXISTS (
                    SELECT 1 FROM cargas WHERE hash_md5 = NEW.hash_md5
                );
            END
        """))
        print("[migration] Trigger verificar_duplicado_carga listo")


def ejecutar_migraciones():
    agregar_columna_costo()
    crear_trigger_duplicado_carga()