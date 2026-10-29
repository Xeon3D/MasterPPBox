"""POST test under the automation build: start <vmdir> held, release the GDB
stub, run <secs> s of emulated time with a screenshot and a text-screen dump
every <every> s (analysis/p10/shots/<tag>-NNNs.*), then save the 32K of
option ROM space at C0000 (analysis/p10/raw/<tag>-c0000.bin) and quit.
  python -I scripts/p10-post.py <exe> <vmdir> <tag> [--secs 20] [--every 5] [--keys 0x3b@8]
--roms picks the ROM folder. --keys holds a set-1 scancode for 100 ms at the given second (repeatable)."""
import argparse, os, socket, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
Auto = import_module('p3-auto').Auto

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('exe'); ap.add_argument('vm'); ap.add_argument('tag')
ap.add_argument('--secs', type=int, default=20); ap.add_argument('--every', type=int, default=5)
ap.add_argument('--keys', action='append', default=[]); ap.add_argument('--port', type=int, default=7777)
ap.add_argument('--roms', default=os.path.join(ROOT, '86box/roms'), help='ROM folder (default 86box/roms)')
a = ap.parse_args()
a.exe = os.path.abspath(a.exe); a.vm = os.path.abspath(a.vm)
shots = os.path.join(ROOT, 'analysis/p10/shots'); os.makedirs(shots, exist_ok=True)
raw = os.path.join(ROOT, 'analysis/p10/raw'); os.makedirs(raw, exist_ok=True)
name = os.path.basename(a.exe).lower()
for _ in range(60):
    if name not in subprocess.run(['tasklist', '/FI', 'IMAGENAME eq ' + name], capture_output=True, text=True).stdout.lower():
        break
    time.sleep(1)
else:
    sys.exit('another %s is still running' % name)
tok = os.path.join(a.vm, 'automation.token')
if os.path.exists(tok): os.remove(tok)
subprocess.Popen([a.exe, '-P', a.vm, '-R', os.path.abspath(a.roms), '-N',
                  '--automation', 'tcp:%d' % a.port, '--automation-hold'],
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
except OSError:
    pass
keys = sorted((float(k.split('@')[1]), int(k.split('@')[0], 0)) for k in a.keys)
t = 0.0
for k in range(a.every, a.secs + 1, a.every):
    while keys and keys[0][0] <= k:
        at, code = keys.pop(0)
        if at > t: c.req('step %d' % int((at - t) * 1000)); t = at
        c.req('key down %#x' % code); c.req('step 100'); c.req('key up %#x' % code); t += 0.1
    c.req('step %d' % int((k - t) * 1000)); t = k
    p = os.path.join(shots, '%s-%03ds' % (a.tag, k)).replace('\\', '/')
    c.req('screenshot ' + p + '.png')
    txt = c.text()
    if isinstance(txt, str):
        open(p + '.txt', 'w').write(txt)
        lines = [l for l in txt.splitlines() if l.strip()]
        print('--- %ds text:' % k, *lines[:25], sep='\n  ', flush=True)
    else:
        print('--- %ds: graphics mode' % k, flush=True)
r = c.req('memr 0xc0000 32768')
open(os.path.join(raw, a.tag + '-c0000.bin'), 'wb').write(bytes.fromhex(r.get('data', '')))
c.req('quit')
c.f.close(); c.s.close()
