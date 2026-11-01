'use strict';
// 页面行为验收：假 DOM 和串口只存在于这个 Node 进程，不进入交付页面。
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert');
const { TextEncoder, TextDecoder } = require('util');
const { URLSearchParams } = require('url');
const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const nodes = new Map();
class Element {
  constructor(tag = '') { this.tagName = tag; this.textContent = ''; this.children = []; this.events = {}; this.style = {}; this.value = ''; this.disabled = false; this.attributes={}; this.classes=new Set(); this.classList={toggle:(name,on)=>{if(on===undefined)on=!this.classes.has(name);if(on)this.classes.add(name);else this.classes.delete(name);return on;},contains:name=>this.classes.has(name)}; }
  addEventListener(type, callback) { this.events[type] = callback; }
  setAttribute(name,value) { this.attributes[name]=String(value); }
  replaceChildren(...children) { this.children = children; }
  appendChild(child) { this.children.push(child); }
  click() { if (this.events.click) return this.events.click({target:this}); }
  remove() {}
  focus() {}
}
for (const match of html.matchAll(/<[^>]*id="([^"]+)"[^>]*>/g)) {
  assert(!nodes.has(match[1]), 'duplicate HTML id: ' + match[1]);
  const element=new Element();element.disabled=/\sdisabled(?:\s|>)/.test(match[0]);
  const plain=html.slice(match.index+match[0].length).match(/^([^<]*)<\//);if(plain)element.textContent=plain[1];
  nodes.set(match[1], element);
}
const writes = [], downloads = [], opens=[], selections=[];
let pendingRead;
const fakeReader = {
  read: () => new Promise(resolve => { pendingRead = resolve; }),
  cancel: async () => { if (pendingRead) pendingRead({done:true}); },
  releaseLock: () => {}
};
const fakePort = {
  open: async options => {opens.push(options);}, close: async () => {}, getInfo: () => ({usbVendorId:0x10c4,usbProductId:0xea60}),
  readable: {getReader: () => fakeReader},
  writable: {getWriter: () => ({write: async data => writes.push(Buffer.from(data).toString('utf8')), releaseLock: () => {}})}
};
let qaNow=Date.now();
class QaDate extends Date { constructor(...args){super(...(args.length?args:[qaNow]));} static now(){return qaNow;} }
const tick=ms=>{qaNow+=ms;};
let fullscreenRequests=0,fullscreenExits=0;
const fakeDocument={getElementById:id=>{assert(nodes.has(id),'unknown DOM id: '+id);return nodes.get(id);},createElement:tag=>new Element(tag),body:new Element('body'),fullscreenElement:null,events:{},addEventListener(type,callback){this.events[type]=callback;}};
fakeDocument.documentElement=new Element('html');
fakeDocument.documentElement.requestFullscreen=async()=>{fullscreenRequests++;fakeDocument.fullscreenElement=fakeDocument.documentElement;fakeDocument.events.fullscreenchange();};
fakeDocument.exitFullscreen=async()=>{fullscreenExits++;fakeDocument.fullscreenElement=null;fakeDocument.events.fullscreenchange();};
const context = vm.createContext({
  TextEncoder, TextDecoder, URLSearchParams, Date:QaDate, setTimeout:(callback,ms)=>{if(ms>=15000){context.qaDemoTimeout=callback;return 7;}return callback();},clearTimeout:()=>{context.qaDemoTimeout=null;},
  setInterval:callback=>{context.qaInterval=callback;return 1;},clearInterval:()=>{context.qaInterval=null;},
  document:fakeDocument,
  window: {isSecureContext:true,location:{search:'?present=1'}}, navigator: {serial:{requestPort:async options => {selections.push(options);return fakePort;}, addEventListener:() => {}}},
  Blob: class { constructor(parts, options) { this.contents=parts.join(''); this.type=options.type; } },
  URL: {createObjectURL: blob => { downloads.push(blob); return 'blob:qa'; }, revokeObjectURL:() => {}}
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'architecture.js'),'utf8'), context, {filename:'architecture.js'});
vm.runInContext(script, context, {filename:'index.html'});
const run = code => vm.runInContext(code, context);
const text = id => nodes.get(id).textContent;
const rx = (line,ending='\r\n') => {context.qaLine=line;context.qaWireBytes=Buffer.byteLength(line+ending);run('receiveLine(qaLine,qaWireBytes)');};
const result = overrides => Object.assign({case:0,config:6,tool:4,selected_tool:4,margin:100,confidence_threshold:16,decode:0,execute:0,argument:37,value:37,cycles:270000,tool_cycles:2700,request_cycles:273000,pmu:{cycles:274000,instret:137000,branches:100,redirect_misses:200,mem_load_stall_cycles:4000,ic_misses:10,dc_misses:20},loads:10,jobs:20,reuses:10,activation_bytes:100,weight_bytes:200,output_bytes:300,mode:3,graph:1,dot4:1,engine_cycles:1000,failures:0,logits:[0,1,2,3,100,4]},overrides);
let checks = 0;
function check(expression, message) { assert(expression, message); checks++; }
(async () => {
  check(run('presentationEnabled') && fakeDocument.body.classList.contains('presentation'), '?present=1 selects presentation layout');
  check(!nodes.get('logDetails').open && !nodes.get('coreRawDetails').open, 'presentation folds long evidence text without removing access');
  check(writes.length===0 && fullscreenRequests===0 && run('port===null && evidenceSession===null') && text('coreScore')==='—', 'opening presentation never connects, transmits, enters fullscreen or invents a score');
  nodes.get('presentationToggle').click();
  check(!run('presentationEnabled') && nodes.get('logDetails').open && nodes.get('coreRawDetails').open && nodes.get('presentationToggle').attributes['aria-pressed']==='false', 'detail toggle restores original evidence panels');
  nodes.get('presentationToggle').click();
  await nodes.get('fullscreenToggle').click();
  check(fullscreenRequests===1 && text('fullscreenToggle')==='退出全屏' && writes.length===0 && run('port===null'), 'fullscreen requires its own explicit click and never touches serial');
  await nodes.get('fullscreenToggle').click();
  check(fullscreenExits===1 && text('fullscreenToggle')==='全屏显示', 'user can exit fullscreen');
  const fullscreenRequest=fakeDocument.documentElement.requestFullscreen;const beforeFullscreenStatus=text('status');
  fakeDocument.documentElement.requestFullscreen=async()=>{throw new Error('Permission denied');};await nodes.get('fullscreenToggle').click();
  check(text('viewHint').includes('Permission denied') && text('status')===beforeFullscreenStatus && writes.length===0 && run('port===null'), 'denied fullscreen explains failure without changing device status or serial');
  fakeDocument.documentElement.requestFullscreen=fullscreenRequest;

  check(nodes.get('downloadEvidence').disabled, 'JSON download disabled before connection');
  check(text('requestCpi') === '—', 'no fabricated CPI before data');
  rx('NR_READY');
  check(run('evidenceSession === null'), 'receive helper without opened serial cannot create evidence session');
  await run('connect()');
  check(run('evidenceSession.entries.length === 0'), 'opening a serial port does not invent RX evidence');
  rx('NeedleRV-X clock_hz=27000000'); rx('NR_READY');
  rx('NR_BUILD '+JSON.stringify({protocol:2,firmware:'software_stage3',clock_hz:27000000,max_utf8_bytes:64,confidence_threshold:16}));
  rx('NR_CONFIG '+JSON.stringify({config:6,mode:3,graph:1,dot4:1}));rx('NR_READY');
  nodes.get('configuration').value='0';await run('sendConfig()');
  check(writes[0] === ':config 0\n' && text('activeConfig').startsWith('6'), 'user configuration request waits for received acknowledgement');
  rx('NR_CONFIG '+JSON.stringify({config:0,mode:0,graph:0,dot4:0}));rx('NR_READY');
  check(text('activeConfig').startsWith('0') && nodes.get('configuration').value==='0', 'received configuration acknowledged');
  nodes.get('command').value='led 37'; await run('send()');
  check(writes[1] === 'led 37\n', 'actual sent UTF-8 text retained');
  rx('NR_RESULT '+JSON.stringify(result()));
  check(text('selectedTool').includes('set_led'), 'selected tool rendered');
  check(text('values').includes('0x25'), 'actual LED return interpreted');
  const beforeViewSwitch=run('JSON.stringify([ready,frequency,evidenceSession,coreTiming])');const beforeViewValue=text('values');const beforeViewRaw=text('tool');const beforeViewFinal=text('selectedTool');const beforeViewWrites=writes.length;
  nodes.get('presentationToggle').click();
  check(run('JSON.stringify([ready,frequency,evidenceSession,coreTiming])')===beforeViewSwitch && text('values')===beforeViewValue && text('tool')===beforeViewRaw && text('selectedTool')===beforeViewFinal && writes.length===beforeViewWrites, 'layout switching preserves raw/final prediction, returned value and serial/evidence state');
  nodes.get('presentationToggle').click();
  check(text('toolLatency') === '0.100 ms', 'dispatch cycles converted using reported clock');
  check(text('requestLatency') === '10.111 ms', 'request scope cycles converted');
  check(text('requestCpi') === '2.000 · 含采样开销', 'CPI based on cycles / instret with overhead label');
  check(text('margin').includes('100 / 16'), 'uncalibrated integer margin and threshold shown');
  check(!JSON.stringify(nodes.get('requestPmu').children).includes('错预测率'), 'no invalid branch miss ratio generated');
  rx('NR_RESULT '+JSON.stringify(result({selected_tool:5,margin:9,decode:1,execute:1,value:0})));
  check(text('tool').includes('set_led') && text('selectedTool').includes('reject'), 'raw class preserved when confidence gate rejects');
  check(!text('values').includes('LED 掩码'), 'reject return is not presented as an LED action');
  rx('NR_RESULT '+JSON.stringify(result({selected_tool:5,decode:8,execute:1,value:0})));
  check(text('decode').includes('语义策略拒绝') && text('tool').includes('set_led'), 'semantic policy reject leaves raw neural class intact');
  rx('NR_RESULT '+JSON.stringify(result({selected_tool:0,tool:0,value:4294964796})));
  check(text('values').includes('-25.00 °C'), 'signed temperature conversion preserved');
  rx('NR_RESULT '+JSON.stringify(result({pmu:{cycles:10,instret:0}})));
  check(text('requestCpi') === '—', 'zero retired instructions does not generate infinity CPI');
  rx('NR_RESULT '+JSON.stringify(result({pmu:undefined,selected_tool:undefined,margin:undefined,confidence_threshold:undefined,tool_cycles:undefined,request_cycles:undefined})));
  check(text('selectedTool').includes('未报告') && text('toolLatency') === '—' && text('requestCpi') === '—', 'old firmware does not receive invented telemetry');
  rx('NR_RESULT '+JSON.stringify(result({tool:5,selected_tool:4,operation:1,selection_source:2,argument:1,value:39})));
  check(text('operation')==='点亮 LED1' && text('values').includes('目标 LED1') && text('values').includes('0x27'), 'bit operation reports target and complete post-update mask');
  check(text('tool').includes('reject') && text('selectionSource').includes('LED schema') && text('resultInterpretation').includes('不能计为神经分类正确'), 'schema rescue never overwrites the raw neural rejection');
  rx('NR_RESULT '+JSON.stringify(result({operation:2,selection_source:0,argument:0,value:38})));
  check(text('operation')==='关闭 LED0' && text('selectionSource').includes('神经分类'), 'LED clear is distinct from mask zero');
  rx('NR_RESULT '+JSON.stringify(result({operation:0,selection_source:0,argument:0,value:0})));
  check(text('operation')==='整体掩码' && text('values').includes('0x00'), 'mask zero remains a complete-mask operation');
  rx('NR_RESULT '+JSON.stringify(result({operation:2,selection_source:0,argument:7,execute:2,value:0})));
  check(!text('values').includes('LED 掩码') && text('values').includes('没有有效硬件结果'), 'PWM-owned pin cannot be shown as a successful LED write');
  rx('NR_RESULT '+JSON.stringify(result({tool:0,selected_tool:1,operation:0,selection_source:4,argument:40,value:40})));
  check(text('selectionSource').includes('PWM schema') && text('tool').includes('read_temp') && text('values').includes('40%') && text('resultInterpretation').includes('不能计为神经分类正确'), 'explicit PWM route keeps the raw neural error visible');
  run('resetCore()');
  rx('Correct operation validated.');
  rx('NR_CYCLES=270000000 NR_HZ=27000000 NR_ITERATIONS=300');
  rx('NR_PMU '+JSON.stringify({scope:'coremark_bracket',cycles:271000000,instret:100000000,branches:200,redirect_misses:250,mem_load_stall_cycles:5000,ic_misses:20,dc_misses:30}));
  rx('NR_RESULT '+JSON.stringify(result({tool:2,selected_tool:2,value:270000000})));
  check(text('coreScore') === '1.111111', 'CoreMark score uses benchmark timer, not PMU sampling cycles');
  check(text('coreCpi') === '2.710 · 含采样开销', 'CoreMark PMU bracket has separate CPI');
  // A clocked candidate is still mock protocol input here, never board evidence.
  rx('NR_READY');
  rx('NR_BUILD '+JSON.stringify({protocol:2,firmware:'software_clocked_candidate',clock_hz:40500000,coremark_iterations:900}));
  check(!run('ready') && nodes.get('send').disabled && nodes.get('applyConfig').disabled, 'new BUILD must wait for its own READY');
  check(text('coreCycles')==='—' && text('coreSeconds')==='—' && text('coreScore')==='—' && text('coreCpi')==='—', 'new BUILD removes prior CoreMark timing, score and PMU');
  check(run('!coreValidated && !coreFailed && coreTiming===null && coreLines.length===0'), 'new BUILD clears prior benchmark acceptance state');
  check(run('frequency===40500000') && text('clock').includes('40,500,000'), 'clocked BUILD is read dynamically');
  rx('NR_READY');rx('NR_RESULT '+JSON.stringify(result({cycles:405000,tool_cycles:4050,request_cycles:409500})));
  check(text('latency')==='10.000 ms' && text('toolLatency')==='0.100 ms' && text('requestLatency')==='10.111 ms', '40.5 MHz scales inference, dispatch and request times');
  run('resetCore()');rx('Correct operation validated.');
  rx('NR_CYCLES=607500000 NR_HZ=40500000 NR_ITERATIONS=900');
  rx('NR_RESULT '+JSON.stringify(result({tool:2,selected_tool:2,value:607500000})));
  check(text('coreSeconds')==='15.000000 秒' && text('coreIterations')==='900' && text('coreScore')==='1.481481', '40.5 MHz / 900 iteration report uses its own timer and iteration count');
  const beforeBenchmarkView=[text('coreCycles'),text('coreSeconds'),text('coreIterations'),text('coreScore')];
  nodes.get('presentationToggle').click();
  check(JSON.stringify(beforeBenchmarkView)===JSON.stringify([text('coreCycles'),text('coreSeconds'),text('coreIterations'),text('coreScore')]), 'layout switching preserves received 40.5 MHz / 900 iteration acceptance');
  // Restore the earlier firmware report for the remaining legacy compatibility cases.
  rx('NR_BUILD '+JSON.stringify({protocol:2,firmware:'software_stage3',clock_hz:27000000}));rx('NR_READY');
  run('resetCore()');rx('Correct operation validated.');rx('NR_CYCLES=100 NR_HZ=27000000 NR_ITERATIONS=300');rx('NR_RESULT '+JSON.stringify(result({tool:2,selected_tool:2})));
  check(text('coreScore') === '未形成有效成绩', 'short benchmark cannot be certified');
  run('resetComparison()');
  const compareResult=(overrides={})=>result(Object.assign({operation:0,selection_source:0},overrides));
  const collect=(command,value)=>{context.qaCommand=command;context.qaResult=value;run('pendingComparisonText=qaCommand;collectComparison(qaResult)');};
  const sw=compareResult({config:0,mode:0,graph:0,dot4:0,cycles:2700000});
  collect('led 37',sw);collect('led 38',compareResult());
  check(!run('evidenceSession.comparisons.length'), 'different commands never form a comparison');
  collect('led 37',compareResult());
  check(text('comparisonStatus').includes('10.000×') && run('evidenceSession.comparisons[0].integer_and_decode_match'), 'same command and integer output give measured inference ratio');
  check(run('evidenceSession.comparisons[0].scope.includes("excludes UART")'), 'comparison scope excludes serial and dispatch');
  collect('led 37',compareResult({logits:[1,1,2,3,100,4]}));
  check(run('evidenceSession.comparisons[0].inference_speedup===null') && text('comparisonStatus').includes('不一致'), 'integer mismatch invalidates the speedup');
  run('resetComparison()');
  for(const bad of [{cycles:0},{cycles:-1},{cycles:1.5},{failures:1},{logits:[1,2]},{selected_tool:undefined},{config:6,mode:0}])collect('led 37',compareResult(bad));
  collect('led 37',sw);
  check(!run('evidenceSession.comparisons.length'), 'malformed/failing results cannot create an accelerated counterpart');
  collect('led 37',compareResult());
  rx('NR_BUILD '+JSON.stringify({protocol:2,firmware:'new-build',clock_hz:27000000}));
  check(run('comparisonEntries.size===0 && evidenceSession.comparisons.length===0'), 'new boot/build clears pairs');
  collect('led 37',compareResult());
  check(!run('evidenceSession.comparisons.length'), 'old-build software result cannot pair with new accelerated result');
  rx('NR_BUILD '+JSON.stringify({protocol:2,firmware:'software_stage3',clock_hz:27000000}));
  collect('led 37',sw);collect('led 37',compareResult());
  nodes.get('clearLog').click();
  check(run('evidenceSession.entries.length > 0'), 'clearing display preserves real received evidence');
  nodes.get('downloadEvidence').click();
  const evidence=JSON.parse(downloads[downloads.length-1].contents);
  check(evidence.comparisons.length===1 && evidence.comparisons[0].inference_speedup===10, 'export retains real-input comparison and scope');
  check(evidence.source === 'web_serial' && evidence.reported_clock_hz === 27000000, 'exported evidence identifies source and received clock');
  check(evidence.firmware_build.firmware==='software_stage3' && evidence.current_configuration===null, 'new boot preserves its own build without reusing prior configuration');
  check(evidence.entries.some(entry => entry.direction === 'TX' && entry.line === 'led 37'), 'export retains raw transmission');
  check(evidence.entries.some(entry => entry.parsed && entry.parsed.kind === 'NR_PMU'), 'export retains parsed received PMU');
  check(evidence.entries.some(entry => entry.parsed && entry.parsed.kind === 'NR_RESULT' && entry.parsed.data.selected_tool === 5), 'export preserves reject telemetry');
  await run('disconnect()');
  check(run('evidenceSession.closed_at !== null && port === null'), 'disconnect closes evidence session and serial');
  await run('connect()');
  check(text('cycles')==='—' && text('selectedTool')==='—' && nodes.get('downloadEvidence').disabled, 'new connection clears old results and waits for real RX evidence');
  await run('disconnect()');
  await run('connect()');
  rx('NR_BUILD '+JSON.stringify({protocol:2,firmware:'phase-candidate',clock_hz:40500000}));
  rx('NR_ACTION '+JSON.stringify({phase:'tool_start',case:9,config:6,tool:2,selected_tool:2,cycles:1651975,decode:0,selection_source:0}));
  check(text('latency').includes('40.790') && text('resultStatus').includes('识别已完成'), 'phase report shows measured inference before long tool');
  check(text('coreScore')==='—' && !run('ready') && text('execution').includes('尚未返回'), 'phase never invents benchmark success score or READY');
  check(text('resultExplanation').includes('至少10秒'), 'human explanation separates inference from benchmark minimum');
  rx('Correct operation validated.');rx('NR_CYCLES=611482119 NR_HZ=40500000 NR_ITERATIONS=900');
  rx('NR_RESULT '+JSON.stringify(result({case:9,tool:2,selected_tool:2,execute:0,value:611482119,cycles:1651975})));
  check(text('coreScore')==='1.471834' && text('resultExplanation').includes('15.098324'), 'only actual completed result produces CRC/timer success');
  check(!run('ready'), 'completed result still waits for actual NR_READY');
  rx('NR_READY');check(run('ready'), 'actual READY alone reopens command input');
  check(run('evidenceSession.entries.some(x=>x.parsed&&x.parsed.kind==="NR_ACTION")'), 'evidence retains original phase notification');
  await run('disconnect()');

  const writesBeforeChoice=writes.length;
  nodes.get('fourthCommand').value='0';nodes.get('fourthCommand').events.change();
  check(nodes.get('command').value==='请读取FPGA当前温度。'&&writes.length===writesBeforeChoice,'fourth selector fills the exact original without sending');
  run('renderResult('+JSON.stringify(result({tool:5,selected_tool:0,selection_source:1,execute:0,value:3855})) +')');
  check(text('resultInterpretation').includes('最终执行成功')&&text('resultInterpretation').includes('不能计为神经分类正确'),'successful rule recovery stays distinct from neural accuracy');
  check(text('resultExplanation').includes('38.55')&&text('resultExplanation').includes('没有被系统拒绝'),'recovered temperature is explained as real success, not rejection');

  // Protocol-v3 and health-check tests remain isolated mock input, never physical evidence.
  const flush=async()=>{for(let i=0;i<16;i++)await Promise.resolve();};
  const protocolBuild={protocol:3,firmware:'service-v3-mock',clock_hz:40500000,capabilities:{fast:1,compact:1,io_snapshot:1,receipt:1}};
  const boot=()=>{rx('NR_BUILD '+JSON.stringify(protocolBuild));rx('NR_FAST_MODE {"enabled":1}');rx('NR_FORMAT {"compact":1}');rx('NR_READY');};
  const fast=(tool,opts={})=>{const o=Object.assign({case:41,config:6,decode:tool===5?8:0,argument:0,operation:0,source:tool===5?3:tool===4?2:tool===1?4:1,execute:tool===5?1:0,value:0,decision:1234,toolCycles:12,requestCycles:1250,kind:0,requested:0,readback:0,match:0,period:0,high:0,enabled:0},opts);return [1,o.case,o.config,tool,o.decode,o.argument,o.operation,o.source,o.execute,o.value,o.decision,o.toolCycles,o.requestCycles,o.kind,o.requested,o.readback,o.match,o.period,o.high,o.enabled];};
  const fastRx=async(tool,opts={})=>{rx('NR_FAST '+JSON.stringify(fast(tool,opts)));await flush();};
  const next=async()=>{rx('NR_READY');await flush();};
  const current=()=>run('healthRun.rows[healthRun.index]');
  const start=async(scope='readonly')=>{nodes.get('healthScope').value=scope;run('startHealth()');await flush();};
  const snapshot={led_mask:165,pwm_period:40500,pwm_high:20250,pwm_enabled:1,pwm_duty:50,restore_supported:1};
  const coreReply=async()=>{
    rx('NR_ACTION '+JSON.stringify({phase:'tool_start',case:41,config:6,tool:null,selected_tool:2,decode:0,selection_source:1,model_used:0,cycles:0,decision_cycles:1234}));
    for(const line of ['seedcrc : 0x8a02','crclist : 0xe714','crcmatrix : 0x1fd7','crcstate : 0x8e3a','crcfinal : 0x1234'])rx(line);
    rx('Correct operation validated.');rx('NR_CYCLES=607500000 NR_HZ=40500000 NR_ITERATIONS=900');
    await fastRx(2,{value:607500000,toolCycles:607500000,requestCycles:607501234});
  };
  const preparePwm=async(io=snapshot)=>{
    await start('io');rx('NR_IO '+JSON.stringify(io));await next();await coreReply();await next();await fastRx(0,{value:3855,kind:3,readback:3855,match:1});await next();await fastRx(3,{value:4294967290,kind:4,readback:4294967290,match:1});await next();
  };
  await run('connect()');
  nodes.get('healthScope').value='io';rx('NR_READY');const oldWire=writes.length;run('startHealth()');await flush();
  check(writes.length===oldWire&&run('healthRun===null')&&text('status').includes('缺少有效NR_BUILD'), 'old firmware cannot receive unknown IO snapshot or temporary write commands');
  boot();
  check(text('activeFast').includes('规则优先')&&text('activeFormat').includes('紧凑帧')&&!nodes.get('applyFast').disabled, 'v3 startup acknowledgements establish actual fast mode and frame format');
  nodes.get('fastMode').value='0';await run("sendProtocolControl('fast')");
  check(writes[writes.length-1]===':fast 0\n'&&text('activeFast').includes('规则优先')&&!run('ready'), 'fast mode request retains old actual state until acknowledgement');
  rx('NR_FAST_MODE {"enabled":0}');
  check(text('activeFast').includes('先运行模型')&&!run('ready'), 'fast acknowledgement does not synthesize READY');await next();
  nodes.get('resultFormat').value='full';await run("sendProtocolControl('format')");rx('NR_FORMAT {"compact":0}');await next();
  check(writes[writes.length-1]===':format full\n'&&text('activeFormat').includes('完整JSON'), 'full output is selected only by supported control and real acknowledgement');
  await fastRx(4,{argument:37,value:37,kind:1,requested:37,readback:37,match:1});
  check(text('tool').includes('未运行模型')&&text('cycles')==='未运行'&&text('latency')==='模型未运行'&&text('processingPath').includes('规则快路径'), 'compact frame never fabricates raw neural classification or inference work');
  check(text('decisionCycles')==='1,234'&&text('decisionLatency')==='0.030 ms'&&text('receipt').includes('寄存器比对一致')&&text('receipt').includes('不代表外部物理'), 'compact decision cycles and explicit register receipt retain their measurement scopes');
  check(run('evidenceSession.entries.some(x=>x.parsed?.kind==="NR_FAST"&&Array.isArray(x.parsed.data)&&x.parsed.data.length===20)')&&text('requestCpi')==='—'&&nodes.get('logits').children.length===0, 'raw compact array is preserved while missing logits and PMU remain absent');
  run('renderResult('+JSON.stringify(result({model_used:1,selection_source:2,tool:5,selected_tool:4,receipt:{kind:1,requested:37,readback:37,match:1}})) +')');
  check(text('processingPath').includes('模型＋规则辅助')&&text('tool').includes('reject')&&text('resultInterpretation').includes('不能计为神经分类正确'), 'hybrid result keeps raw error and rule assistance distinct');
  run('renderResult('+JSON.stringify(result({model_used:1,selection_source:0})) +')');
  check(text('processingPath').includes('模型路径'), 'actual model-use result is labeled as model path');
  await next();

  const fullBegin=writes.length;await start('io');
  check(writes.length===fullBegin+1&&writes[writes.length-1]===':io\n'&&nodes.get('send').disabled&&nodes.get('applyConfig').disabled&&nodes.get('applyFast').disabled, 'IO health run starts with a single read-only snapshot and locks concurrent requests');
  const blankBefore=run('pendingRequest.rx_wire_bytes');rx('');check(run('pendingRequest.rx_wire_bytes')===blankBefore+2,'actual blank CRLF wire bytes are counted without inventing output');
  tick(12);rx('NR_IO '+JSON.stringify(snapshot));await flush();
  check(writes.length===fullBegin+1&&current().state==='等待 NR_READY'&&run('healthRun.initial_io.led_mask')===165, '8-bit LED initial value including bit7 is saved and snapshot response alone cannot advance');
  tick(5);await next();
  check(current().tool===2&&run('healthRun.rows[0].request.result_ms')===12&&run('healthRun.rows[0].request.ready_ms')===17, 'browser response and READY wall clocks are separate measured endpoints');
  const coreWire=writes.length;rx('NR_ACTION '+JSON.stringify({phase:'tool_start',case:41,config:6,tool:null,selected_tool:2,decode:0,selection_source:1,model_used:0,cycles:0,decision_cycles:1234}));
  check(text('tool').includes('未运行模型')&&text('coreScore')==='—'&&writes.length===coreWire&&!run('ready'), 'fast CoreMark phase reports model unused without score or simulated progress');
  await coreReply();
  check(writes.length===coreWire&&current().coremark.crc_lines.length===5&&current().coremark.timing.seconds===15, 'completed CoreMark retains actual CRC lines and full 15-second timer but still waits READY');
  await next();await fastRx(0,{value:3855,kind:3,readback:3855,match:1});await next();await fastRx(3,{value:4294967290,kind:4,readback:4294967290,match:1});await next();
  check(current().tool===1&&writes[writes.length-1]==='请设置PWM占空比为30%。\n', 'temperature and wrapping 32-bit counter complete before the single PWM write');
  await fastRx(1,{argument:30,value:30,kind:2,requested:30,readback:30,match:1,period:40500,high:12150,enabled:1});await next();
  await fastRx(4,{argument:0,operation:2,value:164,kind:1,requested:164,readback:164,match:1});await next();
  check(current().tool===5&&run('healthRun.rows[5].expected_readback')===164, 'LED0 clear preserves all other initial register bits including bit7');
  await fastRx(5);await next();
  check(writes[writes.length-1]==='led 165\n'&&current().restore==='led_mask', 'LED restoration sends the exact original 8-bit mask');
  await fastRx(4,{argument:165,value:165,kind:1,requested:165,readback:165,match:1});await next();
  check(writes[writes.length-1]==='pwm 50\n'&&current().restore==='pwm_duty', 'PWM restoration uses the original exactly representable percentage');
  await fastRx(1,{argument:50,value:50,kind:2,requested:50,readback:50,match:1,period:40500,high:20250,enabled:1});
  check(run('healthRun.active')&&current().state==='等待 NR_READY', 'final matching restore receipt still cannot complete the check before READY');await next();
  check(!run('healthRun.active')&&run('healthRun.state')==='completed'&&run('healthRun.restore_state')==='已逐条回读验证'&&writes.length===fullBegin+9, 'full check completes nine sequential single-tool/control requests with verified register restoration');
  nodes.get('downloadHealth').click();const healthEvidence=JSON.parse(downloads[downloads.length-1].contents);
  check(healthEvidence.schema==='needlervx.health.evidence.v1'&&healthEvidence.health_check.initial_io.led_mask===165&&healthEvidence.health_check.rows[1].coremark.crc_lines.length===5&&healthEvidence.raw_uart_evidence.entries.some(x=>x.parsed?.kind==='NR_FAST'), 'health export contains initial registers, actual benchmark evidence and unchanged raw compact UART lines');
  check(healthEvidence.source==='web_serial'&&healthEvidence.physical_board_verified_by_export===false&&healthEvidence.health_check.rows[0].request.tx_wire_bytes===4&&healthEvidence.health_check.rows[0].request.response_wire_bytes>0&&healthEvidence.health_check.rows[0].request.rx_wire_bytes>0, 'health JSON records actual UTF-8 wire bytes without claiming physical verification');

  await start();const cancelWire=writes.length;run("stopHealth('mock user cancel')");await next();
  check(run('healthRun.state')==='stopped'&&writes.length===cancelWire&&!run('healthRun.may_have_changed'), 'cancel stops only future requests and never restarts on a subsequent READY');
  await start();const rebootWire=writes.length;rx('NR_BUILD '+JSON.stringify(protocolBuild));
  check(!run('ready')&&run('healthRun.stop_reason').includes('NR_BUILD')&&writes.length===rebootWire, 'firmware reboot stops the active run and clears readiness');await next();
  check(writes.length===rebootWire&&!run('healthRun.active'), 'new boot READY never resumes an interrupted check');

  await preparePwm();const noReceiptWire=writes.length;rx('NR_RESULT '+JSON.stringify(result({tool:1,selected_tool:1,argument:30,value:30,model_used:1,selection_source:4})));await next();
  check(run('healthRun.state')==='stopped'&&run('healthRun.stop_reason').includes('匹配回读')&&writes.length===noReceiptWire&&text('healthRestore').includes('手动恢复'), 'missing write receipt stops without automatic restore and preserves explicit manual recovery values');
  await preparePwm();const mismatchWire=writes.length;await fastRx(1,{argument:30,value:31,kind:2,requested:30,readback:31,match:0,period:40500,high:12555,enabled:1});await next();
  check(run('healthRun.state')==='stopped'&&writes.length===mismatchWire&&text('resultStatus').includes('不能确认写入成功') , 'match=0 is a real failure and no later health action or automatic restore is sent');
  check(!text('resultStatus').startsWith('最终执行成功')&&text('execution').includes('回读核对未通过'),'failed register match never leaves a success headline or success execution label');
  await preparePwm();await fastRx(1,{argument:30,value:31,kind:2,requested:30,readback:31,match:1,period:40500,high:12555,enabled:1});await next();
  check(run('healthRun.state')==='stopped', 'contradictory match=1 cannot override requested/readback mismatch');
  await preparePwm();await fastRx(1,{argument:30,value:30,kind:2,requested:30,readback:30,match:1,period:40500,high:12151,enabled:1});await next();
  check(run('healthRun.state')==='stopped', 'rounded PWM percentage cannot override inconsistent raw high/period registers');

  const skipBegin=writes.length;await preparePwm({...snapshot,pwm_enabled:0,pwm_high:0,pwm_duty:null,restore_supported:0});
  check(current().tool===4&&run('healthRun.pwm_skipped')&&run('healthRun.rows[4].state')==='已跳过'&&!writes.slice(skipBegin).some(x=>x.startsWith('pwm ')||x.includes('设置PWM')), 'disabled or nonrepresentable initial PWM skips both PWM writes while preserving raw initial registers');
  await fastRx(4,{argument:0,operation:2,value:164,kind:1,requested:164,readback:164,match:1});await next();await fastRx(5);await next();await fastRx(4,{argument:165,value:165,kind:1,requested:165,readback:165,match:1});await next();
  check(run('healthRun.state')==='completed'&&writes.length===skipBegin+7&&text('healthStatus').includes('跳过'), 'partial IO check marks PWM skipped explicitly and verifies LED restoration only');
  await start('io');rx('NR_IO '+JSON.stringify({...snapshot,pwm_enabled:0,restore_supported:1}));await next();
  check(run('healthRun.pwm_skipped'), 'host independently rejects a restore-supported flag inconsistent with disabled PWM registers');run("stopHealth('end mock')");await next();
  await start('io');rx('NR_IO '+JSON.stringify({...snapshot,led_mask:256}));await next();
  check(run('healthRun.state')==='stopped'&&run('healthRun.initial_io===null'), 'out-of-range IO snapshot cannot become an initial restore value');

  for(const [line,reason] of [['NR_FAST [1,0]','紧凑结果'],['NR_INPUT_ERROR too_long','固件拒绝输入'],['NR_BACKEND_ERROR failure','后端错误'],['ERROR! CRC mismatch','CoreMark原始输出']]){
    await start();const errorWire=writes.length;rx(line);await next();check(run('healthRun.state')==='stopped'&&run('healthRun.stop_reason').includes(reason)&&writes.length===errorWire, 'active check stops on '+line.split(' ')[0]+' and never continues at READY');
  }
  await start();await coreReply();await next();await fastRx(0,{value:3855});await next();await fastRx(3,{value:2});await next();rx('NR_RESULT '+JSON.stringify(result({tool:5,selected_tool:5,decode:undefined,execute:1})));await next();check(run('healthRun.state')==='stopped','expected refusal still requires a real explicit decode reason');
  await start();const prematureReady=writes.length;rx('NR_READY noise');await flush();
  check(!run('ready')&&writes.length===prematureReady&&run('healthRun.active'), 'READY text with extra data does not release the next request');await next();
  check(run('healthRun.state')==='stopped'&&writes.length===prematureReady, 'bare READY without a corresponding result stops the sequence instead of skipping a tool');
  await preparePwm();const disconnectedWire=writes.length;await run('disconnect()');rx('NR_READY');await flush();
  check(run('healthRun.state')==='stopped'&&run('healthRun.initial_io.led_mask')===165&&writes.length===disconnectedWire&&text('healthRestore').includes('手动恢复'), 'disconnect after a potentially transmitted write retains initial values and never auto-restores or continues');
  await run('connect()');
  check(run('healthRun===null')&&nodes.get('healthRows').children.length===0&&text('healthStatus').includes('尚未开始')&&nodes.get('downloadHealth').disabled, 'new serial connection clears prior health report from the live panel');await run('disconnect()');

  check(run('receiptLabel({selected_tool:0,receipt:{kind:3,requested:0,readback:2587,match:1}})').includes('ADC原码')&&!run('receiptLabel({selected_tool:0,receipt:{kind:3,requested:0,readback:2587,match:1}})').includes('请求'), 'read-only ADC receipt never invents a requested temperature or write comparison');
  check(run('receiptLabel({selected_tool:3,receipt:{kind:4,requested:0,readback:123,match:1}})').includes('32位'), 'counter receipt states the sampled cycle value and wraparound instead of a write acknowledgement');
  check(run('receiptLabel({selected_tool:2})').includes('CRC'), 'CoreMark result points to CRC and algorithm timing instead of missing register write receipt');
  check(nodes.get('baudRate').value==='921600'&&!nodes.get('baudRate').disabled,'frozen firmware defaults921600 and baud selection enabled only when disconnected');
  nodes.get('baudRate').value='921600';await run('connect()');
  check(opens.at(-1).baudRate===921600&&run('evidenceSession.serial.baud_rate')===921600&&nodes.get('baudRate').disabled,'explicit921600 passed to port and recorded while connected selector disabled');
  rx('NR_BUILD '+JSON.stringify({firmware:'software_link_kernel_oct29',clock_hz:40500000,uart_baud:921600,protocol:4}));
  check(text('reportedBaud').includes('921,600'),'firmware reported baud displayed without substituting the selected value');
  let prevented=false;fakeDocument.events.keydown({key:'F5',preventDefault(){prevented=true;}});check(prevented&&text('status').includes('断开'),'connected refresh asks user to export/disconnect');
  rx('NR_BUILD '+JSON.stringify({firmware:'legacy',protocol:2}));check(text('reportedBaud').includes('未报告'),'legacy baud is unknown rather than inferred');
  await run('disconnect()');check(!nodes.get('baudRate').disabled,'disconnect re-enables baud selection');
  const baudInit=script.match(/const requestedBaud=[^\n]+\n[^\n]+/)[0];
  for(const query of ['?present=1&baud=921600','?baud=115200','?baud=1500000']){context.window.location.search=query;vm.runInContext('(()=>{'+baudInit+'})()',context);check(nodes.get('baudRate').value===(query.includes('baud=115200')?'115200':'921600'),'URL chooses explicit recovery baud or frozen921600 default: '+query);}
  const beforeArch=run('JSON.stringify([ready,evidenceSession,frequency])');const archWrites=writes.length;
  nodes.get('archNode_xnd').click();check(text('archInfoTitle').includes('4MAC')&&text('archInfoTitle').includes('8MAC')&&text('archInfoFacts').includes('编码器4MAC / 语境8MAC'),'selected chip explains real arithmetic');
  nodes.get('archView').click();check(nodes.get('archSvg').classList.contains('arch-flat')&&nodes.get('archView').attributes['aria-pressed']==='false','flat view is accessible');
  check(writes.length===archWrites&&run('JSON.stringify([ready,evidenceSession,frequency])')===beforeArch,'architecture selection and projection do not send commands or change evidence');
  run('nrArchitecture.render({model_used:0,selected_tool:4,tool:null,decode:0,execute:0,decision_cycles:40500},{frequency:40500000})');
  check(text('archRaw')==='未运行'&&text('archTime')==='1.000 ms'&&nodes.get('archNode_model').classList.contains('arch-muted'),'fast result cannot be presented as neural classification');
  check(nodes.get('archNode_io').classList.contains('arch-used')&&!nodes.get('archNode_xnd').classList.contains('arch-used'),'fast IO bypasses XND');
  run('nrArchitecture.render({model_used:1,mode:0,tool:0,selected_tool:0,decode:0,execute:0},{frequency:40500000})');
  check(nodes.get('archNode_model').classList.contains('arch-used')&&!nodes.get('archNode_xnd').classList.contains('arch-used'),'software configuration does not claim accelerator execution');
  run('nrArchitecture.render({model_used:1,mode:3,tool:4,selected_tool:5,decode:8,execute:1},{frequency:40500000})');
  check(text('archRaw')==='设置 LED'&&text('archFinal')==='拒绝'&&!nodes.get('archNode_io').classList.contains('arch-used')&&nodes.get('archNode_permit').classList.contains('arch-blocked'),'neural false acceptance and final rejection remain distinct');
  check(nodes.get('archNode_xnd').classList.contains('arch-used'),'hardware model path uses XND');
  run('nrArchitecture.render({tool:0,selected_tool:0,decode:0,execute:0},{})');check(text('archPath').includes('未报告')&&!nodes.get('archNode_model').classList.contains('arch-used'),'old firmware never receives inferred model-path claims');
  run('nrArchitecture.reset()');check(text('archRaw')==='—'&&text('archTime')==='—'&&!nodes.get('archNode_xnd').classList.contains('arch-used'),'reset clears prior result highlighting');
  rx('NR_RESULT '+JSON.stringify(result({bias_bytes:40,residual_bytes:8})));check(text('dma')==='648 B'&&text('dmaDetail').includes('偏置 40 B')&&text('dmaDetail').includes('残差 8 B'),'new postprocess DMA counts bias and residual separately');
  rx('NR_RESULT '+JSON.stringify(result({bias_bytes:40})));check(text('dma')==='—','partial new DMA telemetry is unknown rather than assumed zero');
  run('nrArchitecture.render({model_used:1,mode:3,tool:0,selected_tool:0,decode:0,execute:0},{memory:1})');check(nodes.get('archNode_memory').classList.contains('arch-used'),'learned branch highlighted only when firmware declares it');
  run('nrArchitecture.render({model_used:0,mode:3,tool:null,selected_tool:0,decode:0,execute:0},{memory:1})');check(!nodes.get('archNode_memory').classList.contains('arch-used'),'fast path also bypasses learned memory');
  run('nrArchitecture.reset()');
  const sceneBoundary=run('JSON.stringify([ready,frequency,evidenceSession,coreTiming])');const sceneWrites=writes.length;
  nodes.get('archGuidePath').value='fast';nodes.get('archGuidePath').events.change();
  check(text('archSceneBadge').includes('非实测')&&text('archDemoMode').includes('结构演示'),'instructional mode is visibly separate from physical evidence');
  check(nodes.get('archNode_guard').classList.contains('arch-muted')===false&&nodes.get('archNode_model').classList.contains('arch-muted'),'fast teaching sequence marks the encoder as bypassed');
  nodes.get('archNext').click();check((/schema|语法|跳过模型/.test(text('archCaption')))&&!nodes.get('archNode_xnd').classList.contains('arch-used'),'fast teaching never claims a neural or XND run: '+text('archCaption')+' xnd='+nodes.get('archNode_xnd').classList.contains('arch-used'));
  nodes.get('archPlay').click();check(nodes.get('archPlay').attributes['aria-pressed']==='true'&&typeof context.qaInterval==='function','play starts an explicit bounded instructional timer');
  context.qaInterval();nodes.get('archPlay').click();check(nodes.get('archPlay').attributes['aria-pressed']==='false'&&context.qaInterval===null,'pause stops the instructional timer');
  nodes.get('archGuidePath').value='reject';nodes.get('archGuidePath').events.change();nodes.get('archNext').click();nodes.get('archNext').click();
  check(nodes.get('archNode_permit').classList.contains('arch-blocked')&&!nodes.get('archNode_io').classList.contains('arch-used'),'rejection lesson blocks peripheral activation');
  nodes.get('archGuidePath').value='model';nodes.get('archGuidePath').events.change();nodes.get('archPlay').click();
  run('nrArchitecture.render({model_used:0,selected_tool:4,decode:0,execute:0,decision_cycles:40500},{frequency:40500000})');
  check(context.qaInterval===null&&nodes.get('archPlay').attributes['aria-pressed']==='false'&&!text('archSceneBadge').includes('讲解')&&text('archRaw')==='未运行','actual received result takes precedence over instruction and stops animation');
  nodes.get('archFullscreen').click();check(nodes.get('architecturePanel').classList.contains('arch-expanded'),'presentation expansion changes only its own panel');nodes.get('archFullscreen').click();
  nodes.get('archExplode').click();check(nodes.get('archExplode').attributes['aria-pressed']==='true','explode control is explicit');nodes.get('archExplode').click();
  nodes.get('archPlay').click();nodes.get('architectureDetails').open=false;nodes.get('architectureDetails').events.toggle();check(context.qaInterval===null,'closing the panel stops instruction');
  check(writes.length===sceneWrites&&run('JSON.stringify([ready,frequency,evidenceSession,coreTiming])')===sceneBoundary,'all new 3D navigation and instruction controls preserve serial owner and evidence');
  let updates=[],visible=[],focuses=[];context.NeedleScene3D={createScene:()=>({update:s=>updates.push(s),setVisible:v=>visible.push(v),focus:k=>focuses.push(k),setExploded:()=>{},resize:()=>{}})};
  nodes.get('architectureDetails').open=true;if(nodes.get('archView').attributes['aria-pressed']!=='true')nodes.get('archView').click();nodes.get('architectureDetails').events.toggle();
  check(!nodes.get('archStage').hidden&&nodes.get('archSvg').hidden&&text('archRenderState').includes('WebGL'),'successful renderer uses the genuine 3D container');
  run('nrArchitecture.render({model_used:1,mode:0,selected_tool:0,tool:0,decode:0,execute:0},{memory:1})');
  check(updates.at(-1).active.includes('model')&&updates.at(-1).active.includes('memory')&&!updates.at(-1).active.includes('xnd'),'renderer receives software-model path without a false accelerator claim');
  run('nrArchitecture.render({model_used:0,selected_tool:0,decode:0,execute:0},{memory:1})');
  check(!updates.at(-1).active.includes('model')&&!updates.at(-1).active.includes('memory')&&!updates.at(-1).teaching,'renderer cannot confuse real fast path with a neural lesson');
  nodes.get('archNode_memory').click();check(focuses.at(-1)==='memory','module button focuses the matching 3D group');
  fakeDocument.hidden=true;fakeDocument.events.visibilitychange();check(visible.at(-1)===false,'hidden page releases rendering work');fakeDocument.hidden=false;fakeDocument.events.visibilitychange();
  nodes.get('architectureDetails').open=false;nodes.get('architectureDetails').events.toggle();check(visible.at(-1)===false,'closed panel releases rendering work');
  nodes.get('archNode_guard').click();run('nrArchitecture.render({model_used:1,mode:3,tool:5,selected_tool:5,decode:1,execute:1,context_used:1},{build:{context_head:1}})');
  check(text('archInfoTitle').includes('学习语境')&&text('archInfoFacts').includes('已运行'),'learned context head is distinct from rules when the firmware and result declare it');
  run('nrArchitecture.render({model_used:0,selected_tool:0,decode:0,execute:0},{build:{context_head:1}})');check(text('archInfoFacts').includes('未运行神经'),'context capability cannot make the fast path a neural execution');
  run('nrArchitecture.render({model_used:1,tool:0,selected_tool:0,decode:0,execute:0},{})');check(!text('archInfoTitle').includes('学习语境'),'legacy firmware does not receive an invented context head');
  nodes.get('architectureDetails').open=true;nodes.get('architectureDetails').events.toggle();nodes.get('archPlay').click();nodes.get('architectureDetails').open=false;nodes.get('architectureDetails').events.toggle();
  check(updates.at(-1).teaching===false&&visible.at(-1)===false,'closing a playing scene disables renderer animation as well as the UI timer');
  nodes.get('architectureDetails').open=true;nodes.get('architectureDetails').events.toggle();check(updates.at(-1).teaching===false,'reopening a paused scene cannot silently restart animation');
  const v2=[2,44,6,4,0,37,0,2,0,37,22000,500,23000,1,37,37,1,0,0,0,1,0,120,-90,16];
  const beforeContextWire=writes.length;rx('NR_FAST '+JSON.stringify(v2));
  check(text('processingPath').includes('仅语境头')&&text('tool').includes('编码器未运行')&&!text('tool').includes('模型未运行'),'v2 fast path reports neural context use rather than no model');
  check(text('contextUse').includes('已运行')&&text('encoderUse')==='未运行'&&text('contextScores').includes('120 / -90')&&text('contextLatency').includes('未独立报告'),'v2 retains signed context logits and unknown standalone timing');
  check(nodes.get('logits').children.length===0&&nodes.get('encoderLogits').children.length===0&&text('cycles')==='紧凑帧未单列','context-only path invents neither six-way logits nor encoder timing');
  check(!nodes.get('archNode_model').classList.contains('arch-used')&&!nodes.get('archNode_xnd').classList.contains('arch-used')&&nodes.get('archNode_guard').classList.contains('arch-used'),'real context-only 3D path bypasses encoder and XND');
  const v2reject=[...v2];v2reject[3]=5;v2reject[4]=8;v2reject[7]=5;v2reject[8]=1;v2reject[21]=1;v2reject[22]=-22;v2reject[23]=34;
  rx('NR_FAST '+JSON.stringify(v2reject));check(text('selectionSource').includes('学习语境')&&text('resultStatus').includes('学习语境判断拒绝')&&!nodes.get('archNode_io').classList.contains('arch-used'),'learned refusal is visible and cannot be shown as a rule-rescued tool action');
  check(nodes.get('archNode_guard').classList.contains('arch-blocked'),'learned veto is located at the context module in 3D');
  for(const frame of [[...v2].slice(0,24),[...v2,0],v2.map((v,i)=>i===20?0:v),v2.map((v,i)=>i===22?2147483648:v),v2reject.map((v,i)=>i===8?0:v)]){let rejected=false;context.badV2=frame;try{run('decodeCompact(badV2)');}catch(_){rejected=true;}check(rejected,'malformed or contradictory v2 context frame rejected');}
  run('frequency=40500000');
  const hierarchical=result({model_used:1,encoder_used:1,context_used:1,context_deny:1,tool:5,selected_tool:5,decode:8,selection_source:5,execute:1,logits:[0,1,2,3,4,100],encoder_logits:[0,1,2,3,100,4],context_logits:[-22,34],context_threshold:16,context_margin:56,context_cycles:20250,encoder_cycles:270000,cycles:290250});
  rx('NR_RESULT '+JSON.stringify(hierarchical));check(text('tool').includes('分级神经输出')&&nodes.get('encoderLogits').children[4].children[1].textContent==='100'&&nodes.get('logits').children[5].children[1].textContent==='100','joint neural result and original encoder logits remain separate');
  check(text('contextLatency')==='0.500 ms'&&text('resultExplanation').includes('规则不能'),'full context timing is separate and veto is never attributed to a rule rescue: '+text('contextLatency')+' / '+text('resultExplanation'));
  const comparisonBefore=run('JSON.stringify(evidenceSession.comparisons)');run('pendingComparisonText="led37";collectComparison({model_used:2,encoder_used:0,config:6})');check(run('JSON.stringify(evidenceSession.comparisons)')===comparisonBefore,'context-only results cannot enter encoder acceleration comparison');
  rx('NR_ACTION '+JSON.stringify({phase:'tool_start',case:45,config:6,model_used:2,encoder_used:0,context_used:1,context_deny:0,context_logits:[90,-10],context_threshold:16,context_cycles:20250,encoder_cycles:0,selected_tool:2,decode:0,tool:null,cycles:20250,decision_cycles:40500,selection_source:1}));
  check(text('coreStatus').includes('正在运行')&&text('tool').includes('仅语境头')&&text('resultExplanation').includes('编码器未运行'),'CoreMark can start after context-only path without a false encoder result');
  check(writes.length===beforeContextWire,'new protocol result rendering does not send serial commands');
  rx('NR_RESULT '+JSON.stringify(result({model_used:2,encoder_used:0,context_used:1,context_deny:0,context_logits:[80,-20],context_threshold:16,context_cycles:20250,encoder_cycles:0,cycles:20250,tool:null,logits:null,encoder_logits:null})));
  check(text('cycles')==='20,250'&&text('latency')==='0.500 ms'&&text('encoderLatency')==='编码器未运行','full context-only response shows real head cost without implying encoder work');
  check(text('requestCpi')==='—'&&text('json').includes('instret'),'context-only output cannot display an encoder CPI; received raw fields remain in evidence JSON');
  const badTiming={...hierarchical,cycles:270000};context.badTiming=badTiming;let timingRejected=false;try{run('validateNeuralScope(badTiming)');}catch(_){timingRejected=true;}check(timingRejected,'contradictory sum of context and encoder cycles is rejected');
  run('healthRun={scope:"readonly",active:false,state:"completed",index:0,rows:[{label:"语境快路",state:"已完成",command:"led37",result:{model_used:2,encoder_used:0,context_used:1,context_deny:0,selected_tool:4,decode:0,execute:0,value:37,decision_cycles:40500,tool_cycles:2025}}]};renderHealth()');
  check(nodes.get('healthRows').children[0].children[3].textContent.startsWith('1.000 ms')&&nodes.get('healthRows').children[0].children[5].textContent.includes('仅语境头'),'health report uses decision scope and correct context-only source');
  const v3=[3,...v2.slice(1),1,5,5,16720,300,5018];v3[1]=46;
  rx('NR_FAST '+JSON.stringify(v3));
  check(text('processingPath').includes('XND')&&text('encoderUse')==='未运行'&&text('contextHardware').includes('JOB 5'),'v3 identifies real context-only XND and carries only its own hardware counters');
  check(text('contextHardware').includes('未单列')&&text('contextCategory')==='未报告'&&text('intentRepair')==='未报告','compactv3 cannot fabricate failures, auxiliary-category or intent-repair telemetry');
  check(nodes.get('logits').children.length===0&&nodes.get('encoderLogits').children.length===0&&text('cycles')==='紧凑帧未单列','v3 does not fabricate six-way classification or independent neural timing');
  check(nodes.get('archNode_xnd').classList.contains('arch-used')&&nodes.get('archNode_sram').classList.contains('arch-used')&&!nodes.get('archNode_model').classList.contains('arch-used')&&!nodes.get('archNode_memory').classList.contains('arch-used'),'context-only XND lights context hardware and SRAM while bypassing encoder/Engram');
  const contextHardware={loads:5,jobs:5,dma_read_bytes:16720,dma_write_bytes:300,engine_cycles:5018,failures:0};
  const v3full=result({case:47,model_used:3,encoder_used:0,context_used:1,context_xnd_used:1,context_deny:0,context_logits:[88,-40],context_threshold:192,context_cycles:12000,encoder_cycles:0,cycles:12000,tool:null,logits:null,encoder_logits:null,context_hardware:contextHardware,context_hardware_macs:16560,context_category_logits:[100,20,-40,-70,-10,-80,-100,-30,-50],context_category:0,context_bucket:5,context_bucket_source:1,intent_delta:[0,0,0,0,0],intent_repair_used:0});
  rx('NR_RESULT '+JSON.stringify(v3full));
  check(text('contextCategory').includes('执行请求')&&text('contextCategory').includes('不能直接执行')&&text('contextCategoryScores').includes('域外请求'),'auxiliary nine-way category is visible with its execution boundary and raw scores');
  check(text('contextBucket').includes('schema提示')&&text('intentRepair').includes('未使用')&&text('contextHardwareMacs').includes('16,560'),'schema-bucket source and actually received context MACs remain explicit');
  check(text('contextHardware').includes('错误 0')&&text('cycles')==='12,000'&&text('requestCpi')==='—','full contextXND metrics do not create encoder PMU or erase actual neural timing');
  const fullBoth={...hierarchical,case:48,context_xnd_used:1,context_hardware:contextHardware,context_category:6,context_category_logits:[-1,-2,-3,-4,-5,-6,100,-7,-8],context_bucket:4,context_bucket_source:0,intent_delta:[2,3,4,5,6],intent_repair_used:1};
  rx('NR_RESULT '+JSON.stringify(fullBoth));
  check(nodes.get('archNode_model').classList.contains('arch-used')&&nodes.get('archNode_xnd').classList.contains('arch-used')&&text('contextBucket').includes('编码器原判')&&text('intentRepair').includes('已使用'),'full encoder plus contextXND reports both branches and learned intent repair');
  rx('NR_ACTION '+JSON.stringify({...v3full,case:49,phase:'tool_start',decision_cycles:40500,selected_tool:2,decode:0,selection_source:1}));
  check(text('coreStatus').includes('正在运行')&&text('encoderUse')==='未运行'&&text('contextHardware').includes('XND'),'model3 CoreMark start is accepted without full encoder claims');
  for(const frame of [v3.slice(0,30),[...v3,0],v3.map((v,i)=>i===25?0:v),v3.map((v,i)=>i===26?-1:v),v3.map((v,i)=>i===30?4294967296:v)]){let rejected=false;context.badV3=frame;try{run('decodeCompact(badV3)');}catch(_){rejected=true;}check(rejected,'invalid compactv3 count/flag/length rejected');}
  for(const value of [{...v3full,context_xnd_used:0},{...v3full,model_used:2},{...v3full,encoder_used:1},{...v3full,context_category_logits:[1,2]},{...v3full,intent_delta:[1,2]},{...v3full,context_hardware:{jobs:-1}}]){let rejected=false;context.badSemantic=value;try{run('validateNeuralScope(badSemantic)');}catch(_){rejected=true;}check(rejected,'contradictory semantic/hardware metadata rejected');}
  rx('NR_RESULT '+JSON.stringify(result({case:50,model_used:0,encoder_used:0,context_used:0,context_xnd_used:0,context_hardware:{loads:0,jobs:0,dma_read_bytes:0,dma_write_bytes:0,engine_cycles:0,failures:0},context_category:0,context_category_logits:[0,0,0,0,0,0,0,0,0],context_bucket:0,context_bucket_source:0,intent_repair_used:0,intent_delta:[0,0,0,0,0],cycles:0})));
  check(text('contextHardware')==='未运行'&&text('contextCategory')==='未报告'&&text('contextCategoryScores')==='未报告'&&text('contextBucket')==='未报告'&&text('intentRepair')==='未使用','exact machine route cannot turn zero initialized metadata into a neural classification');
  check(writes.length===beforeContextWire,'protocol6 rendering and scene updates never transmit');
  // Frozen-board raw telemetry is used only as parser input in this fake-port test.
  const frozenRaw=JSON.parse(fs.readFileSync(path.join(__dirname,'../../07_runs/board/current/fourth_and_model_921600.json'),'utf8'));
  const frozenBoot=JSON.parse(fs.readFileSync(path.join(__dirname,'../../07_runs/board/current/bootstrap_921600.json'),'utf8')).boot_build;
  await run('connect()');rx('NR_BUILD '+JSON.stringify(frozenBoot));rx('NR_CONFIG {"config":6,"mode":3,"graph":1,"dot4":1}');rx('NR_READY');
  check(run('bootEpoch===1')&&run('evidenceSession.firmware_build.model_weights_bytes===197816'),'frozen identity and real shape remain explicit');
  nodes.get('command').value='led 37';await run('send()');
  const frozenLedger=result({model_used:0,encoder_used:0,context_used:0,cycles:0,receipt:{kind:1,requested:37,readback:37,match:1}});
  rx('NR_RESULT '+JSON.stringify(frozenLedger));tick(4);rx('NR_READY');
  check(run('pendingRequest.response_associated===true&&pendingRequest.receipt_verification.passed&&pendingRequest.audit_state==="执行成功"'),'audit stores real association and successful internal readback');
  check(run('pendingRequest.result.selected_tool===4&&pendingRequest.boot_epoch===1&&pendingRequest.ready_ms>=4')&&text('auditSummary').includes('真实串口'),'ledger retains command outcome, boot epoch, monotonic wall time and source');
  nodes.get('command').value='led 37';await run('send()');
  const firstAuditText=text('values');rx('NR_RESULT '+JSON.stringify({...frozenLedger,config:0,value:99}));
  check(text('values')===firstAuditText&&run('pendingRequest.association_errors[0].reason==="configuration_mismatch"'),'wrong-config result is raw evidence rather than a replacement current result');
  rx('NR_READY');check(run('pendingRequest.audit_state==="READY前缺少回报"'),'READY without accepted reply cannot certify a request');
  nodes.get('command').value='led 37';await run('send()');rx('NR_RESULT '+JSON.stringify(frozenLedger));const correctAuditValue=text('values');
  rx('NR_RESULT '+JSON.stringify({...frozenLedger,value:99}));
  check(text('values')===correctAuditValue&&run('pendingRequest.result.value===37&&pendingRequest.association_errors[0].reason==="duplicate_result"'),'duplicate result cannot overwrite the first accepted reply');rx('NR_READY');
  check(run('pendingRequest.audit_state==="回报关联未通过"'),'duplicate response remains an audit failure after READY');
  const pwmGood=result({selected_tool:1,argument:20,value:20,receipt:{kind:2,requested:20,readback:20,match:1,period:40500,high:8100,enabled:1}});
  context.qaReceipt=pwmGood;check(run('verifyWriteReceipt(qaReceipt).passed'),'PWM receipt requires real matching period, high count and enable');
  for(const delta of [{kind:1},{high:8000},{period:40000},{enabled:0},{readback:21}]){context.qaReceipt={...pwmGood,receipt:{...pwmGood.receipt,...delta}};check(!run('verifyWriteReceipt(qaReceipt).passed'),'inconsistent PWM receipt cannot certify a write');}
  nodes.get('configuration').value='0';await run('sendConfig()');rx('NR_CONFIG {"config":6,"mode":3,"graph":1,"dot4":1}');rx('NR_READY');
  check(run('pendingRequest.control_confirmation.matched===false&&pendingRequest.audit_state==="回报关联未通过"'),'wrong control acknowledgement is retained without confirming requested switch');
  nodes.get('command').value='led 37';await run('send()');rx('NR_BUILD {bad');
  check(run('frequency===null&&evidenceSession.firmware_build===null&&evidenceSession.current_configuration===null')&&text('cycles')==='—','malformed reboot clears previous identity, frequency, result and configuration');
  rx('NR_READY');check(!run('ready')&&nodes.get('send').disabled,'bare READY after malformed reboot cannot unlock the device');
  check(run('evidenceSession.requests.some(x=>x.audit_state==="设备重启中断")'),'interrupted request remains in the audit trail');
  rx('NR_BUILD '+JSON.stringify(frozenBoot));rx('NR_READY');
  const semanticFrames=frozenRaw.samples.filter(x=>x.phase==='semantic_compare').map(x=>x.full_result);
  run('resetComparison()');context.qaSw=semanticFrames[0];context.qaHw=semanticFrames[1];
  run('pendingComparisonText="actual PWM";collectComparison(qaSw);pendingComparisonText="actual PWM";collectComparison(qaHw)');
  check(run('evidenceSession.comparisons[0].integer_and_decode_match')&&run('evidenceSession.comparisons[0].score_fields_compared.includes("fusion_delta")'),'actual full-model comparison covers residual/cascade/tool scores');
  context.qaHw={...semanticFrames[1],fusion_delta:semanticFrames[1].fusion_delta.map((n,i)=>i===0?n+1:n)};
  run('pendingComparisonText="actual PWM";collectComparison(qaHw)');
  check(run('evidenceSession.comparisons[0].inference_speedup===null'),'fusion-only disagreement invalidates a speedup conclusion');
  run('resetCore()');rx('Correct operation validated.');rx('NR_CYCLES=590699515 NR_HZ=40500000 NR_ITERATIONS=1200');
  run('renderResult('+JSON.stringify(result({tool:2,selected_tool:2,value:590699515})) +')');
  check(text('coreScore')==='2.031490','frozen CoreMark displays iterations times1e6 / real cycles, not fixed-point integer');
  await run('disconnect()');
  // The one-click workflow owns one serial transaction at a time and uses only actual ACK+READY.
  await run('connect()');rx('NR_BUILD '+JSON.stringify(frozenBoot));rx('NR_CONFIG {"config":6,"mode":3,"graph":1,"dot4":1}');rx('NR_FAST_MODE {"enabled":1}');rx('NR_FORMAT {"compact":1}');rx('NR_READY');
  nodes.get('fastMode').value='0';nodes.get('fastMode').events.change();
  check(text('confirmedMode').includes('快速控制')&&text('modeDraft').includes('尚未应用'),'unapplied dropdown cannot masquerade as current AI mode');
  const aiStart=writes.length;await run('startDemo("ai")');await flush();
  check(writes.length===aiStart+1&&writes.at(-1)===':fast 0\n'&&nodes.get('send').disabled&&nodes.get('demoQuick').disabled,'AI button first sends actual fast0 and locks competing input');
  check(text('displayAction')==='等待实板结果'&&text('coreScore')==='—','starting demonstration clears old action and benchmark instead of reusing them');
  rx('NR_FAST_MODE {"enabled":0}');await flush();
  check(writes.length===aiStart+1&&text('confirmedMode').includes('AI优先'),'actual mode ACK updates confirmed value but cannot advance before READY');
  rx('NR_READY');await flush();check(writes.at(-1)===':config 6\n'&&text('confirmedMode').includes('AI优先'),'matching ACK and READY permit only the next config request');
  rx('NR_CONFIG {"config":6,"mode":3,"graph":1,"dot4":1}');rx('NR_READY');await flush();check(writes.at(-1)===':format full\n','configuration confirmation precedes the full-format request');
  rx('NR_FORMAT {"compact":0}');await flush();check(writes.at(-1)===':format full\n','format ACK alone cannot start a tool');rx('NR_READY');await flush();
  check(writes.at(-1)==='请将PWM占空比设置为20%。\n'&&text('displayCommand')==='请将PWM占空比设置为20%。','AI demonstration sends the exact already validated single-tool Chinese command');
  rx('NR_RESULT '+JSON.stringify(semanticFrames[1]));await flush();check(run('demoFlow.active')&&!run('ready'),'actual model result still waits for READY');rx('NR_READY');await flush();
  check(run('demoFlow.state==="completed"')&&text('displayAi').includes('完整模型')&&text('displayAction').includes('20%')&&text('displayReadback').includes('一致'),'AI workflow succeeds only with actual encoder use and matching PWM readback');
  check(text('displayCompute')==='74.567 ms'&&text('displayMode').includes('AI优先')&&text('resultStatus').includes('AI识别'),'judge summary reports complete model time and last-request mode rather than semantic sub-time');
  await run('startDemo("quick")');await flush();const quickStart=writes.length;
  rx('NR_READY');await flush();check(writes.length===quickStart&&run('demoFlow.state==="stopped"'),'READY without a matching mode ACK halts before any tool is sent');
  await run('startDemo("quick")');await flush();rx('NR_FAST_MODE {"enabled":0}');rx('NR_READY');await flush();check(run('demoFlow.state==="stopped"'),'wrong fast-mode ACK halts the one-click workflow');
  await run('startDemo("quick")');await flush();context.qaDemoTimeout();check(run('demoFlow.state==="stopped"')&&text('demoStatus').includes('未自动重发'),'control timeout halts and never retries an action');
  rx('NR_FAST_MODE {"enabled":1}');rx('NR_READY');
  await run('startDemo("quick")');await flush();
  for(const ack of ['NR_FAST_MODE {"enabled":1}','NR_CONFIG {"config":6,"mode":3,"graph":1,"dot4":1}','NR_FORMAT {"compact":1}']){rx(ack);rx('NR_READY');await flush();}
  check(run('demoFlow.state==="completed"')&&nodes.get('command').value==='led 37'&&text('confirmedMode').includes('快速控制'),'quick-control entry confirms real settings and fills an explicit request without auto-execution');
  await run('send()');rx('NR_RESULT '+JSON.stringify(frozenLedger));rx('NR_READY');
  check(text('resultStatus')==='实板已执行 · 快速控制'&&nodes.get('resultStatus').className==='status good'&&text('displayCompute')==='本条无需模型','model-free successful IO stays green without giant not-run metrics');
  await run('startDemo("ai")');await flush();for(const ack of ['NR_FAST_MODE {"enabled":0}','NR_CONFIG {"config":6,"mode":3,"graph":1,"dot4":1}','NR_FORMAT {"compact":0}']){rx(ack);rx('NR_READY');await flush();}
  rx('NR_RESULT '+JSON.stringify({...semanticFrames[1],selected_tool:5,execute:1,decode:8,selection_source:3,receipt:undefined}));rx('NR_READY');await flush();
  check(run('demoFlow.state==="stopped"')&&text('displayAction')==='请求已拒绝','AI demonstration cannot hide or rescue a real model/tool refusal');
  await run('startDemo("ai")');await flush();rx('NR_BUILD '+JSON.stringify(frozenBoot));check(run('demoFlow.state==="stopped"')&&!run('ready'),'reboot cancels pending demonstration and requires a fresh READY');rx('NR_READY');
  await run('startDemo("cpu")');await flush();for(const ack of ['NR_FAST_MODE {"enabled":1}','NR_CONFIG {"config":6,"mode":3,"graph":1,"dot4":1}','NR_FORMAT {"compact":1}']){rx(ack);rx('NR_READY');await flush();}
  check(writes.at(-1)==='运行CoreMark并显示CRC结果。\n','CPU self-test uses its own explicit command after confirmed quick mode');
  rx('Correct operation validated.');rx('NR_CYCLES=590699515 NR_HZ=40500000 NR_ITERATIONS=1200');rx('NR_RESULT '+JSON.stringify({...frozenLedger,selected_tool:2,tool:null,value:590699515,receipt:undefined,tool_cycles:590699515}));rx('NR_READY');await flush();
  check(run('demoFlow.state==="completed"')&&text('coreScore')==='2.031490'&&text('displayAi').includes('快速控制'),'CPU success is independent of neural use and uses actual timer/validation');
  await run('disconnect()');
  const selectCount=selections.length;await run('connect()');
  check(selections.length===selectCount+1&&selections.at(-1).filters[0].usbVendorId===0x10c4&&selections.at(-1).filters[0].usbProductId===0xea60,'default chooser filters only the confirmed CP210x UART');
  check(text('uartIdentity').includes('CP210x')&&text('status').includes('串口已打开')&&text('status').includes('KEY0'),'KEY0 is requested only after real open resolved');await run('disconnect()');
  const originalInfo=fakePort.getInfo,originalOpen=fakePort.open;let rejectedBeforeOpen=0;
  fakePort.getInfo=()=>({usbVendorId:0x0403,usbProductId:0x6010});fakePort.open=async()=>{rejectedBeforeOpen++;};nodes.get('otherUart').checked=true;
  await run('connect()');check(rejectedBeforeOpen===0&&run('port===null&&!ready')&&text('status').includes('JTAG')&&text('status').includes('不能解决'),'known dual-channel FTDI JTAG is rejected even in advanced UART selection');
  fakePort.getInfo=originalInfo;fakePort.open=async()=>{throw Error('Failed to open serial port');};nodes.get('otherUart').checked=false;
  await run('connect()');check(run('port===null&&!ready&&!connecting')&&text('status').includes('串口尚未打开')&&text('status').includes('占用')&&text('status').includes('KEY0不能解决'),'open failure is separate from firmware boot and leaves no active port or READY');
  fakePort.open=originalOpen;nodes.get('otherUart').checked=true;await run('connect()');check(selections.at(-1).filters===undefined,'advanced other UART has its own explicit unfiltered chooser');await run('disconnect()');nodes.get('otherUart').checked=false;
  console.log(JSON.stringify({source:'mock_dom_and_serial_behavior_test',checks,failures:0,physical_board_verified:false,physical_display_verified:false,presentation_layout_mock_verified:true}));
})().catch(error => { console.error(error); process.exitCode=1; });
