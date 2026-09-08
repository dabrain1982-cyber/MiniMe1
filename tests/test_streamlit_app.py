import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class StreamlitAppTests(unittest.TestCase):
    def test_empty_app_renders_all_three_tabs_without_exception(self):
        app_path = Path(__file__).resolve().parents[1] / "streamlit_app.py"
        app = AppTest.from_file(str(app_path), default_timeout=15).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs), 3)
        self.assertTrue(any("Geld, aber übersichtlich" in title.value for title in app.title))


if __name__ == "__main__":
    unittest.main()
