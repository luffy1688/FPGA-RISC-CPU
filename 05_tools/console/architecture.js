/* UI state and explanations only. Never opens a serial port or writes evidence. */
(()=>{
  'use strict';
  const el=id=>document.getElementById(id);
  const keys=['uart','cpu','guard','model','xnd','permit','io','sram','memory'];
  const names=['读取温度','设置 PWM','运行 CoreMark','读取计数器','设置 LED','拒绝'];
  const info={
    uart:['UART / USB','一条请求最多64个UTF-8字节。UART把字节送入板卡；电脑只负责输入、显示和证据导出。','帧序号＋CRC16\n输入校验先于模型执行'],
    cpu:['五级 RISC-V CPU','五级RV32IM流水线运行固件、门禁、模型控制和外设访问。I-cache的命中交接保留同步BRAM，连续命中可每拍接收下一条指令。','IF → ID → EX → MEM → WB\n独立I / D Cache · 中断与FENCE.I'],
    guard:['上下文门禁与快路径','先检查解释、假设、否定、多动作和不支持能力。严格机器指令可直接解析；中文先经语境判断，按需运行完整编码器。','快路径 ≠ 神经推理\n两条路径共用执行许可'],
    model:['轻量语义编码器','双层d64编码器产生六类INT32分数。它负责受限工具意图分类；整数分差不是概率，模型原判与最终工具分别保留。','2 blocks · d64 · 4 heads\nINT4权重 / INT8激活 / INT32累加'],
    memory:['学习的字符短语记忆','Unicode字符组成2/3元组后查询学习表，结合上下文门控和投影修正编码向量。这是Needle Engram启发的轻量分支，不是关键词规则。','两个字符短语表＋门控残差\n投影复用XND；不保存用户历史'],
    xnd:['XND · 四路整数乘加','四路MAC支持INT4或INT8权重与INT8激活；语境MLP复用INT8 GEMV，编码器使用既定量化格式。融合单元按既定数值合同依次完成舍入、偏置、饱和及ReLU或残差后处理。','4 MAC · 双输入槽驻留\n先舍入，再偏置与激活处理'],
    permit:['执行许可','神经分数不直接决定寄存器地址。许可层核对工具、参数范围和真实硬件能力；请求被拒绝时不派发工具。','工具＋参数＋能力检查\n不支持的操作保持无侧效应'],
    io:['板载外设与实际返回','LED/PWM写入后核对寄存器。温度来自片内ADC，计数器是32位周期值；CoreMark独立报告真实CRC与算法计时。','GPIO / PWM / ADC / Counter\n回读不等于外部引脚波形测量'],
    sram:['AI SRAM · 128 KiB','提供激活与计算工作区。XND通过双输入槽复用激活，减少重复搬运；图示是逻辑分区，不是布线后的物理地址布局。','128 KiB AI存储区\n工作区、模型常量、栈须分别计量']
  };
  const lessons={
    model:[
      {node:'uart',title:'输入',caption:'中文句子经USB-UART送到FPGA。这里的演示没有发送任何串口数据。',active:['uart'],flow:['input']},
      {node:'cpu',title:'取指',caption:'CPU从Cache取指，五级流水线运行固件。连续I-cache命中通过交接机制进入下一拍。',active:['cpu'],flow:['cpu']},
      {node:'guard',title:'语境',caption:'先识别这是不是允许执行的请求；不满足显式快路径的句子才进入模型。',active:['guard'],flow:['model']},
      {node:'model',title:'编码',caption:'双层编码器把字节序列转换成上下文向量。不是看到一个设备词就直接动作。',active:['model'],flow:['model']},
      {node:'memory',title:'短语',caption:'字符2/3元组查询训练得到的短语表；门控残差补充跨字语境，两个投影复用XND。',active:['memory','model'],flow:['memory','xnd']},
      {node:'xnd',title:'计算',caption:'四路整数乘加计算GEMV；融合后处理减去CPU逐通道循环，输入槽和SRAM协同复用激活。',active:['xnd','sram'],flow:['xnd','sram','permit']},
      {node:'permit',title:'许可',caption:'六类原始分数仍需经过工具、参数和能力检查。模型可以误判，执行地址由固件约束。',active:['permit'],flow:['permit','output']},
      {node:'io',title:'回读',caption:'实际动作后返回寄存器回读；CoreMark则返回真实CRC和计时。只有这些真实返回进入现场证据。',active:['io','uart'],flow:['output','return']}
    ],
    fast:[
      {node:'uart',title:'输入',caption:'显式单工具请求同样经UART到板卡。此讲解不发送指令。',active:['uart'],flow:['input']},
      {node:'guard',title:'快路径',caption:'机器指令直接解析；中文可只运行语境头，再由schema提取合法参数。',active:['cpu','guard'],flow:['cpu','fast']},
      {node:'permit',title:'许可',caption:'快路径仍接受同一道权限、数值范围与硬件能力检查，不绕过执行许可。',active:['permit'],flow:['fast','output']},
      {node:'io',title:'回读',caption:'外设执行后返回读回值；界面分别显示机器直达、仅语境头与完整模型。',active:['io','uart'],flow:['output','return']}
    ],
    reject:[
      {node:'uart',title:'输入',caption:'请求可能是解释、假设、否定，或要求硬件未支持的操作。此例只是结构讲解。',active:['uart'],flow:['input']},
      {node:'guard',title:'语境',caption:'语境门禁先检查是否允许执行；未匹配的模糊表达也可能经过模型后再被拒绝。',active:['cpu','guard'],flow:['cpu']},
      {node:'permit',title:'拒绝',caption:'没有合法工具和参数就不派发动作。拒绝状态与神经原判分别记录，外设不高亮。',active:['permit'],blocked:['permit'],flow:[]},
      {node:'uart',title:'返回',caption:'返回拒绝原因并继续接收下一条请求。拒绝不是虚构一个温度或CoreMark分数。',active:['uart'],flow:['return']}
    ]
  };
  let scene=null,sceneFailed=false,threeD=true,expanded=false,selected='cpu',last=null,context={},teaching=false,playing=false,step=-1,timer=null;
  el('archGuidePath').value='model';el('archSpeed').value='2';
  function choose(key,focus=true){if(!info[key])return;selected=key;for(const k of keys)el('archNode_'+k).classList.toggle('arch-selected',k===key);el('archInfoTitle').textContent=info[key][0];el('archInfoText').textContent=info[key][1];el('archInfoFacts').textContent=info[key][2];
    if(key==='guard'&&((!last&&!context.build)||context.build?.context_head===1)){el('archInfoTitle').textContent='规则门禁＋学习语境判断';el('archInfoText').textContent=context.build?.formal_fast===1?'显式整句命令走严格语法路径，包含已支持的中文参数句式；其余表达由学习语境与工具分支判断。辅助九类语境不直接发出设备动作；学习拒绝不能被规则救回。语境分数、编码器原判与最终工具分别保留，整数分数不是概率。':'业务请求先运行学习语境头；允许后进入schema或完整编码器。学习拒绝不能被规则救回，语境与编码器分数分别保留。';el('archInfoFacts').textContent='固件声明：context_head = 1\n'+(last?.model_used===0?'显式快路径：未运行神经模型':[2,3].includes(last?.model_used)?'本条仅运行语境头'+(last.context_xnd_used===1?'（XND）':'（CPU）')+'，编码器未运行':last?.context_used===1?'本条语境头已运行':last?.context_used===0?'本条语境头未运行':'本条语境头参与状态未报告');}
if(((!last&&!context.build)||context.build?.semantic_weight_cache===1)&&key==='xnd'){el('archInfoTitle').textContent='XND 4MAC ＋ 语义侧核8MAC';el('archInfoText').textContent='编码器使用四路XND（INT4/INT8），语境头使用独立八路MAC与128KiB权重缓存。缓存跨请求驻留，并跳过全零特征分组。图中计算区域合并表示两个引擎，图标不逐一对应乘法器。';el('archInfoFacts').textContent='编码器4MAC / 语境8MAC\n首次装载与缓存复用分开计数';}
if(((!last&&!context.build)||context.build?.sram_bytes===524288)&&key==='sram'){el('archInfoTitle').textContent='共享RAM 512KiB ＋ 权重缓存128KiB';el('archInfoText').textContent='共享RAM分为CPU程序、数据和栈128KiB，以及AI常量与工作区384KiB。语义W1另驻留128KiB缓存；小型工具融合头复用已有隐藏向量。';el('archInfoFacts').textContent='CPU 128KiB / AI 384KiB\n语义W1缓存128KiB';}
if(scene){scene.update({selected});if(focus)scene.focus(key);}}
  function fail(message){sceneFailed=true;el('archRenderState').textContent=message||'3D不可用 · 已显示完整平面说明';el('archStage').hidden=true;el('archSvg').hidden=false;el('archDragHint').hidden=true;el('archExport').disabled=true;scene?.setVisible(false);}
  function ensureScene(){
    if(scene||sceneFailed||!threeD||!el('architectureDetails').open)return;
    if(typeof globalThis.NeedleScene3D?.createScene!=='function'){fail('本地3D模块未加载 · 平面说明仍可用');return;}
    try{el('archStage').hidden=false;scene=globalThis.NeedleScene3D.createScene(el('archStage'),{onSelect:key=>choose(key),onFailure:fail,onExportCaption:()=>el('archCaption').textContent});el('archSvg').hidden=true;el('archDragHint').hidden=false;el('archRenderState').textContent='WebGL 3D · 本地离线资源';el('archExport').disabled=false;scene.update(currentState());scene.setExploded(expanded);}catch(error){fail('WebGL不可用 · '+String(error.message||error).slice(0,90));}
  }
  function pause(){playing=false;scene?.update({teaching:false});if(timer!==null){clearInterval(timer);timer=null;}el('archPlay').textContent='播放讲解';el('archPlay').setAttribute('aria-pressed','false');}
  function steps(){
    const path=el('archGuidePath').value;
    if((context.build&&context.build.semantic_weight_cache!==1)||(!context.build&&last))return lessons[path]||lessons.model;
    if(path==='fast')return [
      {node:'uart',title:'请求',caption:'明确的单工具请求，经UTF-8与帧校验进入板卡。',active:['uart'],flow:['input']},
      {node:'guard',title:'整句匹配',caption:'检查语境、工具与参数；完整命中才跳过模型。',active:['cpu','guard'],flow:['cpu','fast']},
      {node:'permit',title:'执行许可',caption:'快路径仍核对能力与范围，不由模型指定寄存器。',active:['permit'],flow:['fast','output']},
      {node:'io',title:'回读',caption:'动作后读取寄存器；返回结果与下一次就绪。',active:['io','uart'],flow:['output','return']}];
    if(path==='reject')return lessons.reject;
    return [
      {node:'uart',title:'输入校验',caption:'中文输入最多64个UTF-8字节，校验后再处理。',active:['uart'],flow:['input']},
      {node:'guard',title:'语境检查',caption:'先区分执行、解释、假设、引用与多动作。',active:['cpu','guard'],flow:['cpu']},
      {node:'guard',title:'位置特征',caption:'全局1024维，加首尾各512维，保留位置线索。',active:['cpu','guard'],flow:['context']},
      {node:'xnd',title:'语义侧核',caption:'2048→64→16语义头，由8MAC与常驻权重缓存计算。',active:['guard','xnd','sram'],flow:['context','sram']},
      {node:'memory',title:'短语记忆',caption:'学习的2/3-gram表补充短语信息，不保存用户历史。',active:['memory'],flow:['memory']},
      {node:'model',title:'字节编码',caption:'需要完整模型时，再运行双层d64字节编码器。',active:['model','memory'],flow:['model','memory']},
      {node:'xnd',title:'低比特计算',caption:'原4MAC引擎执行INT4/INT8整数运算与融合后处理。',active:['model','xnd','sram'],flow:['xnd','sram']},
      {node:'permit',title:'候选与许可',caption:'受约束残差修正工具候选；许可层核对参数与能力。',active:['cpu','permit'],flow:['permit']},
      {node:'io',title:'真实回读',caption:'读取LED/PWM寄存器，温度与基准返回实际测量。',active:['io','uart'],flow:['output','return']}];
  }

  function currentState(){
    if(teaching&&step>=0){const item=steps()[step];return {semanticCache:((!last&&!context.build)||context.build?.semantic_weight_cache===1),contextHead:((!last&&!context.build)||context.build?.context_head===1),active:item.active,blocked:item.blocked||[],muted:el('archGuidePath').value==='fast'?['model','memory','xnd','sram']:[],selected,flow:item.flow,teaching:playing};}
    if(!last)return {semanticCache:((!last&&!context.build)||context.build?.semantic_weight_cache===1),contextHead:((!last&&!context.build)||context.build?.context_head===1),active:[],muted:[],blocked:[],selected,flow:[],teaching:false};
    const r=last,known=[0,1,2,3].includes(r.model_used),model=r.encoder_used===1||(r.encoder_used===undefined&&r.model_used===1),contextXnd=r.context_xnd_used===1,hardware=(model&&[1,2,3].includes(r.mode))||contextXnd,memory=model&&context.memory===1;
    const success=r.execute===0&&r.decode===0&&Number.isInteger(r.selected_tool)&&r.selected_tool>=0&&r.selected_tool<5;
    const active=['uart','cpu','guard','permit'];if(model)active.push('model');if(hardware)active.push('xnd','sram');if(memory)active.push('memory');if(success)active.push('io');
    const muted=r.model_used===0?['model','memory','xnd','sram']:[2,3].includes(r.model_used)?(contextXnd?['model','memory']:['model','memory','xnd','sram']):model&&!hardware?['xnd','sram']:[];if(!memory)muted.push('memory');
    const flow=['input','cpu','return'];if(contextXnd)flow.push('context','sram');if(known&&r.context_deny!==1)flow.push(...(model?(hardware?['model','xnd','sram','permit']:['model']):['fast']));if(memory)flow.push('memory');if(success)flow.push('output');
    return {semanticCache:((!last&&!context.build)||context.build?.semantic_weight_cache===1),contextHead:((!last&&!context.build)||context.build?.context_head===1),active,muted,blocked:r.execute!==0?(r.selection_source===5?['guard','permit']:['permit']):[],selected,flow,teaching:false};
  }
  function paint(){const s=currentState();for(const k of keys){for(const [cls,list]of [['arch-used',s.active],['arch-muted',s.muted],['arch-blocked',s.blocked]])el('archNode_'+k).classList.toggle(cls,list.includes(k));}scene?.update(s);}
  function showLive(){pause();teaching=false;step=-1;el('archDemoMode').textContent='未播放 · 不发送指令';el('archSceneBadge').classList.toggle('is-teaching',false);el('archSceneBadge').textContent=last?(context.source==='record_replay'?'实测记录回放 · 汇总路径':'本次串口返回 · 汇总路径'):'冻结版本结构 · 未采集本次结果';el('archStepNumber').textContent=last?'本次结果':'总览';el('archCaption').textContent=last?el('archPath').textContent+'。高亮表示汇总路径，不是逐层或逐拍遥测。':'这块板子如何理解一句话？选择步骤，或播放只读的结构讲解。';renderSteps();paint();}
  function renderSteps(){el('archSteps').replaceChildren();steps().forEach((item,i)=>{const b=document.createElement('button');b.type='button';b.setAttribute('aria-current',teaching&&step===i?'step':'false');const no=document.createElement('b');no.textContent=String(i+1).padStart(2,'0');const label=document.createElement('span');label.textContent=item.title;b.appendChild(no);b.appendChild(label);b.addEventListener('click',()=>{pause();showStep(i);});el('archSteps').appendChild(b);});}
  function showStep(index){teaching=true;step=Math.max(0,Math.min(steps().length-1,index));const item=steps()[step];choose(item.node,false);el('archDemoMode').textContent=(playing?'播放中':'已暂停')+' · 结构演示，无串口动作';el('archSceneBadge').classList.toggle('is-teaching',true);el('archSceneBadge').textContent='结构讲解 · 非实测时序';el('archStepNumber').textContent=String(step+1).padStart(2,'0')+' / '+String(steps().length).padStart(2,'0');el('archCaption').textContent=item.caption;renderSteps();paint();scene?.focus(item.node);}
  function startTimer(){if(timer!==null)clearInterval(timer);timer=setInterval(()=>{if(step>=steps().length-1){pause();showStep(step);return;}showStep(step+1);},5000/Number(el('archSpeed').value||2));}
  for(const key of keys)el('archNode_'+key).addEventListener('click',()=>choose(key));
  el('archView').addEventListener('click',()=>{threeD=!threeD;el('archSvg').classList.toggle('arch-flat',!threeD);el('archView').setAttribute('aria-pressed',String(threeD));el('archView').textContent=threeD?'3D场景 · 切换平面':'平面流程 · 切换3D';if(threeD){ensureScene();el('archStage').hidden=!scene||sceneFailed;el('archSvg').hidden=!!scene&&!sceneFailed;}else{el('archStage').hidden=true;el('archSvg').hidden=false;}el('archDragHint').hidden=!threeD||!scene||sceneFailed;scene?.setVisible(threeD&&!sceneFailed&&el('architectureDetails').open);});
  el('archResetCamera').addEventListener('click',()=>scene?.focus(null));
  el('archExplode').addEventListener('click',()=>{expanded=!expanded;el('archExplode').setAttribute('aria-pressed',String(expanded));el('archExplode').textContent=expanded?'合拢计算层':'展开计算层';scene?.setExploded(expanded);});
  el('archFullscreen').addEventListener('click',()=>{const panel=el('architecturePanel');const on=panel.classList.toggle('arch-expanded');el('archFullscreen').textContent=on?'退出放大':'放大展示';el('architectureDetails').open=true;ensureScene();scene?.resize();});
  el('archExport').addEventListener('click',()=>{if(!scene||sceneFailed)return;try{const link=document.createElement('a');link.href=scene.exportImage();link.download='NeedleRV-X_结构示意.png';link.click();}catch(error){el('archRenderState').textContent='图片导出未完成：'+error.message;}});
  el('archNext').addEventListener('click',()=>{pause();showStep(step+1);});el('archPrev').addEventListener('click',()=>{pause();showStep(step<0?0:step-1);});
  el('archPlay').addEventListener('click',()=>{if(playing){pause();showStep(step);return;}playing=true;el('archPlay').textContent='暂停讲解';el('archPlay').setAttribute('aria-pressed','true');showStep(step<0||step===steps().length-1?0:step);startTimer();});
  el('archSpeed').addEventListener('change',()=>{if(playing)startTimer();});el('archGuidePath').addEventListener('change',()=>{pause();showStep(0);});el('archLive').addEventListener('click',showLive);
  el('architectureDetails').addEventListener('toggle',()=>{if(el('architectureDetails').open){ensureScene();scene?.setVisible(threeD&&!sceneFailed);}else{pause();scene?.setVisible(false);}});
  document.addEventListener('visibilitychange',()=>{if(document.hidden){pause();scene?.setVisible(false);}else if(el('architectureDetails').open){scene?.setVisible(threeD&&!sceneFailed);}});
  function reset(){last=null;context={};for(const id of ['archSource','archRaw','archFinal','archTime'])el(id).textContent='—';el('archPath').textContent='尚无本次返回';showLive();}
  function render(r,c={}){
    last={...r};context={...c};const model=r.encoder_used===1||(r.encoder_used===undefined&&r.model_used===1),success=r.execute===0&&r.decode===0&&Number.isInteger(r.selected_tool)&&r.selected_tool<5&&r.selected_tool>=0;
    el('archPath').textContent=([2,3].includes(r.model_used)?'仅语境头'+(r.context_xnd_used===1?'（XND）':'（CPU）')+' · 编码器未运行':model?'模型路径':r.model_used===0?'精确指令路径 · 模型未运行':'旧固件未报告模型路径')+' → '+(success?'工具已返回':r.execute===1?'拒绝，无工具动作':'未取得有效执行结果');
    el('archSource').textContent=[2,3].includes(r.model_used)?(r.context_deny===1?'学习语境拒绝':'语境头＋schema'):r.model_used===0?'显式 schema':model?([1,2,4].includes(r.selection_source)?'模型＋规则辅助':'模型经许可'):'未报告';el('archRaw').textContent=[2,3].includes(r.model_used)?'编码器未运行':r.model_used===0?'未运行':names[r.tool]??'未报告';el('archFinal').textContent=names[r.selected_tool]??'未报告';
    const cycles=Number.isSafeInteger(r.decision_cycles)?r.decision_cycles:null;el('archTime').textContent=cycles!==null&&cycles>=0&&c.frequency>0?(cycles*1000/c.frequency).toFixed(3)+' ms':'未报告';choose(selected,false);showLive();
  }
  globalThis.nrArchitecture=Object.freeze({render,reset,step:index=>{pause();showStep(index);},reference:()=>{context={};choose(selected,false);showLive();},exportModel:()=>scene?.exportModel()});choose('cpu',false);reset();
  if(new URLSearchParams(window.location.search).get('arch')==='1'){el('architectureDetails').open=true;ensureScene();}
})();
