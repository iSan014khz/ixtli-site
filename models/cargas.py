# models/upload.py
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from database import Base

class Carga(Base):
    __tablename__ = "cargas"

    id               = Column(Integer, primary_key=True, index=True)
    archivo_id       = Column(String, unique=True, nullable=False)  # UUID
    hash_md5         = Column(String, unique=True, nullable=False)  # anti-duplicados
    nombre_original  = Column(String, nullable=True)
    fecha_upload     = Column(DateTime, server_default=func.now())
    filas_importadas = Column(Integer, default=0)
    filas_ignoradas  = Column(Integer, default=0)
    periodo_desde    = Column(String, nullable=True)   # "2025-03-01"
    periodo_hasta    = Column(String, nullable=True)   # "2025-03-07"
    mapeo_aplicado   = Column(Text, nullable=True)     # JSON serializado