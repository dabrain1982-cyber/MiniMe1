import json
import tempfile
import unittest
from pathlib import Path
from finance_core import init_db
from proposal_store import revision, status, publish, proposal_path


class ProposalTests(unittest.TestCase):
    def test_publication_and_revision_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'ledger.sqlite3'
            init_db(db)
            self.assertTrue(status(db)['pending'])
            proposal = {k: 'Test' for k in ('title', 'review', 'description', 'benefit', 'drawback')}
            with self.assertRaises(ValueError):
                publish(db, proposal, 'outdated')
            publish(db, proposal, revision(db))
            self.assertFalse(status(db)['pending'])
            self.assertEqual(status(db)['proposal']['title'], 'Test')
            proposal_path(db).write_text('invalid', encoding='utf-8')
            self.assertTrue(status(db)['pending'])

    def test_required_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / 'ledger.sqlite3'
            init_db(db)
            with self.assertRaises(ValueError):
                publish(db, {}, revision(db))
