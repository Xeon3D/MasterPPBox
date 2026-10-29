"""Full (multi-user) boot of the TouchMaster VM under the automation build:
start held, release the GDB stub, answer BIOS F1, boot the loader with
<flags> (default -v), then run <seconds> of emulated time taking a screenshot
every <every> s (analysis/p3/shots/<tag>-NNNs.png), pull dmesg, and leave the
VM running held (or quit with --quit).
  python -I scripts/p3-boot.py <exe> <vmdir> <tag> [--secs 180] [--every 15] [--flags -v] [--quit]"""
import argparse, os, socket, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
Auto = import_module('p3-auto').Auto

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('exe'); ap.add_argument('vm'); ap.add_argument('tag')
ap.add_argument('--secs', type=int, default=180); ap.add_argument('--every', type=int, default=15)
ap.add_argument('--flags', default='-v'); ap.add_argument('--port', type=int, default=7777)
ap.add_argument('--quit', action='store_true')
ap.add_argument('--logfile', help='86Box log file (-L)')
ap.add_argument('--env', action='append', default=[], help='NAME=VALUE for the 86Box process')
a = ap.parse_args()
a.exe = os.path.abspath(a.exe); a.vm = os.path.abspath(a.vm)
shots = os.path.join(ROOT, 'analysis/p3/shots'); os.makedirs(shots, exist_ok=True)
def emu_running():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + os.path.basename(a.exe)], capture_output=True, text=True).stdout
    return os.path.basename(a.exe).lower() in out.lower()
for _ in range(60):          # a closing 86Box still holds the disk image: never start a second one
    if not emu_running(): break
    time.sleep(1)
else:
    sys.exit('another %s is still running' % os.path.basename(a.exe))
tok = os.path.join(a.vm, 'automation.token')
if os.path.exists(tok): os.remove(tok)
env = dict(os.environ, **dict(e.split('=', 1) for e in a.env))
subprocess.Popen([a.exe, '-P', a.vm, '-R', os.path.join(ROOT, '86box/roms'), '-N',
                  '--automation', 'tcp:%d' % a.port, '--automation-hold'] + (['-L', os.path.abspath(a.logfile)] if a.logfile else []),
                 env=env,
                 creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
for _ in range(100):
    if os.path.exists(tok): break
    time.sleep(0.2)
time.sleep(0.5)
c = Auto(a.vm, a.port)
info = c.req('info')
print('machine', info.get('machine'), 'video', info.get('video'), 'sound', info.get('sound'), flush=True)
try:
    g = socket.create_connection(('127.0.0.1', info.get('gdbstub_port', 12345)), timeout=2)
    g.sendall(b'+$c#63'); g.recv(10); g.close()
except OSError: pass
for _ in range(4):
    r = c.req('wait text 25000 BTX loader')
    if r.get('matched'): break
    c.req('key down 0x3b'); c.req('step 100'); c.req('key up 0x3b')
    print('pressed F1', flush=True)
r = c.req('wait text 20000 Hit [Enter]')
c.req('key down 0x39'); c.req('step 100'); c.req('key up 0x39'); c.req('step 300')
c.type('boot %s\n' % a.flags)
t0 = c.req('status')['ms']
for k in range(a.every, a.secs + 1, a.every):
    r = c.req('step %d' % (a.every * 1000))
    p = os.path.join(shots, '%s-%03ds.png' % (a.tag, k)).replace('\\', '/')
    c.req('screenshot ' + p)
    print('t+%3ds ms=%s frames=%s %s' % (k, r.get('ms'), r.get('frames'), r.get('stopped', '')), flush=True)
c.f.close(); c.s.close()
out = os.path.join(ROOT, 'analysis/p3/raw', 'dmesg-%s.txt' % a.tag)
subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts/p3-msgbuf.py'), a.vm, str(a.port), out])
if a.quit:
    Auto(a.vm, a.port).req('quit')
