import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import date
from pathlib import Path
from monthly_workstream import check_month
from month_timeline import timeline_html


class MonthlyWorkflowTests(unittest.TestCase):
    def test_year_change_and_unconfirmed_month(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'test.sqlite3'
            with closing(sqlite3.connect(db)) as conn:
                conn.execute('CREATE TABLE statements (period_start TEXT, confirmed INTEGER)')
                conn.executemany('INSERT INTO statements VALUES (?, ?)', [('2026-11-01', 1), ('2026-12-01', 0)])
                conn.commit()
            self.assertEqual(check_month(db, date(2027, 1, 1))['missing'], ['2026-12'])
            self.assertEqual(check_month(db, date(2026, 12, 1))['missing'], [])

    def test_long_history_negative_and_zero_growth(self):
        months = [f'Testmonat {n}' for n in range(36)]
        html = timeline_html(months, [0, -100, 200] * 12, [0] * 36, lambda x, **k: str(x))
        self.assertEqual(html.count('repeat(36,minmax(140px,1fr))'), 2)
        self.assertEqual(html.count('class="month-cell"'), 72)
        self.assertIn('min-width:5040px', html)
