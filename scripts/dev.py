import os, shutil, subprocess, sys, time
from pathlib import Path
root=Path(__file__).resolve().parents[1]
python=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.exists():raise SystemExit('Run python scripts/setup.py first')
npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
processes=[]
try:
    processes.append(subprocess.Popen([str(python),'manage.py','runserver','127.0.0.1:8000'],cwd=root/'backend'))
    processes.append(subprocess.Popen([npm,'run','dev'],cwd=root/'frontend'))
    print('Open http://localhost:5173/app/ — press Ctrl+C to stop')
    while all(p.poll() is None for p in processes):time.sleep(.5)
finally:
    for p in processes:
        if p.poll() is None:p.terminate()
    for p in processes:
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill()
