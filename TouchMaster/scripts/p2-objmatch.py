"""Find every function of a relocatable ELF32 object (.o) inside linked
executables, with relocated fields wildcarded, and check that the data the
code references (tables) is byte-identical too.
  python -I scripts/p2-objmatch.py <obj.o> <exe> [<exe> ...]
Output: per exe, per function: MATCH@vaddr / MISSING / MULTI, plus data checks."""
import re, struct, sys

def u(fmt, d, o): return struct.unpack_from('<' + fmt, d, o)

class Obj:
    def __init__(s, path):
        d = s.d = open(path, 'rb').read()
        shoff, = u('I', d, 32); shes, shn, shstr = u('HHH', d, 46)
        s.sh = [u('10I', d, shoff + i * shes) for i in range(shn)]
        names = s.sh[shstr]
        s.name = [d[names[4] + h[0]:d.index(b'\0', names[4] + h[0])].decode() for h in s.sh]
        s.syms = []
        for i, h in enumerate(s.sh):
            if h[1] == 2:
                st = s.sh[h[6]]
                for o in range(h[4], h[4] + h[5], 16):
                    nm, val, sz, info, oth, shx = u('IIIBBH', d, o)
                    n = d[st[4] + nm:d.index(b'\0', st[4] + nm)].decode()
                    s.syms.append((n, val, sz, info, shx))
        s.sec = {n: i for i, n in enumerate(s.name)}
        s.rel = {}                                   # target sec idx -> [(off, symidx, type)]
        for h in s.sh:
            if h[1] == 9:
                s.rel.setdefault(h[7], []).extend(
                    (lambda o, i: (o, i >> 8, i & 0xff))(*u('II', d, o)) for o in range(h[4], h[4] + h[5], 8))
    def secdata(s, idx): h = s.sh[idx]; return s.d[h[4]:h[4] + h[5]]

class Exe:
    def __init__(s, path):
        s.d = open(path, 'rb').read()
        phoff, = u('I', s.d, 28); phes, phn = u('HH', s.d, 42)
        s.ph = [u('8I', s.d, phoff + i * phes) for i in range(phn)]
    def off(s, va):
        for p in s.ph:
            if p[0] == 1 and p[2] <= va < p[2] + p[4]: return va - p[2] + p[1]
    def va(s, off):
        for p in s.ph:
            if p[0] == 1 and p[1] <= off < p[1] + p[4]: return off - p[1] + p[2]

def main():
    ob = Obj(sys.argv[1]); text = ob.sec['.text']; tdata = ob.secdata(text)
    rels = sorted(ob.rel.get(text, []))
    funcs = [s for s in ob.syms if s[4] == text and (s[3] & 0xf) == 2 and s[2]]
    for path in sys.argv[2:]:
        ex = Exe(path); print('==', path)
        found = {}; bad = 0
        for name, val, sz, info, shx in funcs:
            code = bytearray(tdata[val:val + sz]); wild = set()
            for o, si, t in rels:
                if val <= o < val + sz:
                    wild.update(range(o - val, min(o - val + 4, sz)))
            pat = b''.join(b'.' if i in wild else re.escape(bytes([code[i]])) for i in range(sz))
            hits = [m.start() for m in re.finditer(pat, ex.d, re.S)]
            if len(hits) == 1:
                found[name] = (val, hits[0]); print('  MATCH   %-28s %5d bytes @ %08x' % (name, sz, ex.va(hits[0])))
            else:
                bad += 1; print('  %-7s %-28s %5d bytes (%d hits)' % ('MISSING' if not hits else 'MULTI', name, sz, len(hits)))
        # data referenced via absolute relocations: compare contents
        checked = set()
        for o, si, t in rels:
            n, sval, ssz, sinfo, sshx = ob.syms[si]
            fn = next((f for f in found if found[f][0] <= o < found[f][0] + ob.syms[[x[0] for x in ob.syms].index(f)][2]), None)
            if t != 1 or not fn or sshx in (0, text) or sshx >= len(ob.sh): continue
            fo = found[fn][1] + (o - found[fn][0])
            target_va, = u('I', ex.d, fo)
            add, = u('I', tdata, o)
            secname = ob.name[sshx]
            if ob.sh[sshx][1] == 8:                  # .bss: nothing to compare
                continue
            key = (secname, add if (sinfo & 0xf) == 3 else sval)
            if key in checked: continue
            checked.add(key)
            base = target_va - (add if (sinfo & 0xf) == 3 else 0)
            src = ob.secdata(sshx)
            if (sinfo & 0xf) == 3:                    # section symbol + addend: compare 64 bytes from addend
                lo, hi = add, min(len(src), add + 64)
                ref = src[lo:hi]; got = ex.d[ex.off(target_va):ex.off(target_va) + len(ref)]
                label = '%s+0x%x' % (secname, add)
            else:
                ref = src[sval:sval + ssz]; got = ex.d[ex.off(target_va):ex.off(target_va) + len(ref)]
                label = n
            same = ref == got
            bad += 0 if same else 1
            print('  DATA    %-28s %3d bytes %s' % (label, len(ref), 'identical' if same else 'DIFFERENT'))
        print('  -> %s' % ('ALL IDENTICAL' if not bad else '%d difference(s)' % bad))

if __name__ == '__main__':
    main()
