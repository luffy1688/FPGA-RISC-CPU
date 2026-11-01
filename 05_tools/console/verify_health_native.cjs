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
const writes = [], downloads = [];
let pendingRead;
const fakeReader = {
  read: () => new Promise(resolve => { pendingRead = resolve; }),
  cancel: async () => { if (pendingRead) pendingRead({done:true}); },
  releaseLock: () => {}
};
const fakePort = {
  open: async () => {}, close: async () => {}, getInfo: () => ({usbVendorId:0x1234}),
  readable: {getReader: () => fakeReader},
  writable: {getWriter: () => ({write: async data => nativeWrite(data), releaseLock: () => {}})}
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
  TextEncoder, TextDecoder, URLSearchParams, Date, setTimeout,
  document:fakeDocument,
  window: {isSecureContext:true,location:{search:'?present=1'}}, navigator: {serial:{requestPort:async () => fakePort, addEventListener:() => {}}},
  Blob: class { constructor(parts, options) { this.contents=parts.join(''); this.type=options.type; } },
  URL: {createObjectURL: blob => { downloads.push(blob); return 'blob:qa'; }, revokeObjectURL:() => {}}
});
vm.runInContext(script, context, {filename:'index.html'});
const run = code => vm.runInContext(code, context);
const text = id => nodes.get(id).textContent;
const rx = (line,ending='\r\n') => {context.qaLine=line;context.qaWireBytes=Buffer.byteLength(line+ending);run('receiveLine(qaLine,qaWireBytes)');};

// Physical UART bridge for the unchanged production page state machine.
// DOM/port shells are test adapters: this is NOT a browser/display recording.
const board=path.resolve(process.argv[2]);let serial=0;
const nativeWrite=async data=>{
 const command=Buffer.from(data).toString('utf8').trimEnd();writes.push(command);
 const temp=path.join(board,'command.pending');
 fs.writeFileSync(temp,JSON.stringify({id:'HEALTH_'+(++serial),text:command}),'utf8');
 for(let attempt=0;;attempt++){try{fs.renameSync(temp,path.join(board,'command.json'));break;}catch(error){if(attempt>50)throw error;await new Promise(resolve=>setTimeout(resolve,5));}}
};
const state=JSON.parse(fs.readFileSync(path.join(board,'capture_status.json'),'utf8').replace(/^\uFEFF/,''));
if(!state.events_path)throw new Error('This diagnostic requires the PS event queue; current capture uses native RPC. Production UI does not depend on this adapter.');
const eventPath=state.events_path;const prior=fs.readFileSync(eventPath,'utf8');
const events=prior.split(/\r?\n/).filter(Boolean).map(line=>JSON.parse(line));
const raw=events.filter(x=>x.direction==='RX').map(x=>x.data.text||'').join('');
let offset=Buffer.byteLength(prior),carry='';
(async()=>{
 await run('connect()');
 for(const prefix of ['NR_BUILD ','NR_CONFIG ','NR_FAST_MODE ','NR_FORMAT ']){
  const lines=raw.split(/\r?\n/).filter(x=>x.startsWith(prefix));assert(lines.length,'Missing real '+prefix);rx(lines[lines.length-1],'\n');
 }
 rx('NR_READY','\n');nodes.get('healthScope').value='io';run('startHealth()');
 const deadline=Date.now()+90000;
 while(run('healthRun.active')&&Date.now()<deadline){
  const end=fs.statSync(eventPath).size;
  if(end>offset){const bytes=Buffer.alloc(end-offset),fd=fs.openSync(eventPath,'r');fs.readSync(fd,bytes,0,bytes.length,offset);fs.closeSync(fd);offset=end;carry+=bytes.toString('utf8');
   const lines=carry.split('\n');carry=lines.pop();for(const line of lines){if(!line.trim())continue;const ev=JSON.parse(line);if(ev.direction!=='RX')continue;
    nativeWire+=(ev.data.text||'');let n;while((n=nativeWire.indexOf('\n'))>=0){const wire=nativeWire.slice(0,n);nativeWire=nativeWire.slice(n+1);rx(wire,'\n');}
   }
  }
  await new Promise(resolve=>setTimeout(resolve,5));
 }
 const health=run('JSON.parse(JSON.stringify(healthRun))');
 const report={source:'production_console_JS_VM_with_physical_UART_bridge',mock_dom:true,mock_device_results:false,browser_verified:false,physical_uart_capture:state.capture_id,health,writes,passed:health.state==='completed'&&writes.length===9};
 fs.writeFileSync(path.join(board,'health_hardware_report.json'),JSON.stringify(report,null,2)+'\n','utf8');
 console.log(JSON.stringify({passed:report.passed,transactions:writes.length,state:health.state,reason:health.stop_reason,initial_io:health.initial_io,restore:health.restore_state}));
 await run('disconnect()');if(!report.passed)process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
let nativeWire='';
