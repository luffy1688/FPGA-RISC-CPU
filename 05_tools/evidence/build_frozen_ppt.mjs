// Reproduce frozen deck: run render_frozen_ppt_views.cjs, then this file, then finish_frozen_ppt.py, then embed_ppt_explanation_gifs.py after GIF generation.
// Inputs: authoritative current JSONs and materials/展示素材 GLB/HTML/MP4. Builds stay in system temp.
import fs from 'node:fs/promises';
import path from 'node:path';
import {Presentation,PresentationFile} from 'file:///C:/Users/luo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';
import {applyPresentationChartFont} from 'file:///C:/Users/luo/.codex/plugins/cache/openai-primary-runtime/presentations/26.1026.10807/skills/presentations/container_tools/artifact_tool_utils.mjs';
const DIR='C:/Users/luo/AppData/Local/Temp/needlervx_ppt';
const MAT='D:/Desktop/FPGA/参赛材料';
const ROOT=process.env.NR_ENGINEERING_ROOT||'D:/FPGA_PDS';
const readJSON=async f=>JSON.parse(await fs.readFile(ROOT+'/'+f,'utf8'));
const E={accept:await readJSON('07_runs/board/current/acceptance_report.json'),selection:await readJSON('07_runs/development/resource_trials/selection.json'),text:await readJSON('07_runs/board/current/native_text_921600.json'),framed:await readJSON('07_runs/board/current/native_framed_921600.json')};
const A=E.accept,S=E.selection;
const B='#143295',G='#C89B61',C='#1455AF',L='#A2B9CC',INK='#28384A',MUT='#65758A',GRID='#DCE3EC',WHITE='#FFFFFF',PALE='#F3F6FA';
const FONT='Microsoft YaHei';
const P=Presentation.create({slideSize:{width:1280,height:720}});
const SOURCE='本项目冻结版实测：上板交付/工程/07_runs/board/current/acceptance_report.json、fourth_and_model_921600.json、native_text_921600.json、native_framed_921600.json；模型选择：07_runs/development/resource_trials/selection.json。2026-10-31。';
const slides=[];
function rect(s,x,y,w,h,fill=WHITE,line=GRID,name){return s.shapes.add({geometry:'rect',name,position:{left:x,top:y,width:w,height:h},fill,line:{fill:line,width:line==='none'?0:1.25}})}
function text(s,t,x,y,w,h,size=24,color=INK,bold=false,align='left',name){const q=s.shapes.add({geometry:'textbox',name,position:{left:x,top:y,width:w,height:h},fill:'none',line:{fill:'none',width:0}});q.text=t;q.text.style={fontFamily:FONT,fontSize:size,color,bold,alignment:align,verticalAlignment:'middle'};q.text.insets=0;return q;}
function rule(s,x,y,w,color=GRID,width=1){return s.shapes.add({geometry:'line',position:{left:x,top:y,width:w,height:0},line:{fill:color,width},fill:'none'});}
function arrow(s,from,to,color=B,fromSide='right',toSide='left'){return s.shapes.connect(from,to,{kind:'elbow',fromSide,toSide,line:{fill:color,width:2},tail:{type:'triangle',width:'med',length:'med'}});}
function block(s,title,body,x,y,w=210,h=115,color=B){const q=rect(s,x,y,w,h,WHITE,color);text(s,title,x+14,y+11,w-28,32,23,color,true,'center');text(s,body,x+14,y+49,w-28,h-58,19,INK,false,'center');return q;}
function base(title,sub=''){let s=P.slides.add();slides.push(s);s.background.fill=WHITE;rect(s,0,0,16,720,B,'none');text(s,title,60,37,1125,60,34,B,true);if(sub)text(s,sub,62,103,1145,40,19,MUT);rule(s,60,659,1156);text(s,'NeedleRV-X  ·  2026.10.31',60,675,520,24,14,MUT);text(s,String(slides.length).padStart(2,'0'),1170,675,48,24,15,B,false,'right');s.speakerNotes.text=SOURCE;return s;}
function notes(s,t){s.speakerNotes.text=t+'\n\n'+SOURCE;}
function chart(s,type,x,y,w,h,categories,series,extra={}){const chartClean=v=>Array.isArray(v)?v.map(chartClean):v&&typeof v==='object'?Object.fromEntries(Object.entries(v).map(([k,v])=>[k==='fontFamily'?'typeface':k,chartClean(v)])):v;let q=s.charts.add(type,chartClean({position:{left:x,top:y,width:w,height:h},categories,series,hasLegend:true,legend:{position:'bottom',overlay:false,textStyle:{fontFamily:FONT,fontSize:17}},xAxis:{textStyle:{fontFamily:FONT,fontSize:17,fill:INK},line:{fill:GRID,width:1}},yAxis:{textStyle:{fontFamily:FONT,fontSize:17,fill:INK},majorGridlines:{fill:GRID,width:1}},chartFill:WHITE,plotAreaFill:WHITE,...extra}));applyPresentationChartFont(q,{fontFamily:FONT});return q;}
function table(s,values,x,y,w,h,colWidths){const t=s.tables.add({rows:values.length,columns:values[0].length,left:x,top:y,width:w,height:h,columnWidths:colWidths,values});t.borders.assign({fill:GRID,width:.8,style:'solid'});for(let i=0;i<values.length;i++)for(let j=0;j<values[i].length;j++){let c=t.getCell(i,j);c.fill=i===0?B:(i%2===0?PALE:WHITE);c.text.style={fontFamily:FONT,fontSize:i===0?20:19,bold:i===0,color:i===0?WHITE:INK,alignment:j===0?'left':'center'};}return t;}

function navigation(s,current){[['全景',12],['俯视',14],['侧视',15]].forEach(([label,target],i)=>{let x=899+i*104;rect(s,x,526,98,42,current===target?G:WHITE,current===target?G:B,'view_'+target);text(s,label,x+6,531,86,30,20,current===target?WHITE:B,true,'center','view_text_'+target);});rect(s,899,585,307,44,B,B,'open_web3d');text(s,'网页自由旋转与分层',908,591,289,32,20,WHITE,true,'center','open_web3d_text');}
// 01 — concise cover.
{
let s=base('NeedleRV-X');
text(s,'离线中文板卡运维',60,168,740,90,55,B,true);
text(s,'自研 RISC-V 处理器与低比特语义加速',64,274,990,55,28,INK);
text(s,'输入中文 → 板上判断 → 许可执行 → 实际回读',64,350,1080,55,25,MUT);
rule(s,64,445,1150,G,2);
const data=[['40.5 MHz','实板时钟'],['25 / 25','第四版指令回归'],['2.03149','CoreMark / MHz']];
data.forEach((d,i)=>{let x=64+i*390;text(s,d[0],x,480,355,62,44,i===2?G:B,true);text(s,d[1],x,553,350,35,21,MUT);});
notes(s,'项目背景：紫光同创选题一。此版是已比较候选中经综合、时序和实板验收选定的冻结版本，非所有指标的绝对最优。第四版为用户指定、已观察回归。CoreMark四次1200迭代均CRC通过。蓝金配色与图表布局启发来自用户提供300页-蓝金配色(1).pptx的主题39及第73、76、98、114页；重建本项目内容，不复用商务样例数据。');
}
// 02 — concrete task and visible acknowledgement.
{
let s=base('板卡检查与现场运维','面向离线设备维护的板卡检查原型；电脑输入与审计，FPGA判断与回读。');
const xs=[62,303,544,785,1026];
const data=[['结温','读取芯片温度','片内ADC采样'],['IO状态','设置LED / PWM','请求值与回读值'],['周期计数','读取硬件计数器','32位可回绕'],['CPU自检','运行CoreMark','计时与五项CRC'],['执行边界','解释 / 多动作 / 越权','拒绝并检查IO不变']];
data.forEach((d,i)=>{text(s,d[0],xs[i],180,195,40,27,i===4?G:B,true);rule(s,xs[i],232,190,i===4?G:B,2);text(s,d[1],xs[i],254,198,65,22,INK);text(s,d[2],xs[i],340,198,60,19,MUT);});
rule(s,62,438,1150);
const st=['请求','路径与许可','动作','实际回读','导出记录'];let prev;
st.forEach((t,i)=>{let b=block(s,t,'',64+i*236,486,210,70,i===4?G:B);if(prev)arrow(s,prev,b);prev=b;});
text(s,'一次请求只执行一个工具；健康检查由控制台串行组织，不是模型自主规划。',64,598,1135,37,22,INK);
notes(s,'应用场景为离线受限板卡运维。LED/PWM回读证明内部寄存器状态，不代替外部引脚波形。健康检查可串行组织多个单工具请求。控制台审计保留来源、路径、实际动作、回读和结果时间。 90秒场景讲解：可以用离线设备柜的维护来理解这个原型。维修员面对一块待检板卡，手边没有寄存器手册，现场也不能联网。他先输入“请读取FPGA当前温度”，再读取周期计数，确认板卡能正常响应。接着设置LED和PWM占空比，页面同时显示请求值与实际寄存器回读；只关闭LED0时，其余位保持原状。然后运行CoreMark，等待约14.6秒，查看CRC和计时，最后导出这次检查记录。它把分散的检查步骤放进一个中文入口，但每条请求仍只执行一个工具，解释、越权和多动作请求要先经过许可检查。这一轮已经验证的是FPGA板卡原型。把它接入工业设备、形成出厂检查工位或加入自动故障诊断，都是未来工作；模型没有控制真实工业设备，PWM寄存器回读也不能代替外部波形测量。');
}
// 03 — split path remains editable.
{
let s=base('分链路决策与共享执行许可','显式命令优先；模糊表达进入模型；两条路径共用工具合同与回读');
let a=block(s,'输入检查','UTF-8 / 64字节\n引用、否定与多动作',62,209,220,123);
let b=block(s,'显式工具语法','唯一工具 + 合法参数\nmodel_used = 0',349,209,230,123);
let c=block(s,'执行许可','能力 / 参数 / 操作\n未通过则不执行',649,209,230,123);
let d=block(s,'硬件工具','温度 / LED / PWM\n计数器 / CoreMark',949,209,258,123);
arrow(s,a,b);arrow(s,b,c);arrow(s,c,d);
let m=block(s,'模型分支','位置语义 + 字节编码器\n语境、意图与受限融合',349,427,358,130,G);
arrow(s,b,m,G,'bottom','top');arrow(s,m,c,G,'right','bottom');
text(s,'未命中',390,356,190,38,21,G,true);
text(s,'语境拒绝可提前返回',62,395,235,65,23,G,true);
text(s,'实际回读 / seq / CRC / READY',890,451,320,75,23,B,true);
text(s,'没有运行模型时，不补填神经分数或推理周期。',62,597,1140,35,22,MUT);
notes(s,'显式快路径不是绕过许可。所有路径都遵守非执行语境、工具能力及参数约束。箭头是计算关系，不是芯片物理布图。');
}
// 04 — model structure.
{
let s=base('位置语义分支与低比特编码器','模型容量为197816B；重点区分“执行命令”与“提到一个命令”');
let g=block(s,'全局特征','Unicode 2/3-gram\n1024维',62,195,222,110,G);
let f=block(s,'首部位置','512维',62,340,222,95,G);
let t=block(s,'尾部位置','512维',62,465,222,95,G);
let merge=block(s,'位置语义头','2048 → 64 → 16\n8 MAC · INT8',368,306,258,148,G);
arrow(s,g,merge,G);arrow(s,f,merge,G);arrow(s,t,merge,G);
let out=block(s,'16个输出','执行许可2 + 语境9\n工具身份5',708,193,260,126,G);arrow(s,merge,out,G);
let enc=block(s,'原字节编码器','d64 · 两层\n4 MAC · INT4×INT8',708,382,260,124,B);
let fusion=block(s,'受约束融合','修复 / 级联\n70 → 5 身份残差',1037,286,184,143,B);
arrow(s,out,fusion,G);arrow(s,enc,fusion,B);
text(s,'身份残差只在合法候选间参与判断，不能撤销拒绝许可。',368,575,832,54,23,INK);
notes(s,'Unicode全局1024+front/back各512。头2048→64→16，binary2+context9+tools5。原字节编码器47066B、语义记忆12800B等包含在总学习权重197816B内。370B身份残差使用hidden64+encoder6，限定合法候选和门限，不等同通用生成式大模型。');
}
// 05 — observed accuracy comparison.
{
let s=base('神经分类与系统结果分别计分','观察集已经参与开发；保留完整分母与较难集合，不把混合成绩改称模型准确率');
const d1=S.observed_neural.observed1138,d2=S.observed_neural.observed900;
chart(s,'bar',53,175,705,390,['1138条观察集','900条观察集'],[
{name:'前一64维候选',values:[100*1058/1138,100*653/900],fill:L},
{name:'当前神经',values:[100*d1.correct/d1.n,100*d2.correct/d2.n],fill:B},
{name:'当前混合系统',values:[100*1135/1138,100*884/900],fill:G}
],{barOptions:{direction:'column',grouping:'clustered',gapWidth:85},yAxis:{min:0,max:100,majorUnit:25,numberFormatCode:'0.0',title:'正确比例（%）',textStyle:{fontFamily:FONT,fontSize:18},majorGridlines:{fill:GRID,width:1}},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.0',textStyle:{fontSize:18,fontFamily:FONT,color:INK}}});
text(s,'合法指令神经正确',826,180,360,40,26,B,true);
text(s,'185 → 195 / 196',826,247,360,64,35,B,true);
text(s,'1138条观察集内',828,314,360,36,20,MUT);
text(s,'169 → 175 / 200',826,402,360,64,35,G,true);
text(s,'较难900条内',828,469,360,36,20,MUT);
text(s,'首次861/1138保留；后续95.52%不是独立盲测。',62,598,1140,40,23,INK);
notes(s,'前一64维rev2 raw1138=1058、raw900=653；当前1087/1138、685/900。默认混合1135/1138、884/900。合法指令195/196与175/200属于模型分类；系统分别193/196、184/200。集合类别不均衡，1138中拒绝类942条，不能只用总准确率说明泛化。');
}
// 06 — editable raw confusion matrices.
{
let s=base('原始神经模型的混淆矩阵','颜色为行归一化召回；格内为原始条数，模型失败保留在矩阵中');
const labels=['温度','PWM','基准','计数','LED','拒绝'];
function matrix(key,x,title){const d=S.observed_neural[key],m=d.confusion_true_rows_pred_columns,sz=57,xx=x+57,yy=220;text(s,title,x,151,510,34,25,B,true);
for(let j=0;j<6;j++)text(s,labels[j],xx+j*sz,yy-38,sz,30,18,INK,false,'center');
for(let i=0;i<6;i++){text(s,labels[i],x,yy+i*sz,50,sz,18,INK,false,'center');const n=m[i].reduce((a,b)=>a+b,0);for(let j=0;j<6;j++){let v=m[i][j]/n;let rgb=v>.75?B:v>.4?'#7593C7':v>0?'#E0E8F4':WHITE;rect(s,xx+j*sz,yy+i*sz,sz,sz,rgb,GRID);text(s,String(m[i][j]),xx+j*sz,yy+i*sz,sz,sz,19,v>.4?WHITE:INK,false,'center');}}
text(s,'预测类别 →',xx+80,yy+352,250,32,18,MUT,false,'center');}
matrix('observed1138',72,'1138条：1087正确（95.52%）');matrix('observed900',677,'900条：685正确（76.11%）');
text(s,'1138：误接受50，误拒绝0',82,606,530,32,21,B,true);text(s,'900：误接受190，误拒绝24',690,606,530,32,21,G,true);
notes(s,'真实类别为行，预测为列，矩阵原始数据直接来自selection.json observed_neural。1138真实拒绝942，900真实拒绝700。当前模型不是零错误；执行合同后观察集误执行放行为0不等于原始神经误接受为0。混淆格为可编辑PowerPoint形状文本。');
}
// 07 — hardware cache dataflow.
{
let s=base('片内缓存与8 MAC语义侧核','用片内存储承载更大的语义头，避免每次重新搬运第一层权重');
let w=block(s,'W1常驻权重','128 KiB\n2048 × 64 INT8',62,196,270,128,G);
let a=block(s,'激活输入','2048维特征\n逐字非零位图',62,414,270,128,B);
let mac=block(s,'8路乘加','非零特征组跳零\nINT32累加',472,292,280,146,G);
let h=block(s,'隐藏层与输出','64维隐藏层\n16项分数',914,292,290,146,B);
arrow(s,w,mac,G);arrow(s,a,mac,B);arrow(s,mac,h,B);
text(s,'缓存命中实测：1个任务 · DMA读写0字节 · 硬件失败0',64,574,1150,44,25,B,true);
notes(s,'主SRAM512KiB与独立W1缓存128KiB不能重复相加写成主存容量。8MAC语义侧核与原4MAC编码器并存。当前config6中文PWM完整模型配对实测context_hardware loads0,jobs1,dma_read_bytes0,dma_write_bytes0,engine_cycles5344,failures0。此图是计算结构，不是外部板卡实物照片。');
}
// 08 — resources and STA.
{
let s=base('同步RAM端口降低逻辑资源','同一模型与同一PRR阶段比较：移除额外异步数组读口，流水周期保持不变');
chart(s,'bar',55,168,665,407,['LUT','FF'],[{name:'优化前',values:[31208,43692],fill:L},{name:'优化后',values:[19456,19116],fill:B}],{barOptions:{direction:'column',grouping:'clustered',gapWidth:90},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'#,##0',textStyle:{fontFamily:FONT,fontSize:19}},yAxis:{min:0,max:50000,majorUnit:10000,numberFormatCode:'#,##0',title:'PRR元件数',textStyle:{fontFamily:FONT,fontSize:17},majorGridlines:{fill:GRID,width:1}}});
table(s,[['本版时序与资源','实测/工具报告'],['时钟','40.5 MHz'],['Setup 慢 / 快','1.901 / 11.214 ns'],['Hold 慢 / 快','0.147 / 0.102 ns'],['失败端点','0'],['DRM36等效','290.5 → 292.5'],['APM','33']],774,190,433,348,[192,241]);
text(s,'模块验证仍为355683周期，全部比较输出一致。',65,604,1120,36,22,INK);
notes(s,'资源来自最终cache_ram/place_route PRR：19456LUT=CLMA+CLMS used LUT，19116FF、292.5 DRM36 equivalent、33APM、1ADC、1GPLL；不要与映射阶段LUT17340或module LUT17201混用。四角时序全部满足，不称实测FMAX。');
}
// 09 — native latency with all dots as editable objects.
{
let s=base('显式命令的原生串口往返','每句每协议n=10；散点为全部样本，短竖线与数字为中位数');
const x0=423,y0=217,w=700,dy=83,commandNames=Object.keys(E.text.summary);
for(let v=0;v<=6;v++){let x=x0+v*w/6;rule(s,x,178,0,GRID);s.shapes.add({geometry:'line',position:{left:x,top:187,width:0,height:354},line:{fill:GRID,width:1}});text(s,String(v),x-18,548,36,30,19,MUT,false,'center');}
const labels=['LED整体掩码37','读取FPGA当前温度','PWM按20%输出','PWM占空比设置20%'];
commandNames.forEach((c,i)=>{text(s,labels[i],65,y0+i*dy-13,340,52,23,INK);for(const [p,off,col,geometry]of [['text',-13,B,'ellipse'],['framed',13,G,'rect']]){let m=E[p].summary[c].metrics.tready_ms;let arr=m.all_samples;arr.forEach((v,j)=>s.shapes.add({geometry,position:{left:x0+v*w/6-4,top:y0+i*dy+off-4+((j%3)-1)*4,width:8,height:8},fill:col,line:{fill:col,width:.6}}));let x=x0+m.median*w/6;s.shapes.add({geometry:'line',position:{left:x,top:y0+i*dy+off-10,width:0,height:20},line:{fill:col,width:2.5}});text(s,m.median.toFixed(3),x0+Math.max(...arr)*w/6+12,y0+i*dy+off-17,90,32,20,col,true);}});
text(s,'ms',1150,548,60,30,19,MUT);rect(s,425,602,14,14,B,B);text(s,'文本',449,589,140,35,20,B);rect(s,577,602,14,14,G,G);text(s,'二进制',601,589,160,35,20,G);text(s,'WriteFile入口 → 真实READY接收',800,589,410,40,20,MUT);
notes(s,'来自本版native_text_921600.json和native_framed_921600.json各4句×10次真实样本。保留中位数及所有采样点，shape散点是可编辑对象，不虚构分布密度。此处包含USB/Windows调度、不含浏览器渲染，测得中位数1.40~5.16ms。n10的最近秩P95等于最大值且不稳定；不是完整模型耗时。');
}
// 10 — same-image full model speed, separate CoreMark scale.
{
let s=base('完整模型加速与CPU基准','相同固件、相同输入，关闭快路径后对比config0与config6');
chart(s,'bar',58,179,720,360,['led 37','中文PWM'],[{name:'软件',values:[7043041/40500,40466391/40500],fill:L},{name:'硬件',values:[410531/40500,3019968/40500],fill:B}],{barOptions:{direction:'column',grouping:'clustered',gapWidth:100},dataLabels:{showValue:true,position:'outEnd',numberFormatCode:'0.00',textStyle:{fontSize:18,fontFamily:FONT}},yAxis:{min:0,max:1100,majorUnit:250,title:'完整模型计算（ms）',textStyle:{fontFamily:FONT,fontSize:18},majorGridlines:{fill:GRID,width:1}}});
text(s,'CoreMark',857,186,345,44,27,B,true);text(s,'2.03149 / MHz',853,249,350,66,36,B,true);text(s,'1200次迭代 · 约14.585秒',857,334,345,44,22,INK);text(s,'4次运行，CRC均5/5通过',857,396,345,44,22,INK);rule(s,857,472,345,G,2);text(s,'13.40× / 17.16×\n模型分数比较一致',857,496,345,80,23,G,true);
text(s,'PWM完整模型74.567ms；语义子区间0.837ms，不能替代完整推理时间。',65,609,1140,33,22,INK);
notes(s,'led37 SW7043041 XND410531 cycles，17.155929759倍；中文PWM SW40466391 XND3019968 cycles，13.399609201倍。clock40500000。CoreMark4次1200迭代，cycle590699475~590699515，14.585172222~14.585173210秒，2.031489733~2.031489871/MHz，CRC seed e9f5/list e714/matrix1fd7/state8e3a/final988c。成绩为本项目实测，不是官方认证评分。');
}
// 11 — physical safeguards and actual receipt.
{
let s=base('实板回归与执行回读','所有检查来自冻结位流的真实串口结果，不以下载成功代替程序运行');
table(s,[['实板检查','本版结果'],['第四版指令集合','25 / 25'],['40条语境拒绝 × 两模式','80 / 80；IO不变'],['6条伪造成绩 × 两模式','12 / 12'],['正反语境控制','8组通过'],['局部否定 / 位保持','LED0改变，其他位保留'],['非法UTF-8 / 序号恢复','拒绝非法输入，合法请求恢复']],63,181,738,372,[365,373]);
text(s,'回读实例',859,186,339,45,26,B,true);
text(s,'LED  37 → 36 → 37',859,254,339,58,28,B,true);
text(s,'只关闭 / 点亮 LED0\n其余位保持不变',859,321,339,68,21,INK);
text(s,'PWM 20%\n40500周期 / 8100高电平',859,421,339,82,23,G,true);
text(s,'结束后恢复：LED37、PWM20%，COM10已释放。',65,601,1140,39,23,MUT);
notes(s,'硬件回归：observed_fourth25_passed25、observed_context_rejections_passed80、score_forgery_guard_cases_passed12、paired_context_control_groups_passed8；partial_negation_positive_readback通过。LED37二进制最低位1，关LED0为36，再开恢复37。PWM40.5MHz、周期40500、高8100为20%。真实回读为寄存器证据，未测外部引脚波形。启动失败日志保留；设备模板时隙修复后GOUTEN1并实际收到NR_BUILD/READY。');
}
// 12 — native 3D has genuine model and fallback, patched after export.
{
let s=base('逻辑结构的三维演示','模型表示功能关系与存储层级，不是板卡实物照片或芯片布局');
let pic=s.images.add({blob:new Uint8Array(await fs.readFile(DIR+'/overview.png')),contentType:'image/png',alt:'NeedleRV-X逻辑结构，原生3D模型占位预览',fit:'contain',position:{left:55,top:160,width:800,height:466}});
text(s,'4 MAC 编码器\n8 MAC 语义侧核\n512 KiB 主SRAM\n128 KiB 权重缓存',913,189,285,178,24,INK);
text(s,'原生模型',913,397,285,36,25,B,true);
text(s,'PowerPoint编辑态\n选择模型后可旋转',913,444,285,63,20,MUT);
navigation(s,12);
notes(s,'真实GLB二进制已嵌入本页 am3d:model3d，fallback为模型预览.png。GLB来自与网页相同的逻辑结构，4+8MAC表示实际架构。PowerPoint2019/2021/365编辑态可用原生3D旋转控件；其他阅读器显示PNG。放映态需要自由旋转/分层/逐步审计时，点本页相对链接展示素材/成果展示.html；该离线网页不连接串口、不冒称当前实况。官方依据：https://support.microsoft.com/en-us/office/graphics-visuals/get-creative-with-3d-models 及 https://learn.microsoft.com/en-us/office/vba/api/powerpoint.shapes.add3dmodel 。未通过实际PowerPointUI操作验证，不保证任意版本放映态自由拖转。');
}
// 13 — short show and scope.
{
let s=base('展示顺序与实现边界','程序已冻结；材料和现场讲解围绕同一版数据展开');
text(s,'30秒流程快览',63,176,640,60,38,B,true);
text(s,'输入 → 判断 → 许可 → 动作 → 回读 → 审计',65,264,1125,50,27,INK);
text(s,'2倍速 · 讲解字幕 · 真实记录回放',65,337,1100,45,25,G,true);
rect(s,65,425,488,59,B,B,'open_demo_video');text(s,'播放2倍速MP4',80,434,455,40,23,WHITE,true,'center','open_demo_video_text');
rect(s,592,425,488,59,WHITE,B,'open_demo_web');text(s,'打开离线交互与完整流程',604,434,464,40,23,B,true,'center','open_demo_web_text');
text(s,'已验证：板上运算、回读、CRC、时序与观察集回归',65,538,1145,41,23,INK);
text(s,'未覆盖：任意中文可靠性、直接HDMI、外部波形/功耗、实测FMAX',65,591,1140,39,21,MUT);
notes(s,'视频相对链接展示素材/三维流程演示_2倍速.mp4，30秒为流程讲解成片，用真实验收事件驱动3D高亮并标明2倍速。CoreMark步骤绑定实际第四版case218，执行一次CoreMark测试；不能把30秒成片当连续硬件实录。独立HTML在展示素材/成果展示.html，无需8765端口。官方最终上传清单及高阶轻量大模型资格仍待确认；自研窄域语义模型不冒称YOLO/生成式LLM。');
}

for(const spec of [{title:'三维结构 俯视视角',image:'top',number:14,body:'处理器 / 语义模块\n8 MAC / 常驻权重缓存'},{title:'三维结构 侧视视角',image:'side',number:15,body:'模块与缓存的叠层关系\n不是实际封装布局'}]){
 let s=base(spec.title,'放映内点击预设视角切换；网页入口提供自由旋转与分层展开');
 s.images.add({blob:new Uint8Array(await fs.readFile(DIR+'/'+spec.image+'.png')),contentType:'image/png',alt:spec.title,fit:'contain',position:{left:55,top:160,width:800,height:466}});
 text(s,'预设3D视角',913,197,290,45,26,B,true);text(s,spec.body,913,269,288,136,21,INK);text(s,'原生模型可在支持的\nPowerPoint编辑态旋转',913,428,286,68,20,MUT);navigation(s,spec.number);
 notes(s,'同一真实GLB模型的预设相机视角，内部幻灯片超链接支持放映内点击切换。切换视角不是放映内鼠标自由旋转。原生编辑态支持需PowerPoint2019及以上；fallback PNG由相同WebGL场景同方向渲染。网页自由旋转链接为相对路径展示素材/成果展示.html。');
}
await fs.mkdir(DIR+'/renders',{recursive:true});
for(let i=0;i<slides.length;i++){
 let b=await P.export({slide:slides[i],format:'png',scale:1});await fs.writeFile(DIR+'/renders/slide-'+String(i+1).padStart(2,'0')+'.png',new Uint8Array(await b.arrayBuffer()));
 console.log('RENDER',i+1);
}
await(await PresentationFile.exportPptx(P)).save(DIR+'/draft.pptx');
await fs.writeFile(DIR+'/render-info.json',JSON.stringify({slides:slides.length,size:[1280,720],fontPolicy:{basis:'design',families:[FONT]},nativeChartSlides:[5,8,10],nativeTableSlides:[8,11],hash_checks:false}));
console.log('DRAFT_READY',slides.length);
