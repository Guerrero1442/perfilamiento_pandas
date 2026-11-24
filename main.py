from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import webbrowser
from pathlib import Path

import pandas as pd

SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".csv": "csv",
    ".txt": "txt",
    ".xlsx": "excel",
    ".xls": "excel",
    ".parquet": "parquet",
}

DEFAULT_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "latin1")
DEFAULT_FALLBACK_DIR = Path(r"G:\Mi unidad\Requerimientos_Demanda\Requerimientos")

MODE_ALIASES: dict[str, str] = {
    "1": "minimal",
    "minimal": "minimal",
    "minimo": "minimal",
    "mínimo": "minimal",
    "2": "estandar",
    "estandar": "estandar",
    "estándar": "estandar",
    "standard": "estandar",
    "3": "explorativo",
    "explorativo": "explorativo",
    "explorative": "explorativo",
    "profundo": "explorativo",
}

INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def detect_file_type(file_path: str | Path) -> str | None:
    """Infiere el tipo de archivo a partir de su extensión."""
    return SUPPORTED_EXTENSIONS.get(Path(file_path).suffix.lower())


def normalize_delimiter(raw: str | None) -> str | None:
    """Normaliza el delimitador ingresado por el usuario (incluyendo \\t)."""
    if raw is None:
        return None
    if raw == r"\t":
        return "\t"
    if raw == "\t":
        return "\t"
    cleaned = raw.strip()
    return cleaned if cleaned else None


def detect_delimiter(file_path: Path, encoding: str) -> str | None:
    """Intenta detectar el delimitador de un archivo CSV/TXT leyendo una muestra."""
    try:
        with file_path.open("r", encoding=encoding, errors="strict") as handle:
            sample = handle.read(8192)
    except (OSError, UnicodeDecodeError):
        return None

    if not sample.strip():
        return None

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;|\t")
        return dialect.delimiter
    except csv.Error:
        return None


def _read_delimited_file(
    file_path: Path,
    delimiter: str | None,
    as_str: bool,
) -> pd.DataFrame:
    """Lee archivos CSV/TXT probando encodings y motores de forma segura."""
    dtype_arg = str if as_str else None
    last_error: Exception | None = None

    for encoding in DEFAULT_ENCODINGS:
        resolved_delimiter = delimiter or detect_delimiter(file_path, encoding)

        # Intento rápido con PyArrow cuando hay delimitador de 1 carácter
        if resolved_delimiter is not None and len(resolved_delimiter) == 1 and not as_str:
            try:
                return pd.read_csv(
                    file_path,
                    sep=resolved_delimiter,
                    encoding=encoding,
                    engine="pyarrow",
                )
            except Exception:
                pass

        # Intento estándar con motor C o Python (para autodetección de sep)
        try:
            if resolved_delimiter is None:
                return pd.read_csv(
                    file_path,
                    sep=None,
                    engine="python",
                    encoding=encoding,
                    dtype=dtype_arg,
                )
            return pd.read_csv(
                file_path,
                sep=resolved_delimiter,
                encoding=encoding,
                dtype=dtype_arg,
                low_memory=False,
            )
        except UnicodeDecodeError as exc:
            last_error = exc
            continue
        except Exception as exc:
            last_error = exc
            # Fallback al motor python si el motor C falla por formato irregular
            if resolved_delimiter is not None:
                try:
                    return pd.read_csv(
                        file_path,
                        sep=resolved_delimiter,
                        engine="python",
                        encoding=encoding,
                        dtype=dtype_arg,
                    )
                except Exception as py_exc:
                    last_error = py_exc

    raise ValueError(
        f"No se pudo leer el archivo '{file_path.name}'. Último error: {last_error}"
    ) from last_error


def load_data(
    file: str | Path,
    file_type: str | None = None,
    delimiter: str | None = None,
    sheet_name: str | int = 0,
    as_str: bool = False,
    sample_size: int | None = None,
    random_state: int = 42,
) -> pd.DataFrame:
    """Carga un archivo CSV, TXT, Excel o Parquet en un DataFrame de pandas."""
    file_path = Path(file)
    if not file_path.is_file():
        raise FileNotFoundError(f"El archivo no existe: {file_path}")

    resolved_type = (file_type or detect_file_type(file_path) or "").strip().lower()

    if resolved_type in {"csv", "txt"}:
        df = _read_delimited_file(
            file_path=file_path,
            delimiter=normalize_delimiter(delimiter),
            as_str=as_str,
        )
    elif resolved_type in {"excel", "xlsx", "xls"}:
        df = pd.read_excel(
            file_path,
            sheet_name=sheet_name,
            dtype=str if as_str else None,
        )
    elif resolved_type == "parquet":
        df = pd.read_parquet(file_path)
    else:
        raise ValueError(
            f"Tipo de archivo no soportado: '{resolved_type or file_path.suffix}'. "
            "Usa csv, txt, excel o parquet."
        )

    if sample_size is not None and sample_size > 0 and len(df) > sample_size:
        df = df.sample(n=sample_size, random_state=random_state)

    return df


def sanitize_filename(name: str, fallback: str = "reporte_perfilamiento") -> str:
    """Limpia un título para usarlo de forma segura como nombre de archivo."""
    sanitized = INVALID_FILENAME_CHARS.sub("_", name.strip())
    sanitized = re.sub(r"\s+", " ", sanitized).strip(" .")
    return sanitized or fallback


def resolve_output_dir(
    requested: str | Path | None,
    input_file: Path,
    create_if_missing: bool = False,
) -> Path:
    """Resuelve la carpeta de salida con respaldos válidos si la ruta no existe."""
    if requested:
        candidate = Path(requested).expanduser()
        if candidate.is_dir():
            return candidate
        if create_if_missing:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        print(f"La ruta '{candidate}' no existe; se usará una ubicación de respaldo.")

    env_dir = os.environ.get("PROFILING_OUTPUT_DIR")
    if env_dir:
        env_path = Path(env_dir).expanduser()
        if env_path.is_dir():
            return env_path

    if DEFAULT_FALLBACK_DIR.is_dir():
        return DEFAULT_FALLBACK_DIR

    return input_file.parent


def normalize_mode(raw_mode: str | None) -> str:
    """Normaliza el modo de reporte a minimal, estandar o explorativo."""
    if not raw_mode:
        return "estandar"
    key = raw_mode.strip().lower()
    if key not in MODE_ALIASES:
        raise ValueError(
            f"Modo de reporte no válido: '{raw_mode}'. "
            "Opciones válidas: minimal, estandar, explorativo."
        )
    return MODE_ALIASES[key]


def generate_report(
    data: pd.DataFrame,
    title: str,
    output_dir: str | Path,
    mode: str = "estandar",
) -> Path:
    """Genera el reporte HTML con ydata-profiling y devuelve su ruta."""
    from ydata_profiling import ProfileReport

    resolved_mode = normalize_mode(mode)
    minimal = resolved_mode == "minimal"
    explorative = resolved_mode == "explorativo"

    output_folder = Path(output_dir)
    output_folder.mkdir(parents=True, exist_ok=True)

    filename = f"{sanitize_filename(title)}.html"
    output_path = output_folder / filename

    profile = ProfileReport(
        data,
        title=title,
        minimal=minimal,
        explorative=explorative,
    )
    profile.to_file(output_path)
    return output_path


def _ask_yes_no(prompt: str, default: bool = False) -> bool:
    """Solicita una respuesta sí/no tolerante a mayúsculas y tildes."""
    suffix = " [S/n]: " if default else " [s/N]: "
    answer = input(f"{prompt}{suffix}").strip().lower()
    if not answer:
        return default
    return answer in {"s", "si", "sí", "y", "yes"}


def select_file_dialog() -> Path | None:
    """Abre el selector gráfico de archivos sin dejar una ventana vacía de Tkinter."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    try:
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askopenfilename(
            title="Selecciona el archivo de datos",
            filetypes=[
                ("Archivos soportados", "*.csv *.txt *.xlsx *.xls *.parquet"),
                ("CSV / TXT", "*.csv *.txt"),
                ("Excel", "*.xlsx *.xls"),
                ("Parquet", "*.parquet"),
                ("Todos los archivos", "*.*"),
            ],
        )
    finally:
        root.destroy()

    return Path(selected) if selected else None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Define los argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="Genera reportes de perfilamiento exploratorio con ydata-profiling.",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        help="Ruta al archivo de datos (csv, txt, xlsx, xls, parquet).",
    )
    parser.add_argument(
        "-t",
        "--type",
        dest="file_type",
        choices=("csv", "txt", "excel", "parquet"),
        help="Tipo de archivo (si se omite, se detecta por extensión).",
    )
    parser.add_argument(
        "-d",
        "--delimiter",
        help=r"Delimitador para CSV/TXT (ej. ',', ';', '|', '\t'). Si se omite, se autodetecta.",
    )
    parser.add_argument(
        "--sheet",
        default=0,
        help="Nombre o índice de hoja para archivos Excel (por defecto: primera hoja).",
    )
    parser.add_argument(
        "--as-str",
        action="store_true",
        help="Lee todas las columnas como texto (útil para preservar ceros a la izquierda).",
    )
    parser.add_argument(
        "-m",
        "--mode",
        choices=("minimal", "estandar", "explorativo"),
        help="Nivel de detalle del reporte: minimal, estandar o explorativo.",
    )
    parser.add_argument(
        "--title",
        help="Título del reporte (por defecto: nombre del archivo).",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Carpeta donde guardar el reporte HTML.",
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Número máximo de filas a muestrear para acelerar archivos muy grandes.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="No abrir automáticamente el reporte en el navegador.",
    )
    return parser.parse_args(argv)


def _prompt_interactive(args: argparse.Namespace) -> argparse.Namespace:
    """Completa parámetros faltantes mediante consola cuando no se pasa --file."""
    file_path = select_file_dialog()
    if file_path is None:
        raise SystemExit("Operación cancelada: no se seleccionó ningún archivo.")
    args.file = file_path

    detected_type = detect_file_type(file_path)
    if args.file_type is None:
        if detected_type:
            print(f"Tipo detectado automáticamente: {detected_type}")
            args.file_type = detected_type
        else:
            args.file_type = input(
                "Ingresa el tipo de archivo (csv, txt, excel, parquet): "
            ).strip().lower()

    if args.file_type in {"csv", "txt"} and args.delimiter is None:
        raw_delim = input(
            r"Ingresa el delimitador (Enter para autodetectar, ej. ',', ';', '|', '\t'): "
        )
        args.delimiter = normalize_delimiter(raw_delim)

    if args.file_type == "excel" and args.sheet == 0:
        raw_sheet = input("Nombre de la hoja de Excel (Enter para la primera): ").strip()
        if raw_sheet:
            args.sheet = int(raw_sheet) if raw_sheet.isdigit() else raw_sheet
        if not args.as_str:
            args.as_str = _ask_yes_no("¿Leer todas las columnas como texto?", default=False)

    if args.mode is None:
        raw_mode = input(
            "Modo de reporte [1=minimal, 2=estandar, 3=explorativo] (Enter=estandar): "
        ).strip()
        args.mode = normalize_mode(raw_mode)

    if args.sample is None:
        raw_sample = input(
            "Tamaño de muestra en filas (Enter para analizar todo el archivo): "
        ).strip()
        if raw_sample:
            args.sample = int(raw_sample)

    if not args.title:
        default_title = file_path.stem
        raw_title = input(f"Título del reporte (Enter='{default_title}'): ").strip()
        args.title = raw_title or default_title

    if args.output is None:
        raw_output = input(
            "Ruta de carpeta de salida (Enter para ubicación predeterminada): "
        ).strip()
        if raw_output:
            args.output = Path(raw_output)

    return args


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal de la aplicación."""
    args = parse_args(argv)
    interactive = args.file is None

    if interactive:
        args = _prompt_interactive(args)

    file_path = Path(args.file)
    title = args.title or file_path.stem
    mode = normalize_mode(args.mode)
    sheet_name: str | int = args.sheet
    if isinstance(sheet_name, str) and sheet_name.isdigit():
        sheet_name = int(sheet_name)

    output_dir = resolve_output_dir(
        requested=args.output,
        input_file=file_path,
        create_if_missing=not interactive,
    )

    print(f"Cargando '{file_path.name}'...")
    data = load_data(
        file=file_path,
        file_type=args.file_type,
        delimiter=args.delimiter,
        sheet_name=sheet_name,
        as_str=args.as_str,
        sample_size=args.sample,
    )
    print(f"Datos cargados: {len(data):,} filas x {len(data.columns)} columnas.")

    print(f"Generando reporte ({mode}) en '{output_dir}'...")
    report_path = generate_report(
        data=data,
        title=title,
        output_dir=output_dir,
        mode=mode,
    )
    print(f"Reporte guardado en: {report_path.resolve()}")

    if not args.no_open:
        webbrowser.open(report_path.resolve().as_uri())

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
