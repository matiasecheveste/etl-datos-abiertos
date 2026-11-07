"""
ETL de datos abiertos — Matías Nicolás Echeveste Cardozo
Informe en Markdown con la calidad del archivo de origen y la evolución de precios por producto.
"""

from __future__ import annotations

import pandas as pd

from .transformar import Resultado


def _tabla(df: pd.DataFrame) -> str:
    encabezado = "| " + " | ".join(df.columns) + " |"
    separador = "|" + "---|" * len(df.columns)
    filas = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in fila) + " |" for fila in df.itertuples(index=False)]
    return "\n".join([encabezado, separador, *filas])


def informe(resultado: Resultado, con_variacion: pd.DataFrame) -> str:
    resumen = (
        con_variacion.groupby(["producto", "unidad"])
        .agg(desde=("periodo", "min"), hasta=("periodo", "max"), meses=("periodo", "count"),
             minimo=("valor", "min"), maximo=("valor", "max"), ultimo=("valor", "last"))
        .reset_index()
    )
    contradictorios = resultado.conflictos.groupby(["periodo", "producto"]).ngroups if len(resultado.conflictos) else 0
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
        *(
            ["## Valores apartados por implausibles", "", _tabla(resultado.atipicos), ""]
            if len(resultado.atipicos)
            else []
        ),
        "## Mayores variaciones mensuales",
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
