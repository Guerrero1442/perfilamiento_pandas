import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import main as app


class TestPerfilamientoMain(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_pyproject_toml_is_valid(self) -> None:
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        with pyproject_path.open("rb") as fh:
            data = tomllib.load(fh)
        self.assertEqual(data["project"]["name"], "perfilamiento-pandas")
        deps = data["project"]["dependencies"]
        self.assertTrue(any(d.startswith("pandas") for d in deps))
        self.assertTrue(any(d.startswith("ydata-profiling") for d in deps))

    def test_detect_file_type(self) -> None:
        self.assertEqual(app.detect_file_type("datos.CSV"), "csv")
        self.assertEqual(app.detect_file_type("datos.txt"), "txt")
        self.assertEqual(app.detect_file_type("datos.xlsx"), "excel")
        self.assertEqual(app.detect_file_type("datos.parquet"), "parquet")
        self.assertIsNone(app.detect_file_type("datos.json"))

    def test_normalize_delimiter(self) -> None:
        self.assertEqual(app.normalize_delimiter(r"\t"), "\t")
        self.assertEqual(app.normalize_delimiter(";"), ";")
        self.assertIsNone(app.normalize_delimiter("   "))
        self.assertIsNone(app.normalize_delimiter(None))

    def test_load_csv_latin1_and_autodetect_delimiter(self) -> None:
        csv_path = self.base_dir / "muestra.txt"
        csv_path.write_bytes("nombre;ciudad;valor\nJosé;Bogotá;100\nMaría;Medellín;250\n".encode("latin1"))

        df = app.load_data(csv_path)
        self.assertEqual(list(df.columns), ["nombre", "ciudad", "valor"])
        self.assertEqual(len(df), 2)
        self.assertEqual(df.loc[0, "nombre"], "José")
        self.assertEqual(int(df.loc[1, "valor"]), 250)

    def test_load_excel_and_parquet_with_sampling(self) -> None:
        source = pd.DataFrame({"id": ["001", "002", "003", "004"], "monto": [10, 20, 30, 40]})

        xlsx_path = self.base_dir / "datos.xlsx"
        source.to_excel(xlsx_path, index=False, sheet_name="Ventas")
        df_excel = app.load_data(xlsx_path, sheet_name="Ventas", as_str=True)
        self.assertEqual(df_excel.loc[0, "id"], "001")

        pq_path = self.base_dir / "datos.parquet"
        source.to_parquet(pq_path, index=False)
        df_sampled = app.load_data(pq_path, sample_size=2, random_state=7)
        self.assertEqual(len(df_sampled), 2)

    def test_sanitize_filename(self) -> None:
        self.assertEqual(app.sanitize_filename('Reporte: Ventas/2026*?. '), "Reporte_ Ventas_2026__")
        self.assertEqual(app.sanitize_filename("   "), "reporte_perfilamiento")

    def test_resolve_output_dir_fallback_to_input_parent(self) -> None:
        fake_input = self.base_dir / "input.csv"
        fake_input.write_text("a,b\n1,2\n", encoding="utf-8")
        missing_dir = self.base_dir / "no_existe"

        with patch.object(app, "DEFAULT_FALLBACK_DIR", self.base_dir / "tampoco_existe"):
            resolved = app.resolve_output_dir(missing_dir, fake_input, create_if_missing=False)
        self.assertEqual(resolved, self.base_dir)

        created = app.resolve_output_dir(missing_dir, fake_input, create_if_missing=True)
        self.assertEqual(created, missing_dir)
        self.assertTrue(missing_dir.is_dir())

    def test_normalize_mode(self) -> None:
        self.assertEqual(app.normalize_mode("1"), "minimal")
        self.assertEqual(app.normalize_mode("Estándar"), "estandar")
        self.assertEqual(app.normalize_mode("EXPLORATIVO"), "explorativo")
        self.assertEqual(app.normalize_mode(""), "estandar")
        with self.assertRaises(ValueError):
            app.normalize_mode("desconocido")

    def test_generate_report_cli_end_to_end(self) -> None:
        csv_path = self.base_dir / "mini.csv"
        csv_path.write_text("a,b\n1,x\n2,y\n3,z\n", encoding="utf-8")
        out_dir = self.base_dir / "out"

        exit_code = app.main(
            [
                "--file",
                str(csv_path),
                "--mode",
                "minimal",
                "--title",
                "Prueba: Mini",
                "--output",
                str(out_dir),
                "--no-open",
            ]
        )
        self.assertEqual(exit_code, 0)
        expected_html = out_dir / "Prueba_ Mini.html"
        self.assertTrue(expected_html.is_file())
        self.assertGreater(expected_html.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
