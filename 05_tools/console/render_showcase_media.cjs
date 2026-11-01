/* Artifact rendering only: opens a disposable headless profile, never the user's serial tab. */
const fs=require('fs');const path=require('path');const {spawn}=require('child_process');
const deps=process.env.NR_NODE_MODULES||'C:/Users/luo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {chromium}=require(path.join(deps,'playwright'));
const root=process.env.NR_LOCAL_ROOT||'D:/Desktop/FPGA';const out=path.join(root,'参赛材料/展示素材');
const args=['-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile=D:/Desktop/system-local-only-20260712/ssh-tunnel/known_hosts','-i','C:/Users/luo/.ssh/hongshu_ai_ed25519','LUO@172.18.58.111'];
(async()=>{
 const remote='ffmpeg -y -hide_banner -loglevel error -f image2pipe -vcodec mjpeg -framerate 12 -i pipe:0 -an -c:v libx264 -preset fast -crf 20 -pix_fmt yuv420p -movflags +faststart "/work/LUO/NeedleRV-X/参赛材料/展示素材/三维流程演示_3倍速.mp4"';
 const encoder=spawn('ssh',[...args,remote],{windowsHide:true,stdio:['pipe','pipe','pipe']});let errorLog='';encoder.stderr.on('data',b=>errorLog+=b.toString());encoder.stdout.on('data',()=>{});encoder.stdin.on('error',e=>{errorLog+=e.message;});
 const finished=new Promise((resolve,reject)=>encoder.on('close',code=>code===0?resolve():reject(Error('ffmpeg failed '+code+' '+errorLog))));finished.catch(()=>{});
 const browser=await chromium.launch({executablePath:process.env.NR_EDGE||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1600,height:900},deviceScaleFactor:1});let errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(require('url').pathToFileURL(path.join(out,'成果展示.html')).href);await page.waitForFunction(()=>NRShowcase.ready);await page.waitForTimeout(300);await page.evaluate(()=>{document.getElementById("speed").value="3";NRShowcase.pause();});
  const subtitles=await page.evaluate(()=>NRShowcase.steps.map(s=>s[3]));
  for(let frame=0;frame<240;frame++){
   await page.evaluate(t=>{NRShowcase.renderAt(t);NRShowcase.api.update({teaching:true});},frame/12);await page.waitForTimeout(20);
   if(frame===0)await page.screenshot({path:path.join(out,'展示预览.png')});
   if([24,96,168,216].includes(frame))await page.screenshot({path:path.join(require('os').tmpdir(),'needlervx_showcase_render',`video-${frame}.png`)});
   const b=await page.screenshot({type:'jpeg',quality:85});if(!encoder.stdin.write(b))await new Promise(resolve=>encoder.stdin.once('drain',resolve));
   if(frame%60===0)console.log('MEDIA_FRAME',frame,'/240');
  }
  encoder.stdin.end();await finished;if(errors.length)throw Error(errors.join(';'));
  const stamp=ms=>{const s=Math.floor(ms/1000),m=Math.floor(s/60);return '00:'+String(m).padStart(2,'0')+':'+String(s%60).padStart(2,'0')+','+String(ms%1000).padStart(3,'0');};
  fs.writeFileSync(path.join(out,'展示字幕.srt'),subtitles.map((s,i)=>`${i+1}\n${stamp(Math.round(i*5000/3))} --> ${stamp(Math.round((i+1)*5000/3))}\n${s}`).join('\n\n')+'\n','utf8');
  await page.evaluate(()=>{NRShowcase.pause();NRShowcase.api.setExploded(false);NRShowcase.api.update({active:[],flow:[],selected:null,teaching:false,semanticCache:true,contextHead:true});});await page.waitForTimeout(650);
  const model=await page.evaluate(async()=>Array.from(new Uint8Array(await NRShowcase.exportModel())));fs.writeFileSync(path.join(out,'LumaRV_逻辑结构.glb'),Buffer.from(model));
  console.log('MEDIA_RENDERED 20 seconds at 3x; LumaRV GLB exported');
 }finally{encoder.stdin.end();await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
