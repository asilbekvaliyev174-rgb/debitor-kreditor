import struct, sys

def read_file(path):
    with open(path,'rb') as f:
        return f.read()

class OLE:
    def __init__(self, data):
        self.data = data
        assert data[:8] == bytes.fromhex('d0cf11e0a1b11ae1'), 'not OLE2'
        self.sector_shift = struct.unpack_from('<H', data, 30)[0]
        self.mini_shift = struct.unpack_from('<H', data, 32)[0]
        self.sec_size = 1 << self.sector_shift
        self.mini_size = 1 << self.mini_shift
        self.num_fat = struct.unpack_from('<I', data, 44)[0]
        self.dir_start = struct.unpack_from('<I', data, 48)[0]
        self.mini_cutoff = struct.unpack_from('<I', data, 56)[0]
        self.minifat_start = struct.unpack_from('<I', data, 60)[0]
        self.num_minifat = struct.unpack_from('<I', data, 64)[0]
        self.difat_start = struct.unpack_from('<I', data, 68)[0]
        self.num_difat = struct.unpack_from('<I', data, 72)[0]
        self._build_difat()
        self._build_fat()
        self._read_dir()
        self._build_minifat()

    def sector_offset(self, sid):
        return 512 + sid * self.sec_size

    def read_sector(self, sid):
        off = self.sector_offset(sid)
        return self.data[off:off+self.sec_size]

    def _build_difat(self):
        self.difat = []
        for i in range(109):
            v = struct.unpack_from('<I', self.data, 76 + i*4)[0]
            if v == 0xFFFFFFFF: break
            self.difat.append(v)
        sid = self.difat_start
        ENDOFCHAIN = 0xFFFFFFFE
        cnt = 0
        while sid != ENDOFCHAIN and sid != 0xFFFFFFFF and cnt < self.num_difat:
            sec = self.read_sector(sid)
            n = self.sec_size // 4
            for i in range(n-1):
                v = struct.unpack_from('<I', sec, i*4)[0]
                if v != 0xFFFFFFFF:
                    self.difat.append(v)
            sid = struct.unpack_from('<I', sec, (n-1)*4)[0]
            cnt += 1

    def _build_fat(self):
        fat = bytearray()
        for sid in self.difat:
            fat += self.read_sector(sid)
        self.fat = list(struct.unpack('<%dI' % (len(fat)//4), bytes(fat)))

    def chain(self, start):
        ENDOFCHAIN = 0xFFFFFFFE
        out = []
        sid = start
        while sid != ENDOFCHAIN and sid != 0xFFFFFFFF and sid < len(self.fat):
            out.append(sid)
            sid = self.fat[sid]
            if len(out) > 1000000: break
        return out

    def read_stream_fat(self, start, size=None):
        out = bytearray()
        for sid in self.chain(start):
            out += self.read_sector(sid)
        if size is not None:
            out = out[:size]
        return bytes(out)

    def _read_dir(self):
        dirdata = self.read_stream_fat(self.dir_start)
        self.entries = []
        for i in range(0, len(dirdata), 128):
            ent = dirdata[i:i+128]
            if len(ent) < 128: break
            namelen = struct.unpack_from('<H', ent, 64)[0]
            if namelen == 0:
                self.entries.append(None); continue
            name = ent[:namelen-2].decode('utf-16-le', 'replace')
            objtype = ent[66]
            start = struct.unpack_from('<I', ent, 116)[0]
            sz = struct.unpack_from('<I', ent, 120)[0]
            self.entries.append({'name':name,'type':objtype,'start':start,'size':sz})

    def _build_minifat(self):
        mf = self.read_stream_fat(self.minifat_start)
        self.minifat = list(struct.unpack('<%dI' % (len(mf)//4), mf)) if mf else []
        # root entry holds mini stream
        root = None
        for e in self.entries:
            if e and e['type']==5:
                root=e; break
        self.ministream = self.read_stream_fat(root['start'], root['size']) if root else b''

    def mini_chain(self, start):
        ENDOFCHAIN = 0xFFFFFFFE
        out=[]; sid=start
        while sid != ENDOFCHAIN and sid != 0xFFFFFFFF and sid < len(self.minifat):
            out.append(sid); sid=self.minifat[sid]
            if len(out)>1000000: break
        return out

    def read_stream(self, name):
        e = None
        for x in self.entries:
            if x and x['name']==name:
                e=x; break
        if e is None: return None
        if e['size'] >= self.mini_cutoff:
            return self.read_stream_fat(e['start'], e['size'])
        # mini
        out=bytearray()
        for sid in self.mini_chain(e['start']):
            off = sid*self.mini_size
            out += self.ministream[off:off+self.mini_size]
        return bytes(out[:e['size']])

# ---------- BIFF8 parsing ----------
def parse_biff(stream):
    pos = 0
    records = []
    n = len(stream)
    while pos + 4 <= n:
        rec, size = struct.unpack_from('<HH', stream, pos)
        pos += 4
        data = stream[pos:pos+size]
        pos += size
        records.append((rec, data))
    return records

def parse_unicode_string(data, pos):
    # standalone version (for LABEL records, no continue crossing)
    cch = struct.unpack_from('<H', data, pos)[0]; pos+=2
    flags = data[pos]; pos+=1
    fHighByte = flags & 0x01
    fExtSt = (flags>>2)&1
    fRichSt = (flags>>3)&1
    crun=0; cbExt=0
    if fRichSt:
        crun = struct.unpack_from('<H', data, pos)[0]; pos+=2
    if fExtSt:
        cbExt = struct.unpack_from('<I', data, pos)[0]; pos+=4
    if fHighByte:
        s = data[pos:pos+cch*2].decode('utf-16-le','replace'); pos+=cch*2
    else:
        s = data[pos:pos+cch].decode('latin-1','replace'); pos+=cch
    if fRichSt: pos += crun*4
    if fExtSt: pos += cbExt
    return s, pos


class SSTReader:
    """Segment-aware reader for BIFF8 SST that correctly handles CONTINUE
    boundaries, where a split inside character data repeats the flags byte."""
    def __init__(self, segments):
        self.segments = segments  # list of bytes
        self.seg = 0
        self.pos = 0

    def _advance_if_needed(self):
        while self.seg < len(self.segments) and self.pos >= len(self.segments[self.seg]):
            self.seg += 1
            self.pos = 0

    def eof(self):
        self._advance_if_needed()
        return self.seg >= len(self.segments)

    def read_raw(self, n):
        # read n bytes, crossing segment boundaries WITHOUT consuming flag byte
        out = bytearray()
        while n > 0:
            self._advance_if_needed()
            if self.seg >= len(self.segments):
                break
            cur = self.segments[self.seg]
            take = min(n, len(cur) - self.pos)
            out += cur[self.pos:self.pos+take]
            self.pos += take
            n -= take
        return bytes(out)

    def read_u16(self):
        return struct.unpack('<H', self.read_raw(2))[0]

    def read_u8(self):
        return self.read_raw(1)[0]

    def read_chars(self, cch, high_byte):
        # read cch characters; on crossing a segment boundary mid-data a new
        # flags byte is present that may change the encoding width
        chars = []
        i = 0
        while i < cch:
            self._advance_if_needed()
            if self.seg >= len(self.segments):
                break
            cur = self.segments[self.seg]
            remaining_in_seg = len(cur) - self.pos
            if high_byte:
                can = remaining_in_seg // 2
                if can <= 0:
                    # need to cross; consumed below
                    pass
                take = min(cch - i, can)
                if take > 0:
                    chunk = cur[self.pos:self.pos+take*2]
                    chars.append(chunk.decode('utf-16-le', 'replace'))
                    self.pos += take*2
                    i += take
            else:
                take = min(cch - i, remaining_in_seg)
                if take > 0:
                    chunk = cur[self.pos:self.pos+take]
                    chars.append(chunk.decode('latin-1', 'replace'))
                    self.pos += take
                    i += take
            if i < cch:
                # cross boundary: move to next segment and read flag byte
                self.seg += 1
                self.pos = 0
                if self.seg >= len(self.segments):
                    break
                flag = self.segments[self.seg][self.pos]
                self.pos += 1
                high_byte = flag & 0x01
        return ''.join(chars)

    def read_string(self):
        cch = self.read_u16()
        flags = self.read_u8()
        fHighByte = flags & 0x01
        fExtSt = (flags >> 2) & 1
        fRichSt = (flags >> 3) & 1
        crun = 0; cbExt = 0
        if fRichSt:
            crun = self.read_u16()
        if fExtSt:
            cbExt = struct.unpack('<I', self.read_raw(4))[0]
        s = self.read_chars(cch, fHighByte)
        if fRichSt:
            self.read_raw(crun * 4)
        if fExtSt:
            self.read_raw(cbExt)
        return s

def main(path):
    data = read_file(path)
    ole = OLE(data)
    print('STREAMS:', [e['name'] for e in ole.entries if e], file=sys.stderr)
    wb = ole.read_stream('Workbook') or ole.read_stream('Book')
    recs = parse_biff(wb)
    # Build SST
    sst = []
    i=0
    # find SST record (0x00FC) - may have continues
    # We need to handle CONTINUE records concatenation for SST
    # Reconstruct full SST blob
    full = None
    rec_list = recs
    # gather: find SST then following CONTINUE (0x003C)
    sst_segments = None
    for idx,(rec,d) in enumerate(rec_list):
        if rec == 0x00FC:
            total, unique = struct.unpack_from('<II', d, 0)
            segs = [d[8:]]
            j = idx+1
            while j < len(rec_list) and rec_list[j][0]==0x003C:
                segs.append(rec_list[j][1])
                j+=1
            sst_segments = segs
            break
    if sst_segments:
        reader = SSTReader(sst_segments)
        for k in range(unique):
            if reader.eof():
                break
            try:
                sst.append(reader.read_string())
            except Exception:
                break
    # Now parse cells per sheet
    rows = {}  # sheet index -> list of (row,col,value)
    cur_sheet = 0
    sheets_cells = []
    cells = []
    for rec,d in rec_list:
        if rec == 0x0809:  # BOF
            pass
        elif rec == 0x00FD:  # LABELSST
            row,col,xf,isst = struct.unpack_from('<HHHI', d, 0)
            val = sst[isst] if isst < len(sst) else ''
            cells.append((row,col,val))
        elif rec == 0x0204:  # LABEL
            row,col,xf = struct.unpack_from('<HHH', d, 0)
            s,_ = parse_unicode_string(d, 6)
            cells.append((row,col,s))
        elif rec == 0x0203:  # NUMBER
            row,col,xf = struct.unpack_from('<HHH', d, 0)
            num = struct.unpack_from('<d', d, 6)[0]
            cells.append((row,col,num))
        elif rec == 0x027E:  # RK
            row,col,xf = struct.unpack_from('<HHH', d, 0)
            rk = struct.unpack_from('<i', d, 6)[0]
            cells.append((row,col,rk_value(rk)))
        elif rec == 0x00BD:  # MULRK
            row,col1 = struct.unpack_from('<HH', d, 0)
            pos=4
            c=col1
            while pos+6 <= len(d)-2:
                xf,rk = struct.unpack_from('<Hi', d, pos)
                cells.append((row,c,rk_value(rk)))
                pos+=6; c+=1
        elif rec == 0x0006 or rec==0x0406:  # FORMULA
            row,col,xf = struct.unpack_from('<HHH', d, 0)
            # result
            res = d[6:14]
            if res[6:8]==b'\xff\xff':
                # string/bool/error
                pass
            else:
                num = struct.unpack_from('<d', res, 0)[0]
                cells.append((row,col,num))
    print_cells(cells)

def rk_value(rk):
    cents = rk & 1
    isint = rk & 2
    v = rk >> 2
    if isint:
        val = v
    else:
        # the int part shifted is the top 30 bits of a double
        val = struct.unpack('<d', struct.pack('<q', (rk & 0xFFFFFFFC) << 32))[0]
    if cents:
        val = val/100.0
    return val

def print_cells(cells):
    if not cells:
        print('NO CELLS'); return
    maxrow = max(c[0] for c in cells)
    maxcol = max(c[1] for c in cells)
    grid = {}
    for r,c,v in cells:
        grid[(r,c)] = v
    import csv
    out = []
    for r in range(maxrow+1):
        rowvals=[]
        for c in range(maxcol+1):
            v = grid.get((r,c),'')
            rowvals.append(v)
        out.append(rowvals)
    w = csv.writer(sys.stdout)
    for row in out:
        w.writerow([fmt(x) for x in row])

def fmt(x):
    if isinstance(x,float):
        if x==int(x): return str(int(x))
        return repr(x)
    return str(x)

if __name__=='__main__':
    main(sys.argv[1])
