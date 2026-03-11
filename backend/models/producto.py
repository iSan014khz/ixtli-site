# models/producto.py
from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import relationship
from backend.database import Base

class Producto(Base):
    __tablename__ = "productos"

    id            = Column(Integer, primary_key=True, index=True)
    nombre        = Column(String, nullable=False, unique=True)
    categoria     = Column(String, nullable=True)          # libre, ej: "Bebidas"
    precio_venta  = Column(Float, nullable=True)           # puede venir del CSV
    stock_actual  = Column(Integer, nullable=False, default=0)
    stock_minimo  = Column(Integer, nullable=False, default=5)  # umbral de alerta
    unidad        = Column(String, nullable=False, default="pieza")  # pieza, kg, lt

    ventas        = relationship("Venta", back_populates="producto")