import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from finance_core import (
    ParsedStatement,
    ParsedTransaction,
    aggregate_amounts,
    import_statement,
    init_db,
    load_statements,
    load_transactions,
    parse_statement_pdf,
    _find_period,
    PeriodParseError,
)


class FinanceCoreTests(unittest.TestCase):
    def test_booking_dates_determine_month_without_period_heading(self):
        for rows in (
            ["02.04.2026 31.03.2026 Gehalt +3.000,00", "29.04.2026 Aldi -54,87"],
            ["Kontoauszug erstellt am 01.05.2026", "02.04. 31.03. Gehalt +3.000,00", "29.04. Aldi -54,87"],
            ["02.02.2024 Gehalt +3.000,00", "28.02.2024 Aldi -54,87"],
        ):
            with self.subTest(rows=rows):
                start, end = _find_period("\n".join(rows), rows)
                expected = (date(2024, 2, 1), date(2024, 2, 29)) if "2024" in rows[0] else (date(2026, 4, 1), date(2026, 4, 30))
                self.assertEqual((start, end), expected)

    def test_booking_month_is_not_guessed_when_year_missing_or_months_conflict(self):
        for rows in (
            ["02.04. Gehalt +3.000,00", "29.04. Aldi -54,87"],
            ["02.04.2026 Gehalt +3.000,00", "02.05.2026 Aldi -54,87"],
        ):
            with self.subTest(rows=rows), self.assertRaises(PeriodParseError):
                _find_period("\n".join(rows), rows)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.sqlite3"
        init_db(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def statement(self):
        transactions = [
            ParsedTransaction(
                booking_date="2026-08-02", value_date=None, party="Arbeitgeber",
                booking_text="Gehalt", purpose="", amount_cents=300_000,
                direction="Haben", currency="EUR", main_category="Einnahmen",
                subcategory="Gehalt", merchant="Nicht eindeutig", category_status="Automatisch",
                fingerprint="tx-income",
            ),
            ParsedTransaction(
                booking_date="2026-08-03", value_date=None, party="Aldi",
                booking_text="Kartenzahlung", purpose="", amount_cents=-5_487,
                direction="Soll", currency="EUR", main_category="Lebensmittel",
                subcategory="Supermarkt", merchant="Aldi", category_status="Automatisch",
                fingerprint="tx-expense",
            ),
            ParsedTransaction(
                booking_date="2026-08-04", value_date=None, party="Eigenes Konto",
                booking_text="Umbuchung", purpose="", amount_cents=-50_000,
                direction="Soll", currency="EUR", main_category="interne Umbuchungen",
                subcategory="Eigene Konten", merchant="Nicht eindeutig", category_status="Automatisch",
                special_type="Interne Umbuchung", fingerprint="tx-internal",
            ),
        ]
        return ParsedStatement(
            file_hash="file-one", filename="auszug.pdf", account_token="account-one",
            account_masked="DE•• •••• •••• 1234", period_start="2026-08-01",
            period_end="2026-08-31", beginning_cents=100_000, ending_cents=344_513,
            currency="EUR", transactions=transactions, reconciliation_diff_cents=0,
            confirmed=True,
        )

    def test_cent_exact_import_and_duplicate_prevention(self):
        first = import_statement(self.db, self.statement())
        second = import_statement(self.db, self.statement())
        self.assertEqual(first["imported"], 3)
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(load_statements(self.db)), 1)
        self.assertEqual(len(load_transactions(self.db)), 3)

    def test_income_expense_and_internal_are_separate(self):
        rows = [item.__dict__ for item in self.statement().transactions]
        totals = aggregate_amounts(rows)
        self.assertEqual(totals["income_cents"], 300_000)
        self.assertEqual(totals["expense_cents"], 5_487)
        self.assertEqual(totals["internal_net_cents"], -50_000)
        self.assertEqual(totals["movement_cents"], 244_513)

    def test_text_pdf_is_parsed_and_reconciled_without_balance_rows_as_transactions(self):
        extracted = """Kontoauszug
IBAN DE12 3456 7890 1234 5678 90
Abrechnungszeitraum 01.08.2026 - 31.08.2026
Währung EUR
01.08.2026 Anfangssaldo 1.000,00 H
02.08. 02.08. Gehalt Arbeitgeber +3.000,00 EUR
03.08. 03.08. Aldi Kartenzahlung -54,87 EUR
31.08.2026 Endsaldo 3.945,13 H
"""

        class Page:
            def extract_text(self):
                return extracted

        class Reader:
            pages = [Page()]

        with patch("finance_core.PdfReader", return_value=Reader()):
            parsed = parse_statement_pdf(b"%PDF-test", "august.pdf")

        self.assertEqual(parsed.account_masked, "DE•• •••• •••• 7890")
        self.assertEqual(len(parsed.transactions), 2)
        self.assertEqual(parsed.reconciliation_diff_cents, 0)
        self.assertTrue(parsed.confirmed)

    def test_period_is_derived_from_dated_old_and_new_balance(self):
        extracted = """Kontoauszug
IBAN DE12 3456 7890 1234 5678 90
Währung EUR
Alter Kontostand vom 31.03.2026 1.000,00 H
02.04. 02.04. Gehalt Arbeitgeber +3.000,00 EUR
03.04. 03.04. Aldi Kartenzahlung -54,87 EUR
Neuer Kontostand vom 30.04.2026 3.945,13 H
"""

        class Page:
            def extract_text(self):
                return extracted

        class Reader:
            pages = [Page()]

        with patch("finance_core.PdfReader", return_value=Reader()):
            parsed = parse_statement_pdf(b"%PDF-test", "kontoauszug.pdf")

        self.assertEqual(parsed.period_start, "2026-04-01")
        self.assertEqual(parsed.period_end, "2026-04-30")
        self.assertEqual(parsed.reconciliation_diff_cents, 0)

    def test_manual_period_override_avoids_guessing(self):
        extracted = """Kontoauszug
IBAN DE12 3456 7890 1234 5678 90
Währung EUR
Anfangssaldo 1.000,00 H
02.04. 02.04. Gehalt Arbeitgeber +3.000,00 EUR
03.04. 03.04. Aldi Kartenzahlung -54,87 EUR
Endsaldo 3.945,13 H
"""

        class Page:
            def extract_text(self):
                return extracted

        class Reader:
            pages = [Page()]

        with patch("finance_core.PdfReader", return_value=Reader()):
            parsed = parse_statement_pdf(
                b"%PDF-test",
                "kontoauszug.pdf",
                period_override=(date(2026, 4, 1), date(2026, 4, 30)),
            )

        self.assertEqual(parsed.period_start, "2026-04-01")
        self.assertEqual(parsed.period_end, "2026-04-30")
        self.assertTrue(parsed.confirmed)


if __name__ == "__main__":
    unittest.main()
