# Perfilamiento de Datos con ydata-profiling

Herramienta en Python para generar reportes automáticos de análisis exploratorio de datos (EDA) en HTML usando [`ydata-profiling`](https://docs.profiling.ydata.ai/).

Soporta archivos **CSV**, **TXT**, **Excel (`.xlsx`, `.xls`)** y **Parquet**, con detección automática de formato, delimitador y codificación, además de muestreo opcional para archivos grandes.

## Requisitos e instalación con `uv`

1. Instala [`uv`](https://docs.astral.sh/uv/getting-started/installation/) si aún no lo tienes.
2. Clona el repositorio e instala las dependencias desde `pyproject.toml`:

```sh
git clone <URL_DEL_REPOSITORIO>
cd perfilamiento_pandas
uv sync
```

## Uso

### Modo interactivo (con selector gráfico de archivos)

Ejecuta el script sin argumentos:

```sh
uv run main.py
```

El asistente te guiará paso a paso:
1. Selecciona el archivo en la ventana emergente (`.csv`, `.txt`, `.xlsx`, `.xls`, `.parquet`).
2. El tipo de archivo se detecta automáticamente por su extensión.
3. Si es `CSV` o `TXT`, puedes indicar el delimitador (`,`, `;`, `|`, `\t`) o presionar **Enter** para autodetectarlo.
4. Si es `Excel`, puedes elegir el nombre/índice de la hoja y si deseas leer todas las columnas como texto.
5. Elige el modo del reporte:
   - `minimal`: rápido y ligero (recomendado para tablas grandes).
   - `estandar`: balance entre detalle y velocidad.
   - `explorativo`: análisis profundo (correlaciones, interacciones y alertas detalladas).
6. Opcionalmente indica un tamaño de muestra en filas, título del reporte y carpeta de salida.

### Modo CLI (automatización sin ventana emergente)

```sh
uv run main.py --file datos.csv --mode minimal --title "Reporte Ventas" --output ./reportes
```

Ejemplos adicionales:

```sh
# Archivo delimitado por tabulaciones con muestreo de 50,000 filas sin abrir el navegador
uv run main.py -f datos.txt -d "\t" --sample 50000 --no-open

# Hoja específica de Excel preservando todas las columnas como texto
uv run main.py -f archivo.xlsx --sheet "Hoja2" --as-str -m explorativo

# Ver todas las opciones disponibles
uv run main.py --help
```

### Ruta de salida predeterminada

Si no indicas carpeta de salida (o la ruta ingresada no existe en modo interactivo), el script busca en este orden:
1. La variable de entorno `PROFILING_OUTPUT_DIR` (si apunta a un directorio existente).
2. La ruta corporativa por defecto (`G:\Mi unidad\Requerimientos_Demanda\Requerimientos`), si existe.
3. La misma carpeta del archivo de entrada.

## Pruebas

Para ejecutar la suite de pruebas unitarias:

```sh
uv run pytest
```

o usando `unittest` directamente:

```sh
uv run python -m unittest discover -s tests -v
```

## Licencia

Este proyecto está licenciado bajo la licencia MIT.
