import subprocess, sys, os, time

python_exe = r'C:\Users\jiajianpeng\AppData\Local\Programs\Python\Python314\python.exe'
workdir = os.path.dirname(os.path.abspath(__file__))
script = os.path.join(workdir, 'mcs8_web_panel.py')

env = os.environ.copy()
env['MCS8_PANEL_HOST'] = '0.0.0.0'
env['MCS8_PANEL_PORT'] = '8788'

log_path = os.path.join(workdir, 'server.log')
proc = subprocess.Popen(
    [python_exe, '-u', script],
    cwd=workdir,
    env=env,
    stdout=open(log_path, 'w'),
    stderr=subprocess.STDOUT,
    creationflags=0x00000010
)

print(f'Server PID: {proc.pid}')
time.sleep(5)
if proc.poll() is not None:
    print(f'Server exited with code {proc.returncode}')
    with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
        print(f.read()[:1000])
else:
    print('Server is running!')
    import urllib.request
    try:
        r = urllib.request.urlopen('http://127.0.0.1:8788/api/health', timeout=5)
        print(f'HTTP health check: {r.status}')
    except Exception as e:
        print(f'HTTP health check failed: {e}')