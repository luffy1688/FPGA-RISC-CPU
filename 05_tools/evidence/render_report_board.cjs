// Isolated rendering of the existing logical model for report figures; no serial access.
const fs=require('fs'),path=require('path');
const {chromium}=require('C:/Users/luo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{const b=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});try{
 const p=await b.newPage({viewport:{width:1600,height:1000},deviceScaleFactor:1});await p.goto(require('url').pathToFileURL('D:/Desktop/FPGA/参赛材料/展示素材/成果展示.html').href);await p.waitForFunction(()=>NRShowcase.ready);await p.evaluate(()=>{NRShowcase.pause();NRShowcase.api.setExploded(false);NRShowcase.api.update({teaching:false,semanticCache:true,contextHead:true,dualCore:true,active:[],flow:[],selected:null});});await p.waitForTimeout(650);
 const data=await p.evaluate(()=>{const a=NRShowcase.api,w=a.inspect(),groups={};w.scene.traverse(o=>{if(o.userData.key)groups[o.userData.key]=o;});
 const keys=['uart','cpu','memory','model','guard','xnd','sram','permit','io','worker'],lift=[3.8,3.4,1.8,2.2,3.4,2.1,2.2,3.4,3,3];keys.forEach((k,i)=>groups[k].position.y=lift[i]);
 w.renderer.setPixelRatio(1);w.renderer.setSize(1000,445,false);w.camera.aspect=1000/445;w.camera.fov=32;w.camera.updateProjectionMatrix();w.camera.position.set(13.5,23.3,23.5);w.controls.target.set(0,1.4,0);w.controls.update();w.scene.updateMatrixWorld(true);w.renderer.render(w.scene,w.camera);
 const c=document.createElement('canvas');c.width=1000;c.height=700;const x=c.getContext('2d');x.fillStyle='white';x.fillRect(0,0,1000,700);x.drawImage(w.renderer.domElement,0,0,1000,445);x.textAlign='center';
 const anchors={uart:1,cpu:1.2,memory:1.2,model:1.6,guard:1.5,xnd:2,sram:2,permit:1,io:1,worker:1.2};
 keys.forEach((k,i)=>{const v=groups[k].position.clone().set(0,anchors[k],0);groups[k].localToWorld(v);v.project(w.camera);const px=(v.x*.5+.5)*1000,py=(-v.y*.5+.5)*445;x.beginPath();x.arc(px,py,19,0,Math.PI*2);x.fillStyle='#143295';x.fill();x.font='600 23px Microsoft YaHei';x.fillStyle='white';x.fillText(String(i+1).padStart(2,'0'),px,py+8);});
 const labels=['串口输入输出','RV32IM与Cache','字符短语记忆','双层字节编码器','位置语境判断','4MAC与8MAC','SRAM与权重缓存','工具执行许可','GPIO / PWM / ADC','独立副核与64KiB'];
 x.textAlign='left';labels.forEach((s,i)=>{const cx=24+i%3*326,cy=480+Math.floor(i/3)*56;x.fillStyle='#143295';x.font='600 25px Microsoft YaHei';x.fillText(String(i+1).padStart(2,'0'),cx,cy);x.font='25px Microsoft YaHei';x.fillStyle='#26384C';x.fillText(s,cx+48,cy);});return c.toDataURL('image/png');});
 const out='D:/Desktop/FPGA/参赛材料/图表/报告_三维结构.png';fs.writeFileSync(out,Buffer.from(data.split(',')[1],'base64'));console.log('REPORT_BOARD_FIGURE_READY');
 }finally{await b.close();}})().catch(e=>{console.error(e);process.exitCode=1});
