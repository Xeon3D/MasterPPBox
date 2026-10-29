"""Semantic diff of two ELF32 relocatable objects, function by function:
disassemble, replace intra-.text call/jump targets by 'func+off' and
relocated operands by symbol names, then compare instruction streams.
  python -I scripts/p2-objdiff.py <a.o> <b.o> [func ...]"""
import difflib, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capstone
from importlib import import_module
objmatch = import_module('p2-objmatch')

def norm(ob):
    text = ob.sec['.text']; td = ob.secdata(text)
    funcs = sorted([s for s in ob.syms if s[4] == text and (s[3] & 0xf) == 2 and s[2]], key=lambda s: s[1])
    relat = {o: ob.syms[si] for o, si, t in ob.rel.get(text, [])}
    def fname(off):
        for n, v, sz, i, x in funcs:
            if v <= off < v + sz: return '%s+0x%x' % (n, off - v)
        return hex(off)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    out = {}
    for n, v, sz, i, x in funcs:
        lines = []
        for ins in md.disasm(td[v:v + sz], v):
            ops = ins.op_str
            for k in range(ins.address, ins.address + ins.size):
                if k in relat:
                    rn = relat[k][0] or ob.name[relat[k][4]] if relat[k][4] < len(ob.name) else relat[k][0]
                    ops += '  ; reloc ' + (relat[k][0] or ob.name[relat[k][4]])
                    break
            if ins.mnemonic.startswith('j') or ins.mnemonic == 'call':
                m = re.fullmatch(r'0x([0-9a-f]+)', ins.op_str)
                if m:
                    t = int(m.group(1), 16)
                    ops = (('<%s>' % fname(t)) if not (v <= t < v + sz) else '.+0x%x' % (t - v)) + ops[len(ins.op_str):]
            lines.append('%s %s' % (ins.mnemonic, ops))
        out[n] = lines
    return out

a, b = norm(objmatch.Obj(sys.argv[1])), norm(objmatch.Obj(sys.argv[2]))
only = sys.argv[3:]
for n in sorted(set(a) | set(b)):
    if only and n not in only: continue
    if n not in a or n not in b:
        print('ONLY IN %s: %s' % ('A' if n in a else 'B', n)); continue
    if a[n] == b[n]:
        print('SAME     %s' % n)
    else:
        print('DIFFERS  %s (%d vs %d insns)' % (n, len(a[n]), len(b[n])))
        if only:
            for l in difflib.unified_diff(a[n], b[n], 'a', 'b', lineterm='', n=1): print('    ' + l)
