#!/usr/bin/env python3
"""Physical regression of four original observed user batches. No retry/rewrite."""
import datetime,json,re,sys,time
from pathlib import Path
from native_latency import Win32Serial,Runner

def cases(materials,root):
    names=['用户25条中文测试报告.md','第二批25条中文验证报告.md','第三四批中文指令验证_20261027.md']
    groups=[]
    for batch,name,prefix in [(1,names[0],''),(2,names[1],'B'),(3,names[2],'T')]:
        rows=[]
        for line in (materials/name).read_text(encoding='utf-8-sig').splitlines():
            columns=[x.strip() for x in line.split('|')]
            if len(columns)>3 and re.fullmatch(prefix+r'\d\d',columns[1]):
                number=int(columns[1][-2:]);rows.append(dict(id='B%d_%02d'%(batch,number),batch=batch,text=columns[2]))
        assert len(rows)==25,(name,len(rows))
        for i,c in enumerate(rows,1):
            tool=0 if i<=4 else 4 if i<=8 else 1 if i<=12 else 3 if i<=16 else 2 if i<=20 else 5
            c.update(tool=tool,argument=0,operation=0)
            if tool==4:
                if batch==1:c.update(argument=[0,0,1,0][i-5],operation=[1,2,1,2][i-5])
                elif batch==2:c['argument']=[1,3,0,2][i-5]
                else:c.update(argument=[3,0,0,0][i-5],operation=[0,2,1,0][i-5])
            if tool==1:c['argument']=([50,25,75,0] if batch==1 else [10,30,60,90] if batch==2 else [20,40,60,80])[i-9]
        groups.extend(rows)
    spec=json.loads((root/'07_runs/board/baseline/acceptance_cases.json').read_text(encoding='utf-8-sig'))
    for c in spec['cases']:
        if c.get('group')!='fourth':continue
        h=c['expected'];groups.append(dict(id='B4_'+c['id'][1:],batch=4,text=c['text'],tool=5 if h['status'] else h['final_index'],argument=h['argument'],operation=h['operation']))
    assert len(groups)==100
    return groups

def exact_ack(sample,prefix):
    if not any(x['text']==prefix for x in sample['events']):raise RuntimeError('Missing exact ACK: '+prefix)

def overflow(run,text):
    wire=text.encode('utf-8')+b'\n'
    a=dict(text=text,phase='oversize_original',tx_hex=wire.hex(),events=[],rx_chunks=[])
    run.evidence['samples'].append(a);run.ready=False
    a['t0write_ns'],a['twrite_ns']=run.serial.write(wire)
    deadline=a['t0write_ns']+int(run.timeout*1e9)
    while not run.ready:
        index,stamp,events=run.receive(deadline);a['rx_chunks'].append(index);a['events'].extend(events)
        if any(x['kind']=='NR_BUILD' for x in events):raise RuntimeError('Restart during oversized input')
        if any(x['kind']=='NR_READY' for x in events):run.ready=True;a['tready_ns']=stamp
    a['tready_ms']=(a['tready_ns']-a['t0write_ns'])/1e6
    a['admission_rejected']=any(x['kind']=='NR_INPUT_ERROR' for x in a['events']) and not any(x['kind'] in ['NR_RESULT','NR_FAST','NR_BINARY'] for x in a['events'])
    return a

def main():
    root,materials,out=map(Path,sys.argv[1:4]);boot=Path(sys.argv[4])
    if out.exists():raise RuntimeError('Refusing overwrite of raw evidence '+str(out))
    source=json.loads(boot.read_text(encoding='utf-8-sig'))
    assert source.get('passed') and source['boot_build']['firmware']=='experimental_position_fusion_oct30'
    e=dict(schema='needlervx.four_observed_batches.v1',source='physical_native_uart',started_at=datetime.datetime.now().astimezone().isoformat(),bootstrap_source=str(boot),build=source['boot_build'],automatic_retry=False,scope='Four original observed user sets; not independent or blind accuracy',samples=[],rx_chunks=[],initial_rx=[],checks=[],coremark_runs=[],failures=[])
    run=None;s=None;initial=None
    try:
        original=cases(materials,root)
        s=Win32Serial('COM10',921600);run=Runner(s,e,45,'text');run.ready=True
        e['ready_source']='Explicit handoff from completed bootstrap; no reset or other serial client since then'
        e['link']=run.request(':link','identity')['link'];assert e['link']['uart_baud']==921600
        e['manifest']=run.request(':tools','manifest')
        for command,ack in [(':fast 1','NR_FAST_MODE 1'),(':config 6','NR_CONFIG 6'),(':format full','NR_FORMAT full')]:
            sample=run.request(command,'setup')
            # ACK exact values are preserved; Runner requires a matching READY boundary.
            if not any(x['kind'] not in ['OTHER','NR_READY'] for x in sample['events']):raise RuntimeError('No setup acknowledgement '+command)
        initial=run.request(':io','initial_io')['io'];e['initial_io']=initial
        for c in original:
            before=run.request(':io','before_'+c['id'])['io']
            size=len(c['text'].encode('utf-8'))
            a=overflow(run,c['text']) if size>64 else run.request(c['text'],'batch_%d'%c['batch'])
            after=run.request(':io','after_'+c['id'])['io']
            check=dict(id=c['id'],batch=c['batch'],text=c['text'],utf8_bytes=size,expected={k:c[k]for k in ['tool','argument','operation']},before_io=before,after_io=after,errors=[])
            def require(ok,message):
                if not ok:check['errors'].append(message)
            v=a.get('result',{});check['actual']=v
            if size>64:
                check['scope']='protocol_length_rejection; no semantic inference';check['admission_events']=[x['text']for x in a['events']]
                require(c['tool']==5 and a.get('admission_rejected'),'Oversized original not safely rejected')
                require(before==after,'IO changed on input rejection')
            else:
                check['scope']='system_tool_parameter_execution'
                require(v.get('selected_tool')==c['tool'],'Tool mismatch')
                require(v.get('execute')==(1 if c['tool']==5 else 0),'Execution status mismatch')
                if c['tool']==5:
                    require(v.get('decode')!=0,'Rejected request decoded as executable');require(before==after,'IO changed on rejected request')
                else:
                    require(v.get('argument')==c['argument'] and v.get('operation')==c['operation'],'Argument/operation mismatch')
                    require(v.get('decode')==0,'Valid command rejected by decoder')
                    wanted=dict(before)
                    if c['tool']==4:
                        val=c['argument'] if c['operation']==0 else before['led_mask']|1<<c['argument'] if c['operation']==1 else before['led_mask']&~(1<<c['argument'])
                        require(v.get('value')==val and after['led_mask']==val,'LED value/readback mismatch')
                        require(all(after[k]==before[k]for k in before if k!='led_mask'),'LED changed unrelated PWM state')
                    elif c['tool']==1:
                        require(v.get('value')==c['argument'] and after['pwm_duty']==c['argument'] and after['pwm_period']==40500 and after['pwm_high']==405*c['argument'] and after['pwm_enabled']==1,'PWM period/duty/readback mismatch')
                        require(after['led_mask']==before['led_mask'],'PWM changed LED mask')
                    else:require(before==after,'Read/self-test changed LED/PWM')
                    receipt=v.get('receipt',{})
                    if c['tool'] in [0,1,4]:require(receipt.get('match',v.get('receipt_match'))==1,'Missing/mismatched register receipt')
                    if c['tool']==0:
                        require(v.get('receipt_kind',receipt.get('kind'))==3 and -4000<=v.get('value',-99999)<=12500,'Temperature unavailable/invalid or not backed by ADC receipt')
                    if c['tool']==2:
                        raw='\n'.join(x['text']for x in a['events']);timing=re.search(r'NR_CYCLES=(\d+) NR_HZ=(\d+) NR_ITERATIONS=(\d+)',raw)
                        require('Correct operation validated.'in raw and 'NR_COREMARK_RETURN'in raw and bool(timing),'Missing CoreMark validation/timing')
                        if timing:
                            cycles,hz,n=map(int,timing.groups());require(n==1200 and hz==40500000 and cycles/hz>=10 and v.get('value')==cycles,'Invalid CoreMark timing contract')
                            crc={}
                            for key in ['seedcrc','crclist','crcmatrix','crcstate','crcfinal']:
                                values=re.findall(key+r'\s*:\s*0x([0-9a-fA-F]+)',raw);require(len(values)==1,'Missing/duplicate '+key)
                                if len(values)==1:crc[key]=values[0].lower()
                            require(all(crc.get(k)==value for k,value in {'seedcrc':'e9f5','crclist':'e714','crcmatrix':'1fd7','crcstate':'8e3a'}.items()),'CoreMark CRC mismatch')
                            e['coremark_runs'].append(dict(id=c['id'],iterations=n,cycles=cycles,seconds=cycles/hz,coremark_per_mhz=n*1000000/cycles,crc=crc))
                require(v.get('uart_status',0)&4==0,'UART receive overrun')
            check['passed']=not check['errors'];check['tready_ms']=a['tready_ms'];e['checks'].append(check)
            print(json.dumps(dict(id=c['id'],passed=check['passed'],tool=v.get('selected_tool'),execute=v.get('execute'),model_used=v.get('model_used'),errors=check['errors']),ensure_ascii=True),flush=True)
            out.write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        finals=[x['crc'].get('crcfinal')for x in e['coremark_runs']]
        e['coremark_consistent']=len(finals)==16 and len(set(finals))==1
        if not e['coremark_consistent']:e['failures'].append('Not all 16 requested CoreMark runs completed with matching final CRC')
    except BaseException as error:e['failures'].append(repr(error))
    finally:
        if run is not None and run.ready:
            try:
                run.request('led 37','restore_demo_baseline',{'tool':4,'execute':0,'value':37});run.request('pwm 20','restore_demo_baseline',{'tool':1,'execute':0,'value':20})
                e['final_io']=run.request(':io','final_io')['io'];e['ready_at_close']=run.ready
            except BaseException as error:e['failures'].append('restore '+repr(error))
        if s is not None:
            try:e['driver_status']=s.errors();s.close()
            except BaseException as error:e['failures'].append('close '+repr(error))
        e['summary']=[dict(batch=b,passed=sum(c['passed']for c in e['checks']if c['batch']==b),tested=sum(c['batch']==b for c in e['checks']))for b in [1,2,3,4]]
        e['passed']=len(e['checks'])==100 and all(c['passed']for c in e['checks']) and not e['failures'] and e.get('driver_status',{}).get('error_flags')==0
        e['finished_at']=datetime.datetime.now().astimezone().isoformat();out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(e,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:e[k]for k in ['passed','summary','failures']},ensure_ascii=True),flush=True)
    return 0 if e['passed']else 1
if __name__=='__main__':sys.exit(main())
