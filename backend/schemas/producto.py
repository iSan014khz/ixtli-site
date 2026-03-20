from pydantic import BaseModel, computed_field
from typing import Optional


class ProductoRespuesta(BaseModel):
    id: int
    nombre: str
    categoria: Optional[str] = None
    precio_venta: float
    costo: Optional[float] = None
    stock_actual: int
    stock_minimo: int
    unidad: str

    @computed_field             # Incluimos la propiedad en el JSON de respuesta
    @property                  # Convierte el método en una propiedad de la clase(Esquema) - producto.alerta_stock
    def alerta_stock(self) -> bool:
        return self.stock_actual < self.stock_minimo

    @computed_field             # Incluimos la propiedad en el JSON de respuesta
    @property                   # Convierte el método en una propiedad de la clase(Esquema) - producto.margen_pct
    def margen_pct(self) -> Optional[float]:
        if self.precio_venta and self.costo and self.precio_venta > 0:
            return round((self.precio_venta - self.costo) / self.precio_venta * 100, 1)
        return None

    # Con esta configuración podemos recibir objetos tipo SQLAlchemy en lugar de diccionarios
    model_config = {"from_attributes": True} 


class ProductoCrear(BaseModel):
    nombre: str
    categoria: Optional[str] = None
    precio_venta: float
    costo: Optional[float] = None       # opcional; para cálculo de margen
    stock_minimo: int = 5               # se puede recalcular con /recalcular-stock-minimo
    unidad: str = "pieza"


class ProductoActualizar(BaseModel):
    nombre: Optional[str] = None
    categoria: Optional[str] = None
    precio_venta: Optional[float] = None
    costo: Optional[float] = None
    stock_minimo: Optional[int] = None
    unidad: Optional[str] = None
