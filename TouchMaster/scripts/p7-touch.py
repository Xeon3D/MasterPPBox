"""Touch the screen at x,y (frame pixels) through the automation socket, then
run <ms> and screenshot to <png>.
  python -I scripts/p7-touch.py <vmdir> <port> <x> <y> <ms> <png>"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
a = import_module('p3-auto').Auto(sys.argv[1], sys.argv[2])
x, y, ms = sys.argv[3], sys.argv[4], int(sys.argv[5])
png = os.path.abspath(sys.argv[6]).replace(os.sep, '/')
for r in ('tablet %s %s 1' % (x, y), 'step 150', 'tablet %s %s 0' % (x, y), 'step 50', 'tablet out',
          'step %d' % ms, 'screenshot ' + png):
    out = a.req(r)
    if not out.get('ok'):
        print(r, out)
print(out)
