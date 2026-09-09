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
        self.assertEqual(result["Art"], "Strom")
        self.assertEqual(result["Anbieter"], "E.ON")
        self.assertEqual(result["Erfasst seit"], "seit April 2026 erfasst")
        self.assertEqual(result["Rhythmus"], "Monatlich")
        self.assertNotIn("Vertragsbeginn", result)

    def test_booking_purpose_becomes_human_obligation_instead_of_person_name(self):
        rows = [{
            "booking_date": f"2026-0{month}-04", "amount_cents": -149,
            "main_category": "Versicherungen und Finanzen", "merchant": "",
            "party": "Trautmann", "booking_text": "Entgelt Trautmann",
            "purpose": "MONATLICHES ENTGELT GIROCARD (DEBITKARTE)",
        } for month in (4, 5, 6)]
        result = observed_obligations(rows)[0]
        self.assertEqual(result["Art"], "Girocard-Gebühr")
        self.assertEqual(result["Anbieter"], "ING")
        self.assertEqual(result["Betrag"], "1,49 €/Monat")

    def test_prime_is_recognized_as_annual_from_booking_text(self):
        rows = [{
            "booking_date": "2026-06-10", "amount_cents": -8990,
            "main_category": "Abonnements", "merchant": "Amazon Prime",
            "party": "Amazon", "booking_text": "AMZNPrime DE",
        }]
        result = observed_obligations(rows)[0]
        self.assertEqual(result["Art"], "Prime-Mitgliedschaft")
        self.assertEqual(result["Rhythmus"], "Jährlich")
        self.assertEqual(result["Betrag"], "89,90 €/Jahr")

    def test_refund_is_not_an_income_source(self):
        rows = [{"booking_date": "2026-05-05", "amount_cents": 150000,
                 "main_category": "Erstattungen", "merchant": "", "party": "Erstattung"}]
        self.assertEqual(observed_income_sources(rows), [])


if __name__ == "__main__":
    unittest.main()
