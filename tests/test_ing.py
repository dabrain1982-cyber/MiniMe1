import unittest
from unittest.mock import patch
from types import SimpleNamespace
from finance_core import parse_statement_pdf, ParseError, _merchant_and_category


PAGE = '''Girokonto Nummer 1234567890
Kontoauszug April 2026
Buchung Buchung / Verwendungszweck Betrag (EUR)
Valuta
02.04.2026 Lastschrift ALDI SE -20,00
01.04.2026 Einkauf
Referenz: test-01
03.04.2026 Gehalt/Rente Arbeitgeber 100,00
03.04.2026 LOHN/GEHALT
34GKKA1234567890_T
ING-DiBa AG
Alter Saldo 1.000,00 Euro
Neuer Saldo 1.080,00 Euro
IBAN DE12 3456 7890 1234 5678 90
Seite 1 von 1
'''


class IngTests(unittest.TestCase):
    def parse(self, pages):
        reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda t=t: t) for t in pages])
        with patch('finance_core.PdfReader', return_value=reader):
            return parse_statement_pdf(b'%PDF-example', 'renamed.pdf')

    def test_two_line_layout_positive_credit_and_legal_page(self):
        statement = self.parse([PAGE, 'Bitte beachten Sie die nachstehenden Hinweise:\nLegal text'])
        self.assertEqual(len(statement.transactions), 2)
        self.assertEqual(statement.transactions[0].value_date, '2026-04-01')
        self.assertEqual(statement.transactions[1].amount_cents, 10000)
        self.assertNotIn('Legal', statement.transactions[1].purpose)
        self.assertTrue(statement.confirmed)

    def test_missing_page_rejected(self):
        with self.assertRaises(ParseError):
            self.parse([PAGE.replace('von 1', 'von 2')])

    def test_missing_value_date_rejected(self):
        with self.assertRaises(ParseError):
            self.parse([PAGE.replace('01.04.2026 Einkauf', 'Einkauf')])

    def test_categories_do_not_confuse_payment_methods_or_substrings(self):
        for text, merchant, category in [
            ('Lastschrift E-Plus Service GmbH Aldi Talk', 'Aldi Talk', 'Kommunikation'),
            ('Lastschrift PayPal Spotify AB', 'Spotify', 'Abonnements'),
            ('Lastschrift MCDONALDS Referenz: uber', "McDonald's", 'Gastronomie und Lieferdienste'),
        ]:
            result = _merchant_and_category(text, -100)
            self.assertEqual(result[:2], (merchant, category))
        self.assertEqual(_merchant_and_category('Echtzeitüberweisung Unbekannt', -100)[1], 'Zu prüfen')
