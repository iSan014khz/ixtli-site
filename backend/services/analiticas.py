import pandas as pd
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import Producto, Venta


# ── Helpers internos ────────────────────────────────────────────────────────────

def _dt_inicio(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time())

def _dt_fin(d: date) -> datetime:
    return datetime.combine(d, datetime.max.time())

def _formato_strftime(agrupacion: str) -> str:
    return {"dia": "%Y-%m-%d", "semana": "%Y-%W", "mes": "%Y-%m"}.get(agrupacion, "%Y-%m-%d")


# ── 1. Ventas por período  (Descriptiva — ¿Cómo voy?) ──────────────────────────

def ventas_por_periodo(
    db: Session,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    agrupacion: Literal["dia", "semana", "mes"] = "dia",
) -> list[dict]:
    """
    Devuelve el total de ventas e ingresos agrupados por período.
    Sin filtro de fechas retorna todo el historial.
    """
    fmt = _formato_strftime(agrupacion)

    query = db.query(
        func.strftime(fmt, Venta.fecha).label("periodo"),
        func.coalesce(func.sum(Venta.precio_total), 0.0).label("ingresos"),
        func.count(Venta.id).label("num_ventas"),
        func.coalesce(func.sum(Venta.cantidad), 0).label("unidades_vendidas"),
    )

    if desde and hasta:
        query = query.filter(
            Venta.fecha >= _dt_inicio(desde),
            Venta.fecha <= _dt_fin(hasta),
        )

    resultados = query.group_by("periodo").order_by("periodo").all()

    return [
        {
            "periodo": r.periodo,
            "ingresos": round(float(r.ingresos), 2),
            "num_ventas": r.num_ventas,
            "unidades_vendidas": r.unidades_vendidas,
        }
        for r in resultados
    ]


# ── 2. Top productos  (Descriptiva — ¿Qué me mueve?) ───────────────────────────

def top_productos(
    db: Session,
    limite: int = 10,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
) -> list[dict]:
    """
    Ranking de productos ordenado por cantidad vendida.
    Incluye ingresos totales y participación porcentual.
    """
    query = db.query(
        Venta.producto_nombre,
        func.sum(Venta.cantidad).label("cantidad_total"),
        func.coalesce(func.sum(Venta.precio_total), 0.0).label("ingresos_total"),
    )

    if desde and hasta:
        query = query.filter(
            Venta.fecha >= _dt_inicio(desde),
            Venta.fecha <= _dt_fin(hasta),
        )

    resultados = (
        query.group_by(Venta.producto_nombre)
        .order_by(func.sum(Venta.cantidad).desc())
        .limit(limite)
        .all()
    )

    total_unidades = sum(r.cantidad_total for r in resultados) or 1

    return [
        {
            "posicion": i + 1,
            "producto": r.producto_nombre,
            "cantidad_total": r.cantidad_total,
            "ingresos_total": round(float(r.ingresos_total), 2),
            "participacion_pct": round(r.cantidad_total / total_unidades * 100, 1),
        }
        for i, r in enumerate(resultados)
    ]


# ── 3. Rotación de inventario  (Diagnóstica — ¿Qué tan eficiente soy?) ─────────

def rotacion_inventario(db: Session, ventana_dias: int = 30) -> list[dict]:
    """
    Para cada producto calcula:
    - Promedio de ventas diarias en la ventana
    - Días estimados hasta agotar el stock actual
    Ordenado del más urgente al menos urgente.
    """
    productos = db.query(Producto).all()
    corte = datetime.now() - timedelta(days=ventana_dias)

    resultado = []
    for p in productos:
        ventas_periodo = (
            db.query(func.coalesce(func.sum(Venta.cantidad), 0))
            .filter(Venta.producto_id == p.id, Venta.fecha >= corte)
            .scalar()
        )

        promedio_diario = round(ventas_periodo / ventana_dias, 3)
        dias_restantes = (
            round(p.stock_actual / promedio_diario) if promedio_diario > 0 else None
        )

        resultado.append(
            {
                "producto_id": p.id,
                "nombre": p.nombre,
                "categoria": p.categoria,
                "stock_actual": p.stock_actual,
                "stock_minimo": p.stock_minimo,
                "alerta": p.stock_actual < p.stock_minimo,
                f"ventas_ultimos_{ventana_dias}d": ventas_periodo,
                "promedio_diario": promedio_diario,
                "dias_stock_estimados": dias_restantes,
            }
        )

    resultado.sort(
        key=lambda x: (x["dias_stock_estimados"] is None, x["dias_stock_estimados"])
    )
    return resultado


# ── 4. Ticket promedio  (Diagnóstica — ¿Estoy creciendo bien?) ─────────────────

def ticket_promedio(
    db: Session,
    agrupacion: Literal["dia", "semana", "mes"] = "dia",
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
) -> list[dict]:
    """
    Ticket promedio por período junto con tendencia respecto al período anterior.
    Un ticket creciente indica que los clientes compran más por visita.
    """
    fmt = _formato_strftime(agrupacion)

    query = db.query(
        func.strftime(fmt, Venta.fecha).label("periodo"),
        func.coalesce(func.avg(Venta.precio_total), 0.0).label("ticket_promedio"),
        func.count(Venta.id).label("num_ventas"),
        func.coalesce(func.sum(Venta.precio_total), 0.0).label("ingresos_total"),
    )

    if desde and hasta:
        query = query.filter(
            Venta.fecha >= _dt_inicio(desde),
            Venta.fecha <= _dt_fin(hasta),
        )

    filas = query.group_by("periodo").order_by("periodo").all()

    resultado = []
    for i, r in enumerate(filas):
        ticket_anterior = filas[i - 1].ticket_promedio if i > 0 else None
        ticket_actual = float(r.ticket_promedio)

        if ticket_anterior is not None and ticket_anterior > 0:
            variacion_pct = round((ticket_actual - float(ticket_anterior)) / float(ticket_anterior) * 100, 1)
        else:
            variacion_pct = None

        resultado.append(
            {
                "periodo": r.periodo,
                "ticket_promedio": round(ticket_actual, 2),
                "num_ventas": r.num_ventas,
                "ingresos_total": round(float(r.ingresos_total), 2),
                "variacion_pct": variacion_pct,
            }
        )

    return resultado


# ── 5. Stock crítico  (Predictiva — ¿Qué problema viene?) ──────────────────────

def stock_critico(db: Session, ventana_dias: int = 30) -> dict:
    """
    Identifica productos que agotarán su stock antes de X días.
    Clasifica cada producto en: CRÍTICO (≤3 días), ALERTA (4-7 días), VIGILAR (8-30 días).
    Incluye la cantidad mínima sugerida a reponer.
    """
    rotacion = rotacion_inventario(db, ventana_dias)

    criticos, alertas, vigilar = [], [], []

    for p in rotacion:
        dias = p["dias_stock_estimados"]
        promedio = p["promedio_diario"]

        if dias is None:
            continue

        # Cantidad sugerida para cubrir la ventana completa
        reposicion_sugerida = max(0, round(promedio * ventana_dias) - p["stock_actual"])

        entrada = {
            "producto_id": p["producto_id"],
            "nombre": p["nombre"],
            "categoria": p["categoria"],
            "stock_actual": p["stock_actual"],
            "stock_minimo": p["stock_minimo"],
            "dias_restantes": dias,
            "promedio_diario": promedio,
            "reposicion_sugerida": reposicion_sugerida,
        }

        if dias <= 3:
            criticos.append(entrada)
        elif dias <= 7:
            alertas.append(entrada)
        elif dias <= ventana_dias:
            vigilar.append(entrada)

    return {
        "resumen": {
            "criticos": len(criticos),
            "alertas": len(alertas),
            "vigilar": len(vigilar),
        },
        "critico": criticos,
        "alerta": alertas,
        "vigilar": vigilar,
    }
