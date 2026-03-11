# models/venta.py
from sqlalchemy import Column, Integer, Float, DateTime, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

class Venta(Base):
    __tablename__ = "ventas"

    id              = Column(Integer, primary_key=True, index=True)
    producto_id     = Column(Integer, ForeignKey("productos.id"), nullable=True)
    producto_nombre = Column(String, nullable=False)   # desnormalizado — razón abajo
    cantidad        = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=True)
    precio_total    = Column(Float, nullable=True)
    fecha           = Column(DateTime, nullable=False)
    fecha_registro  = Column(DateTime, server_default=func.now())

    producto = relationship("Producto", back_populates="ventas")