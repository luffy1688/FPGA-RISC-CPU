"""Decode captured single-bit Qt QString rows in Pango WDF; preserve originals."""
from pathlib import Path
import argparse,struct,json,hashlib,re,statistics,csv
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def channel(blob,name,depth):
    encoded=name.encode('utf-16-be'); found=[]; start=0
    while True:
        pos=blob.find(encoded,start)
        if pos<0: break
        start=pos+2; tail=pos+len(encoded)
        if pos<4 or struct.unpack_from('>I',blob,pos-4)[0]!=len(encoded) or tail+8>len(blob): continue
        width,nbytes=struct.unpack_from('>II',blob,tail)
        if width!=1 or nbytes!=depth*2 or tail+8+nbytes>len(blob): continue
        text=blob[tail+8:tail+8+nbytes].decode('utf-16-be')
        if len(text)==depth and set(text)<=set('01xXzZ'): found.append(text)
    if len(found)!=1: raise ValueError(f'{name}: expected exactly one {depth}-sample row, found {len(found)}')
    return found[0]
def decode(path,meta):
    blob=path.read_bytes()
    if struct.unpack_from('>I',blob,0)[0]!=len(blob)-4: raise ValueError('WDF outer record length mismatch')
    depth=meta['depth']; fields={}; project=path.with_suffix('.dprj').read_text()
    for field in meta['fields']:
        names=field.get('nets',[field['name']])
        rows=[]
        for i,n in enumerate(names):
            expected=f'.DataChannel<{field["lsb"]+i}>={n}'
            if expected not in project: raise ValueError('DPRJ channel association missing: '+expected)
            rows.append(channel(blob,n,depth))
        values=[]
        for j in range(depth):
            if any(row[j] not in '01' for row in rows): values.append(None)
            else: values.append(sum((row[j]=='1')<<i for i,row in enumerate(rows)))
        fields[field['name']]=values
    return fields

def elf_context(root,elf=None,mem=None,built_mem=None,hashes=False):
    import subprocess,shutil
    elf=Path(elf)if elf else root/'07_runs/model/interactive.elf'
    mem=Path(mem)if mem else root/'06_pango/firmware/model_interactive.mem'
    built_mem=Path(built_mem)if built_mem else root/'07_runs/model/interactive.mem'
    words=[int(x,16) for x in mem.read_text().split()]
    meta={'elf':str(elf),'firmware_mem':str(mem),'built_mem_matches_board':built_mem.read_bytes()==mem.read_bytes()}
    if hashes:meta.update(elf_sha256=sha(elf),firmware_mem_sha256=sha(mem))
    candidates=[shutil.which('riscv32-unknown-elf-objcopy'),'/opt/Andestech/toolchains/nds32le-elf-mculib-v5/bin/riscv32-unknown-elf-objcopy']
    obj=next((p for p in candidates if p and Path(p).is_file()),None)
    if obj:
        b=subprocess.run([obj,'-O','binary',str(elf),'/dev/stdout'],capture_output=True,timeout=20)
        data=b''.join(w.to_bytes(4,'little') for w in words)
        meta['elf_binary_matches_board_mem']=b.returncode==0 and bool(b.stdout) and data[:len(b.stdout)]==b.stdout and not any(data[len(b.stdout):])
    symbols=subprocess.run(['readelf','-sW',str(elf)],capture_output=True,text=True,check=True,timeout=10)
    funcs=[]
    for line in symbols.stdout.splitlines():
        a=line.split()
        if len(a)>=8 and a[3]=='FUNC' and int(a[2])>0:funcs.append((int(a[1],16),int(a[2]),a[-1]))
    return meta,funcs,words

def bounds(values):
    v=[x for x in values if x is not None]
    return {'min':min(v) if v else None,'max':max(v) if v else None,'unknown_samples':len(values)-len(v)}
def edges(v,a,b): return [i for i in range(1,len(v)) if v[i-1]==a and v[i]==b]
def run(folder,map_path,elf=None,mem=None,built_mem=None,hashes=False):
    context,functions,firmware_words=elf_context(Path(__file__).resolve().parents[2],elf,mem,built_mem,hashes)
    if elf is not None:
        assert context['built_mem_matches_board'] and context.get('elf_binary_matches_board_mem'), 'New companion ELF/ROM lineage mismatch'
    mapping=json.loads(map_path.read_text()); report={'scope':'Actual FPGA ILA samples; internal pre-pad GPIO; no external probe or measured-frequency claim','signal_map':str(map_path),'elf_lineage':context,'hashes_recorded':hashes,'captures':{}}
    for tag,core in [('adc_a',0),('adc_b',0),('pwm25',1),('coremark',0),('xnd',0)]:
        p=folder/(tag+'.wdf')
        if not p.exists(): continue
        meta=mapping['core'+str(core)]; f=decode(p,meta)
        out={'wdf':str(p),'sample_clock_hz':meta.get('sample_clock_hz',mapping['clock_hz_reference']),'depth':meta['depth'],'width':meta['width'],'fields':{n:bounds(v) for n,v in f.items()}}
        if hashes:out.update(wdf_sha256=sha(p),project_sha256=sha(p.with_suffix('.dprj')))
        if core==0:
            valid=f['adc_valid'];fault=f['adc_fault'];ot=f['adc_ot'];raw=f['adc_raw']
            ok=[i for i in range(meta['depth']) if valid[i]==1 and fault[i]==0 and raw[i] not in (None,0,4095)]
            out['adc']={'valid_samples_in_window':len(ok),'raw_codes':sorted({raw[i] for i in ok}),'status_values_reconstructed':sorted({valid[i]+2*fault[i]+4+8*ot[i] for i in ok if ot[i] is not None}),'available_bit':'constant 1 from HARD_ADC build, not a separately sampled net','sample_counter':bounds(f['adc_samples']),'centidegrees_from_raw':sorted({(raw[i]*1219+50)//100-27315 for i in ok})}
            out['activity']={n:sum(x==1 for x in f[n]) for n in ['mispredict','mem_hold','load_hazard','ex_valid','uart_rx_valid','fetch_active','id_valid','fetch_drop','mem_valid','wb_valid']if n in f}
            out['activity']['xnd_busy_samples']=sum(x==0 for x in f['xnd_idle'])
            out['activity']['unique_pc_count']=len({x for x in f['pc'] if x is not None})
            if tag=='adc_a':
                pc=f['pc'];seq=[x for i,x in enumerate(pc) if x is not None and (i==0 or x!=pc[i-1])][:12]
                checks=[]
                for a,b in zip(seq,seq[1:]):
                    w=firmware_words[a//4]
                    if w&127==99:
                        imm=((w>>31)&1)<<12|((w>>7)&1)<<11|((w>>25)&63)<<5|((w>>8)&15)<<1
                        if imm&4096:imm-=8192
                        checks.append(b in (a+4,a+imm))
                    else:checks.append(b==a+4)
                out['serialized_sample_order']={'pc_sequence':seq,'matches_firmware_poll_loop_flow':all(checks) and bool(checks)}
            if tag=='coremark':
                import collections
                counts=collections.Counter()
                for pc in f['pc']:
                    hit=[x for x in functions if pc is not None and x[0]<=pc<x[0]+x[1]]
                    counts[min(hit,key=lambda x:x[1])[2] if hit else '<unknown>']+=1
                out['pc_functions']=dict(counts.most_common())
                out['coremark_named_pc_samples']=sum(v for k,v in counts.items() if k.startswith(('core_','matrix_','cmp_','calc_func','crc','iterate')))
            if tag in ['coremark','xnd']:
                with (folder/(tag+'_samples.csv')).open('w',newline='') as g:
                    w=csv.writer(g);names=list(f);w.writerow(['sample']+names)
                    for i in range(meta['depth']):w.writerow([i]+[f[n][i] for n in names])
        else:
            pin=f['nt_led[7]']; rises=edges(pin,0,1);falls=edges(pin,1,0)
            rising_periods=[b-a for a,b in zip(rises,rises[1:])]
            falling_periods=[b-a for a,b in zip(falls,falls[1:])]
            periods=rising_periods if rising_periods else falling_periods
            highs=[]
            for a in rises:
                candidates=[x for x in falls if x>a]
                if candidates:highs.append(candidates[0]-a)
            out['pwm']={'rising_edges':rises,'falling_edges':falls,'period_samples':periods,'period_edge':'rising'if rising_periods else'falling','high_samples':highs,'enable':bounds(f['u_board/u_soc/pwm_enable']),'frequency_hz_from_reference_clock':out['sample_clock_hz']/statistics.mean(periods) if periods else None,'duty_percent':100*statistics.mean(highs)/statistics.mean(periods) if periods and highs else None}
            with (folder/'pwm25_edges.csv').open('w',newline='') as g:
                w=csv.writer(g);w.writerow(['sample','value'])
                if pin:w.writerow([0,pin[0]])
                for i in sorted(rises+falls):w.writerow([i,pin[i]])
        report['captures'][tag]=out
    if 'adc_a' in report['captures'] and 'adc_b' in report['captures']:
        a=report['captures']['adc_a']['adc']['sample_counter']['min'];b=report['captures']['adc_b']['adc']['sample_counter']['min']
        report['adc_sample_counter_delta_mod32']=(b-a)%(2**32)
    (folder/'analysis.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--dir',type=Path,required=True);a.add_argument('--map',type=Path,required=True);a.add_argument('--elf',type=Path);a.add_argument('--mem',type=Path);a.add_argument('--built-mem',type=Path);a.add_argument('--hashes',action='store_true',help='Optional legacy archival hashes; disabled for normal analysis');args=a.parse_args();run(args.dir,args.map,args.elf,args.mem,args.built_mem,args.hashes)
