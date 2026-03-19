import math

import pandas as pd
from datetime import date, datetime, timedelta
from typing import Literal, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

 

# ── Helpers internos ────────────────────────────────────────────────────────────

def _dt_inicio(d: date) -> datetime:
    return datetime.combine(d, datetime.min.time())

def _dt_fin(d: date) -> datetime:
    return datetime.combine(d, datetime.max.time())

def _formato_strftime(agrupacion: str) -> str:
    return {"dia": "%Y-%m-%d", "semana": "%Y-%W", "mes": "%Y-%m"}.get(agrupacion, "%Y-%m-%d")


def _rows(db: Session, sql: str, params: dict | None = None) -> list[dict]:
    """Ejecuta SQL y devuelve lista de dicts (mappings)."""
    return [dict(r) for r in db.execute(text(sql), params or {}).mappings().all()]


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
    where = ""
    params: dict = {}
    if desde and hasta:
        where = "WHERE fecha >= :inicio AND fecha <= :fin"
        params = {"inicio": _dt_inicio(desde), "fin": _dt_fin(hasta)}

    rows = _rows(
        db,
        f"""
        SELECT strftime('{fmt}', fecha) AS periodo,
               COALESCE(SUM(precio_total), 0.0) AS ingresos,
               COUNT(1) AS num_ventas,
               COALESCE(SUM(cantidad), 0) AS unidades_vendidas
        FROM ventas
        {where}
        GROUP BY periodo
        ORDER BY periodo
        """,
        params,
    )
    return [
        {
            "periodo": r["periodo"],
            "ingresos": round(float(r["ingresos"]), 2),
            "num_ventas": int(r["num_ventas"]),
            "unidades_vendidas": int(r["unidades_vendidas"]),
        }
        for r in rows
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
    where = ""
    params: dict = {"lim": limite}
    if desde and hasta:
        where = "WHERE fecha >= :inicio AND fecha <= :fin"
        params.update({"inicio": _dt_inicio(desde), "fin": _dt_fin(hasta)})

    rows = _rows(
        db,
        f"""
        SELECT producto_nombre AS producto,
               SUM(cantidad) AS cantidad_total,
               COALESCE(SUM(precio_total), 0.0) AS ingresos_total
        FROM ventas
        {where}
        GROUP BY producto_nombre
        ORDER BY SUM(cantidad) DESC
        LIMIT :lim
        """,
        params,
    )

    total_unidades = sum(int(r["cantidad_total"]) for r in rows) or 1
    return [
        {
            "posicion": i + 1,
            "producto": r["producto"],
            "cantidad_total": int(r["cantidad_total"]),
            "ingresos_total": round(float(r["ingresos_total"]), 2),
            "participacion_pct": round(int(r["cantidad_total"]) / total_unidades * 100, 1),
        }
        for i, r in enumerate(rows)
    ]


# ── 3. Rotación de inventario  (Diagnóstica — ¿Qué tan eficiente soy?) ─────────

def rotacion_inventario(db: Session, ventana_dias: int = 30) -> list[dict]:
    """
    Para cada producto calcula:
    - Promedio de ventas diarias en la ventana
    - Días estimados hasta agotar el stock actual
    Ordenado del más urgente al menos urgente.
    """
    corte = datetime.now() - timedelta(days=ventana_dias)
    rows = _rows(
        db,
        f"""
        SELECT
          p.id AS producto_id,
          p.nombre,
          p.categoria,
          p.stock_actual,
          p.stock_minimo,
          CASE WHEN p.stock_actual < p.stock_minimo THEN 1 ELSE 0 END AS alerta,
          COALESCE(v.cant, 0) AS ventas_periodo
        FROM productos p
        LEFT JOIN (
          SELECT producto_id, SUM(cantidad) AS cant
          FROM ventas
          WHERE fecha >= :corte AND producto_id IS NOT NULL
          GROUP BY producto_id
        ) v ON v.producto_id = p.id
        ORDER BY p.nombre
        """,
        {"corte": corte},
    )

    resultado = []
    for r in rows:
        ventas_periodo = float(r["ventas_periodo"] or 0)
        promedio_diario = round(ventas_periodo / ventana_dias, 3)
        dias_restantes = round(r["stock_actual"] / promedio_diario) if promedio_diario > 0 else None
        resultado.append(
            {
                "producto_id": r["producto_id"],
                "nombre": r["nombre"],
                "categoria": r["categoria"],
                "stock_actual": r["stock_actual"],
                "stock_minimo": r["stock_minimo"],
                "alerta": bool(r["alerta"]),
                f"ventas_ultimos_{ventana_dias}d": int(ventas_periodo),
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
    where = ""
    params: dict = {}
    if desde and hasta:
        where = "WHERE fecha >= :inicio AND fecha <= :fin"
        params = {"inicio": _dt_inicio(desde), "fin": _dt_fin(hasta)}

    filas = _rows(
        db,
        f"""
        SELECT strftime('{fmt}', fecha) AS periodo,
               COALESCE(AVG(precio_total), 0.0) AS ticket_promedio,
               COUNT(1) AS num_ventas,
               COALESCE(SUM(precio_total), 0.0) AS ingresos_total
        FROM ventas
        {where}
        GROUP BY periodo
        ORDER BY periodo
        """,
        params,
    )

    resultado = []
    for i, r in enumerate(filas):
        ticket_anterior = float(filas[i - 1]["ticket_promedio"]) if i > 0 else None
        ticket_actual = float(r["ticket_promedio"])
        if ticket_anterior is not None and ticket_anterior > 0:
            variacion_pct = round((ticket_actual - ticket_anterior) / ticket_anterior * 100, 1)
        else:
            variacion_pct = None

        resultado.append(
            {
                "periodo": r["periodo"],
                "ticket_promedio": round(ticket_actual, 2),
                "num_ventas": int(r["num_ventas"]),
                "ingresos_total": round(float(r["ingresos_total"]), 2),
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
    rows = _rows(
        db,
        """
        SELECT
          p.id AS producto_id,
          p.nombre,
          p.categoria,
          p.precio_venta,
          p.costo,
          SUM(v.cantidad) AS cantidad_vendida,
          COUNT(v.id) AS num_ventas
        FROM productos p
        JOIN ventas v ON v.producto_id = p.id
        WHERE p.costo IS NOT NULL AND p.precio_venta IS NOT NULL
        GROUP BY p.id, p.nombre, p.categoria, p.precio_venta, p.costo
        """,
    )
    if not rows:
        return []

    resultado = []
    for r in rows:
        precio = float(r["precio_venta"])
        costo = float(r["costo"])
        margen_u = precio - costo
        cantidad = int(r["cantidad_vendida"] or 0)
        margen_pct = round(margen_u / precio * 100, 1) if precio > 0 else 0.0
        resultado.append(
            {
                "posicion": 0,
                "producto_id": int(r["producto_id"]),
                "nombre": r["nombre"],
                "categoria": r["categoria"] or "",
                "precio_venta": round(precio, 2),
                "costo": round(costo, 2),
                "margen_unitario": round(margen_u, 2),
                "margen_pct": margen_pct,
                "cantidad_vendida": cantidad,
                "num_ventas": int(r["num_ventas"] or 0),
                "margen_total": round(margen_u * cantidad, 2),
            }
        )

    resultado.sort(key=lambda x: x["margen_total"], reverse=True)
    for i, r in enumerate(resultado[:limite], start=1):
        r["posicion"] = i

    return resultado[:limite]


# ── Ventas por día de semana ──────────────────────────────────────────────────

DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

def ventas_por_dia_semana(db: Session) -> list[dict]:
    """Ventas históricas agrupadas por día de la semana usando pandas."""
    rows = _rows(db, "SELECT fecha, precio_total FROM ventas WHERE fecha IS NOT NULL AND precio_total IS NOT NULL")

    if not rows:
        return [{"dia_num": n, "dia": DIAS_ES[n], "total": 0.0, "num_ventas": 0}
                for n in range(7)]

    df = pd.DataFrame(rows)
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
    rows = _rows(db, "SELECT fecha, precio_total FROM ventas WHERE fecha IS NOT NULL AND precio_total IS NOT NULL")

    if not rows:
        return [{"hora": f"{h:02d}:00", "total": 0.0, "num_ventas": 0}
                for h in range(6, 23)]

    df = pd.DataFrame(rows)
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
    productos = _rows(
        db,
        "SELECT id, nombre, categoria, stock_actual, stock_minimo FROM productos ORDER BY nombre",
    )
    ventas_rows = _rows(
        db,
        """
        SELECT producto_id, cantidad, fecha
        FROM ventas
        WHERE fecha >= :desde AND producto_id IS NOT NULL
        """,
        {"desde": desde},
    )

    if ventas_rows:
        df = pd.DataFrame(ventas_rows, columns=["producto_id", "cantidad", "fecha"])
        df["fecha"] = pd.to_datetime(df["fecha"]).dt.normalize()
        rango = pd.date_range(df["fecha"].min(), df["fecha"].max(), freq="D")
    else:
        df = pd.DataFrame(columns=["producto_id", "cantidad", "fecha"])
        rango = pd.date_range(datetime.now(), datetime.now(), freq="D")

    resultado = []
    for p in productos:
        pid = int(p["id"])
        p_df = df[df["producto_id"] == pid]

        if p_df.empty:
            # Sin historial → no se sugiere cambio
            resultado.append({
                "producto_id":          pid,
                "nombre":               p["nombre"],
                "categoria":            p["categoria"] or "",
                "stock_actual":         p["stock_actual"],
                "stock_minimo_actual":  p["stock_minimo"],
                "stock_minimo_sugerido": p["stock_minimo"],
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
            "producto_id":           pid,
            "nombre":                p["nombre"],
            "categoria":             p["categoria"] or "",
            "stock_actual":          p["stock_actual"],
            "stock_minimo_actual":   p["stock_minimo"],
            "stock_minimo_sugerido": sugerido,
            "avg_diario":            round(float(avg), 2),
            "std_diario":            round(float(std), 2),
            "sin_datos":             False,
            "diferencia":            sugerido - int(p["stock_minimo"]),
        })

    return resultado
