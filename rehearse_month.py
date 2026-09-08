"""Rehearse August in disposable DB; prepare a separate four-month user test DB."""
import os
import sqlite3
import tempfile
from collections import Counter
from contextlib import closing
from datetime import date
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from finance_core import load_statements, load_transactions, parse_statement_pdf, import_statement, get_merchant_rules
from verify_ing_import import independent_rows
from monthly_workstream import check_month

ROOT = Path(__file__).resolve().parent
LIVE = ROOT / 'data/finanzbilanz.sqlite3'
USER_TEST = ROOT / 'data/generalprobe-20260906.sqlite3'
PDF = Path('C:/Users/DaBra/Desktop/Bewerbungsunterlagen/Mein neuer Job/Syensqo/2210120561_Kontoauszug_20260902 (1).pdf')


def backup(target):
    assert target.resolve() != LIVE.resolve()
    assert not target.exists(), 'Existing test database must not be overwritten'
    with closing(sqlite3.connect(LIVE.as_uri() + '?mode=ro', uri=True)) as source:
        with closing(sqlite3.connect(target)) as destination:
            source.backup(destination)


def remove_august(target):
    assert target.resolve() != LIVE.resolve()
    assert target.resolve() == USER_TEST.resolve() or target.resolve().is_relative_to((ROOT / 'tmp').resolve())
    with closing(sqlite3.connect(target)) as db:
        ids = [r[0] for r in db.execute("SELECT id FROM statements WHERE period_start='2026-08-01'")]
        assert len(ids) == 1
        db.execute('DELETE FROM transactions WHERE statement_id=?', (ids[0],))
        db.execute('DELETE FROM statements WHERE id=?', (ids[0],))
        db.commit()


def render(db, expected_months):
    with patch.dict(os.environ, {'FINANZBILANZ_DB_PATH': str(db), 'FINANZBILANZ_TEST_MODE': '1'}):
        app = AppTest.from_file(str(ROOT / 'streamlit_app.py'), default_timeout=20).run()
        assert not app.exception, app.exception
        assert len(app.tabs) == 3
        assert len(app.selectbox(key='selected_month').options) == expected_months
        assert len(app.get('vega_lite_chart')) >= 2
        for month in app.selectbox(key='selected_month').options:
            app.selectbox(key='selected_month').select(month).run()
            assert not app.exception
        return app


def main():
    before = (load_statements(LIVE), load_transactions(LIVE))
    assert check_month(LIVE, date(2026, 9, 6))['missing'] == []
    (ROOT / 'tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='finanzprobe-', dir=ROOT / 'tmp') as folder:
        trial = Path(folder) / 'trial.sqlite3'
        backup(trial)
        remove_august(trial)
        old = (load_statements(trial), load_transactions(trial))
        assert len(old[0]) == 4
        assert check_month(trial, date(2026, 9, 6))['missing'] == ['2026-08']
        render(trial, 4)
        parsed = parse_statement_pdf(PDF.read_bytes(), PDF.name, get_merchant_rules(trial))
        assert independent_rows(PDF) == Counter((t.booking_date, t.amount_cents) for t in parsed.transactions)
        assert parsed.beginning_cents == old[0][-1]['ending_cents']
        assert parsed.ending_cents == 940449
        assert import_statement(trial, parsed)['imported'] == 35
        assert import_statement(trial, parsed)['duplicate']
        after = load_statements(trial), load_transactions(trial)
        assert after[0][:4] == old[0]
        old_ids = {r['id'] for r in old[1]}
        assert [r for r in after[1] if r['id'] in old_ids] == old[1]
        assert len(after[1]) == 205
        assert check_month(trial, date(2026, 9, 6))['missing'] == []
        render(trial, 5)
        print('PASS: April-Juli unchanged; August 35 bookings, ending 9404.49; independent PDF extraction; duplicate blocked; 4/5-month UI and every month selection; reminder states.')
    if not USER_TEST.exists():
        backup(USER_TEST)
        remove_august(USER_TEST)
    assert before == (load_statements(LIVE), load_transactions(LIVE))
    print('PASS: live statements and bookings unchanged. User upload test ready:', USER_TEST)


if __name__ == '__main__':
    main()
