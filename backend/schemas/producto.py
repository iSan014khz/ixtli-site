from pydantic import BaseModel, computed_field
from typing import Optional

class ProductoRespuesta(BaseModel):
    id: int
    nombre: str
    categoria: str
    precio_venta: float
    stock_actual: int
    stock_minimo: int
    unidad: str
    @computed_field
    @property
    def alerta_stock(self) -> bool:
        return self.stock_actual < self.stock_minimo
        
    # es importante — sin él Pydantic no puede leer los objetos que devuelve SQLAlchemy directamente, solo diccionarios.
    model_config = {"from_attributes": True} 
    
class ProductoCrear(BaseModel):
    nombre: str
    categoria: str
    precio_venta: float
    stock_minimo: int
    unidad: str
    
class ProductoActualizar(BaseModel):
    nombre: Optional[str] = None # Campos opcionales
    categoria: Optional[str] = None # Campos opcionales
    precio_venta: Optional[float] = None # Campos opcionales
    stock_minimo: Optional[int] = None # Campos opcionales
    unidad: Optional[str] = None # Campos opcionales
    
