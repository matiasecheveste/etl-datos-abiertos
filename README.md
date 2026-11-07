# ETL de precios de combustibles (datos abiertos de Uruguay)

Proceso de extracción, transformación y carga sobre el conjunto **«Precios de Combustibles - Poder Ejecutivo»**
que ANCAP publica en el [Catálogo de Datos Abiertos](https://catalogodatos.gub.uy/dataset/ancap-precio-combustible-pe):
precios máximos mensuales, con IVA, aprobados por decreto.

**Tecnologías:** Python 3.11+, pandas, SQLite (vistas con funciones de ventana), pytest, Ruff y GitHub Actions.

## Qué demuestra

El archivo publicado tiene problemas reales de calidad, y cada uno tiene una regla y una prueba:

| Problema en el origen | Tratamiento |
|---|---|
| Dos marcas BOM al inicio del archivo | Se eliminan antes de leer |
| Columnas «Unidad» y «Valor» invertidas | Se detecta cuál contiene el número |
| Decimales con coma y la marca `S/C` (sin cotización) | Conversión numérica; `S/C` se descarta y se cuenta |
| Nombres con asteriscos y espacios sobrantes | Normalización (`GASOIL 50-S *` → `GASOIL 50-S`) |
| Hasta 30 filas repetidas por producto y mes, a veces con valores distintos | Se toma el valor más frecuente y se informan los conflictos (p. ej. Super 95 en agosto de 2023: 71,39 frente a 142,55) |
| Valores con la unidad equivocada (un precio por kilo publicado como $/ton) | Se apartan los que se alejan más de 5 veces de la mediana del producto |

Además:

- **Carga idempotente** en SQLite (`INSERT … ON CONFLICT DO UPDATE`), con un esquema normalizado y restricciones
  `CHECK`.
- **Vista `variaciones`** con `LAG() OVER (PARTITION BY … ORDER BY …)` para la variación mensual.
- **Informe en Markdown** con la calidad del origen, un resumen por producto y las mayores variaciones.
- **CI programada:** además de las pruebas, el día 1 de cada mes descarga la versión vigente, la procesa y
  publica el informe y la base como artefactos.

Resultado sobre el archivo completo (versión del 12/10/2026): 26 618 filas leídas, 16 298 sin cotización,
9 761 duplicadas, 106 períodos con valores contradictorios, 1 valor apartado y 558 precios cargados.

## Uso

```bash
python -m venv .venv && . .venv/bin/activate   # en Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest

# con la muestra incluida (extracto real 2023–2024 de cinco productos)
python -m etl --entrada datos/muestra-precios-combustibles.csv --base precios.db --informe informe.md

# con la versión vigente del catálogo
python -m etl --descargar --base precios.db --informe informe.md
sqlite3 precios.db "SELECT * FROM variaciones WHERE producto = 'SUPER 95 30-S' ORDER BY periodo DESC LIMIT 6"
```

## Estructura

```
etl/transformar.py   Lectura y reglas de limpieza
etl/cargar.py        Esquema SQLite, carga idempotente y vista de variaciones
etl/informe.py       Informe en Markdown
etl/__main__.py      Línea de comandos
datos/               Extracto real del conjunto publicado, usado en las pruebas
```

## Datos

Fuente: ANCAP, Catálogo de Datos Abiertos del Uruguay, bajo la Licencia de Datos Abiertos de Uruguay (AGESIC).

## Autoría

Desarrollado por **Matías Nicolás Echeveste Cardozo**. Código bajo licencia MIT.
