# p6: prefix each line of a pdftotext -layout file with its PDF page number (pages split on \f)
import sys
src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding='utf-8', errors='replace') as f, open(dst, 'w', encoding='utf-8') as o:
    for n, page in enumerate(f.read().split('\f'), 1):
        for line in page.splitlines():
            o.write(f"p{n}: {line}\n")
