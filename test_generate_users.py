import csv
import io
import runpy
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch


class GenerateUsersTest(unittest.TestCase):
    def run_script(self, directory, path="users.csv", locale="en", count="1"):
        script = Path(__file__).with_name("generate_users.py")
        return subprocess.run(
            [sys.executable, "-B", str(script)],
            input=f"{path}\n{locale}\n{count}\n",
            text=True, capture_output=True, cwd=directory, timeout=30,
        )

    def assert_input_error(self, result, field):
        self.assertEqual(result.returncode, 1)
        self.assertIn(field, result.stderr.lower())
        self.assertNotIn("Traceback", result.stderr)

    def test_invalid_count_preserves_output(self):
        for count in ("abc", "3.5", "-1"):
            for existing in (False, True):
                with self.subTest(count=count, existing=existing), tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / "users.csv"
                    if existing:
                        output.write_bytes(b"sentinel;keep\n")
                    result = self.run_script(directory, count=count)
                    self.assert_input_error(result, "count")
                    if existing:
                        self.assertEqual(output.read_bytes(), b"sentinel;keep\n")
                    else:
                        self.assertFalse(output.exists())

    def test_invalid_locale_preserves_output_including_zero_count(self):
        for count in ("1", "0"):
            for existing in (False, True):
                with self.subTest(count=count, existing=existing), tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / "users.csv"
                    if existing:
                        output.write_bytes(b"sentinel;keep\n")
                    result = self.run_script(directory, locale="not-a-locale", count=count)
                    self.assert_input_error(result, "locale")
                    if existing:
                        self.assertEqual(output.read_bytes(), b"sentinel;keep\n")
                    else:
                        self.assertFalse(output.exists())

    def test_invalid_paths_including_zero_count(self):
        for count in ("1", "0"):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                parent_file = Path(directory) / "parent-file"
                parent_file.write_bytes(b"keep")
                for path in ("missing/users.csv", ".", "   ", "parent-file/users.csv", "bad\x00.csv"):
                    with self.subTest(path=path):
                        result = self.run_script(directory, path=path, count=count)
                        self.assert_input_error(result, "path")
                        self.assertEqual(set(Path(directory).iterdir()), {parent_file})
                        self.assertEqual(parent_file.read_bytes(), b"keep")

    def test_zero_count_does_not_open_output_or_generate(self):
        script = Path(__file__).with_name("generate_users.py")
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "users.csv"
                if existing:
                    output.write_bytes(b"sentinel;keep\n")
                stdout = io.StringIO()
                with patch("builtins.input", side_effect=[str(output), "en", "0"]), \
                        patch("builtins.open", side_effect=AssertionError("Output must not be opened")), \
                        patch("mimesis.Generic", side_effect=AssertionError("Generation must not start")), \
                        redirect_stdout(stdout):
                    try:
                        runpy.run_path(str(script), run_name="__main__")
                    except SystemExit as error:
                        self.assertEqual(error.code, 0)
                self.assertIn("0", stdout.getvalue())
                self.assertIn("unchanged", stdout.getvalue().lower())
                if existing:
                    self.assertEqual(output.read_bytes(), b"sentinel;keep\n")
                else:
                    self.assertFalse(output.exists())

    def test_open_permission_error_is_readable(self):
        script = Path(__file__).with_name("generate_users.py")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "users.csv"
            stderr = io.StringIO()
            with patch("builtins.input", side_effect=[str(output), "en", "1"]), \
                    patch("builtins.open", side_effect=PermissionError("Permission denied")), \
                    redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    runpy.run_path(str(script), run_name="__main__")
            self.assertEqual(raised.exception.code, 1)
            self.assertIn("cannot open", stderr.getvalue().lower())
            self.assertIn(str(output), stderr.getvalue())
            self.assertIn("Permission denied", stderr.getvalue())
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertFalse(output.exists())

    def test_defaults_and_whitespace_normalization(self):
        for count in ("", "   "):
            with self.subTest(count=count), tempfile.TemporaryDirectory() as directory:
                result = self.run_script(directory, path="", locale="", count=count)
                self.assertEqual(result.returncode, 0, result.stderr)
                with (Path(directory) / "users_data.csv").open(newline="") as file:
                    self.assertEqual(len(list(csv.reader(file, delimiter=";"))), 100)
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_script(directory, locale=" RU ", count=" 1 ")
            self.assertEqual(result.returncode, 0, result.stderr)
            with (Path(directory) / "users.csv").open(newline="") as file:
                self.assertEqual(len(list(csv.reader(file, delimiter=";"))), 1)

    def test_valid_request_appends_to_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "users.csv"
            output.write_bytes(b"sentinel;keep\n")
            result = self.run_script(directory)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.read_bytes().startswith(b"sentinel;keep\n"))
            with output.open(newline="") as file:
                rows = list(csv.reader(file, delimiter=";"))
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(rows[1]), 13)

    def test_generates_users_with_valid_age_and_preferences(self):
        script = Path(__file__).with_name("generate_users.py")
        for language in ("en", "ru"):
            with self.subTest(language=language), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "users.csv"
                with patch("builtins.input", side_effect=[str(output), language, "100"]):
                    namespace = runpy.run_path(str(script), run_name="__main__")

                for name in ("MUSIC_GENRES", "MOVIES"):
                    values = namespace[name]
                    self.assertEqual(len(values), 20)
                    self.assertEqual(len(set(values)), 20)
                    self.assertTrue(all(isinstance(value, str) and value.strip() for value in values))

                with output.open(newline="") as file:
                    rows = list(csv.reader(file, delimiter=";"))
                self.assertEqual(len(rows), 100)
                for row in rows:
                    self.assertEqual(len(row), 13)
                    self.assertRegex(row[1], r"^[A-Z]+_[0-9]+$")
                    self.assertTrue(16 <= int(row[3]) <= 90)
                    self.assertIn(row[8], namespace["MUSIC_GENRES"])
                    self.assertIn(row[9], namespace["MOVIES"])


if __name__ == "__main__":
    unittest.main()
