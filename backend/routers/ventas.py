from fastapi import APIRouter, HTTPException, Depends
from backend.database import get_db
from backend.schemas.venta import VentaCrear
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime
from typing import Optional

router = APIRouter(prefix="/ventas", tags=["ventas"])

def _fecha_to_str(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v.replace("Z", "")).strftime("%Y-%m-%d")
        except ValueError:
            return v[:10] if len(v) >= 10 else v
    return v.strftime("%Y-%m-%d")

@router.get("/")
def obtener_ventas(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Lista el historial de ventas. Acepta filtros opcionales: ?desde=2025-03-01&hasta=2025-03-07"""
    if (desde is None) != (hasta is None):
        raise HTTPException(status_code=400, detail="Debes proporcionar ambos filtros: desde y hasta")
    if desde and hasta:
        if desde > hasta:
            raise HTTPException(status_code=400, detail="'desde' no puede ser posterior a 'hasta'")
        inicio = datetime.combine(desde, datetime.min.time())
        fin = datetime.combine(hasta, datetime.max.time())
        rows = db.execute(
            text("""
                SELECT id, producto_id, producto_nombre, cantidad,
                       precio_unitario, precio_total, fecha
                FROM ventas
                WHERE fecha >= :inicio AND fecha <= :fin
                ORDER BY fecha DESC, id DESC
            """),
            {"inicio": inicio, "fin": fin},
        ).mappings().all()
    else:
        rows = db.execute(
            text("""
                SELECT id, producto_id, producto_nombre, cantidad,
                       precio_unitario, precio_total, fecha
                FROM ventas
                ORDER BY fecha DESC, id DESC
            """)
        ).mappings().all()

    out = []
    for r in rows:
        d = dict(r)
        d["fecha"] = _fecha_to_str(d.get("fecha"))
        out.append(d)
    return out

@router.post("/", status_code=201)
def registrar_venta(datos: VentaCrear, db: Session = Depends(get_db)):
    prod = db.execute(
        text("""
            SELECT id, nombre, precio_venta, stock_actual
            FROM productos WHERE id = :id
        """),
        {"id": datos.producto_id},
    ).mappings().first()
    if not prod:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if int(prod["stock_actual"]) < datos.cantidad:
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente. Disponible: {prod['stock_actual']}"
        )

    precio_unitario = prod["precio_venta"]  # siempre viene de la BD
    precio_total = round(precio_unitario * datos.cantidad, 2)
    fecha = datetime.combine(datos.fecha, datetime.min.time()) if datos.fecha else datetime.now()


    # Insert venta
    db.execute(
        text(
            """
            INSERT INTO ventas (producto_id, producto_nombre, cantidad, precio_unitario, precio_total, fecha)
            VALUES (:producto_id, :producto_nombre, :cantidad, :precio_unitario, :precio_total, :fecha)
            """
        ),
        {
            "producto_id": prod["id"],
            "producto_nombre": prod["nombre"],
            "cantidad": datos.cantidad,
            "precio_unitario": precio_unitario,
            "precio_total": precio_total,
            "fecha": fecha,
        },
    )

    venta_id = db.execute(text("SELECT last_insert_rowid() AS id")).mappings().one()["id"]
    
    # Descontar stock
    db.execute(
        text("UPDATE productos SET stock_actual = stock_actual - :cant WHERE id = :id"),
        {"cant": datos.cantidad, "id": prod["id"]},
    )

    db.commit()

    venta = db.execute(
        text(
            """
            SELECT id, producto_id, producto_nombre, cantidad, precio_unitario, precio_total, fecha
            FROM ventas
            WHERE id = :id
            """
        ),
        {"id": venta_id},
    ).mappings().one()

    stock_restante = db.execute(
        text("SELECT stock_actual FROM productos WHERE id = :id"),
        {"id": prod["id"]},
    ).mappings().one()["stock_actual"]

    return {
        "id": venta["id"],
        "producto_id": venta["producto_id"],
        "producto_nombre": venta["producto_nombre"],
        "cantidad": venta["cantidad"],
        "precio_unitario": venta["precio_unitario"],
        "precio_total": venta["precio_total"],
        "fecha": _fecha_to_str(venta.get("fecha")),
        "stock_restante": stock_restante,
    }
