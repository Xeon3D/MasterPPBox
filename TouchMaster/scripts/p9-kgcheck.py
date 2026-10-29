"""Check 86Box's dolphin_keygen.c against scripts/p1-mkchips.py: build the C
generator standalone in WSL (32-bit and 64-bit), run both over a matrix of
serials, countries, versions, times and seeds, and compare the images byte
for byte.
  python -I scripts/p9-kgcheck.py"""
import hashlib, itertools, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'F:/Claude/86Box-Next2-touchmaster/src'
OUT = os.path.join(ROOT, 'analysis', 'p9', 'kg')
os.makedirs(OUT, exist_ok=True)

def wsl(p):
    p = os.path.abspath(p).replace('\\', '/')
    return '/mnt/' + p[0].lower() + p[2:]

builds = {}
for bits in ('32', '64'):
    exe = os.path.join(OUT, 'kgtest%s' % bits)
    cmd = 'gcc -m%s -O2 -Wall -I %s/include %s/device/dolphin_keygen.c %s -o %s' % (
        bits, wsl(SRC), wsl(SRC), wsl(os.path.join(ROOT, 'analysis/p9/kgtest.c')), wsl(exe))
    r = subprocess.run(['wsl', '-e', 'sh', '-c', cmd], capture_output=True, text=True)
    if r.returncode:
        sys.exit('build %s failed:\n%s' % (bits, r.stderr))
    builds[bits] = exe

serials = [100922889, 60000922889, 60068100468, 90012345678, 1, 99999999999999]
countries = [1, 22, 24, 29, 99]
versions = [(1, 0), (3, 0), (3, 2)]
times = [971100000, 1793000000]
seeds = [0x12345678, 0xFFFFFFF0, 7]
fails = n = 0
for serial, country, (maj, mi), t, seed in itertools.product(serials, countries, versions, times, seeds):
    py = [os.path.join(OUT, 'py_u9.nvr'), os.path.join(OUT, 'py_ab.nvr')]
    subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'scripts/p1-mkchips.py'), '--serial', str(serial),
                    '--country', str(country), '--version', '%d.%d' % (maj, mi), '--time', str(t),
                    '--devseed', hex(seed), '--out-u9', py[0], '--out-abyss', py[1]],
                   check=True, capture_output=True)
    ref = [open(p, 'rb').read() for p in py]
    for bits, exe in builds.items():
        c = [os.path.join(OUT, 'c%s_u9.nvr' % bits), os.path.join(OUT, 'c%s_ab.nvr' % bits)]
        subprocess.run(['wsl', '-e', wsl(exe), str(serial), str(country), str(maj), str(mi), str(t), str(seed),
                        wsl(c[0]), wsl(c[1])], check=True)
        got = [open(p, 'rb').read() for p in c]
        n += 1
        if got != ref:
            fails += 1
            print('MISMATCH', bits, serial, country, maj, mi, t, hex(seed),
                  [i for i in range(257) if got[0][i] != ref[0][i]][:8], [i for i in range(257) if got[1][i] != ref[1][i]][:8])
print('%d comparisons, %d mismatches' % (n, fails))
