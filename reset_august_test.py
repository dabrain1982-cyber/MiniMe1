"""Explicit user-requested reset of August in the named test ledger only."""
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

root = Path(__file__).resolve().parent
target = (root / 'data/generalprobe-20260906.sqlite3').resolve()
live = (root / 'data/finanzbilanz.sqlite3').resolve()
assert target != live and target.parent == (root / 'data').resolve()
assert target.is_file()

def snapshot(path):
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
        return list(db.iterdump())

original = snapshot(live)
with closing(sqlite3.connect(target)) as db:
    rows = db.execute("SELECT id FROM statements WHERE period_start='2026-08-01' AND period_end='2026-08-31'").fetchall()
    assert len(rows) == 1, 'Expected exactly one August statement in test database'
    backup = target.with_name('generalprobe-vor-reset-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sqlite3')
    assert not backup.exists()
    with closing(sqlite3.connect(backup)) as copy:
        db.backup(copy)
    assert snapshot(backup) == snapshot(target)
    old = db.execute('SELECT * FROM transactions WHERE statement_id<>? ORDER BY id', rows[0]).fetchall()
    with db:
        count = db.execute('DELETE FROM transactions WHERE statement_id=?', rows[0]).rowcount
        db.execute('DELETE FROM statements WHERE id=?', rows[0])
    assert db.execute('SELECT * FROM transactions ORDER BY id').fetchall() == old
    assert db.execute('SELECT COUNT(*) FROM statements').fetchone()[0] == 4
assert snapshot(live) == original
print(f'Removed {count} August bookings from TEST ONLY. Verified backup: {backup}. Live ledger unchanged.')
