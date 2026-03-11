# schemas/venta.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class VentaCrear(BaseModel):
    producto_id: int
    cantidad: int
    fecha: Optional[datetime] = None  # si no viene, usas datetime.now() en el endpoint

class VentaRespuesta(BaseModel):
    id: int
    producto_id: Optional[int]
    producto_nombre: str
    cantidad: int
    precio_unitario: Optional[float]
    precio_total: Optional[float]
    fecha: datetime
    fecha_registro: datetime

    model_config = {"from_attributes": True}


"""
{
  "producto_id": 5,
  "cantidad": 3,
  "fecha": "2025-03-10T14:30:00"  // opcional
}
```

Lo que el **endpoint calcula por su cuenta** antes de insertar:
```
precio_unitario  →  lo busca en la tabla productos con el producto_id
precio_total     →  cantidad × precio_unitario
producto_nombre  →  lo busca en la tabla productos con el producto_id
fecha            →  si no viene, datetime.now()
"""

"""
Una cosa que vale notar
precio_unitario y precio_total son Optional[float] en VentaResponse 
porque cuando la venta viene de un CSV importado puede que el usuario no haya mapeado esas columnas. 
No siempre vas a tener esos datos, y el schema debe reflejar esa realidad.
"""