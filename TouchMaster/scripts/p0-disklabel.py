import struct,sys
for path in sys.argv[1:]:
    f=open(path,'rb'); f.seek(512); d=f.read(512)
    off=d.find(struct.pack('<I',0x82564557))
    print("==",path,"label@",512+off)
    l=d[off:]
    magic,typ,subtype=struct.unpack_from('<IHH',l,0)
    typename=l[8:24].rstrip(b'\0'); packname=l[24:40].rstrip(b'\0')
    secsize,nsect,ntrack,ncyl,secpercyl,secperunit=struct.unpack_from('<IIIIII',l,40)
    print("type",typ,"typename",typename,"packname",packname)
    print("secsize",secsize,"nsect",nsect,"ntrack",ntrack,"ncyl",ncyl,"secpercyl",secpercyl,"secperunit",secperunit, secperunit*secsize/1e9,"GB")
    npart,bbsize,sbsize=struct.unpack_from('<HII',l,138)
    print("npart",npart)
    for i in range(npart):
        size,offset,fsize,fstype,frag,cpg=struct.unpack_from('<IIIBBH',l,148+16*i)
        if size: print(" %s: size=%d (%.1f MB) off=%d fstype=%d fsize=%d frag=%d cpg=%d"%(chr(97+i),size,size/2048,offset,fstype,fsize,frag,cpg))
