from fastapi import FastAPI
from backend.routers import cargar_archivos, uploads, ventas, productos, reportes
import uvicorn

app = FastAPI()

app.include_router(cargar_archivos.router)
app.include_router(uploads.router)
app.include_router(ventas.router)
app.include_router(productos.router)
app.include_router(reportes.router)

@app.get("/")
def read_root():
    return {"message": "Bienvenido a la API de carga de archivos"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)