"""
ETL de datos abiertos — Matías Nicolás Echeveste Cardozo
Limpieza del conjunto «Precios de Combustibles - Poder Ejecutivo» (ANCAP, Catálogo de Datos Abiertos).

Problemas reales del archivo publicado que resuelve esta etapa:
- marcas de orden de bytes (BOM) repetidas al inicio;
- columnas «Unidad» y «Valor» invertidas (el número aparece en «Unidad»);
- decimales con coma y la marca «S/C» (sin cotización);
- nombres de producto con asteriscos y espacios sobrantes;
- filas duplicadas por mes, a veces con valores distintos (se toma el valor más frecuente);
- valores con la unidad equivocada (p. ej. un precio por kilo publicado como $/ton), que se apartan y se informan.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pandas as pd

COLUMNAS = ["anio", "mes", "producto", "unidad", "valor"]
UNIDADES = {"$/lt": "litro", "$/kg": "kilo", "$/ton": "tonelada"}
_NUMERO = re.compile(r"^\d+(?:[.,]\d+)?$")
RANGO_PLAUSIBLE = (0.2, 5.0)  # proporción admitida respecto de la mediana del producto


@dataclass(frozen=True)
class Resultado:
    precios: pd.DataFrame
    filas_leidas: int
    sin_cotizacion: int
    duplicadas: int
    conflictos: pd.DataFrame
    atipicos: pd.DataFrame


def leer(contenido: bytes) -> pd.DataFrame:
    """Lee el CSV crudo tolerando BOM repetidos, separador «;» y líneas vacías."""
    texto = contenido.decode("utf-8").lstrip("\ufeff")
    tabla = pd.read_csv(io.StringIO(texto), sep=";", dtype=str, skip_blank_lines=True, keep_default_na=False)
    tabla.columns = COLUMNAS
    return tabla[tabla["anio"].str.strip() != ""]


def normalizar_producto(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre.replace("*", "")).strip().upper()


def _corregir_columnas(fila: pd.Series) -> tuple[str, str]:
    """Devuelve (valor, unidad) aunque el origen tenga las columnas invertidas."""
    unidad, valor = fila["unidad"].strip(), fila["valor"].strip()
    if _NUMERO.match(unidad) and valor in UNIDADES:
        return unidad, valor
    return valor, unidad


def transformar(crudo: pd.DataFrame) -> Resultado:
    tabla = crudo.copy()
    corregidas = tabla.apply(_corregir_columnas, axis=1, result_type="expand")
    tabla["valor"], tabla["unidad"] = corregidas[0], corregidas[1]

    sin_cotizacion = int((tabla["valor"] == "S/C").sum())
    tabla = tabla[tabla["valor"].str.match(_NUMERO.pattern)].copy()

    tabla["producto"] = tabla["producto"].map(normalizar_producto)
    tabla["valor"] = tabla["valor"].str.replace(",", ".", regex=False).astype(float)
    tabla["unidad"] = tabla["unidad"].map(UNIDADES)
    tabla["periodo"] = pd.to_datetime(
        {"year": tabla["anio"].astype(int), "month": tabla["mes"].astype(int), "day": 1}
    ).dt.strftime("%Y-%m")

    claves = ["periodo", "producto", "unidad"]
    conteo = tabla.groupby([*claves, "valor"]).size().rename("veces").reset_index()
    variantes = conteo.groupby(claves)["valor"].transform("nunique")
    conflictos = conteo[variantes > 1].sort_values([*claves, "veces"], ascending=[True, True, True, False])

    elegidos = (
        conteo.sort_values([*claves, "veces", "valor"], ascending=[True, True, True, False, True])
        .drop_duplicates(claves)
        .drop(columns="veces")
        .sort_values(["producto", "periodo"])
    )
    proporcion = elegidos["valor"] / elegidos.groupby("producto")["valor"].transform("median")
    plausible = proporcion.between(*RANGO_PLAUSIBLE)
    precios = elegidos[plausible].reset_index(drop=True)
    return Resultado(
        precios=precios,
        filas_leidas=len(crudo),
        sin_cotizacion=sin_cotizacion,
        duplicadas=len(tabla) - len(elegidos),
        conflictos=conflictos.reset_index(drop=True),
        atipicos=elegidos[~plausible].reset_index(drop=True),
    )


def variaciones(precios: pd.DataFrame) -> pd.DataFrame:
    """Agrega la variación porcentual respecto al período anterior con dato, por producto."""
    tabla = precios.sort_values(["producto", "periodo"]).copy()
    anterior = tabla.groupby("producto")["valor"].shift()
    tabla["variacion_pct"] = ((tabla["valor"] / anterior - 1) * 100).round(2)
    return tabla
