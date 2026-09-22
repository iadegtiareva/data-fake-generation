import csv
import runpy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class GenerateUsersTest(unittest.TestCase):
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
