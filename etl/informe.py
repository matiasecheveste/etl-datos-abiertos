"""
ETL de datos abiertos — Matías Nicolás Echeveste Cardozo
Informe en Markdown con la calidad del archivo de origen y la evolución de precios por producto.
"""

from __future__ import annotations

import pandas as pd

from .transformar import Resultado

TITULOS = {
    "producto": "Producto",
    "unidad": "Unidad",
    "desde": "Desde",
    "hasta": "Hasta",
    "meses": "Meses",
    "minimo": "Mínimo ($)",
    "maximo": "Máximo ($)",
    "ultimo": "Último ($)",
    "periodo": "Período",
    "valor": "Valor ($)",
    "variacion_pct": "Variación (%)",
    "mediana": "Mediana ($)",
}


def _celda(v: object) -> str:
    """Formato del Uruguay: coma decimal y dos decimales para importes y porcentajes."""
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    if isinstance(v, float):
        return f"{v:.2f}".replace(".", ",")
    return str(v)


def _tabla(df: pd.DataFrame) -> str:
    encabezado = "| " + " | ".join(TITULOS.get(c, c) for c in df.columns) + " |"
    separador = "|" + "---|" * len(df.columns)
    filas = ["| " + " | ".join(_celda(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return "\n".join([encabezado, separador, *filas])


def periodos_contradictorios(resultado: Resultado) -> int:
    """Cantidad de pares producto-período con más de un valor distinto en el origen."""
    return resultado.conflictos.groupby(["periodo", "producto"]).ngroups if len(resultado.conflictos) else 0


def informe(resultado: Resultado, con_variacion: pd.DataFrame) -> str:
    resumen = (
        con_variacion.groupby(["producto", "unidad"])
        .agg(
            desde=("periodo", "min"),
            hasta=("periodo", "max"),
            meses=("periodo", "count"),
            minimo=("valor", "min"),
            maximo=("valor", "max"),
            ultimo=("valor", "last"),
        )
        .reset_index()
    )
    contradictorios = periodos_contradictorios(resultado)
    partes = [
        "# Precios máximos de combustibles",
        "",
        "Fuente: ANCAP, «Precios de Combustibles - Poder Ejecutivo», Catálogo de Datos Abiertos de Uruguay.",
        "",
        "## Calidad del archivo de origen",
        "",
        f"- Filas leídas: {resultado.filas_leidas}",
        f"- Sin cotización (S/C): {resultado.sin_cotizacion}",
        f"- Duplicadas descartadas: {resultado.duplicadas}",
        f"- Períodos con valores contradictorios: {contradictorios}",
        f"- Valores fuera de rango apartados: {len(resultado.atipicos)}",
        "",
        "## Resumen por producto",
        "",
        _tabla(resumen),
        "",
        *(["## Valores apartados por implausibles", "", _tabla(resultado.atipicos), ""] if len(resultado.atipicos) else []),
        "## Mayores variaciones mensuales",
        "",
        "Variación respecto del período anterior publicado para el mismo producto.",
        "",
        _tabla(
            con_variacion.dropna(subset=["variacion_pct"])
            .reindex(con_variacion["variacion_pct"].abs().sort_values(ascending=False).index)
            .dropna(subset=["variacion_pct"])
            .head(10)[["producto", "periodo", "valor", "variacion_pct"]]
        ),
        "",
    ]
    return "\n".join(partes)
