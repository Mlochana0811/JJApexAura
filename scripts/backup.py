"""Backup SQLite + private media to a new ZIP; PostgreSQL uses pg_dump separately."""
import argparse, datetime, hashlib, json, sqlite3, tempfile, zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--database',default=str(root/'backend/db.sqlite3'));p.add_argument('--output-dir',default=str(root/'backups'));args=p.parse_args()
database=Path(args.database)
if not database.is_file():raise SystemExit('SQLite database not found; pass --database or use pg_dump for PostgreSQL')
output=Path(args.output_dir);output.mkdir(parents=True,exist_ok=True)
name=output/f'hr-backup-{datetime.datetime.now():%Y%m%d-%H%M%S-%f}.zip'
with tempfile.TemporaryDirectory() as tmp:
    copy=Path(tmp)/'db.sqlite3'
    with sqlite3.connect(f'file:{database}?mode=ro',uri=True) as source,sqlite3.connect(copy) as dest:source.backup(dest)
    with zipfile.ZipFile(name,'x',zipfile.ZIP_DEFLATED) as z:
        z.write(copy,'db.sqlite3')
        manifest={'db.sqlite3':hashlib.sha256(copy.read_bytes()).hexdigest()}
        media=root/'backend/media'
        if media.exists():
            for f in media.rglob('*'):
                if f.is_file():
                    arc='media/'+str(f.relative_to(media)).replace('\\','/');z.write(f,arc);manifest[arc]=hashlib.sha256(f.read_bytes()).hexdigest()
        z.writestr('manifest.json',json.dumps(manifest,indent=2))
print(name)
print('Contains confidential HR data. Store in an encrypted, access-controlled offsite location.')
