from datetime import date, datetime, timedelta
from typing import Literal, Optional


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Producto, Venta
from backend.services import analiticas

router = APIRouter(prefix="/reportes", tags=["reportes"])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _rango_dia(d: date):
    return datetime.combine(d, datetime.min.time()), datetime.combine(d, datetime.max.time())


def _validar_rango(desde: Optional[date], hasta: Optional[date]):
    if (desde is None) != (hasta is None):
        raise HTTPException(status_code=400, detail="Debes proporcionar ambos: desde y hasta")
    if desde and hasta and desde > hasta:
        raise HTTPException(status_code=400, detail="'desde' no puede ser posterior a 'hasta'")


def _formato_strftime(agrupacion: str) -> str:
    return {
        "dia": "%Y-%m-%d",
        "semana": "%Y-%W",
        "mes": "%Y-%m"
    }.get(agrupacion, "%Y-%m-%d")


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    """KPIs del día: ventas totales, ticket promedio, alertas activas y top 3 productos"""
    inicio, fin = _rango_dia(date.today())

    total, num_ventas = db.query(
        func.coalesce(func.sum(Venta.precio_total), 0.0),
        func.count(Venta.id)
    ).filter(Venta.fecha >= inicio, Venta.fecha <= fin).first()

    ticket_promedio = round(total / num_ventas, 2) if num_ventas > 0 else 0.0

    alertas = db.query(func.count(Producto.id)).filter(
        Producto.stock_actual < Producto.stock_minimo
    ).scalar()

    top_3 = db.query(
        Venta.producto_nombre,
        func.sum(Venta.cantidad).label("cantidad")
    ).filter(
        Venta.fecha >= inicio, Venta.fecha <= fin
    ).group_by(Venta.producto_nombre).order_by(
        func.sum(Venta.cantidad).desc()
    ).limit(3).all()

    return {
        "ventas_totales_hoy": round(float(total), 2),
        "num_transacciones_hoy": num_ventas,
        "ticket_promedio_hoy": ticket_promedio,
        "alertas_activas": alertas,
        "top_3_productos_hoy": [{"producto": r[0], "cantidad": r[1]} for r in top_3]
    }


@router.get("/ventas-por-periodo")
def ventas_por_periodo(
    agrupacion: Literal["dia", "semana", "mes"] = "dia",
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Ventas agrupadas por período. Acepta ?agrupacion=dia|semana|mes&desde=&hasta="""
    _validar_rango(desde, hasta)

    fmt = _formato_strftime(agrupacion)

    query = db.query(
        func.strftime(fmt, Venta.fecha).label("periodo"),
        func.coalesce(func.sum(Venta.precio_total), 0.0).label("total"),
        func.count(Venta.id).label("num_ventas")
    )

    if desde and hasta:
        query = query.filter(
            Venta.fecha >= datetime.combine(desde, datetime.min.time()),
            Venta.fecha <= datetime.combine(hasta, datetime.max.time())
        )

    resultados = query.group_by("periodo").order_by("periodo").all()

    return [{"periodo": r.periodo, "total": round(float(r.total), 2), "num_ventas": r.num_ventas}
            for r in resultados]


@router.get("/top-productos")
def top_productos(
    limite: int = 10,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Ranking de productos más vendidos por cantidad. Acepta ?limite=10&desde=&hasta="""
    _validar_rango(desde, hasta)

    if limite < 1 or limite > 100:
        raise HTTPException(status_code=400, detail="'limite' debe estar entre 1 y 100")

    query = db.query(
        Venta.producto_nombre,
        func.sum(Venta.cantidad).label("cantidad_total"),
        func.coalesce(func.sum(Venta.precio_total), 0.0).label("ingresos_total")
    )

    if desde and hasta:
        query = query.filter(
            Venta.fecha >= datetime.combine(desde, datetime.min.time()),
            Venta.fecha <= datetime.combine(hasta, datetime.max.time())
        )

    resultados = query.group_by(Venta.producto_nombre).order_by(
        func.sum(Venta.cantidad).desc()
    ).limit(limite).all()

    return [
        {
            "posicion": i + 1,
            "producto": r.producto_nombre,
            "cantidad_total": r.cantidad_total,
            "ingresos_total": round(float(r.ingresos_total), 2)
        }
        for i, r in enumerate(resultados)
    ]


@router.get("/rotacion")
def rotacion(db: Session = Depends(get_db)):
    """Por cada producto: stock actual, promedio de ventas diarias y días estimados de stock"""
    productos = db.query(Producto).all()
    hace_30_dias = datetime.now() - timedelta(days=30)

    resultado = []
    for p in productos:
        ventas_30d = db.query(
            func.coalesce(func.sum(Venta.cantidad), 0)
        ).filter(
            Venta.producto_id == p.id,
            Venta.fecha >= hace_30_dias
        ).scalar()

        promedio_diario = round(ventas_30d / 30, 2)
        dias_restantes = (
            round(p.stock_actual / promedio_diario) if promedio_diario > 0 else None
        )

        resultado.append({
            "producto_id": p.id,
            "nombre": p.nombre,
            "categoria": p.categoria,
            "stock_actual": p.stock_actual,
            "stock_minimo": p.stock_minimo,
            "alerta": p.stock_actual < p.stock_minimo,
            "ventas_ultimos_30d": ventas_30d,
            "promedio_diario": promedio_diario,
            "dias_stock_estimados": dias_restantes
        })

    resultado.sort(key=lambda x: (x["dias_stock_estimados"] is None, x["dias_stock_estimados"]))
    return resultado


@router.get("/ticket-promedio")
def ticket_promedio(
    agrupacion: Literal["dia", "semana", "mes"] = "dia",
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """Ticket promedio agrupado por período. Acepta ?agrupacion=dia|semana|mes&desde=&hasta="""
    _validar_rango(desde, hasta)

    fmt = _formato_strftime(agrupacion)

    query = db.query(
        func.strftime(fmt, Venta.fecha).label("periodo"),
        func.coalesce(func.avg(Venta.precio_total), 0.0).label("ticket_promedio"),
        func.count(Venta.id).label("num_ventas")
    )

    if desde and hasta:
        query = query.filter(
            Venta.fecha >= datetime.combine(desde, datetime.min.time()),
            Venta.fecha <= datetime.combine(hasta, datetime.max.time())
        )

    resultados = query.group_by("periodo").order_by("periodo").all()

    return [
        {
            "periodo": r.periodo,
            "ticket_promedio": round(float(r.ticket_promedio), 2),
            "num_ventas": r.num_ventas
        }

        for r in resultados
    ]


@router.get("/ventas-por-dia-semana")
def ventas_por_dia_semana(db: Session = Depends(get_db)):
    """Ventas históricas por día de la semana (Lunes=0 … Domingo=6), calculado con pandas."""
    return analiticas.ventas_por_dia_semana(db)


@router.get("/flujo-por-hora")
def flujo_por_hora(dia_semana: int = 0, db: Session = Depends(get_db)):
    """Flujo de compras por hora para un día de la semana (Lunes=0 … Domingo=6)."""
    return analiticas.flujo_por_hora(db, dia_semana)


@router.get("/top-por-margen")
def top_por_margen(limite: int = 10, db: Session = Depends(get_db)):
    """Top productos por margen de ganancia total. Solo productos con costo definido."""
    return analiticas.top_por_margen(db, limite)


@router.get("/stock-minimo-sugerido")
def stock_minimo_sugerido(
    lead_time_dias: int = 3,
    ventana_dias:   int = 60,
    db: Session = Depends(get_db),
):
    """
    Previsualiza el stock mínimo óptimo calculado automáticamente.
    No aplica cambios a la base de datos.
    Parámetros opcionales: ?lead_time_dias=3&ventana_dias=60
    """
    return analiticas.calcular_stock_minimo_optimo(db, lead_time_dias, ventana_dias)
