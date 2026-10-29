"""Find out where a given 86Box machine's BIOS puts the PCI I/O BARs that the
TouchMaster kernel/sound hard-code (Rage 0xD800, ES1371 0xEF00).
For each machine: write analysis/p3/probe/<machine>/86box.cfg (same devices as
the main VM, the OEM working disk), start the automation build held, answer
the BIOS F1 prompt, boot the FreeBSD loader with 'boot -sv' (single user: /rw
is never mounted, the disk is not written), pull dmesg from RAM, quit.
  python -I scripts/p3-probe-bars.py <machine>[:<cpu_family>[:<hz>:<multi>]] ...
Writes analysis/p3/probe/<machine>/dmesg.txt and prints the PCI map lines."""
import os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
Auto = import_module('p3-auto').Auto

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXE = os.path.join(ROOT, 'analysis/p3/build86/src/86Box-Next2.exe')
ROMS = os.path.join(ROOT, '86box/roms')
DISK = os.path.join(ROOT, 'analysis/p3/vm/tm-oem.img').replace('\\', '/')
PORT = 7790
CFG = """[Machine]
machine = {m}
cpu_family = {cpu}
cpu_speed = {hz}
cpu_multi = {mul}
cpu_use_dynarec = 1
fpu_type = internal
mem_size = 65536
[Video]
gfxcard = {video}
[Input devices]
keyboard_type = keyboard_at
mouse_type = none
tablet_type = microtouch_touchpen
[Sound]
sndcard = es1371
[Hard disks]
hdd_01_fn = {disk}
hdd_01_ide_channel = 0:0
hdd_01_parameters = 63, 16, 16708, 0, ide
[Floppy and CD-ROM drives]
fdd_01_type = 35_2hd
fdd_02_type = none
cdrom_01_parameters = 0, none
[Network]
net_01_link = 0
"""

def probe(spec, video='mach64_rage2p'):
    p = spec.split(':')
    m = p[0]; cpu = p[1] if len(p) > 1 else 'pentium2_deschutes'
    hz = p[2] if len(p) > 2 else '350000000'; mul = p[3] if len(p) > 3 else '3.5'
    vm = os.path.join(ROOT, 'analysis/p3/probe', m)
    os.makedirs(vm, exist_ok=True)
    open(os.path.join(vm, '86box.cfg'), 'w').write(CFG.format(m=m, cpu=cpu, hz=hz, mul=mul, video=video, disk=DISK))
    tok = os.path.join(vm, 'automation.token')
    if os.path.exists(tok): os.remove(tok)
    proc = subprocess.Popen([EXE, '-P', vm, '-R', ROMS, '-N', '--automation', 'tcp:%d' % PORT, '--automation-hold'])
    for _ in range(100):
        if os.path.exists(tok): break
        time.sleep(0.2)
    time.sleep(0.5)
    a = Auto(vm, PORT)
    import socket                                   # release the GDB stub's initial stop
    try:
        g = socket.create_connection(('127.0.0.1', a.req('info').get('gdbstub_port', 12345)), timeout=2)
        g.sendall(b'+$c#63'); g.recv(10); g.close()
    except OSError: pass
    log = []
    say = lambda *x: print('   ..', m, *x, file=sys.stderr, flush=True)
    say('started', a.req('status').get('ms'))
    for _ in range(4):                              # up to 4 BIOS prompts (F1 / setup)
        r = a.req('wait text 25000 BTX loader')
        if r.get('matched'): break
        a.req('key down 0x3b'); a.req('step 100'); a.req('key up 0x3b'); log.append('F1')   # 'press F1' (CMOS defaults)
    say('bios', log)
    r = a.req('wait text 20000 Hit [Enter]')
    say('loader prompt', r)
    a.req('key down 0x39'); a.req('step 100'); a.req('key up 0x39'); a.req('step 300')
    a.type('boot -sv\n')
    r = a.req('wait text 60000 Enter full pathname')
    say('single user', r)
    shot = os.path.join(vm, 'screen.png').replace('\\', '/')
    a.req('screenshot ' + shot)
    out = os.path.join(vm, 'dmesg.txt')
    a.f.close(); a.s.close()                        # the socket takes one client at a time
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts/p3-msgbuf.py'), vm, str(PORT), out])
    try: Auto(vm, PORT).req('quit')
    except Exception: pass
    proc.wait(30)
    d = open(out).read() if os.path.exists(out) else ''
    print('=== %s (%s) single-user reached: %s  %s' % (m, cpu, r.get('matched'), ' '.join(log)))
    cur = None
    for line in d.splitlines():
        if re.search(r'got probed|^\s*map\[|<.*> .*on pci|^(rag|est)\d', line):
            print('   ' + line.strip())

if __name__ == '__main__':
    for s in sys.argv[1:]:
        try: probe(s)
        except Exception as e:                      # keep going; never leave a VM running
            print('=== %s FAILED: %r' % (s, e))
            subprocess.run(['taskkill', '/F', '/IM', os.path.basename(EXE)], capture_output=True)
            time.sleep(1)
