"""Type digits on TouchMaster's numeric keypad screen (diag GetNumFromUser:
1-9 in a 3x3 grid from (67,95), 0 at (167,393)), press OK, screenshot.
  python -I scripts/p8-keypad.py <vmdir> <port> <digits> <png> [settle_ms]"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
a = import_module('p3-auto').Auto(sys.argv[1], sys.argv[2])
keys = {str(n): (67 + ((n - 1) % 3) * 100, 95 + ((n - 1) // 3) * 99) for n in range(1, 10)}
keys['0'] = (167, 393)
def touch(x, y, ms=600):
    for r in ('tablet %d %d 1' % (x, y), 'step 120', 'tablet %d %d 0' % (x, y), 'step 40', 'tablet out', 'step %d' % ms):
        a.req(r)
for ch in sys.argv[3]:
    touch(*keys[ch])
touch(478, 341, int(sys.argv[5]) if len(sys.argv) > 5 else 4000)
print(a.req('screenshot ' + os.path.abspath(sys.argv[4]).replace(os.sep, '/')))
