from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from models import Venta, Producto
from database import get_db
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import Optional

router = APIRouter(prefix="/ventas", tags=["ventas"])


class VentaCreate(BaseModel):
    producto_id: int
    cantidad: int
    precio_unitario: Optional[float] = None
    fecha: Optional[date] = None


@router.get("/")
def obtener_ventas(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Lista el historial de ventas. Acepta filtros opcionales: ?desde=2025-03-01&hasta=2025-03-07"""
    if (desde is None) != (hasta is None):
        raise HTTPException(
            status_code=400,
            detail="Debes proporcionar ambos filtros: desde y hasta"
        )
    if desde and hasta:
        if desde > hasta:
            raise HTTPException(
                status_code=400,
                detail="'desde' no puede ser posterior a 'hasta'"
            )
        ventas = db.query(Venta).filter(
            Venta.fecha >= datetime.combine(desde, datetime.min.time()),
            Venta.fecha <= datetime.combine(hasta, datetime.max.time())
        ).all()
    else:
        ventas = db.query(Venta).all()

    return [{
        "id": venta.id,
        "producto_id": venta.producto_id,
        "producto_nombre": venta.producto_nombre,
        "cantidad": venta.cantidad,
        "precio_unitario": venta.precio_unitario,
        "precio_total": venta.precio_total,
        "fecha": venta.fecha.strftime("%Y-%m-%d")
    } for venta in ventas]


@router.post("/", status_code=201)
def registrar_venta(datos: VentaCreate, db: Session = Depends(get_db)):
    """Registra una venta manual y descuenta el stock del producto"""
    producto = db.query(Producto).filter(Producto.id == datos.producto_id).first()
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    if producto.stock_actual < datos.cantidad:
        raise HTTPException(
            status_code=400,
            detail=f"Stock insuficiente. Disponible: {producto.stock_actual}"
        )

    precio_unitario = datos.precio_unitario if datos.precio_unitario is not None else producto.precio_venta
    precio_total = round(precio_unitario * datos.cantidad, 2) if precio_unitario is not None else None
    fecha = datetime.combine(datos.fecha, datetime.min.time()) if datos.fecha else datetime.now()

    venta = Venta(
        producto_id=producto.id,
        producto_nombre=producto.nombre,
        cantidad=datos.cantidad,
        precio_unitario=precio_unitario,
        precio_total=precio_total,
        fecha=fecha
    )
    db.add(venta)

    producto.stock_actual -= datos.cantidad

    db.commit()
    db.refresh(venta)

    return {
        "id": venta.id,
        "producto_id": venta.producto_id,
        "producto_nombre": venta.producto_nombre,
        "cantidad": venta.cantidad,
        "precio_unitario": venta.precio_unitario,
        "precio_total": venta.precio_total,
        "fecha": venta.fecha.strftime("%Y-%m-%d"),
        "stock_restante": producto.stock_actual
    }
