"""Minimal read-only UFS1 (FreeBSD) reader. Usage:
  ufs1.py <image> <part_offset_sectors> list            -> TSV manifest to stdout
  ufs1.py <image> <part_offset_sectors> extract <outdir> [maxsize]
Never writes to the image."""
import struct,sys,os,stat
class UFS:
    def __init__(s,path,partoff):
        s.f=open(path,'rb'); s.base=partoff*512
        sb=s.rd(8192,2048)
        assert struct.unpack_from('<I',sb,1372)[0]==0x011954,"not UFS1"
        g=lambda o:struct.unpack_from('<i',sb,o)[0]
        s.iblkno=g(16); s.cgoffset=g(24); s.cgmask=g(28); s.ncg=g(44)
        s.bsize=g(48); s.fsize=g(52); s.frag=g(56); s.fragshift=g(96)
        s.nindir=g(116); s.inopb=g(120); s.ipg=g(184); s.fpg=g(188)
        s.maxsymlink=g(1320) if g(1320)>0 else 60
        s.sb=sb
    def rd(s,off,n): s.f.seek(s.base+off); return s.f.read(n)
    def cgimin(s,c): return s.fpg*c + s.cgoffset*(c & ~s.cgmask) + s.iblkno
    def inode(s,ino):
        c=ino//s.ipg; fsba=s.cgimin(c)+(((ino%s.ipg)//s.inopb)<<s.fragshift)
        d=s.rd(fsba*s.fsize+(ino%s.inopb)*128,128)
        mode,nlink=struct.unpack_from('<HH',d,0); size=struct.unpack_from('<Q',d,8)[0]
        mtime=struct.unpack_from('<i',d,24)[0]
        db=struct.unpack_from('<12i',d,40); ib=struct.unpack_from('<3i',d,88)
        flags,blocks,gen,uid,gid=struct.unpack_from('<IiiII',d,100)
        return dict(ino=ino,mode=mode,nlink=nlink,size=size,mtime=mtime,db=db,ib=ib,flags=flags,blocks=blocks,uid=uid,gid=gid,raw=d)
    def ind(s,blk,level,out,need):
        if len(out)>=need: return
        if blk==0:
            out.extend([0]*min(need-len(out),s.nindir**(level+1))); return
        ptrs=struct.unpack('<%di'%s.nindir,s.rd(blk*s.fsize,s.bsize))
        for p in ptrs:
            if len(out)>=need: return
            if level==0: out.append(p)
            else: s.ind(p,level-1,out,need)
    def blocks(s,ino):
        need=(ino['size']+s.bsize-1)//s.bsize
        out=list(ino['db'][:need])
        for lvl,b in enumerate(ino['ib']):
            if len(out)>=need: break
            s.ind(b,lvl,out,need)
        return out
    def read(s,ino):
        if stat.S_ISLNK(ino['mode']) and ino['size']<s.maxsymlink and ino['blocks']==0:
            return ino['raw'][40:40+ino['size']]
        out=bytearray(); rem=ino['size']
        for b in s.blocks(ino):
            n=min(rem,s.bsize)
            out+= s.rd(b*s.fsize,n) if b else bytes(n); rem-=n
        return bytes(out)
    def readdir(s,ino):
        d=s.read(ino); o=0; res=[]
        while o<len(d):
            i,reclen,typ,nl=struct.unpack_from('<IHBB',d,o)
            if reclen==0: o=(o//512+1)*512; continue
            if i: res.append((d[o+8:o+8+nl].decode('latin1'),i))
            o+=reclen
        return res
    def walk(s,ino=2,path=''):
        for name,i in s.readdir(s.inode(ino)):
            if name in ('.','..'): continue
            n=s.inode(i); p=path+'/'+name
            yield p,n
            if stat.S_ISDIR(n['mode']): yield from s.walk(i,p)
if __name__=='__main__':
    img,off,cmd=sys.argv[1],int(sys.argv[2]),sys.argv[3]
    u=UFS(img,off)
    if cmd=='info':
        print(dict(bsize=u.bsize,fsize=u.fsize,ncg=u.ncg,ipg=u.ipg,fpg=u.fpg,fsmnt=u.sb[212:212+64].split(b'\0')[0]))
    elif cmd=='list':
        for p,n in u.walk():
            t=stat.filemode(n['mode']); extra=''
            if stat.S_ISLNK(n['mode']): extra=u.read(n).decode('latin1')
            print('%s\t%d\t%d\t%d:%d\t%s\t%s\t%s'%(t,n['size'],n['mtime'],n['uid'],n['gid'],hex(n['flags']),p,extra))
    elif cmd=='extract':
        out=sys.argv[4]; maxsz=int(sys.argv[5]) if len(sys.argv)>5 else 1<<40
        for p,n in u.walk():
            dst=os.path.join(out,p.lstrip('/'))
            m=n['mode']
            if stat.S_ISDIR(m): os.makedirs(dst,exist_ok=True)
            elif stat.S_ISREG(m) and n['size']<=maxsz:
                os.makedirs(os.path.dirname(dst),exist_ok=True)
                open(dst,'wb').write(u.read(n))
                try: os.utime(dst,(n['mtime'],n['mtime']))
                except: pass
            elif stat.S_ISLNK(m):
                os.makedirs(os.path.dirname(dst),exist_ok=True)
                open(dst+'.symlink','wb').write(u.read(n))
