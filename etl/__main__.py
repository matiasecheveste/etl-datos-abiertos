"""
ETL de datos abiertos — Matías Nicolás Echeveste Cardozo
Línea de comandos: extrae (archivo local o URL oficial), transforma, carga en SQLite y genera un informe.

Uso:
    python -m etl --entrada datos/muestra-precios-combustibles.csv --base precios.db --informe informe.md
    python -m etl --descargar --base precios.db
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

from .cargar import cargar
from .informe import informe, periodos_contradictorios
from .transformar import leer, transformar, variaciones

URL_OFICIAL = (
    "https://catalogodatos.gub.uy/dataset/556beb30-02fc-4d06-909a-f42083c89ef7/resource/"
    "c486544e-0fca-4f6f-8403-3ee379a868f4/download/datos-de-precios-de-combustibles.csv"
)


def extraer(entrada: Path | None, descargar: bool) -> bytes:
    if descargar:
        with urllib.request.urlopen(URL_OFICIAL, timeout=60) as respuesta:  # noqa: S310 (URL fija y https)
            return respuesta.read()
    if entrada is None:
        raise SystemExit("Indique --entrada o --descargar")
    return entrada.read_bytes()


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="etl", description="ETL de precios de combustibles (datos abiertos de Uruguay)")
    parser.add_argument("--entrada", type=Path, help="CSV local con el formato publicado")
    parser.add_argument("--descargar", action="store_true", help="descarga la versión vigente del catálogo")
    parser.add_argument("--base", type=Path, default=Path("precios.db"), help="archivo SQLite de destino")
    parser.add_argument("--informe", type=Path, help="ruta del informe en Markdown")
    args = parser.parse_args(argumentos)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    resultado = transformar(leer(extraer(args.entrada, args.descargar)))
    cargadas = cargar(resultado.precios, args.base)
    print(
        f"Leídas {resultado.filas_leidas} filas · sin cotización {resultado.sin_cotizacion} · "
        f"duplicadas {resultado.duplicadas} · períodos contradictorios {periodos_contradictorios(resultado)} · "
        f"apartados {len(resultado.atipicos)} · cargadas {cargadas}"
    )
    if args.informe:
        args.informe.write_text(informe(resultado, variaciones(resultado.precios)), encoding="utf-8")
        print(f"Informe: {args.informe}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
