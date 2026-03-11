# schemas/cargaArch.py
from pydantic import BaseModel
from typing import List, Optional

class MapeoColumnas(BaseModel):
    archivo_id: str
    # Clave: columna del archivo, valor: columna del sistema
    mapeo: dict[str, str]
    nombre_archivo: Optional[str] = None
    
class FilaError(BaseModel):
    fila: int
    columna: str
    error: str
    
class ResultadoCarga(BaseModel):
    ok: bool
    filas_importadas: int
    filas_ignoradas: int
    errores: list[FilaError] = []
    periodo: dict[str, str]
    solapamiento_resultado: bool