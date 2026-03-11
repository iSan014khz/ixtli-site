# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

engine = create_engine(
    "sqlite:///./data/abarrote.db",
    connect_args={"check_same_thread": False}  # necesario solo para SQLite
)
"""
El engine es la conexión física a la base de datos. La cadena "sqlite:///./data/abarrote.db" 
le dice dos cosas: qué motor usar (SQLite) y dónde está el archivo. 
Es como configurar el acceso a la BD, pero todavía no abre ninguna conexión — solo la prepara.
"""

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# autocommit=False → los cambios no se guardan solos, tú controlas cuándo confirmar
# autoflush=False → no envía cambios a la BD hasta que tú lo indiques
# bind=engine → le dice a qué BD conectarse

class Base(DeclarativeBase):
    """
    Esta clase es el registro central de todos tus modelos. 
    Cuando escribes class Producto(Base) en models/producto.py, SQLAlchemy sabe que esa clase representa una tabla. 
    Cuando llamas Base.metadata.create_all(engine) en main.py, SQLAlchemy recorre todos los modelos registrados
    y crea sus tablas en la BD si no existen.
    """
    pass
    # pass simplemente significa que no le agregas nada extra — solo la heredas.


# Dependencia para inyectar la sesión en los endpoints
# Generador de la base de datos: devuelve una sesión nueva por cada solicitud
def get_db():
    db = SessionLocal()   # abre una sesión nueva
    try:
        yield db          # la entrega al endpoint, y se mantiene abierta
    finally:
        db.close()        # la cierra pase lo que pase, incluso si hay un error