"""Sample where the guest CPU is: EIP/CR3 histogram over N steps of <ms> each.
  python -I scripts/p3-sample.py <vmdir> <port> [n=300] [ms=7]"""
import collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module
A = import_module('p3-auto').Auto(sys.argv[1], sys.argv[2])
n = int(sys.argv[3]) if len(sys.argv) > 3 else 300; ms = int(sys.argv[4]) if len(sys.argv) > 4 else 7
c = collections.Counter(); cr3 = collections.Counter()
for i in range(n):
    A.req('step %d' % ms)
    r = A.req('regs')
    c['%08x' % r['eip']] += 1; cr3['%08x' % r.get('cr3', 0)] += 1
print('eip:', c.most_common(30)); print('cr3:', cr3.most_common(10))
