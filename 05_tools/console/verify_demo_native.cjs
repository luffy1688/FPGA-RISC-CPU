/* Production JS with physical UART. Fake DOM/port shell; NOT Edge/display acceptance.
   Only run after explicit serial handoff. --bootstrap-json PATH --assume-ready labels prior boot context, never RX. */
'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm');
const fixture=fs.readFileSync(path.join(__dirname,'test_console.cjs'),'utf8').split('(async () => {')[0];
const driver=String.raw`
const {spawn}=require('child_process');
const arg=name=>{const i=process.argv.indexOf(name);return i<0?null:process.argv[i+1];};
const output=arg('--output'),python=arg('--python'),portName=arg('--port')||'COM10',baud=Number(arg('--baud')||921600);
if(!output||!python)throw Error('Required: --python EXE --output JSON; optional --port COM10 --baud921600 --bootstrap-json PATH --assume-ready');
if(fs.existsSync(output))throw Error('Refusing overwrite of raw evidence: '+output);
const bootPath=arg('--bootstrap-json'),assumeReady=process.argv.includes('--assume-ready');
if(!!bootPath!==assumeReady)throw Error('--bootstrap-json and --assume-ready require an explicit coordinated READY handoff');
const nativeEvents=[],writeWaiters=new Map(),chunks=[];let nativeChild=null,readWaiter=null,nativeError=null,bridgeCarry='',writeIndex=0,childClosed=null;
context.Date=Date;context.setTimeout=setTimeout;context.clearTimeout=clearTimeout;context.performance=performance;
const pythonBridge="import sys,json,threading,queue,base64\nsys.path.insert(0,sys.argv[3])\nfrom native_latency import Win32Serial\nlock=threading.Lock();stop=threading.Event();serial=None\ndef emit(v):\n with lock:\n  print(json.dumps(v,separators=(',',':')),flush=True)\ndef pump():\n while not stop.is_set():\n  try:x=serial.queue.get(timeout=.1)\n  except queue.Empty:continue\n  if isinstance(x,BaseException):emit({'event':'error','error':repr(x)});return\n  stamp,data=x;emit({'event':'rx','received_ns':stamp,'hex':data.hex()})\ntry:\n serial=Win32Serial(sys.argv[1],int(sys.argv[2]));emit({'event':'opened','settings':serial.settings})\n threading.Thread(target=pump,daemon=True).start()\n for line in sys.stdin:\n  message=json.loads(line)\n  if message['op']=='close':break\n  if message['op']!='write':raise ValueError('Unknown bridge op')\n  data=base64.b64decode(message['base64']);t0,t1=serial.write(data);emit({'event':'tx','id':message['id'],'hex':data.hex(),'t0write_ns':t0,'twrite_ns':t1})\nexcept BaseException as error:emit({'event':'error','error':repr(error)})\nfinally:\n stop.set()\n if serial is not None:\n  try:emit({'event':'driver_status','data':serial.errors()});serial.close()\n  except BaseException as error:emit({'event':'error','error':'close '+repr(error)})\n emit({'event':'closed'})\n";
function deliver(chunk){if(readWaiter){const resolve=readWaiter;readWaiter=null;resolve({value:new Uint8Array(chunk),done:false});}else chunks.push(chunk);}
function fail(error){nativeError=error;for(const p of writeWaiters.values())p.reject(error);writeWaiters.clear();}
fakeReader.read=()=>chunks.length?Promise.resolve({value:new Uint8Array(chunks.shift()),done:false}):new Promise(resolve=>{readWaiter=resolve;});
fakeReader.cancel=async()=>{if(readWaiter){const resolve=readWaiter;readWaiter=null;resolve({done:true});}};
fakePort.getInfo=()=>({usbVendorId:0x10c4,usbProductId:0xea60});
fakePort.open=async options=>{
 if(options.baudRate!==baud)throw Error('Page baud differs from selected native baud');
 await new Promise((resolve,reject)=>{
  nativeChild=spawn(python,['-u','-c',pythonBridge,portName,String(baud),path.resolve(__dirname,'../board')],{windowsHide:true,stdio:['pipe','pipe','pipe']});
  childClosed=new Promise(done=>nativeChild.on('close',done));
  nativeChild.on('error',error=>{fail(error);reject(error);});nativeChild.stderr.on('data',b=>process.stderr.write(b));
  nativeChild.stdout.on('data',b=>{bridgeCarry+=b.toString('utf8');let n;while((n=bridgeCarry.indexOf('\n'))>=0){const line=bridgeCarry.slice(0,n);bridgeCarry=bridgeCarry.slice(n+1);if(!line)continue;const e=JSON.parse(line);nativeEvents.push(e);
   if(e.event==='opened')resolve();else if(e.event==='rx')deliver(Buffer.from(e.hex,'hex'));else if(e.event==='tx'){const p=writeWaiters.get(e.id);if(p){writeWaiters.delete(e.id);p.resolve();}}else if(e.event==='error'){const error=Error(e.error);fail(error);reject(error);}
  }});
 });
};
fakePort.writable.getWriter=()=>({write:data=>new Promise((resolve,reject)=>{const id=++writeIndex;writes.push(Buffer.from(data).toString('utf8'));writeWaiters.set(id,{resolve,reject});nativeChild.stdin.write(JSON.stringify({op:'write',id,base64:Buffer.from(data).toString('base64')})+'\n');}),releaseLock:()=>{}});
fakePort.close=async()=>{if(!nativeChild)return;if(!nativeChild.stdin.destroyed)nativeChild.stdin.end(JSON.stringify({op:'close'})+'\n');await childClosed;nativeChild=null;};
const wait=async(predicate,ms,label)=>{const deadline=Date.now()+ms;while(!predicate()){if(nativeError)throw nativeError;if(Date.now()>deadline)throw Error(label+' timeout');await new Promise(resolve=>setTimeout(resolve,5));}};
(async()=>{
 let passed=false,error=null;const startedAt=new Date().toISOString();
 try{
  nodes.get('baudRate').value=String(baud);await run('connect()');assert(run('port!==null'),'Production connect() did not open native UART');
  if(assumeReady){const b=JSON.parse(fs.readFileSync(bootPath,'utf8').replace(/^\uFEFF/,''));b.boot_build=b.boot_build||b.build;assert(b.passed===true&&b.boot_build?.firmware==='experimental_position_fusion_oct30','Handoff requires successful selected firmware boot');
   context.handoffBuild=b.boot_build;context.handoffPath=path.resolve(bootPath);
   run('evidenceSession.firmware_build=handoffBuild;frequency=handoffBuild.clock_hz;evidenceSession.reported_clock_hz=frequency;evidenceSession.handoff_context={source_file:handoffPath,assume_ready_explicit:true,not_new_RX:true};ready=true;renderWorker();nrArchitecture.setBuild(handoffBuild);refreshControls()');
  }else{console.log('WAITING_FOR_REAL_NR_BUILD_READY: press KEY0 once');await wait(()=>run('ready&&evidenceSession.firmware_build?.firmware==="experimental_position_fusion_oct30"'),120000,'Actual boot');}
  run('evidenceSession.source="production_JS_VM_with_native_UART"');
  const dual=run('workerSupported()');if(dual){await run('sendWorker("start")');await wait(()=>run('ready&&pendingRequest.ready_received_at&&workerState?.busy'),10000,'Background worker start');}
  for(const kind of ['ai','quick']){await run('startDemo("'+kind+'")');await wait(()=>run('!demoFlow.active'),90000,'Demo '+kind);assert(run('demoFlow.state==="completed"'),run('demoFlow.reason'));console.log('DEMO_PASS',kind);}
  await run('send()');await wait(()=>run('ready&&pendingRequest.ready_received_at'),10000,'Quick LED response');assert(run('pendingRequest.result.selected_tool===4&&pendingRequest.result.execute===0&&pendingRequest.result.value===37&&pendingRequest.receipt_verification.passed'),'Quick LED failed');console.log('QUICK_LED_PASS');
  if(dual){await run('sendWorker("status")');await wait(()=>run('ready&&pendingRequest.ready_received_at'),10000,'Concurrent worker status');assert(run('workerState.busy'),'Worker did not overlap AI/IO demonstration');console.log('BACKGROUND_AI_IO_OVERLAP_PASS');}
  await run('startDemo("cpu")');await wait(()=>run('!demoFlow.active'),90000,'CPU selftest');assert(run('demoFlow.state==="completed"'),run('demoFlow.reason'));assert(Number.isFinite(Number(text('coreScore')))&&Number(text('coreScore'))>0,'Missing valid CoreMark score');console.log('CPU_SELFTEST_PASS',text('coreScore'));
  if(dual){assert(run('dualBenchmark?.valid===true')||Number(text('dualScore'))>0,'Missing validated dual scoreboard');await run('sendWorker("status")');await wait(()=>run('ready&&pendingRequest.ready_received_at'),10000,'Worker completed');assert(run('workerState.done&&workerState.validated&&!workerState.fault'),'Worker completion not validated');}
  assert(writes.length===(dual?15:12),'Unexpected transaction count '+writes.length);passed=true;
 }catch(e){error=String(e.stack||e);process.exitCode=1;}
 finally{
  try{await run('disconnect()');}catch(e){passed=false;error=(error||'')+';close '+e;process.exitCode=1;}
  const driverStatus=nativeEvents.filter(x=>x.event==='driver_status').at(-1)?.data;if(nativeError||driverStatus?.error_flags){passed=false;error=(error||'')+';native '+String(nativeError||JSON.stringify(driverStatus));process.exitCode=1;}
  const evidence=run('evidenceSession?JSON.parse(JSON.stringify(evidenceSession)):null');
  const report={schema:'needlervx.production_console_demo.v1',source:'production_JS_state_machine_with_physical_native_UART',started_at:startedAt,finished_at:new Date().toISOString(),passed,error,mock_dom:true,mock_serial_results:false,browser_verified:false,physical_display_verified:false,port:portName,baud,boot_context:assumeReady?'explicit_ready_handoff_with_prior_boot_source':'actual_NR_BUILD_and_READY_received_by_this_run',writes,native_events:nativeEvents,page_evidence:evidence,display_summary:{action:text('displayAction'),readback:text('displayReadback'),ai:text('displayAi'),core_score:text('coreScore')}};
  fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n','utf8');console.log(JSON.stringify({passed,error,output,transactions:writes.length,browser_verified:false}));
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
`;
if(process.argv.includes('--check-only')){new vm.Script(fixture+driver,{filename:'production_demo_native.cjs'});console.log('PRODUCTION_DEMO_BRIDGE_SYNTAX_PASS; no UART opened');}
else vm.runInNewContext(fixture+driver,{require,__dirname,__filename,console,Buffer,process,Date,setTimeout,clearTimeout,performance:require('perf_hooks').performance},{filename:'production_demo_native.cjs'});
