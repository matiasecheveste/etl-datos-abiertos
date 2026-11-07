"""
ETL de datos abiertos — Matías Nicolás Echeveste Cardozo
Carga idempotente en SQLite con un esquema normalizado y una vista de variaciones.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

ESQUEMA = """
CREATE TABLE IF NOT EXISTS productos (
  id      INTEGER PRIMARY KEY,
  nombre  TEXT NOT NULL UNIQUE,
  unidad  TEXT NOT NULL CHECK (unidad IN ('litro', 'kilo', 'tonelada'))
);
CREATE TABLE IF NOT EXISTS precios (
  producto_id  INTEGER NOT NULL REFERENCES productos(id),
  periodo      TEXT    NOT NULL CHECK (periodo GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]'),
  valor        REAL    NOT NULL CHECK (valor > 0),
  PRIMARY KEY (producto_id, periodo)
);
CREATE VIEW IF NOT EXISTS variaciones AS
SELECT p.nombre AS producto, p.unidad, x.periodo, x.valor,
       ROUND((x.valor / LAG(x.valor) OVER w - 1) * 100, 2) AS variacion_pct
  FROM precios x JOIN productos p ON p.id = x.producto_id
WINDOW w AS (PARTITION BY x.producto_id ORDER BY x.periodo);
"""


def cargar(precios: pd.DataFrame, ruta: Path | str) -> int:
    """Inserta o actualiza los precios; ejecutarla dos veces con los mismos datos no duplica filas."""
    with sqlite3.connect(ruta) as conexion:
        conexion.execute("PRAGMA foreign_keys = ON")
        conexion.executescript(ESQUEMA)
        productos = precios[["producto", "unidad"]].drop_duplicates()
        conexion.executemany(
            "INSERT INTO productos (nombre, unidad) VALUES (?, ?) ON CONFLICT(nombre) DO UPDATE SET unidad = excluded.unidad",
            productos.itertuples(index=False, name=None),
        )
        ids = dict(conexion.execute("SELECT nombre, id FROM productos"))
        filas = [(ids[f.producto], f.periodo, float(f.valor)) for f in precios.itertuples(index=False)]
        conexion.executemany(
            "INSERT INTO precios (producto_id, periodo, valor) VALUES (?, ?, ?) "
            "ON CONFLICT(producto_id, periodo) DO UPDATE SET valor = excluded.valor",
            filas,
        )
        return len(filas)
