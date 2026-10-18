"""Restore to a NEW empty directory, verify hashes and SQLite integrity; never overwrite live data."""
import argparse, hashlib, json, sqlite3, zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('backup');p.add_argument('destination');args=p.parse_args()
dest=Path(args.destination).resolve()
if dest.exists():raise SystemExit('Destination must not already exist')
with zipfile.ZipFile(args.backup) as z:
    manifest=json.loads(z.read('manifest.json'))
    for name,digest in manifest.items():
        path=(dest/name).resolve()
        if dest not in path.parents:raise SystemExit('Unsafe archive path')
        data=z.read(name)
        if hashlib.sha256(data).hexdigest()!=digest:raise SystemExit(f'Checksum failed: {name}')
    dest.mkdir(parents=True)
    for name in manifest:
        path=dest/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(z.read(name))
with sqlite3.connect(dest/'db.sqlite3') as db:
    result=db.execute('PRAGMA integrity_check').fetchone()[0]
    if result!='ok':raise SystemExit(result)
print(f'Backup restored and verified in {dest}. Test this copy before any live recovery.')
