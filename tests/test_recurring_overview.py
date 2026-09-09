import unittest

from recurring_overview import observed_income_sources, observed_obligations


class RecurringOverviewTests(unittest.TestCase):
    def test_observed_dates_are_not_called_contract_start(self):
        rows = [
            {"booking_date": f"2026-0{month}-02", "amount_cents": -7000,
             "main_category": "Wohnen und Energie", "merchant": "E.ON", "party": "E.ON"}
            for month in (4, 5, 6)
        ]
        result = observed_obligations(rows)[0]
        self.assertEqual(result["Erstmals erfasst"], "02.04.2026")
        self.assertEqual(result["Rhythmus"], "Monatlich beobachtet")
        self.assertNotIn("Vertragsbeginn", result)

    def test_refund_is_not_an_income_source(self):
        rows = [{"booking_date": "2026-05-05", "amount_cents": 150000,
                 "main_category": "Erstattungen", "merchant": "", "party": "Erstattung"}]
        self.assertEqual(observed_income_sources(rows), [])


if __name__ == "__main__":
    unittest.main()
