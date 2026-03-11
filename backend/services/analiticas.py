import math

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


# ── Top productos por margen de ganancia ──────────────────────────────────────

def top_por_margen(db: Session, limite: int = 10) -> list[dict]:
    """
    Ranking de productos por margen de ganancia total generado.
    Solo incluye productos con costo definido.

    Métricas por producto:
    - margen_unitario  = precio_venta − costo
    - margen_pct       = margen_unitario / precio_venta × 100
    - margen_total     = margen_unitario × cantidad_vendida  ← criterio de orden
    """
    prods = (
        db.query(Producto)
        .filter(Producto.costo.isnot(None), Producto.precio_venta.isnot(None))
        .all()
    )
    if not prods:
        return []

    ids = [p.id for p in prods]
    ventas_rows = db.query(Venta.producto_id, Venta.cantidad).filter(
        Venta.producto_id.in_(ids)
    ).all()

    if not ventas_rows:
        return []

    df = pd.DataFrame(ventas_rows, columns=["producto_id", "cantidad"])
    grp = df.groupby("producto_id")["cantidad"].agg(
        cantidad_total="sum", num_ventas="count"
    ).reset_index()

    p_map = {p.id: p for p in prods}
    resultado = []

    for _, row in grp.iterrows():
        pid  = int(row["producto_id"])
        p    = p_map.get(pid)
        if not p:
            continue

        margen_u  = p.precio_venta - p.costo
        margen_pct = round(margen_u / p.precio_venta * 100, 1) if p.precio_venta > 0 else 0.0
        cantidad  = int(row["cantidad_total"])

        resultado.append({
            "posicion":         0,
            "producto_id":      pid,
            "nombre":           p.nombre,
            "categoria":        p.categoria or "",
            "precio_venta":     round(p.precio_venta, 2),
            "costo":            round(p.costo, 2),
            "margen_unitario":  round(margen_u, 2),
            "margen_pct":       margen_pct,
            "cantidad_vendida": cantidad,
            "num_ventas":       int(row["num_ventas"]),
            "margen_total":     round(margen_u * cantidad, 2),
        })

    resultado.sort(key=lambda x: x["margen_total"], reverse=True)
    for i, r in enumerate(resultado[:limite], start=1):
        r["posicion"] = i

    return resultado[:limite]


# ── Ventas por día de semana ──────────────────────────────────────────────────

DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

def ventas_por_dia_semana(db: Session) -> list[dict]:
    """Ventas históricas agrupadas por día de la semana usando pandas."""
    rows = db.query(Venta.fecha, Venta.precio_total).all()

    if not rows:
        return [{"dia_num": n, "dia": DIAS_ES[n], "total": 0.0, "num_ventas": 0}
                for n in range(7)]

    df = pd.DataFrame(rows, columns=["fecha", "precio_total"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["dia_semana"] = df["fecha"].dt.dayofweek  # 0=Lunes … 6=Domingo

    grp = (
        df.groupby("dia_semana")["precio_total"]
        .agg(total="sum", num_ventas="count")
        .reset_index()
    )

    resultado = []
    for n in range(7):
        fila = grp[grp["dia_semana"] == n]
        resultado.append({
            "dia_num":    n,
            "dia":        DIAS_ES[n],
            "total":      round(float(fila["total"].iloc[0]), 2) if not fila.empty else 0.0,
            "num_ventas": int(fila["num_ventas"].iloc[0])        if not fila.empty else 0,
        })
    return resultado


# ── Flujo de compras por hora ─────────────────────────────────────────────────

def flujo_por_hora(db: Session, dia_semana: int = 0) -> list[dict]:
    """Ventas por hora para un día de la semana dado (0=Lunes … 6=Domingo)."""
    rows = db.query(Venta.fecha, Venta.precio_total).all()

    if not rows:
        return [{"hora": f"{h:02d}:00", "total": 0.0, "num_ventas": 0}
                for h in range(6, 23)]

    df = pd.DataFrame(rows, columns=["fecha", "precio_total"])
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["dia_semana"] = df["fecha"].dt.dayofweek
    df["hora"]       = df["fecha"].dt.hour

    filtro = df[df["dia_semana"] == dia_semana]

    grp = (
        filtro.groupby("hora")["precio_total"]
        .agg(total="sum", num_ventas="count")
        .reset_index()
    )

    resultado = []
    for h in range(6, 23):
        fila = grp[grp["hora"] == h]
        resultado.append({
            "hora":       f"{h:02d}:00",
            "total":      round(float(fila["total"].iloc[0]), 2) if not fila.empty else 0.0,
            "num_ventas": int(fila["num_ventas"].iloc[0])        if not fila.empty else 0,
        })
    return resultado


# ── Stock mínimo óptimo ───────────────────────────────────────────────────────
# Fórmula de punto de reorden con stock de seguridad:
#   stock_min = avg_diario * lead_time + Z * std_diario * sqrt(lead_time)
# Z = 1.65  →  nivel de servicio 95 %
# lead_time = días estimados para recibir un pedido (configurable)
_Z_95 = 1.65


def calcular_stock_minimo_optimo(
    db: Session,
    lead_time_dias: int = 3,
    ventana_dias: int = 60,
) -> list[dict]:
    """
    Calcula el stock mínimo óptimo por producto usando pandas.

    Para cada producto:
    - Construye una serie diaria de unidades vendidas (rellenando 0 en días sin venta)
    - Calcula demanda promedio y desviación estándar
    - Aplica la fórmula de punto de reorden con stock de seguridad al 95 %
    """
    desde = datetime.now() - timedelta(days=ventana_dias)

    productos = db.query(Producto).order_by(Producto.nombre).all()
    ventas_rows = db.query(
        Venta.producto_id,
        Venta.cantidad,
        Venta.fecha,
    ).filter(Venta.fecha >= desde).all()

    if ventas_rows:
        df = pd.DataFrame(ventas_rows, columns=["producto_id", "cantidad", "fecha"])
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.normalize()
        rango = pd.date_range(df["fecha"].min(), df["fecha"].max(), freq="D")
    else:
        df = pd.DataFrame(columns=["producto_id", "cantidad", "fecha"])
        rango = pd.date_range(datetime.now(), datetime.now(), freq="D")

    resultado = []
    for p in productos:
        p_df = df[df["producto_id"] == p.id]

        if p_df.empty:
            # Sin historial → no se sugiere cambio
            resultado.append({
                "producto_id":          p.id,
                "nombre":               p.nombre,
                "categoria":            p.categoria or "",
                "stock_actual":         p.stock_actual,
                "stock_minimo_actual":  p.stock_minimo,
                "stock_minimo_sugerido": p.stock_minimo,
                "avg_diario":           0.0,
                "std_diario":           0.0,
                "sin_datos":            True,
                "diferencia":           0,
            })
            continue

        # Serie diaria (días sin ventas → 0)
        daily = (
            p_df.groupby("fecha")["cantidad"]
            .sum()
            .reindex(rango, fill_value=0)
        )

        avg = daily.mean()
        std = daily.std(ddof=1) if len(daily) > 1 else 0.0
        if pd.isna(std):
            std = 0.0

        safety = _Z_95 * std * math.sqrt(lead_time_dias)
        sugerido = math.ceil(avg * lead_time_dias + safety)
        sugerido = max(sugerido, 3)   # mínimo absoluto de 3 unidades

        resultado.append({
            "producto_id":           p.id,
            "nombre":                p.nombre,
            "categoria":             p.categoria or "",
            "stock_actual":          p.stock_actual,
            "stock_minimo_actual":   p.stock_minimo,
            "stock_minimo_sugerido": sugerido,
            "avg_diario":            round(float(avg), 2),
            "std_diario":            round(float(std), 2),
            "sin_datos":             False,
            "diferencia":            sugerido - p.stock_minimo,
        })

    return resultado
