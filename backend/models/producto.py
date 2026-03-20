# models/producto.py
from sqlalchemy import Column, Integer, String, Numeric
from backend.database import Base

class Producto(Base):
    __tablename__ = "productos"

    id            = Column(Integer, primary_key=True, index=True)
    nombre        = Column(String(150), nullable=False, unique=True)
    categoria     = Column(String(50), nullable=True)          # libre, ej: "Bebidas"
    precio_venta  = Column(Numeric(10, 2), nullable=True)           # puede venir del CSV
    costo         = Column(Numeric(10, 2), nullable=True)           # costo al dueño (opcional)
    stock_actual  = Column(Integer, nullable=False, default=0)
    stock_minimo  = Column(Integer, nullable=False, default=5)  # umbral de alerta
    unidad        = Column(String(10), nullable=False, default="pieza")  # pieza, kg, lt