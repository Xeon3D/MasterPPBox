"""Minimal client for the 86Box automation socket (doc/specifications/automation.md).
  python -I scripts/p3-auto.py <vmdir> <port> "<request>" ["<request>" ...]
Reads the token from <vmdir>/automation.token, sends each request, prints each
JSON reply on one line. Special pseudo-requests:
  textdump            -> 'text' rendered as plain rows (CP437 -> ascii-ish)
  type <string>       -> types the string with set-1 scancodes (a-z 0-9 space - . / = enter as \\n)
"""
import json, os, socket, sys

SC = {**{c: s for c, s in zip('1234567890-=', range(0x02, 0x0E))},
      **{c: s for c, s in zip('qwertyuiop[]', range(0x10, 0x1C))},
      **{c: s for c, s in zip("asdfghjkl;'", range(0x1E, 0x29))},
      **{c: s for c, s in zip('zxcvbnm,./', range(0x2C, 0x36))},
      ' ': 0x39, '\n': 0x1C, '`': 0x29, '\\': 0x2B}
SHIFTED = {'!': '1', '@': '2', '#': '3', '$': '4', '%': '5', '^': '6', '&': '7', '*': '8',
           '(': '9', ')': '0', '_': '-', '+': '=', ':': ';', '"': "'", '<': ',', '>': '.',
           '?': '/', '|': '\\', '~': '`'}

class Auto:
    def __init__(self, vmdir, port):
        self.s = socket.create_connection(('127.0.0.1', int(port)))
        self.f = self.s.makefile('rwb')
        tok = open(os.path.join(vmdir, 'automation.token')).read().strip()
        r = self.req('auth ' + tok)
        if not r.get('ok'): sys.exit('auth failed: %r' % r)
    def req(self, line):
        self.f.write((line + '\n').encode()); self.f.flush()
        return json.loads(self.f.readline())
    def text(self):
        r = self.req('text')
        if not r.get('ok'): return r
        rows = [bytes.fromhex(h).decode('cp437').encode('ascii', 'replace').decode().rstrip() for h in r['chars']]
        return '\n'.join(rows)
    def type(self, s):
        for ch in s:
            shift = ch.isupper() or ch in SHIFTED
            base = SHIFTED.get(ch, ch.lower())
            codes = [SC[base]]
            if shift: self.req('key down 0x2a')
            self.req('key down %#x' % codes[0]); self.req('key up %#x' % codes[0])
            if shift: self.req('key up 0x2a')
        return {'ok': True, 'typed': len(s)}

if __name__ == '__main__':
    a = Auto(sys.argv[1], sys.argv[2])
    for q in sys.argv[3:]:
        if q == 'textdump': print(a.text())
        elif q.startswith('type '): print(json.dumps(a.type(q[5:].encode().decode('unicode_escape'))))
        else: print(json.dumps(a.req(q)))
