/* Real Three geometry/scene tests with a fake renderer; no browser or WebGL claim. */
'use strict';
const assert=require('assert'),path=require('path');const {pathToFileURL}=require('url');
(async()=>{
 const THREE=await import('./.arch-build/node_modules/three/build/three.module.js');
 const frames=new Map();let counter=0,now=0,renders=0,disposed=false;global.performance={now:()=>now};
 global.requestAnimationFrame=fn=>{frames.set(++counter,fn);return counter;};global.cancelAnimationFrame=id=>frames.delete(id);
 const tick=(limit=100)=>{for(let i=0;i<limit&&frames.size;i++){const pending=[...frames.values()];frames.clear();now+=16;for(const fn of pending)fn(now);}};
 class Element{constructor(tag){this.tag=tag;this.style={};this.events={};this.children=[];this.hidden=false;this.textContent='';this.attributes={};this.classList={toggle:()=>{}};}appendChild(c){this.children.push(c);}setAttribute(k,v){this.attributes[k]=v;}addEventListener(k,fn){this.events[k]=fn;}remove(){}getBoundingClientRect(){return {left:0,top:0,width:900,height:540};}getContext(){return {fillRect(){},fillText(){},drawImage(){},measureText(s){return {width:s.length*14};}};}toDataURL(){return 'data:image/png;base64,unit-only';}}
 global.document={createElement:tag=>new Element(tag)};
 const canvas=new Element('canvas'),host=new Element('div');host.clientWidth=900;host.clientHeight=540;
 const renderer={domElement:canvas,setPixelRatio(){},setSize(){},render(scene,camera){renders++;scene.updateMatrixWorld();camera.updateMatrixWorld();},dispose(){disposed=true;}};
 const module=await import(pathToFileURL(path.join(__dirname,'architecture-scene.js')).href);
 const api=module.createScene(host,{rendererFactory:()=>renderer,controlsFactory:camera=>({target:new THREE.Vector3(),update(){camera.lookAt(this.target);},addEventListener(){},dispose(){}})});
 const world=api.inspect();assert(world.modules.length===10&&world.paths.length===12);assert(host.children.includes(canvas));let workerGroup;world.scene.traverse(o=>{if(o.userData.key==='worker')workerGroup=o;});assert(workerGroup&&!workerGroup.visible);api.update({dualCore:true,workerBusy:true});assert(workerGroup.visible);api.update({dualCore:false,workerBusy:false});assert(!workerGroup.visible);
 let instances=0,finite=0;world.scene.traverse(obj=>{if(obj.isInstancedMesh)instances+=obj.count;for(const v of [...obj.position,...obj.scale]){assert(Number.isFinite(v));finite++;}});assert(instances===512);assert(finite>1000);
 api.update({active:['cpu'],muted:['model','xnd'],selected:'cpu',teaching:false,flow:[]});tick();assert(frames.size===0,'idle scene must not continuously render');
 const before=renders;api.focus('memory');tick();assert(renders>before&&frames.size===0,'camera tween stops after arrival');
 api.setExploded(true);tick();assert(frames.size===0);const board=world.scene.children.find(x=>x.isGroup);const mem=board.children.find(x=>x.userData.key==='memory');assert(mem.position.y>2.19);
 api.update({teaching:true,flow:['input','context','sram']});tick(5);assert(frames.size>0);api.setVisible(false);assert(frames.size===0);const paused=renders;tick();assert(renders===paused);
 api.setVisible(true);api.update({teaching:false});tick();assert(frames.size===0);assert(api.exportImage().startsWith('data:image/png'));
 api.dispose();assert(disposed&&frames.size===0);
 console.log(JSON.stringify({source:'real_three_geometry_with_fake_renderer',geometry_finite_values:finite,learned_table_cells:instances,offline:true,browser_verified:false,webgl_verified:false,idle_animation_stops:true}));
})().catch(error=>{console.error(error);process.exitCode=1;});
