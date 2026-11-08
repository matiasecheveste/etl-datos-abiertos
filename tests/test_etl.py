"""
ETL de datos abiertos — Matías Nicolás Echeveste Cardozo
Pruebas de extracción, limpieza, carga idempotente e informe.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from etl.__main__ import main
from etl.cargar import cargar
from etl.transformar import leer, normalizar_producto, transformar, variaciones

MUESTRA = Path(__file__).parent.parent / "datos" / "muestra-precios-combustibles.csv"

CRUDO = (
    "\ufeff\ufeffAño;Mes;Producto;Unidad;Valor\r\n"
    "2024;1;SUPER 95 30-S;S/C;S/C\r\n"
    "2024;2;SUPER 95 30-S;76,54;$/lt\r\n"
    "2024;2;SUPER 95 30-S;76,54;$/lt\r\n"
    "2024;2;SUPER 95 30-S;153,08;$/lt\r\n"
    "2024;3;SUPER 95 30-S;$/lt;78,04\r\n"
    "2024;3;SUPERGAS *;59,16;$/kg\r\n"
    ";;;;\r\n"
).encode()


@pytest.fixture
def resultado():
    return transformar(leer(CRUDO))


def test_lee_con_bom_repetido_y_descarta_lineas_vacias():
    tabla = leer(CRUDO)
    assert list(tabla.columns) == ["anio", "mes", "producto", "unidad", "valor"]
    assert len(tabla) == 6


def test_normaliza_nombres():
    assert normalizar_producto(" GASOIL 50-S * ") == "GASOIL 50-S"


def test_corrige_columnas_invertidas_y_decimales(resultado):
    p = resultado.precios.set_index(["producto", "periodo"])["valor"]
    assert p[("SUPER 95 30-S", "2024-03")] == 78.04
    assert p[("SUPERGAS", "2024-03")] == 59.16
    assert set(resultado.precios["unidad"]) == {"litro", "kilo"}


def test_resuelve_duplicados_por_valor_mas_frecuente(resultado):
    p = resultado.precios.set_index(["producto", "periodo"])["valor"]
    assert p[("SUPER 95 30-S", "2024-02")] == 76.54
    assert resultado.sin_cotizacion == 1
    assert resultado.duplicadas == 2
    assert list(resultado.conflictos["valor"]) == [76.54, 153.08]


def test_aparta_valores_con_unidad_equivocada():
    filas = [f"2025;{m};PROPANO *;{v};$/ton" for m, v in [(1, "90500"), (2, "91000"), (3, "84,6"), (4, "92000")]]
    crudo = "\n".join(["Año;Mes;Producto;Unidad;Valor", *filas])
    r = transformar(leer(crudo.encode()))
    assert r.atipicos["valor"].tolist() == [84.6]
    assert r.precios["periodo"].tolist() == ["2025-01", "2025-02", "2025-04"]


def test_variaciones(resultado):
    v = variaciones(resultado.precios)
    fila = v[(v["producto"] == "SUPER 95 30-S") & (v["periodo"] == "2024-03")]
    assert fila["variacion_pct"].item() == pytest.approx(1.96)


def test_carga_idempotente_y_vista_sql(tmp_path, resultado):
    base = tmp_path / "p.db"
    assert cargar(resultado.precios, base) == 3
    cargar(resultado.precios, base)
    with sqlite3.connect(base) as c:
        assert c.execute("SELECT COUNT(*) FROM precios").fetchone() == (3,)
        filas = c.execute("SELECT periodo, variacion_pct FROM variaciones WHERE producto = 'SUPER 95 30-S'").fetchall()
    assert filas == [("2024-02", None), ("2024-03", 1.96)]


def test_muestra_real_detecta_el_valor_atipico_de_agosto_2023():
    r = transformar(leer(MUESTRA.read_bytes()))
    p = r.precios.set_index(["producto", "periodo"])["valor"]
    assert p[("SUPER 95 30-S", "2023-08")] == 71.39
    assert 142.55 in r.conflictos["valor"].tolist()
    assert r.precios["valor"].gt(0).all()
    assert not r.precios.duplicated(["producto", "periodo"]).any()


def test_linea_de_comandos(tmp_path, capsys):
    informe = tmp_path / "informe.md"
    assert main(["--entrada", str(MUESTRA), "--base", str(tmp_path / "p.db"), "--informe", str(informe)]) == 0
    assert "cargadas" in capsys.readouterr().out
    texto = informe.read_text(encoding="utf-8")
    assert "## Resumen por producto" in texto and "SUPER 95 30-S" in texto
    assert "| Mínimo ($) |" in texto and "| 78,54 |" in texto  # encabezados legibles y coma decimal
    assert isinstance(pd.read_sql("SELECT * FROM variaciones", sqlite3.connect(tmp_path / "p.db")), pd.DataFrame)
