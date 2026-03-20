"""
Migraciones ligeras para SQLite.
Se ejecutan automáticamente al arrancar el servidor; son idempotentes.
"""
from sqlalchemy import text
from backend.database import engine


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
    crear_trigger_duplicado_carga()