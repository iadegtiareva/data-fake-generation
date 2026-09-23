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
    def test_import_has_no_side_effects(self):
        script = Path(__file__).with_name("generate_users.py")
        with patch("builtins.input", side_effect=AssertionError("Unexpected input")), \
                patch("builtins.open", side_effect=AssertionError("Unexpected output")):
            namespace = runpy.run_path(str(script), run_name="import_check")
        self.assertTrue(callable(namespace["main"]))

    def test_incomplete_input(self):
        script = Path(__file__).with_name("generate_users.py")
        for answers in ("", "users.csv\n", "users.csv\nen\n"):
            with self.subTest(answers=answers), tempfile.TemporaryDirectory() as directory:
                result = subprocess.run(
                    [sys.executable, "-B", str(script)], input=answers,
                    text=True, capture_output=True, cwd=directory, timeout=30,
                )
                self.assert_input_error(result, "input ended")
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_interrupted_input(self):
        script = Path(__file__).with_name("generate_users.py")
        stderr = io.StringIO()
        with patch("builtins.input", side_effect=KeyboardInterrupt), \
                patch("builtins.open", side_effect=AssertionError("Unexpected output")), \
                redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as raised:
                try:
                    runpy.run_path(str(script), run_name="__main__")
                except KeyboardInterrupt:
                    self.fail("KeyboardInterrupt escaped the CLI")
        self.assertEqual(raised.exception.code, 130)
        self.assertIn("Interrupted by user", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_output_errors_after_first_record(self):
        script = Path(__file__).with_name("generate_users.py")
        failures = [
            ("write", OSError("Disk full"), 1),
            ("close", OSError("Flush failed"), 1),
            ("write", UnicodeEncodeError("ascii", "я", 0, 1, "not ASCII"), 1),
            ("write", csv.Error("Invalid CSV data"), 1),
            ("write", KeyboardInterrupt(), 130),
        ]
        real_open = open
        for stage, error, code in failures:
            with self.subTest(stage=stage, error=type(error).__name__), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "users.csv"
                output.write_bytes(b"sentinel;keep\n")
                writes = []

                class FaultyFile:
                    def __init__(self, file):
                        self.file = file

                    def __enter__(self):
                        return self

                    def write(self, data):
                        if stage == "write" and writes:
                            raise error
                        result = self.file.write(data)
                        writes.append(data)
                        return result

                    def __exit__(self, *args):
                        self.file.close()
                        if stage == "close":
                            raise error

                def faulty_open(*args, **kwargs):
                    return FaultyFile(real_open(*args, **kwargs))

                stderr = io.StringIO()
                with patch("builtins.input", side_effect=[str(output), "en", "2"]), \
                        patch("builtins.open", side_effect=faulty_open), redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as raised:
                        try:
                            runpy.run_path(str(script), run_name="__main__")
                        except KeyboardInterrupt:
                            self.fail("KeyboardInterrupt escaped the CLI")
                self.assertEqual(raised.exception.code, code)
                completed = 0 if stage == "close" else 1
                self.assertIn(f"Completed records in this run: {completed}.", stderr.getvalue())
                self.assertIn("Check the file before retrying", stderr.getvalue())
                self.assertIn("incomplete", stderr.getvalue().lower())
                self.assertNotIn("Traceback", stderr.getvalue())
                self.assertTrue(output.read_bytes().startswith(b"sentinel;keep\n"))
                with output.open(newline="") as file:
                    self.assertEqual(len(list(csv.reader(file, delimiter=";"))), 2)

    def test_partial_failure_reports_only_completed_records(self):
        script = Path(__file__).with_name("generate_users.py")
        real_open = open
        for stage in ("open", "write", "partial_write", "close", "interrupt"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "users.csv"
                original = b"sentinel;keep\n"
                output.write_bytes(original)
                successful_records = []
                opens = 0

                class FaultyFile:
                    def __init__(self, file, index):
                        self.file = file
                        self.index = index

                    def __enter__(self):
                        return self

                    def write(self, data):
                        if self.index == 3 and stage in ("write", "partial_write", "interrupt"):
                            if stage == "partial_write":
                                self.file.write("incomplete;fragment")
                            if stage == "interrupt":
                                raise KeyboardInterrupt()
                            raise OSError("Disk full")
                        result = self.file.write(data)
                        if self.index < 3:
                            successful_records.append(data)
                        return result

                    def __exit__(self, *args):
                        self.file.close()
                        if self.index == 3 and stage == "close":
                            raise OSError("Close failed")

                def faulty_open(*args, **kwargs):
                    nonlocal opens
                    index = opens
                    opens += 1
                    if index == 3 and stage == "open":
                        raise PermissionError("Cannot reopen")
                    return FaultyFile(real_open(*args, **kwargs), index)

                stderr = io.StringIO()
                with patch("builtins.input", side_effect=[str(output), "en", "5"]), \
                        patch("builtins.open", side_effect=faulty_open), redirect_stderr(stderr):
                    with self.assertRaises(SystemExit) as raised:
                        runpy.run_path(str(script), run_name="__main__")
                self.assertEqual(raised.exception.code, 130 if stage == "interrupt" else 1)
                content = output.read_bytes()
                self.assertTrue(content.startswith(original))
                with output.open(newline="") as file:
                    text = file.read()
                self.assertTrue(text.startswith("sentinel;keep\n" + "".join(successful_records)))
                if stage == "partial_write":
                    self.assertTrue(content.endswith(b"incomplete;fragment"))
                self.assertIn("Completed records in this run: 3.", stderr.getvalue())
                self.assertIn("incomplete", stderr.getvalue().lower())
                self.assertIn("Check the file before retrying", stderr.getvalue())
                self.assertNotIn("Traceback", stderr.getvalue())

    def test_internal_generation_errors_keep_traceback(self):
        script = Path(__file__).with_name("generate_users.py")
        for error_name in ("AttributeError", "TypeError", "OSError", "ValueError"):
            with self.subTest(error=error_name), tempfile.TemporaryDirectory() as directory:
                driver = (
                    "import runpy\nfrom unittest.mock import Mock, patch\n"
                    "user = Mock()\n"
                    f"user.person.identifier.side_effect = {error_name}('internal failure')\n"
                    "with patch('mimesis.Generic', return_value=user):\n"
                    f"    runpy.run_path({str(script)!r}, run_name='__main__')\n"
                )
                result = subprocess.run(
                    [sys.executable, "-B", "-c", driver], input="users.csv\nen\n1\n",
                    text=True, capture_output=True, cwd=directory, timeout=30,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Traceback", result.stderr)
                self.assertIn(f"{error_name}: internal failure", result.stderr)

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
