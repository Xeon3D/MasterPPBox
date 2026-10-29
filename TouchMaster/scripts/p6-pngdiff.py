"""p6: count differing bytes between pairs of PNG frames, with p5-contact's stdlib reader.
  python -I scripts/p6-pngdiff.py <a.png> <b.png> [<a.png> <b.png> ...]"""
import os, sys
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, 'p5-contact.py')).read()
_ns = {}
exec(_src.split('\nout, cols, k')[0], _ns)  # p5-contact has no __main__ guard
read_png = _ns['read_png']
args = sys.argv[1:]
for a, b in zip(args[0::2], args[1::2]):
    A, B = read_png(a), read_png(b)
    print(os.path.basename(a), os.path.basename(b), 'size', A[:2], B[:2], end=' ')
    if A[:2] != B[:2]:
        print('SIZE DIFFERS')
        continue
    n = sum(1 for x, y in zip(A[2], B[2]) if x != y)
    print('diff', n, 'of', len(A[2]))
