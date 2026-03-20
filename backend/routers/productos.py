from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.schemas.producto import ProductoCrear, ProductoActualizar
from backend.services import analiticas
from sqlalchemy.orm import Session
from sqlalchemy import text

router = APIRouter(prefix="/productos", tags=["productos"])

_SEL_PRODUCTOS = """
SELECT
  id, nombre, categoria, precio_venta, costo,
  stock_actual, stock_minimo, unidad
FROM productos
"""


@router.get("/")
def obtener_productos(categoria: str = None, db: Session = Depends(get_db)):
    """Obtiene todos los productos, opcionalmente filtrando por categoría"""
    if categoria:
        rows = db.execute(
            text(_SEL_PRODUCTOS + " WHERE categoria = :categoria ORDER BY nombre"),
            {"categoria": categoria},
        ).mappings().all()
        if not rows:
            raise HTTPException(status_code=404, detail="Categoría no encontrada")
    else:
        rows = db.execute(text(_SEL_PRODUCTOS + " ORDER BY nombre")).mappings().all()

    return [dict(r) for r in rows]

@router.post("/recalcular-stock-minimo")
def recalcular_stock_minimo(
    lead_time_dias: int = 3,
    ventana_dias:   int = 60,
    db: Session = Depends(get_db),
):
    """
    Calcula y aplica el stock mínimo óptimo a todos los productos con historial.
    Usa la fórmula: stock_min = avg_diario * lead_time + 1.65 * std_diario * sqrt(lead_time)
    """
    sugerencias = analiticas.calcular_stock_minimo_optimo(db, lead_time_dias, ventana_dias)
    actualizados: list[dict] = []

    for s in sugerencias:
        if s["sin_datos"]:
            continue
        db.execute(
            text("UPDATE productos SET stock_minimo = :nuevo WHERE id = :id"),
            {"nuevo": s["stock_minimo_sugerido"], "id": s["producto_id"]},
        )
        actualizados.append(
            {
                "id": s["producto_id"],
                "nombre": s["nombre"],
                "anterior": s["stock_minimo_actual"],
                "nuevo": s["stock_minimo_sugerido"],
            }
        )

    db.commit()
    return {
        "ok":         True,
        "actualizados": len(actualizados),
        "detalle":    actualizados,
    }


@router.get("/alertas")
def obtener_alertas(db: Session = Depends(get_db)):
    """Obtiene los productos con stock por debajo del mínimo"""
    rows = db.execute(
        text(
            """
            SELECT id, nombre, stock_actual, stock_minimo
            FROM productos
            WHERE stock_actual < stock_minimo
            ORDER BY (stock_minimo - stock_actual) DESC, nombre
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]

@router.get("/{id}")
def obtener_producto(id: int, db: Session = Depends(get_db)):
    """Obtiene un producto por su ID"""
    row = db.execute(text(_SEL_PRODUCTOS + " WHERE id = :id"), {"id": id}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return dict(row)

@router.post("/")
@router.post("/")
def crear_producto(producto: ProductoCrear, db: Session = Depends(get_db)):
    existe = db.execute(
        text("SELECT 1 AS ok FROM productos WHERE nombre = :nombre LIMIT 1"),
        {"nombre": producto.nombre},
    ).mappings().first()
    if existe:
        raise HTTPException(status_code=409, detail="Ya existe un producto con ese nombre")

    db.execute(
        text("""
            INSERT INTO productos (nombre, categoria, precio_venta, costo, stock_actual, stock_minimo, unidad)
            VALUES (:nombre, :categoria, :precio_venta, :costo, 0, :stock_minimo, :unidad)
        """),
        {
            "nombre": producto.nombre,
            "categoria": producto.categoria,
            "precio_venta": producto.precio_venta,
            "costo": producto.costo,
            "stock_minimo": producto.stock_minimo,
            "unidad": producto.unidad,
        },
    )
    db.commit()  # ← commit antes de leer
    new_id = db.execute(text("SELECT last_insert_rowid() AS id")).mappings().one()["id"]
    row = db.execute(text(_SEL_PRODUCTOS + " WHERE id = :id"), {"id": new_id}).mappings().one()
    return {"estado": "OK", **dict(row)}


@router.patch("/{id}")
def actualizar_producto(id: int, producto: ProductoActualizar, db: Session = Depends(get_db)):
    """Actualiza un producto existente"""
    actual = db.execute(text(_SEL_PRODUCTOS + " WHERE id = :id"), {"id": id}).mappings().first()
    if not actual:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    nuevo = {
        "nombre": producto.nombre if producto.nombre is not None else actual["nombre"],
        "categoria": producto.categoria if producto.categoria is not None else actual["categoria"],
        "precio_venta": producto.precio_venta if producto.precio_venta is not None else actual["precio_venta"],
        "costo": producto.costo if producto.costo is not None else actual["costo"],
        "stock_minimo": producto.stock_minimo if producto.stock_minimo is not None else actual["stock_minimo"],
        "unidad": producto.unidad if producto.unidad is not None else actual["unidad"],
        "id": id,
    }

    # si cambian el nombre, validar que no choque con otro producto
    if producto.nombre is not None and producto.nombre != actual["nombre"]:
        existe = db.execute(
            text("SELECT 1 AS ok FROM productos WHERE nombre = :nombre AND id <> :id LIMIT 1"),
            {"nombre": producto.nombre, "id": id},
        ).mappings().first()
        if existe:
            raise HTTPException(status_code=409, detail="Ya existe otro producto con ese nombre")

    db.execute(
        text(
            """
            UPDATE productos
            SET nombre = :nombre,
                categoria = :categoria,
                precio_venta = :precio_venta,
                costo = :costo,
                stock_minimo = :stock_minimo,
                unidad = :unidad
            WHERE id = :id
            """
        ),
        nuevo,
    )
    db.commit()

    row = db.execute(text(_SEL_PRODUCTOS + " WHERE id = :id"), {"id": id}).mappings().one()
    return {"estado": "OK", **dict(row)}
    
@router.delete("/{id}")
def eliminar_producto(id: int, db: Session = Depends(get_db)):
    """Elimina un producto existente, si no tiene ventas asociadas"""
    prod = db.execute(text(_SEL_PRODUCTOS + " WHERE id = :id"), {"id": id}).mappings().first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    ventas = db.execute(
        text("SELECT COUNT(1) AS n FROM ventas WHERE producto_id = :id"),
        {"id": id},
    ).mappings().one()["n"]
    if ventas and int(ventas) > 0:
        raise HTTPException(status_code=400, detail="Producto tiene ventas asociadas, no se puede eliminar")

    db.execute(text("DELETE FROM productos WHERE id = :id"), {"id": id})
    db.commit()

    return {"estado": "OK", **dict(prod)}
    