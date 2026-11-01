/* Logical chip-floorplan teaching scene. Not the placed/routed physical layout.
 * three.js r186, MIT; bundled locally for offline operation. */
import * as THREE from './.arch-build/node_modules/three/build/three.module.js';
import {OrbitControls} from './.arch-build/node_modules/three/examples/jsm/controls/OrbitControls.js';
import {GLTFExporter} from './.arch-build/node_modules/three/examples/jsm/exporters/GLTFExporter.js';
export function createScene(host,{onSelect,onFailure,onExportCaption,rendererFactory,controlsFactory}={}){
  const scene=new THREE.Scene();scene.background=new THREE.Color('#edf2f5');
  scene.fog=new THREE.Fog('#edf2f5',32,75);
  const renderer=rendererFactory?rendererFactory():new THREE.WebGLRenderer({antialias:true,alpha:false,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(globalThis.devicePixelRatio||1,1.6));renderer.setSize(Math.max(1,host.clientWidth),Math.max(1,host.clientHeight));
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.12;
  renderer.domElement.setAttribute('aria-label','可旋转的LumaRV逻辑芯片剖面；模块也可用下方按钮选择');
  renderer.domElement.setAttribute('tabindex','0');host.appendChild(renderer.domElement);
  const camera=new THREE.PerspectiveCamera(38,1,.1,150);camera.position.set(16,18,20);
  const controls=controlsFactory?controlsFactory(camera,renderer.domElement):new OrbitControls(camera,renderer.domElement);controls.target.set(0,.2,0);controls.enableDamping=false;controls.minDistance=10;controls.maxDistance=42;controls.minPolarAngle=.16;controls.maxPolarAngle=Math.PI*.47;controls.enablePan=true;
  controls.mouseButtons={LEFT:THREE.MOUSE.ROTATE,MIDDLE:THREE.MOUSE.DOLLY,RIGHT:THREE.MOUSE.PAN};
  scene.add(new THREE.HemisphereLight('#ffffff','#879cad',2.2));
  const light=new THREE.DirectionalLight('#fff4e6',3);light.position.set(-7,20,12);scene.add(light);
  const fill=new THREE.DirectionalLight('#b8d8f3',1.2);fill.position.set(12,7,-15);scene.add(fill);
  const root=new THREE.Group();scene.add(root);
  const modules=new Map(),pickables=[],paths=[],labels=[];let visible=true,disposed=false,frame=0,animation=null,explosion=0,targetExplosion=0;
  let state={active:[],blocked:[],muted:[],selected:null,teaching:false,flow:[]};
  const material=(color,metal=.15)=>new THREE.MeshStandardMaterial({color,roughness:.5,metalness:metal});
  const sharedBox=new THREE.BoxGeometry(1,1,1),silver=material('#b5c1c7',.7),gold=material('#b49758',.65),traceMat=material('#719c96',.5);
  function box(parent,x,y,z,w,h,d,mat){const m=new THREE.Mesh(sharedBox,mat);m.position.set(x,y,z);m.scale.set(w,h,d);parent.add(m);return m;}
  box(root,0,-.46,0,18.6,.34,10.6,material('#49716d',.35));
  box(root,0,-.72,0,19,.12,11,material('#d2dce1',.5));
  box(root,0,-.91,0,19.7,.20,11.7,material('#c2cdd4',.35));
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(180,180),material('#e4ebef',0));floor.rotation.x=-Math.PI/2;floor.position.y=-1.06;scene.add(floor);
  const grid=new THREE.GridHelper(100,80,'#c5d3dc','#d7e1e7');grid.position.y=-1.055;scene.add(grid);
  for(let x=-8.8;x<=8.8;x+=.44){box(root,x,-.275,-4.8,.025,.015,9.5,traceMat);}
  for(let z=-4.5;z<=4.5;z+=.5){box(root,0,-.264,z,17.8,.012,.018,traceMat);}
  for(const x of [-8.7,8.7])for(const z of [-4.65,4.65]){
    const standoff=new THREE.Mesh(new THREE.CylinderGeometry(.16,.16,.34,12),silver);standoff.position.set(x,-.17,z);root.add(standoff);
    const screw=new THREE.Mesh(new THREE.CylinderGeometry(.08,.08,.35,10),material('#53646e',.5));screw.position.set(x,-.15,z);root.add(screw);
  }
  function textTexture(text,{background='#1e3544',color='#f5f8fa',width=512,height=128,font=42}={}){
    const c=document.createElement('canvas');c.width=width;c.height=height;const ctx=c.getContext('2d');ctx.fillStyle=background;ctx.fillRect(0,0,width,height);ctx.font=`600 ${font}px system-ui,Microsoft YaHei,sans-serif`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillStyle=color;ctx.fillText(text,width/2,height/2,width-24);const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;return t;
  }
  function plaque(parent,text,x,y,z,w,d,bg='#eaf0f3',ink='#233f4f',font=40){const m=new THREE.Mesh(new THREE.PlaneGeometry(w,d),new THREE.MeshBasicMaterial({map:textTexture(text,{background:bg,color:ink,font}),side:THREE.DoubleSide}));m.rotation.x=-Math.PI/2;m.position.set(x,y,z);parent.add(m);return m;}
  function create(key,title,x,z,w,d,color){
    const g=new THREE.Group();g.position.set(x,0,z);g.userData.key=key;root.add(g);
    const mat=material(color,.3);const base=box(g,0,.20,0,w,.48,d,mat);
    for(let i=0;i<7;i++){const a=(i-3)*w/8;box(g,a,-.03,d/2+.12,.09,.08,.24,silver);box(g,a,-.03,-d/2-.12,.09,.08,.24,silver);}
    for(let i=0;i<5;i++){const a=(i-2)*d/6;box(g,-w/2-.12,-.03,a,.24,.08,.08,silver);box(g,w/2+.12,-.03,a,.24,.08,.08,silver);}
    const outline=new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(w+.08,.56,d+.08)),new THREE.LineBasicMaterial({color:'#e1a568'}));outline.position.y=.24;outline.visible=false;g.add(outline);
    const anchor=new THREE.Vector3(0,1.15,0);const label=document.createElement('button');label.className='arch3-label';label.textContent=title;label.type='button';label.addEventListener('click',()=>onSelect?.(key));label.setAttribute('aria-label','查看'+title);host.appendChild(label);labels.push({key,object:g,anchor,label});
    modules.set(key,{key,g,mat,base,outline,color:new THREE.Color(color),origin:new THREE.Vector3(x,0,z),lift:key==='model'?1.65:key==='memory'?2.2:key==='cpu'?1.2:key==='xnd'?1.6:.65});
    g.traverse(o=>{if(o.isMesh){o.userData.module=key;pickables.push(o);}});return g;
  }
  const uart=create('uart','UART / USB',-7.3,-2.65,1.6,1.6,'#779da7');
  box(uart,0,.64,0,1.2,.42,1.35,silver);box(uart,-.06,.67,.69,.78,.22,.04,material('#263a46'));
  plaque(uart,'UTF-8',0,.87,-.12,1,.38);
  const cpu=create('cpu','RV32IM · 五级CPU',-3.6,-2.15,3.3,2.7,'#476879');
  const stageColors=['#d3e6ec','#bcd6df','#9cbbc8','#b8cbd6','#dfebef'];
  for(let i=0;i<5;i++){box(cpu,-1.25+i*.62,.68,-.38,.52,.45,1.33,material(stageColors[i]));plaque(cpu,['IF','ID','EX','MEM','WB'][i],-1.25+i*.62,.915,-.38,.50,.34,'#f5f8fa','#254555',50);}
  box(cpu,-.66,.64,.78,1.30,.32,.47,material('#a9c9b8'));plaque(cpu,'I-CACHE',-.66,.81,.78,1.25,.36);
  box(cpu,.79,.64,.78,1.30,.32,.47,material('#c6b9d8'));plaque(cpu,'D-CACHE',.79,.81,.78,1.25,.36);
  const guard=create('guard','上下文门禁',.15,-3.05,2.1,1.25,'#8c80a8');
  for(let i=0;i<3;i++)box(guard,-.55+i*.55,.67,0,.32,.45,.7,material(['#c3b8d5','#e3dcea','#a797bd'][i]));
  const permit=create('permit','执行许可',3.3,-3,2.1,1.3,'#719c87');
  box(permit,0,.72,0,1.34,.54,.74,material('#b8d5c6'));plaque(permit,'POLICY',0,1.0,0,1.28,.40);
  const io=create('io','GPIO · PWM · ADC',7,-2.3,2.4,2.1,'#c29b6e');
  for(let i=0;i<6;i++){const led=new THREE.Mesh(new THREE.CylinderGeometry(.105,.13,.25,12),material('#8fa29e'));led.position.set(-.85+i*.34,.58,-.55);io.add(led);}
  box(io,-.62,.68,.40,.68,.42,.56,material('#b7cbd2'));plaque(io,'ADC',-.62,.91,.40,.64,.31);
  box(io,.56,.68,.40,1.02,.42,.56,material('#dbbd97'));plaque(io,'PWM',.56,.91,.40,.98,.31);
  const mem=create('memory','Unicode 字符短语记忆',-6.45,2.2,2.8,2.6,'#9c8bb8');
  const tileGeometry=new THREE.BoxGeometry(.10,.08,.10);
  for(let bank=0;bank<2;bank++){
    box(mem,0,.58+(bank*.38),0,2.5,.12,2.25,material(bank?'#c3b4d8':'#b4a1cd'));
    const tiles=new THREE.InstancedMesh(tileGeometry,material(bank?'#e5d9ef':'#d3c2e5'),256);const m=new THREE.Matrix4();
    for(let row=0;row<16;row++)for(let col=0;col<16;col++){m.makeTranslation((col-7.5)*.13,.70+bank*.38,(row-7.5)*.13);tiles.setMatrixAt(row*16+col,m);}mem.add(tiles);
  }
  plaque(mem,'2-GRAM  /  3-GRAM',0,1.17,0,2.4,.43,'#ede7f4','#54416e',34);
  const model=create('model','双层语义编码器',-2.65,2.2,3.1,2.6,'#7c9eb2');
  for(let layer=0;layer<2;layer++){
    const y=.66+layer*.45;box(model,0,y,0,2.75,.13,2.2,material(layer?'#bdd4e1':'#a6c5d7'));
    for(let h=0;h<4;h++)box(model,-.98+h*.65,y+.12,-.3,.43,.12,.8,material('#f2f7fa'));
    plaque(model,layer?'BLOCK 2':'BLOCK 1',0,y+.10,.70,2.45,.36,'#dfeaf0','#305b73',37);
  }
  const xnd=create('xnd','XND · 四路整数乘加',1.20,2.15,3.1,2.55,'#ba845e');
  for(let i=0;i<4;i++){
    const x=-1.05+(i%2)*.76,z=-.65+Math.floor(i/2)*.72;box(xnd,x,.70,z,.63,.50,.60,material('#dfb58a'));plaque(xnd,'MAC '+i,x,.96,z,.58,.23,'#f8ecdc','#77512c',36);
  }
  box(xnd,1.05,.70,-.26,.58,.51,1.36,material('#a5c6b4'));plaque(xnd,'FUSE',1.05,.97,-.26,.54,.32,'#dcecdf','#325b49',33);
  plaque(xnd,'INT4 / INT8 → INT32',-.20,.47,1.00,2.6,.28,'#d6b294','#69482e',32);
  const sram=create('sram','AI SRAM · 128 KiB',5.45,2.0,3.0,2.8,'#6f9c91');
  for(let bank=0;bank<2;bank++){const x=bank? .73:-.73;box(sram,x,.73,-.25,1.20,.54,1.7,material(bank?'#bad6ca':'#a7ccbc'));for(let i=0;i<5;i++)box(sram,x,.99,-.88+i*.31,1.04,.05,.045,material('#edf5ef'));plaque(sram,bank?'SLOT B':'SLOT A',x,1.04,.48,1.1,.32,'#e4f1e9','#3c6657',36);}
  plaque(sram,'MODEL / WORKSPACE',0,.47,1.13,2.7,.26,'#bddbcc','#3b5e50',29);
  // Separate physical lane counts are shown only for the selected cached semantic design.
  const semanticDeck=new THREE.Group();xnd.add(semanticDeck);
  box(semanticDeck,0,1.36,0,2.86,.14,2.25,material('#173b70'));
  for(let lane=0;lane<8;lane++){
    const x=-1.03+(lane%4)*.69,z=-.52+Math.floor(lane/4)*.81;
    box(semanticDeck,x,1.61,z,.55,.33,.62,material('#c89b61'));
    plaque(semanticDeck,String(lane),x,1.79,z,.43,.28,'#fff3dc','#574025',42);
  }
  plaque(semanticDeck,'SEMANTIC 8 MAC',0,1.80,.91,2.60,.25,'#143295','#ffffff',32);
  const weightDeck=new THREE.Group();sram.add(weightDeck);
  box(weightDeck,0,1.40,-.02,2.65,.17,2.30,material('#173b70'));
  for(let bank=0;bank<4;bank++)box(weightDeck,-.96+bank*.64,1.67,-.06,.49,.34,1.65,material(bank%2?'#b7cadd':'#c89b61'));
  plaque(weightDeck,'W1 CACHE 128 KiB',0,1.89,.99,2.62,.28,'#143295','#ffffff',32);
  const semanticHead=new THREE.Group();guard.add(semanticHead);
  box(semanticHead,0,1.04,0,1.92,.12,1.05,material('#173b70'));
  plaque(semanticHead,'2048 > 64 > 16',0,1.12,0,1.8,.48,'#143295','#ffffff',40);
  semanticDeck.visible=weightDeck.visible=semanticHead.visible=false;
  // Populate newly added child geometry into the picking list as well.
  for(const [key,module] of modules)module.g.traverse(o=>{if(o.isMesh){o.userData.module=key;if(!pickables.includes(o))pickables.push(o);}});
  function makePath(key,points){const curve=new THREE.CatmullRomCurve3(points.map(p=>new THREE.Vector3(...p)),false,'centripetal');const mat=material('#829fa6',.35);const tube=new THREE.Mesh(new THREE.TubeGeometry(curve,36,.035,6,false),mat);root.add(tube);const bead=new THREE.Mesh(new THREE.SphereGeometry(.10,10,8),new THREE.MeshBasicMaterial({color:'#e9af6b'}));bead.visible=false;root.add(bead);paths.push({key,curve,tube,mat,bead});}
  makePath('input',[[-6.4,.1,-2.65],[-5.7,.1,-2.65],[-5.4,.1,-2.15]]);
  makePath('cpu',[[-1.85,.1,-2.15],[-1.55,.1,-2.15],[-1.35,.1,-3.05],[-.98,.1,-3.05]]);
  makePath('fast',[[1.25,.1,-3.05],[2.2,.1,-3.05]]);
  makePath('context',[[.15,.1,-2.35],[.15,.1,-.8],[1.2,.1,-.8],[1.2,.1,.75]]);
  makePath('model',[[.15,.1,-2.35],[.15,.1,-1.1],[-2.65,.1,-.9],[-2.65,.1,.75]]);
  makePath('memory',[[-5,.1,2.2],[-4.24,.1,2.2]]);
  makePath('xnd',[[-1,.1,2.2],[-.4,.1,2.2]]);
  makePath('permit',[[1.2,.1,.75],[1.2,.1,-.4],[3.3,.1,-.6],[3.3,.1,-2.25]]);
  makePath('sram',[[2.85,.1,2.2],[3.8,.1,2.2]]);
  makePath('output',[[4.43,.1,-3],[5.3,.1,-3],[5.3,.1,-2.3],[5.7,.1,-2.3]]);
  makePath('return',[[8.25,.1,-2.3],[8.75,.1,-2.3],[8.75,.1,4.35],[-8.55,.1,4.35],[-8.55,.1,-2.65],[-8.16,.1,-2.65]]);
  plaque(root,'LUMARV  /  LOGICAL CUTAWAY',0,-.245,-4.45,7,.42,'#49716d','#dbe9e7',35);
  const raycaster=new THREE.Raycaster();let down=null;
  function pointerDown(e){down=[e.clientX,e.clientY];}
  function pointerUp(e){if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;const rect=renderer.domElement.getBoundingClientRect();const p=new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(p,camera);const hit=raycaster.intersectObjects(pickables,false)[0];if(hit)onSelect?.(hit.object.userData.module);down=null;}
  renderer.domElement.addEventListener('pointerdown',pointerDown);renderer.domElement.addEventListener('pointerup',pointerUp);
  function renderNow(){if(!visible||disposed)return;scene.updateMatrixWorld();renderer.render(scene,camera);const v=new THREE.Vector3();for(const item of labels){v.copy(item.anchor);item.object.localToWorld(v);v.project(camera);const shown=v.z>-1&&v.z<1&&Math.abs(v.x)<1.1&&Math.abs(v.y)<1.1;item.label.hidden=!shown;if(shown){item.label.style.transform=`translate(-50%,-50%) translate(${(v.x*.5+.5)*host.clientWidth}px,${(-v.y*.5+.5)*host.clientHeight}px)`;if(item.key==='guard')item.label.textContent=state.contextHead?'规则门禁 / 学习语境头':'上下文门禁';if(item.key==='xnd')item.label.textContent=state.semanticCache?'计算区 · XND4 / 语境8MAC':'XND · 四路整数乘加';if(item.key==='sram')item.label.textContent=state.semanticCache?'共享AI384KiB / 权重缓存128KiB':'AI SRAM · 128KiB';item.label.classList.toggle('is-active',state.active.includes(item.key));item.label.classList.toggle('is-selected',state.selected===item.key);item.label.classList.toggle('is-muted',state.muted.includes(item.key));}}}
  function schedule(){if(!frame&&visible&&!disposed)frame=requestAnimationFrame(t=>{frame=0;tick(t);});}
  function tick(t){if(!visible||disposed)return;let again=false;
    if(Math.abs(explosion-targetExplosion)>.001){explosion+=(targetExplosion-explosion)*.17;for(const module of modules.values())module.g.position.y=explosion*module.lift;again=true;}
    if(animation){const a=animation,p=Math.min(1,(t-a.start)/550),smooth=p*p*(3-2*p);camera.position.lerpVectors(a.from,a.to,smooth);controls.target.lerpVectors(a.targetFrom,a.targetTo,smooth);controls.update();if(p===1)animation=null;else again=true;}
    if(state.teaching){for(let i=0;i<paths.length;i++){const p=paths[i];p.bead.visible=state.flow.includes(p.key);if(p.bead.visible)p.bead.position.copy(p.curve.getPointAt(((t*.00045)+i*.07)%1));}again=true;}else for(const p of paths)p.bead.visible=false;
    renderNow();if(again)schedule();
  }
  function update(next){state={...state,...next};semanticDeck.visible=weightDeck.visible=!!state.semanticCache;semanticHead.visible=!!state.contextHead;for(const module of modules.values()){
    const used=state.active.includes(module.key),blocked=state.blocked.includes(module.key),muted=state.muted.includes(module.key);module.mat.color.copy(module.color);module.mat.emissive.set(blocked?'#9d4a35':used?'#285546':'#000000');module.mat.emissiveIntensity=blocked?.5:used?.33:0;module.mat.transparent=muted;module.mat.opacity=muted?.34:1;module.outline.visible=state.selected===module.key;
  }for(const p of paths){p.mat.color.set(state.flow.includes(p.key)?'#76a48f':'#829fa6');p.mat.emissive.set(state.flow.includes(p.key)?'#31564b':'#000000');p.mat.emissiveIntensity=state.flow.includes(p.key)?.45:0;}schedule();}
  function focus(key,immediate=false){const m=modules.get(key);const center=m?m.g.position.clone().add(new THREE.Vector3(0,.3,0)):new THREE.Vector3(0,.2,0);const offset=m?new THREE.Vector3(7,8,10):new THREE.Vector3(16,18,20);const to=center.clone().add(offset);if(immediate){camera.position.copy(to);controls.target.copy(center);controls.update();renderNow();}else{animation={start:performance.now(),from:camera.position.clone(),to,targetFrom:controls.target.clone(),targetTo:center};schedule();}}
  function resize(){if(!visible||disposed||!host.clientWidth)return;renderer.setSize(host.clientWidth,host.clientHeight);camera.aspect=host.clientWidth/host.clientHeight;camera.updateProjectionMatrix();renderNow();}
  const observer=typeof ResizeObserver==='function'?new ResizeObserver(resize):null;observer?.observe(host);controls.addEventListener('change',renderNow);controls.addEventListener('start',()=>{animation=null;});
  function contextLost(event){event.preventDefault();visible=false;if(frame)cancelAnimationFrame(frame);frame=0;onFailure?.('WebGL上下文已丢失。可切换到平面说明，串口连接不受影响。');}
  renderer.domElement.addEventListener('webglcontextlost',contextLost);
  function exportImage(){renderNow();const canvas=document.createElement('canvas');canvas.width=1600;canvas.height=1000;const ctx=canvas.getContext('2d');ctx.fillStyle='#edf2f5';ctx.fillRect(0,0,1600,1000);ctx.drawImage(renderer.domElement,0,80,1600,820);ctx.fillStyle='#233f4f';ctx.font='600 30px system-ui,Microsoft YaHei,sans-serif';ctx.fillText('LumaRV · 逻辑芯片剖面',44,48);ctx.font='20px system-ui,Microsoft YaHei,sans-serif';ctx.fillText('结构示意 / 非物理布局 / 非逐拍遥测',44,950);ctx.fillText((onExportCaption?.()||'离线结构讲解').slice(0,70),44,983);
    // Labels are projected from the same camera; no result or latency is invented.
    for(const item of labels){if(item.label.hidden)continue;const v=item.anchor.clone();item.object.localToWorld(v);v.project(camera);const x=(v.x*.5+.5)*1600,y=80+(-v.y*.5+.5)*820;const txt=item.label.textContent;ctx.font='600 19px system-ui,Microsoft YaHei,sans-serif';const w=ctx.measureText(txt).width+24;ctx.fillStyle='#ffffffeb';ctx.fillRect(x-w/2,y-15,w,30);ctx.fillStyle='#294552';ctx.fillText(txt,x-w/2+12,y+7);}
    return canvas.toDataURL('image/png');
  }
  async function exportModel(){
    const group=root.clone(true);group.name='LumaRV logical architecture';const instanced=[];
    group.traverse(o=>{if(o.isMesh)o.userData={};if(o.isInstancedMesh)instanced.push(o);});
    // Flatten instance decorations for Office consumers that lack GPU-instancing extensions.
    for(const old of instanced){const copies=new THREE.Group();copies.position.copy(old.position);copies.quaternion.copy(old.quaternion);copies.scale.copy(old.scale);for(let i=0;i<old.count;i++){const mesh=new THREE.Mesh(old.geometry,old.material);old.getMatrixAt(i,mesh.matrix);mesh.matrixAutoUpdate=false;copies.add(mesh);}old.parent.add(copies);old.removeFromParent();}
    group.updateMatrixWorld(true);const bounds=new THREE.Box3().setFromObject(group);group.position.sub(bounds.getCenter(new THREE.Vector3()));group.updateMatrixWorld(true);
    return new GLTFExporter().parseAsync(group,{binary:true,onlyVisible:true,trs:false});
  }
  resize();return {update,focus,resize,exportModel,setExploded:value=>{targetExplosion=value?1:0;schedule();},setVisible:value=>{visible=!!value;if(!visible){if(frame)cancelAnimationFrame(frame);frame=0;}else{resize();schedule();}},exportImage,inspect:()=>({modules:[...modules.keys()],paths:paths.map(p=>p.key),scene,camera,renderer,controls}),dispose:()=>{disposed=true;if(frame)cancelAnimationFrame(frame);observer?.disconnect();controls.dispose();renderer.dispose();for(const item of labels)item.label.remove();renderer.domElement.remove();}};
}
