from pathlib import Path
import json,collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
from matplotlib.text import Text
from matplotlib import font_manager
R=Path('/work/LUO/NeedleRV-X');OUT=R/'参赛材料/图表';OUT.mkdir(exist_ok=True)
FONT='/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc'
BLUE='#143295';TEAL='#6EA8A5';GOLD='#C89B61';INK='#26384C';MUT='#65758A';GRID='#DCE3EC';PALE='#F3F6F9';ROSE='#BB6B82'
plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#ADB9C5','font.size':12,'savefig.facecolor':'white','svg.fonttype':'none'})
def save(fig,name):
 for t in fig.findobj(Text):t.set_fontproperties(font_manager.FontProperties(fname=FONT,size=t.get_fontsize(),weight=t.get_fontweight()))
 for ext in ['png','svg']:fig.savefig(str(OUT/(name+'.'+ext)),dpi=200,bbox_inches='tight',pad_inches=.2)
 plt.close(fig);print('FIG',name,flush=True)
def diagram():
 fig,ax=plt.subplots(figsize=(12.4,5.2));ax.set_xlim(0,12.4);ax.set_ylim(0,5.2);ax.axis('off')
 def box(x,y,w,h,title,body,color=BLUE):
  ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.08,rounding_size=.08',fc='white',ec=color,lw=1.5));ax.text(x+w/2,y+h-.3,title,ha='center',va='center',size=13.3,weight='bold',color=color);ax.text(x+w/2,y+.35,body,ha='center',va='center',size=10.7,color=INK,linespacing=1.55)
 def arrow(x,y,x2,y2,color=BLUE):ax.add_patch(FancyArrowPatch((x,y),(x2,y2),arrowstyle='-|>',mutation_scale=14,lw=1.5,color=color))
 box(.15,3.45,2.05,1.2,'中文输入','请将PWM占空比\n设置为20%')
 box(2.8,3.45,2.05,1.2,'板上CPU','UART接收\n任务调度')
 box(5.45,3.45,2.05,1.2,'语境与意图','工具类别\n参数与语境')
 box(8.1,3.45,1.8,1.2,'执行许可','工具能力\n数值范围')
 box(10.5,3.45,1.65,1.2,'PWM操作','写入后回读\n20% → 20%',TEAL)
 for a,b in [(2.22,2.77),(4.88,5.42),(7.53,8.07),(9.93,10.47)]:arrow(a,4.05,b,4.05)
 ax.text(.15,5.02,'一句中文，到一次板上操作',size=18,weight='bold',color=BLUE)
 box(2.8,.55,2.05,1.8,'位置语义头','全局 / 首 / 尾\n2048 → 64 → 16\n独立8MAC侧核',GOLD)
 box(5.45,.55,2.05,1.8,'字节编码器','双层 d64 / 4 heads\n字符短语记忆\n4MAC INT4 / INT8',GOLD)
 box(8.1,.55,1.8,1.8,'片上缓存','128KiB权重\nAI区384KiB\n计算与数据复用',TEAL)
 arrow(6.47,3.42,6.47,2.38,GOLD);arrow(4.88,1.45,5.42,1.45,GOLD);arrow(8.07,1.45,7.53,1.45,TEAL)
 ax.text(.15,.15,'机器指令直接解析；中文按需调用语境头与完整编码器。三条路径使用同一个执行接口。',size=11.5,color=MUT)
 save(fig,'项目_指令流程')
def training():
 rows=[json.loads(x)for x in (R/'07_runs/development/context_generalization/capacity/train.jsonl').read_text().splitlines()if x.strip()];cnt=collections.Counter(x['intent']for x in rows);assert len(rows)==25014
 labels=['读取温度','设置PWM','运行CoreMark','读取计数器','设置LED','拒绝请求'];ks=['read_temp','set_pwm','run_coremark','read_counter','set_led','reject'];values=[cnt[k]for k in ks]
 fig,ax=plt.subplots(figsize=(11.8,4.2));fig.subplots_adjust(left=.13,right=.79,top=.78,bottom=.24)
 ax.barh(np.arange(6),values,color=[TEAL,TEAL,TEAL,TEAL,TEAL,ROSE],height=.61);ax.invert_yaxis();ax.set_yticks(range(6));ax.set_yticklabels(labels);ax.set_xlim(0,18200);ax.set_xticks([0,4000,8000,12000,16000]);ax.set_xlabel('训练文本条数');ax.grid(axis='x',color=GRID,lw=.7);ax.set_axisbelow(True)
 for i,v in enumerate(values):ax.text(v+200,i,f'{v:,}',va='center',size=12,color=INK)
 fig.text(.055,.92,'中文训练语料分布',size=18,weight='bold',color=BLUE);fig.text(.055,.84,'25,014条训练文本，覆盖五类设备操作和拒绝请求',size=12,color=MUT)
 fig.text(.81,.65,'9,155',size=24,weight='bold',color=TEAL);fig.text(.81,.58,'合法操作',size=12,color=INK)
 fig.text(.81,.43,'15,859',size=24,weight='bold',color=ROSE);fig.text(.81,.36,'拒绝请求',size=12,color=INK)
 fig.text(.055,.025,'含2,800条MASSIVE中文域外请求，按板卡能力重新标注；其余为任务语料与合成语境扩展。',size=11,color=MUT)
 save(fig,'项目_训练数据')
def pwm_result():
 d=json.loads((R/'07_runs/board/current/demo_hardware_report.json').read_text());q=next(x for x in d['page_evidence']['requests']if x.get('result',{}).get('model_used')==1 and x.get('result',{}).get('selected_tool')==1);v=q['result'];a=v['receipt'];assert a['match']==1
 fig,ax=plt.subplots(figsize=(10,4.0));ax.set_xlim(0,10);ax.set_ylim(0,4);ax.axis('off')
 ax.text(.15,3.65,'中文PWM指令的处理结果',size=18,weight='bold',color=BLUE)
 rows=[('输入',q['command']),('模型与工具','设置PWM  /  set_pwm'),('模型耗时',f"{v['cycles']/40500000*1000:.3f} ms"),('参数与读回',f"请求 {a['requested']}%    读回 {a['readback']}%    一致"),('PWM寄存器',f"周期 {a['period']}    高电平 {a['high']}    使能 {a['enabled']}")]
 for i,(name,value)in enumerate(rows):
  y=3.1-i*.55;ax.text(.2,y,name,size=13,color=MUT,va='center');ax.text(2.15,y,value,size=14,color=BLUE if i==3 else INK,weight='bold'if i==3 else'normal',va='center');ax.plot([.15,9.7],[y-.25,y-.25],color=GRID,lw=.8)
 save(fig,'报告_实板记录节选')
def performance():
 fig=plt.figure(figsize=(12.4,4.3));ax=fig.add_axes([.08,.20,.48,.58]);sw=40466391/40500000*1000;hw=3019968/40500000*1000
 vals=[sw,hw];bars=ax.barh([0,1],vals,color=[TEAL,BLUE],height=.55);ax.invert_yaxis();ax.set_yticks([0,1]);ax.set_yticklabels(['软件计算','专用加速']);ax.set_xlabel('完整中文PWM模型计算耗时（ms）');ax.set_xlim(0,1200);ax.set_xticks([0,250,500,750,1000]);ax.grid(axis='x',color=GRID,lw=.7);ax.set_axisbelow(True)
 for i,v in enumerate(vals):ax.text(v+22,i,f'{v:.3f}',va='center',size=13,weight='bold',color=INK)
 fig.text(.055,.92,'计算加速与资源开销',size=18,weight='bold',color=BLUE);fig.text(.055,.83,'同一镜像、相同输入与模型，软件路径和加速路径对照',size=12,color=MUT)
 fig.text(.66,.65,f'{sw/hw:.2f}×',size=34,weight='bold',color=BLUE);fig.text(.66,.56,'完整模型加速比',size=13,color=INK)
 fig.text(.66,.40,'197,816 B',size=25,weight='bold',color=GOLD);fig.text(.66,.31,'部署学习权重',size=13,color=INK)
 fig.text(.055,.035,'40.5MHz  ·  CoreMark/MHz 2.031490  ·  LUT 19,456  ·  FF 19,116  ·  33 APM',size=12,color=MUT)
 save(fig,'项目_计算性能')
if __name__=='__main__':diagram();training();performance();pwm_result()
