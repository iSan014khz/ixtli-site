from datetime import date, datetime, timedelta
from typing import Literal, Optional


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from backend.database import get_db
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

    r = db.execute(
        text(
            """
            SELECT
              COALESCE(SUM(precio_total), 0.0) AS total,
              COUNT(1) AS num_ventas
            FROM ventas
            WHERE fecha >= :inicio AND fecha <= :fin
            """
        ),
        {"inicio": inicio, "fin": fin},
    ).mappings().one()

    total = float(r["total"] or 0.0)
    num_ventas = int(r["num_ventas"] or 0)
    ticket_promedio = round(total / num_ventas, 2) if num_ventas > 0 else 0.0

    alertas = db.execute(
        text("SELECT COUNT(1) AS n FROM productos WHERE stock_actual < stock_minimo")
    ).mappings().one()["n"]

    top_3 = db.execute(
        text(
            """
            SELECT producto_nombre, SUM(cantidad) AS cantidad
            FROM ventas
            WHERE fecha >= :inicio AND fecha <= :fin
            GROUP BY producto_nombre
            ORDER BY SUM(cantidad) DESC
            LIMIT 3
            """
        ),
        {"inicio": inicio, "fin": fin},
    ).mappings().all()

    return {
        "ventas_totales_hoy": round(float(total), 2),
        "num_transacciones_hoy": num_ventas,
        "ticket_promedio_hoy": ticket_promedio,
        "alertas_activas": int(alertas or 0),
        "top_3_productos_hoy": [{"producto": r["producto_nombre"], "cantidad": r["cantidad"]} for r in top_3],
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
    where = ""
    params = {}
    if desde and hasta:
        where = "WHERE fecha >= :inicio AND fecha <= :fin"
        params = {
            "inicio": datetime.combine(desde, datetime.min.time()),
            "fin": datetime.combine(hasta, datetime.max.time()),
        }

    rows = db.execute(
        text(
            f"""
            SELECT strftime('{fmt}', fecha) AS periodo,
                   COALESCE(SUM(precio_total), 0.0) AS total,
                   COUNT(1) AS num_ventas
            FROM ventas
            {where}
            GROUP BY periodo
            ORDER BY periodo
            """
        ),
        params,
    ).mappings().all()

    return [
        {"periodo": r["periodo"], "total": round(float(r["total"]), 2), "num_ventas": int(r["num_ventas"])}
        for r in rows
    ]


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

    where = ""
    params = {"lim": limite}
    if desde and hasta:
        where = "WHERE fecha >= :inicio AND fecha <= :fin"
        params.update(
            {
                "inicio": datetime.combine(desde, datetime.min.time()),
                "fin": datetime.combine(hasta, datetime.max.time()),
            }
        )

    rows = db.execute(
        text(
            f"""
            SELECT producto_nombre AS producto,
                   SUM(cantidad) AS cantidad_total,
                   COALESCE(SUM(precio_total), 0.0) AS ingresos_total
            FROM ventas
            {where}
            GROUP BY producto_nombre
            ORDER BY SUM(cantidad) DESC
            LIMIT :lim
            """
        ),
        params,
    ).mappings().all()

    return [
        {
            "posicion": i + 1,
            "producto": r["producto"],
            "cantidad_total": int(r["cantidad_total"]),
            "ingresos_total": round(float(r["ingresos_total"]), 2),
        }
        for i, r in enumerate(rows)
    ]


@router.get("/rotacion")
def rotacion(db: Session = Depends(get_db)):
    """Por cada producto: stock actual, promedio de ventas diarias y días estimados de stock"""
    hace_30_dias = datetime.now() - timedelta(days=30)
    # Un solo query: productos + ventas_30d agregadas por producto_id
    rows = db.execute(
        text(
            """
            SELECT
              p.id AS producto_id,
              p.nombre,
              p.categoria,
              p.stock_actual,
              p.stock_minimo,
              CASE WHEN p.stock_actual < p.stock_minimo THEN 1 ELSE 0 END AS alerta,
              COALESCE(v.cant_30d, 0) AS ventas_ultimos_30d
            FROM productos p
            LEFT JOIN (
              SELECT producto_id, SUM(cantidad) AS cant_30d
              FROM ventas
              WHERE fecha >= :corte AND producto_id IS NOT NULL
              GROUP BY producto_id
            ) v ON v.producto_id = p.id
            """
        ),
        {"corte": hace_30_dias},
    ).mappings().all()

    resultado = []
    for r in rows:
        ventas_30d = float(r["ventas_ultimos_30d"] or 0)
        promedio_diario = round(ventas_30d / 30, 2)
        dias_restantes = round(r["stock_actual"] / promedio_diario) if promedio_diario > 0 else None
        resultado.append(
            {
                "producto_id": r["producto_id"],
                "nombre": r["nombre"],
                "categoria": r["categoria"],
                "stock_actual": r["stock_actual"],
                "stock_minimo": r["stock_minimo"],
                "alerta": bool(r["alerta"]),
                "ventas_ultimos_30d": int(ventas_30d),
                "promedio_diario": promedio_diario,
                "dias_stock_estimados": dias_restantes,
            }
        )
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
    where = ""
    params = {}
    if desde and hasta:
        where = "WHERE fecha >= :inicio AND fecha <= :fin"
        params = {
            "inicio": datetime.combine(desde, datetime.min.time()),
            "fin": datetime.combine(hasta, datetime.max.time()),
        }

    rows = db.execute(
        text(
            f"""
            SELECT strftime('{fmt}', fecha) AS periodo,
                   COALESCE(AVG(precio_total), 0.0) AS ticket_promedio,
                   COUNT(1) AS num_ventas
            FROM ventas
            {where}
            GROUP BY periodo
            ORDER BY periodo
            """
        ),
        params,
    ).mappings().all()

    return [
        {
            "periodo": r["periodo"],
            "ticket_promedio": round(float(r["ticket_promedio"]), 2),
            "num_ventas": int(r["num_ventas"]),
        }
        for r in rows
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
