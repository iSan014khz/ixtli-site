# models/venta.py
from sqlalchemy import Column, Integer, Numeric, DateTime, String, ForeignKey
from sqlalchemy.sql import func
from backend.database import Base

class Venta(Base):
    __tablename__ = "ventas"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    producto_id     = Column(Integer, ForeignKey("productos.id"), nullable=False)
    
    # desnormalización: El usuario podría cambiar el nombre, precio, etc. del producto
    producto_nombre = Column(String(150), nullable=False)

    cantidad        = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(10, 2), nullable=False)
    precio_total    = Column(Numeric(10, 2), nullable=False)
    fecha           = Column(DateTime, nullable=False) # Fecha de la venta que el usuario proporciona
    fecha_registro  = Column(DateTime, server_default=func.now()) # Fecha de registro en la BD