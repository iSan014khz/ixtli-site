from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.routers import cargasArch, ventas, productos, reportes
from backend import migrations
import uvicorn

migrations.ejecutar_migraciones()

app = FastAPI(title="Ixtli API", version="1.0.0")

# ── API routers ────────────────────────────────────────────────────────────────
app.include_router(cargasArch.router)
app.include_router(ventas.router)
app.include_router(productos.router)
app.include_router(reportes.router)

# ── Frontend pages ─────────────────────────────────────────────────────────────
@app.get("/", response_class=FileResponse, include_in_schema=False)
def serve_dashboard():
    return FileResponse("frontend/index.html")

@app.get("/app/ventas", response_class=FileResponse, include_in_schema=False)
def serve_ventas():
    return FileResponse("frontend/ventas.html")

@app.get("/app/productos", response_class=FileResponse, include_in_schema=False)
def serve_productos():
    return FileResponse("frontend/productos.html")

@app.get("/app/importar", response_class=FileResponse, include_in_schema=False)
def serve_importar():
    return FileResponse("frontend/importar.html")

# Archivos estáticos (CSS, JS, etc.)
app.mount("/", StaticFiles(directory="frontend"), name="static")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
