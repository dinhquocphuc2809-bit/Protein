"""Import server-only credentials and create the first private admin ticket."""
import argparse
import json
import os
from pathlib import Path

from backend.config import Settings
from backend.database import Database
from backend.providers import KeyPool
from backend.security import Security


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--credentials', type=Path, required=True)
    args = parser.parse_args()
    settings = Settings()
    db = Database(settings.data_dir / 'auvirel.sqlite3')
    security = Security(db, settings)
    pool = KeyPool(db, security)
    records = json.loads(args.credentials.read_text())
    for provider, values in records.items():
        if provider == 'modal' and len(values) != 3:
            raise ValueError('Exactly the three server ASR accounts are required')
        for index, value in enumerate(values, 1):
            pool.add(provider, value, f'{provider} {index}')
    path = settings.data_dir / 'initial-ticket.json'
    if not db.one('SELECT id FROM tickets LIMIT 1'):
        ticket = security.create_ticket('Owner acceptance testing', 30*86400)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as output:
            json.dump(ticket, output)
    print('Server credentials imported; initial ticket remains in the private data directory')


if __name__ == '__main__':
    main()
