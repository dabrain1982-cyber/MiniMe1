"""Local acceptance check. Run with PDF paths; --import writes verified statements."""
import argparse
from collections import Counter
from datetime import datetime
from pathlib import Path
import json
import tempfile

import pdfplumber
from finance_core import parse_statement_pdf, import_statement, init_db, load_transactions, load_statements, money_to_cents, aggregate_amounts


def independent_rows(path):
    # Separate PDF engine and geometric columns, independent of the pypdf parser.
    rows = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            for word in words:
                if word['x0'] >= 100:
                    continue
                try:
                    day = datetime.strptime(word['text'], '%d.%m.%Y').date().isoformat()
                except ValueError:
                    continue
                amounts = [w['text'] for w in words if w['x0'] > 480 and abs(w['top'] - word['top']) < 2 and ',' in w['text']]
                if len(amounts) == 1:
                    amount = amounts[0]
                    rows.append((day, money_to_cents(amount.lstrip('-'), -1 if amount.startswith('-') else 1)))
    return Counter(rows)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument('pdfs', nargs='+', type=Path)
    cli.add_argument('--import', dest='save', action='store_true')
    args = cli.parse_args()
    statements = sorted([parse_statement_pdf(p.read_bytes(), p.name) for p in args.pdfs], key=lambda s: s.period_start)
    assert len({s.account_token for s in statements}) == 1, 'Different accounts'
    for path in args.pdfs:
        s = next(s for s in statements if s.filename == path.name)
        assert independent_rows(path) == Counter((t.booking_date, t.amount_cents) for t in s.transactions), 'Independent extraction differs'
        assert s.confirmed, 'Balance mismatch'
        assert len({t.fingerprint for t in s.transactions}) == len(s.transactions), 'Repeated fingerprints need review'
    for previous, current in zip(statements, statements[1:]):
        assert previous.ending_cents == current.beginning_cents, 'Balance continuity mismatch'
    with tempfile.TemporaryDirectory() as directory:
        testdb = Path(directory) / 'acceptance.sqlite3'
        init_db(testdb)
        for s in statements:
            result = import_statement(testdb, s)
            assert result['imported'] == len(s.transactions)
            assert import_statement(testdb, s)['duplicate']
        assert len(load_transactions(testdb)) == sum(len(s.transactions) for s in statements)
    if args.save:
        db = Path(__file__).parent / 'data' / 'finanzbilanz.sqlite3'
        init_db(db)
        for s in statements:
            import_statement(db, s)
    report = []
    for s in statements:
        totals = aggregate_amounts(t.__dict__ for t in s.transactions)
        report.append(dict(month=s.period_start[:7], bookings=len(s.transactions), beginning_cents=s.beginning_cents,
                           ending_cents=s.ending_cents, difference_cents=s.reconciliation_diff_cents,
                           growth_cents=s.ending_cents-s.beginning_cents, **totals))
    output = Path(__file__).parent / 'data' / 'importpruefung.json'
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))
    print('Independent PDF engine, all booking dates/amounts, balance continuity and duplicate import: PASS')


if __name__ == '__main__':
    main()
