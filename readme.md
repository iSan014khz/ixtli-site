# Ixtli — Abarrotes Smart

Sistema de gestión y análisis para tienda de abarrotes. API REST con FastAPI, base SQLite y dashboard web.

---

## Estructura del proyecto

```
Ixtli Site/
├── main.py                    # Punto de entrada FastAPI
├── requirements.txt           # Dependencias Python
├── readme.md
├── arquitectura.txt           # Documento de arquitectura
│
├── backend/
│   ├── __init__.py
│   ├── database.py            # Conexión SQLite + SessionLocal
│   ├── migrations.py          # Migraciones automáticas (ej: añadir columna costo)
│   ├── seed_data.py           # Script para generar datos de prueba
│   │
│   ├── models/                # Tablas SQLAlchemy
│   │   ├── __init__.py
│   │   ├── producto.py        # Producto (nombre, precio, stock, costo…)
│   │   ├── venta.py           # Venta (producto, cantidad, fecha, precio_total)
│   │   └── cargas.py          # Carga (historial de importaciones)
│   │
│   ├── schemas/               # Validación Pydantic
│   │   ├── __init__.py
│   │   ├── producto.py        # ProductoCrear, ProductoActualizar, ProductoRespuesta
│   │   ├── venta.py           # Esquemas de venta
│   │   └── carga.py           # MapeoColumnas, ResultadoCarga
│   │
│   ├── routers/               # Endpoints FastAPI
│   │   ├── __init__.py
│   │   ├── productos.py       # CRUD productos + alertas + recalcular stock
│   │   ├── ventas.py          # Listar/crear ventas
│   │   ├── reportes.py        # Dashboard, KPIs, top, rotación, etc.
│   │   └── cargasArch.py      # Subir CSV/XLSX y confirmar importación
│   │
│   └── services/              # Lógica de negocio
│       ├── __init__.py
│       ├── analiticas.py      # Cálculos con Pandas (ventas, margen, rotación, stock)
│       └── formatear_datos.py # Formateo de respuestas
│
├── frontend/
│   ├── index.html             # Dashboard principal
│   ├── ventas.html            # Página Ventas
│   ├── productos.html         # Página Productos
│   ├── importar.html          # Página Importar CSV
│   ├── chart-container.html   # Ejemplo/referencia de gráficas
│   │
│   ├── css/
│   │   ├── app.css            # Estilos compartidos (sidebar, cards, tablas, modales)
│   │   ├── index.css          # Estilos adicionales
│   │   └── dasboard.css       # Estilos del dashboard
│   │
│   ├── js/
│   │   ├── common.js          # API helper, formateadores, sidebar, reloj
│   │   ├── dashboard.js       # KPIs, gráficas, top productos, rotación
│   │   ├── ventas.js          # Tabla ventas + modal registrar
│   │   ├── productos.js       # Grid productos + CRUD + auto stock
│   │   └── importar.js        # Flujo subir → mapear → confirmar
│   │
│   └── imgs/
│       └── folder.png
│
├── scripts/
│   └── generar_csvs.py       # Genera CSV/XLSX de prueba y opcionalmente sube al API
│
├── data/
│   └── abarrote.db            # Base SQLite (generada automáticamente)
│
├── temp/                      # Archivos temporales de carga (se borran tras confirmar)
│
└── test_csvs/                 # CSVs/XLSX generados por generar_csvs.py
```

---

## Descripción de archivos

### Raíz


| Archivo            | Descripción                                                                                                                                                                                    |
| ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`          | Inicia migraciones, registra routers (`productos`, `ventas`, `reportes`, `cargasArch`), sirve páginas HTML (`/`, `/app/ventas`, `/app/productos`, `/app/importar`) y monta archivos estáticos. |
| `requirements.txt` | Dependencias: FastAPI, uvicorn, pydantic, SQLAlchemy, pandas, openpyxl, python-multipart.                                                                                                      |


### Backend


| Archivo         | Descripción                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------- |
| `database.py`   | Engine SQLite y `get_db()`. Crea la BD en `data/abarrote.db`.                               |
| `migrations.py` | Migraciones idempotentes al arrancar. Ej: añade columna `costo` a `productos` si no existe. |
| `seed_data.py`  | Genera productos y ~1500 ventas de 90 días. Ejecutar: `python backend/seed_data.py`.        |


### Models


| Archivo       | Descripción                                                                                        |
| ------------- | -------------------------------------------------------------------------------------------------- |
| `producto.py` | Tabla `productos`: id, nombre, categoria, precio_venta, stock_actual, stock_minimo, costo, unidad. |
| `venta.py`    | Tabla `ventas`: producto_id, producto_nombre, cantidad, precio_unitario, precio_total, fecha.      |
| `cargas.py`   | Tabla `cargas`: historial de importaciones (hash MD5, filas, periodo, mapeo).                      |


### Schemas


| Archivo       | Descripción                                                 |
| ------------- | ----------------------------------------------------------- |
| `producto.py` | `ProductoCrear`, `ProductoActualizar`, `ProductoRespuesta`. |
| `venta.py`    | Esquemas Pydantic para ventas.                              |
| `carga.py`    | `MapeoColumnas`, `ResultadoCarga`.                          |


### Routers


| Archivo         | Descripción                                                                                                                                                                            |
| --------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `productos.py`  | `GET/POST /productos`, `GET /productos/alertas`, `GET/PATCH/DELETE /productos/{id}`, `POST /productos/recalcular-stock-minimo`.                                                        |
| `ventas.py`     | `GET/POST /ventas` con filtros por fecha.                                                                                                                                              |
| `reportes.py`   | `GET /reportes/dashboard`, `ventas-por-periodo`, `top-productos`, `top-por-margen`, `ticket-promedio`, `rotacion`, `stock-minimo-sugerido`, `ventas-por-dia-semana`, `flujo-por-hora`. |
| `cargasArch.py` | `POST /cargas/previa-carga`, `POST /cargas/confirmar-carga`, `GET /cargas/historial`.                                                                                                  |


### Services


| Archivo              | Descripción                                                                                                                                                                       |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `analiticas.py`      | Funciones con Pandas: ventas por período, top productos, top por margen, ticket promedio, rotación, stock crítico, ventas por día de semana, flujo por hora, stock mínimo óptimo. |
| `formatear_datos.py` | Formateo de respuestas para reportes.                                                                                                                                             |


### Frontend


| Archivo          | Descripción                                                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `index.html`     | Dashboard: KPIs, ventas por período, top productos (unidades/margen), ticket, alertas, día de semana, flujo por hora, rotación. |
| `ventas.html`    | Lista de ventas con filtros y modal para registrar venta manual.                                                                |
| `productos.html` | Grid de productos, CRUD, modal de auto stock mínimo.                                                                            |
| `importar.html`  | Subida CSV/XLSX, mapeo de columnas, confirmación e historial.                                                                   |
| `app.css`        | Variables, sidebar, header, KPIs, cards, tablas, modales, top productos, stock/alertas.                                         |
| `common.js`      | `API.get/post`, formateadores, sidebar, reloj, modales.                                                                         |
| `dashboard.js`   | Carga KPIs, gráficas Chart.js, top productos, ticket, alertas, rotación, día de semana, flujo por hora.                         |
| `ventas.js`      | Carga ventas filtradas, modal registrar.                                                                                        |
| `productos.js`   | Carga productos, CRUD, modal auto stock.                                                                                        |
| `importar.js`    | Preview, mapeo, confirmación, historial de cargas.                                                                              |


### Scripts


| Archivo           | Descripción                                                                                                                  |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `generar_csvs.py` | Genera 5 CSVs/XLSX de prueba en `test_csvs/`. Opciones: `--upload` (sube al API), `--reset` (reseed BD), `--solo <archivo>`. |


---

## Cómo ejecutar

```bash
# Crear entorno virtual e instalar (Python 3.11 64bits)
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# Datos de prueba (opcional)
python backend/seed_data.py

# Levantar servidor
python main.py
```

Abrir `http://127.0.0.1:8000`. API docs en `http://127.0.0.1:8000/docs`.

---

## Endpoints principales


| Método | Ruta                                         | Descripción                               |
| ------ | -------------------------------------------- | ----------------------------------------- |
| GET    | `/`                                          | Dashboard                                 |
| GET    | `/app/ventas`                                | Página ventas                             |
| GET    | `/app/productos`                             | Página productos                          |
| GET    | `/app/importar`                              | Página importar                           |
| GET    | `/reportes/dashboard`                        | KPIs del día                              |
| GET    | `/reportes/ventas-por-periodo?agrupacion=dia | semana                                    |
| GET    | `/reportes/top-productos?limite=8`           | Top por unidades                          |
| GET    | `/reportes/top-por-margen?limite=8`          | Top por margen total                      |
| GET    | `/reportes/rotacion`                         | Rotación e inventario crítico             |
| POST   | `/cargas/previa-carga`                       | Sube archivo, devuelve columnas + preview |
| POST   | `/cargas/confirmar-carga`                    | Aplica mapeo e inserta ventas             |


