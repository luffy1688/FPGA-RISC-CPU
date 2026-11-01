// Graphics export in an isolated headless profile; no user tabs or serial access.
// Development source is on the server. Windows supplies WebGL rendering only;
// authoritative UART evidence and final MP4/GIF encoding stay on the server.
const fs=require('fs'),path=require('path'),{spawn}=require('child_process');
const deps=process.env.NR_NODE_MODULES||'C:/Users/luo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {chromium}=require(path.join(deps,'playwright'));
const ROOT=process.env.NR_LOCAL_ROOT||'D:/Desktop/FPGA';
const ENGINE=process.env.NR_ENGINEERING_ROOT||'D:/FPGA_PDS';
const OUT=process.env.NR_MODEL_BUILD||path.join(require('os').tmpdir(),'needlervx_ppt_gifs','model_labeled');
const FPS=8,DURATION=20,PREVIEW=process.argv.includes("--preview");
const args=['-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=D:/Desktop/system-local-only-20260712/ssh-tunnel/known_hosts','-i','C:/Users/luo/.ssh/hongshu_ai_ed25519','LUO@172.18.58.111'];
(async()=>{
 fs.mkdirSync(OUT,{recursive:true});
 const evidence=JSON.parse(fs.readFileSync(path.join(ENGINE,'07_runs/board/current/demo_hardware_report.json'),'utf8'));
 const req=evidence.page_evidence.requests.find(x=>x.result?.model_used===1&&x.result?.selected_tool===1&&x.result?.execute===0&&x.result?.receipt?.match===1);
 if(!evidence.passed||!req||req.result.argument!==20||req.result.receipt.period!==40500||req.result.receipt.high!==8100)throw Error('Missing actual validated full-model PWM20 receipt');
 const data={command:req.command,case:req.result.case,clock:evidence.page_evidence.firmware_build.clock_hz,cycles:req.result.cycles,receipt:req.result.receipt,firmware:evidence.page_evidence.firmware_build.firmware};
 const remote='ffmpeg -y -hide_banner -loglevel error -f image2pipe -vcodec mjpeg -framerate '+FPS+' -i pipe:0 -an -c:v libx264 -preset fast -crf 19 -pix_fmt yuv420p -movflags +faststart "/work/LUO/NeedleRV-X/参赛材料/展示素材/三维模型_旋转分层.mp4"';
 const encoder=spawn('ssh',[...args,PREVIEW?'cat >/dev/null':remote],{windowsHide:true,stdio:['pipe','pipe','pipe']});let logs='';encoder.stderr.on('data',b=>logs+=b);encoder.stdout.on('data',()=>{});encoder.stdin.on('error',e=>logs+=e.message);
 const finished=new Promise((resolve,reject)=>encoder.on('close',code=>code===0?resolve():reject(Error('ffmpeg '+code+' '+logs))));finished.catch(()=>{});
 const browser=await chromium.launch({executablePath:process.env.NR_EDGE||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(require('url').pathToFileURL(path.join(ROOT,'参赛材料/展示素材/成果展示.html')).href);await page.waitForFunction(()=>window.NRShowcase?.ready);
  await page.evaluate(()=>{NRShowcase.pause();NRShowcase.api.setExploded(false);NRShowcase.api.update({teaching:false,semanticCache:true,contextHead:true,active:[],flow:[],muted:[],selected:null});});await page.waitForTimeout(700);
  await page.evaluate(data=>{
   const api=NRShowcase.api,w=api.inspect(),groups={};w.scene.traverse(o=>{if(o.userData?.key)groups[o.userData.key]=o;});
   const keys=['uart','cpu','memory','model','guard','xnd','sram','permit','io'];if(keys.some(k=>!groups[k]))throw Error('Missing scene module');
   const W=1280,H=720,VIEW={x:250,y:126,w:780,h:452};
   w.renderer.setPixelRatio(1);w.renderer.setSize(VIEW.w,VIEW.h,false);w.camera.aspect=VIEW.w/VIEW.h;w.camera.fov=34;w.camera.updateProjectionMatrix();
   const canvas=document.createElement('canvas');canvas.width=W;canvas.height=H;const c=canvas.getContext('2d');
   const BLUE='#143295',GOLD='#BF8B47',INK='#26384C',MUT='#64778A',GRID='#D6DFE7',GREEN='#287666';
   const nodes=[
    {k:'uart',n:'01',title:'串口输入 / 输出',lines:['UART / USB · UTF-8'],x:24,y:156},
    {k:'cpu',n:'02',title:'RISC-V 处理器',lines:['五级流水：IF ID EX MEM WB','独立指令 / 数据 Cache'],x:24,y:250},
    {k:'memory',n:'03',title:'字符短语记忆',lines:['Unicode 2 / 3-gram'],x:24,y:344},
    {k:'model',n:'04',title:'双层字节编码器',lines:['2 blocks · d64 · 低比特'],x:24,y:438},
    {k:'guard',n:'05',title:'语境判断与门禁',lines:['位置语义头 2048 → 64 → 16'],x:1032,y:146},
    {k:'xnd',n:'06',title:'整数计算区',lines:['编码器 4MAC / 语境 8MAC'],x:1032,y:236},
    {k:'sram',n:'07',title:'片上存储与缓存',lines:['CPU128KiB + AI384KiB','独立权重缓存 128KiB'],x:1032,y:326},
    {k:'permit',n:'08',title:'执行许可',lines:['核对工具、参数与硬件能力'],x:1032,y:416},
    {k:'io',n:'09',title:'外设与寄存器回读',lines:['LED / PWM / ADC / Counter'],x:1032,y:506}
   ];
   const lift={uart:3.8,cpu:3.4,memory:1.8,model:2.2,guard:3.4,xnd:2.1,sram:2.2,permit:3.4,io:3.0};
   const anchors={uart:[0,1,0],cpu:[0,1.2,0],memory:[0,1.2,0],model:[0,1.6,0],guard:[0,1.5,0],xnd:[0,2.0,0],sram:[0,2.0,0],permit:[0,1.0,0],io:[0,1.0,0]};
   function rr(x,y,wi,h,r,fill,stroke,sw=1){c.beginPath();c.roundRect(x,y,wi,h,r);c.fillStyle=fill;c.fill();if(stroke){c.strokeStyle=stroke;c.lineWidth=sw;c.stroke();}}
   function text(t,x,y,size=20,color=INK,bold=false,align='left'){c.font=(bold?'600 ':'')+size+'px Microsoft YaHei,sans-serif';c.fillStyle=color;c.textAlign=align;c.fillText(t,x,y);c.textAlign='left';}
   function point(k){let v=groups[k].position.clone().set(...anchors[k]);groups[k].localToWorld(v);v.project(w.camera);return {x:VIEW.x+(v.x*.5+.5)*VIEW.w,y:VIEW.y+(-v.y*.5+.5)*VIEW.h};}
   function circle(x,y,r,fill){c.beginPath();c.arc(x,y,r,0,Math.PI*2);c.fillStyle=fill;c.fill();}
   const stages=[
    {s:0,e:1.8,a:keys,title:'分层认识九个模块',caption:'计算、存储、语境与外设逐一对应。'},
    {s:1.8,e:3.6,a:['uart','cpu','permit','io'],title:'控制层：接收、调度与执行',caption:'CPU调度请求，工具通过许可后操作外设。'},
    {s:3.6,e:5.5,a:['memory','model','guard'],title:'语义层：位置、短语与编码',caption:'位置特征与短语记忆共同理解中文请求。'},
    {s:5.5,e:7.5,a:['xnd','sram'],title:'计算层：4MAC、8MAC与缓存',caption:'128KiB W1缓存服务8MAC语境侧核。'},
    {s:7.5,e:10,a:keys,title:'模块合拢，进入指令流程',caption:'用一条PWM20%请求串起整个处理过程。'},
    {s:10,e:12,a:['uart'],links:[],node:0,title:'① 输入中文：设置PWM20%',caption:'本例采用完整模型路径。'},
    {s:12,e:14,a:['uart','cpu'],links:[['uart','cpu']],node:1,title:'② CPU接收与调度',caption:'UART接收UTF-8字节，CPU调度后续处理。'},
    {s:14,e:16,a:['guard','cpu'],links:[['cpu','guard']],node:2,title:'③ 语境判断：单工具请求',caption:'位置特征区分动作、否定与多动作。'},
    {s:16,e:18,a:['guard','xnd','sram'],links:[['sram','xnd'],['xnd','guard']],node:2,title:'④ 8MAC计算位置语境',caption:'2048→64→16语境头，W1权重缓存命中。'},
    {s:18,e:21,a:['model','memory','xnd','sram'],links:[['guard','model'],['memory','model'],['model','xnd'],['sram','xnd']],node:3,title:'⑤ 4MAC计算工具意图',caption:'双层编码器与短语记忆给出PWM候选。'},
    {s:21,e:23,a:['permit','xnd'],links:[['xnd','permit']],node:4,title:'⑥ CPU修正与执行许可',caption:'CPU计算70→5残差，核对工具与20%参数。'},
    {s:23,e:25,a:['permit','io'],links:[['permit','io']],node:5,title:'⑦ 写PWM：周期40500，高8100',caption:'固定1kHz周期，占空比设置为20%。'},
    {s:25,e:27,a:['io','cpu'],links:[['io','cpu']],node:6,title:'⑧ 读回寄存器：20%，一致',caption:'使能1，周期40500，高电平8100。'},
    {s:27,e:30,a:['uart','cpu','io','permit'],links:[['io','cpu'],['cpu','uart']],node:7,title:'⑨ 返回结果，继续接收请求',caption:'完整模型74.567ms，PWM请求与读回一致。'}
   ];
   window.renderModelFrame=t=>{
    const st=stages.find(s=>t>=s.s&&t<s.e)||stages.at(-1),q=Math.min(1,Math.max(0,(t-7.5)/2.5)),explode=t<7.5?1:t<10?1-q*q*(3-2*q):0;
    api.update({active:st.a,flow:[],selected:null,teaching:false,semanticCache:true,contextHead:true,muted:[]});
    for(const k of keys)groups[k].position.y=lift[k]*explode;
    const orbit=t<7.5?.025*Math.sin(t*.6):0;
    w.camera.position.set(13.5+orbit*10,22.0+explode*1.3,23.5-orbit*7);w.controls.target.set(0,.35+explode*.9,0);w.controls.update();w.scene.updateMatrixWorld(true);w.renderer.render(w.scene,w.camera);
    c.fillStyle='#FFFFFF';c.fillRect(0,0,W,H);c.drawImage(w.renderer.domElement,VIEW.x,VIEW.y,VIEW.w,VIEW.h);
    text('澄灯 LumaRV  模块分层与指令闭环',26,37,27,BLUE,true);
    text('控制板试产与返修 · 单项复测与参数读回',27,62,17,MUT);
    const phase=t<7.5?0:t<10?1:2;
    ['01  分层认模块','02  合拢结构','03  指令执行闭环'].forEach((s,i)=>{rr(26+i*204,78,193,35,7,i===phase?BLUE:'#F2F5F8');text(s,39+i*204,101,18,i===phase?'white':MUT,i===phase);});
    if(t>=10){rr(658,78,596,35,7,'#F7F0E5','#E8D6B8');text('请求：'+data.command,674,101,18,INK,true);}
    else text('4MAC编码器 + 8MAC语义侧核',1254,101,18,MUT,false,'right');
    const ps=Object.fromEntries(keys.map(k=>[k,point(k)]));
    // Fixed callout positions and projected anchors prevent labels from covering modules.
    for(const n of nodes){const p=ps[n.k],active=st.a.includes(n.k),left=n.x<500,edge=left?n.x+224:n.x,cy=n.y+34,elbow=left?edge+12:edge-12;
     c.beginPath();c.moveTo(edge,cy);c.lineTo(elbow,cy);c.lineTo(p.x,p.y);c.strokeStyle=active?'#C89B61':'#BAC7D2';c.lineWidth=active?1.7:.9;c.stroke();
    }
    // Deliberately schematic arrows: they explain dependency, not physical wires or real time.
    for(let j=0;j<(st.links||[]).length;j++){
     const [ka,kb]=st.links[j],a=ps[ka],b=ps[kb],returning=ka==='io'&&kb==='uart';let curve;
     if(returning){curve=[a,{x:995,y:572},{x:285,y:572},b];}
     else{const bend=(j%2?1:-1)*30;curve=[a,{x:a.x+(b.x-a.x)*.33,y:a.y+(b.y-a.y)*.33+bend},{x:a.x+(b.x-a.x)*.66,y:a.y+(b.y-a.y)*.66+bend},b];}
     const bez=u=>{const v=1-u;return{x:v*v*v*curve[0].x+3*v*v*u*curve[1].x+3*v*u*u*curve[2].x+u*u*u*curve[3].x,y:v*v*v*curve[0].y+3*v*v*u*curve[1].y+3*v*u*u*curve[2].y+u*u*u*curve[3].y};};
     c.beginPath();c.moveTo(a.x,a.y);c.bezierCurveTo(curve[1].x,curve[1].y,curve[2].x,curve[2].y,b.x,b.y);c.strokeStyle=GOLD;c.lineWidth=3.2;c.stroke();
     const end=bez(.96),prev=bez(.91),angle=Math.atan2(end.y-prev.y,end.x-prev.x);c.beginPath();c.moveTo(end.x,end.y);c.lineTo(end.x-12*Math.cos(angle-.45),end.y-12*Math.sin(angle-.45));c.lineTo(end.x-12*Math.cos(angle+.45),end.y-12*Math.sin(angle+.45));c.closePath();c.fillStyle=GOLD;c.fill();
     const token=bez(((t-st.s)*.62+j*.24)%1);circle(token.x,token.y,6,'#FFFFFF');circle(token.x,token.y,4,GOLD);
    }
    for(const n of nodes){const p=ps[n.k],active=st.a.includes(n.k);circle(p.x,p.y,12,active?GOLD:BLUE);text(n.n,p.x,p.y+4,12,'white',true,'center');rr(n.x,n.y,224,77,7,active?'#FFFAF1':'#F8FAFC',active?'#C89B61':GRID,active?1.6:1);text(n.n+'  '+n.title,n.x+11,n.y+26,19,active?BLUE:INK,true);n.lines.forEach((s,i)=>text(s,n.x+11,n.y+49+i*19,15.6,MUT));}
    if(t>=10){const labels=['输入','CPU','语境','编码','许可','写PWM','回读','返回'];for(let i=0;i<labels.length;i++){const x=262+i*94;rr(x,578,87,25,4,i<st.node?GREEN:i===st.node?GOLD:'#E7EDF2');text(labels[i],x+43.5,596,15,i<=st.node?'white':MUT,i===st.node,'center');}}
    else{text('模块编号与两侧名称一一对应',638,596,17,MUT,false,'center');}
    if(t>=27){rr(354,475,572,76,8,'#FFFFFFF5','#B5CEC6',1.5);text('PWM设置结果 · '+data.case,369,498,16,MUT);text('完整模型 '+(data.cycles/data.clock*1000).toFixed(3)+' ms',369,529,22,BLUE,true);text('回读 20%  ✓',908,529,23,GREEN,true,'right');}
    rr(24,617,1232,77,7,'#F1F5F9');text(st.title,41,646,23,BLUE,true);text(st.caption,41,675,18,INK);
    text('逻辑结构 · 运行记录讲解 · 3×',26,711,14,MUT);text('20%请求 → 20%读回',1254,711,14,MUT,false,'right');
    return canvas.toDataURL('image/jpeg',.91);
   };
   window.MODEL_TIMELINE=stages.map(({s,e,title})=>({start:s,end:e,title}));
  },data);
  const snapshots=[0,16,32,48,64,80,100,120,136,152];
  for(const frame of PREVIEW?[0,48,152]:Array.from({length:FPS*DURATION},(_,i)=>i)){
   const raw=await page.evaluate(t=>renderModelFrame(t),frame/FPS*1.5);const b=Buffer.from(raw.split(',')[1],'base64');
   if(snapshots.includes(frame))fs.writeFileSync(path.join(OUT,'frame-'+String(frame).padStart(3,'0')+'.jpg'),b);
   if(!encoder.stdin.write(b))await new Promise(resolve=>encoder.stdin.once('drain',resolve));
   if(frame%40===0)console.log('LABELED_MODEL_FRAME',frame,'/'+(FPS*DURATION));
  }
  encoder.stdin.end();await finished;if(errors.length)throw Error(errors.join(';'));
  const report={preview_only:PREVIEW,frames:PREVIEW?snapshots.length:FPS*DURATION,fps:FPS,duration_seconds:DURATION,modules:9,source:'logical_structure_explanation_from_saved_physical_PWM_receipt',evidence_file:'07_runs/board/current/demo_hardware_report.json',record_case:data.case,model_used:1,request:data.command,receipt:data.receipt,live_serial_access:false,timeline:await page.evaluate(()=>MODEL_TIMELINE.map(s=>({...s,start:s.start/1.5,end:s.end/1.5})))};
  fs.writeFileSync(path.join(OUT,'render_info.json'),JSON.stringify(report,null,2)+'\n','utf8');console.log(PREVIEW?'LABELED_MODEL_PREVIEW_READY':'LABELED_MODEL_VIDEO_READY',JSON.stringify({duration_seconds:DURATION,modules:9,model_used:1,record_case:data.case}));
 }finally{encoder.stdin.end();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
