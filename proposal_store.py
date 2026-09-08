"""Versioned proposal handoff between the local ledger and the chat workflow."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from finance_core import load_statements, load_transactions


def revision(db):
    data = [load_statements(db), load_transactions(db)]
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def proposal_path(db):
    return Path(db).with_suffix('.proposal.json')


def status(db):
    current = revision(db)
    path = proposal_path(db)
    try:
        proposal = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(proposal, dict):
            raise ValueError('Invalid proposal')
    except (OSError, ValueError):
        proposal = None
    return {'revision': current, 'pending': not proposal or proposal.get('revision') != current,
            'proposal': proposal}


def publish(db, source, expected_revision):
    if revision(db) != expected_revision:
        raise ValueError('Datenstand hat sich geändert. Vor Veröffentlichung erneut prüfen.')
    for key in ('title', 'review', 'description', 'benefit', 'drawback'):
        if not isinstance(source.get(key), str) or not source[key].strip():
            raise ValueError('Missing proposal field: ' + key)
    payload = {**source, 'revision': expected_revision,
               'created_at': datetime.now().astimezone().isoformat(timespec='seconds')}
    path = proposal_path(db)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


if __name__ == '__main__':
    cli = argparse.ArgumentParser()
    cli.add_argument('--db', type=Path, required=True)
    cli.add_argument('--publish', type=Path)
    cli.add_argument('--revision')
    args = cli.parse_args()
    if args.publish:
        publish(args.db, json.loads(args.publish.read_text(encoding='utf-8')), args.revision)
    print(json.dumps(status(args.db), ensure_ascii=False))
