"""Read-only monthly reminder check; never changes the app or its ledger."""
import argparse
import json
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def check_month(db, today=None):
    today = today or date.today()
    due = (today.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    db = Path(db).resolve()
    with closing(sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)) as conn:
        rows = conn.execute('SELECT period_start, confirmed FROM statements ORDER BY period_start').fetchall()
    present = {start[:7] for start, confirmed in rows if confirmed}
    first = min(present, default=due)
    cursor = date.fromisoformat(first + '-01')
    missing = []
    while cursor.strftime('%Y-%m') <= due:
        key = cursor.strftime('%Y-%m')
        if key not in present:
            missing.append(key)
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return {'due': due, 'missing': missing, 'months': len(rows), 'db': str(db)}


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--db', type=Path, default=ROOT / 'data' / 'finanzbilanz.sqlite3')
    cli.add_argument('--date', type=date.fromisoformat)
    args = cli.parse_args()
    print(json.dumps(check_month(args.db, args.date), ensure_ascii=False))
