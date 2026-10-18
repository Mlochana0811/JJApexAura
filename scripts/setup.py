"""Cross-platform local setup: python scripts/setup.py [--demo]."""
import argparse, os, secrets, shutil, subprocess, sys, venv
from pathlib import Path
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--demo',action='store_true');args=parser.parse_args()
if sys.version_info<(3,11):raise SystemExit('Python 3.11 or newer is required')
node=shutil.which('node');npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
if not node or not npm:raise SystemExit('Install Node.js 22.12+ (or 24 LTS) with npm, then run setup again')
version=subprocess.check_output([node,'--version'],text=True).strip().lstrip('v').split('.')
if int(version[0])<22 or (int(version[0])==22 and int(version[1])<12):raise SystemExit('Node.js 22.12+ or 24 LTS is required')
env=root/'.env'
if not env.exists():
    text=(root/'.env.example').read_text().replace('replace-with-a-unique-random-secret-at-least-50-characters-long',secrets.token_urlsafe(64)).replace('change-this-before-running-docker',secrets.token_urlsafe(32))
    env.write_text(text)
venv.create(root/'.venv',with_pip=True)
python=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def run(cmd,cwd=root):subprocess.run([str(v) for v in cmd],cwd=cwd,check=True)
run([python,'-m','pip','install','-r','backend/requirements.txt'])
run([npm,'ci'],root/'frontend')
run([python,'manage.py','migrate'],root/'backend')
run([python,'manage.py','createcachetable'],root/'backend')
if args.demo:
    password=secrets.token_urlsafe(14)+'!7a'
    run([python,'manage.py','seed_demo','--password',password],root/'backend')
    print('\nDemo temporary password:',password)
    print('Accounts: demo.admin / demo.hr / demo.manager / demo.employee')
else:
    print('\nCreate your system admin account:')
    run([python,'manage.py','createsuperuser'],root/'backend')
print('\nReady. Run: python scripts/dev.py')
print('Open http://localhost:5173/app/')
