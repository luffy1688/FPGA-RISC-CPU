from pathlib import Path
import json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.text import Text
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch
R=Path('/work/LUO/NeedleRV-X');O=R/'参赛材料/图表';O.mkdir(parents=True,exist_ok=True)
F=json.loads((R/'07_runs/board/current/final_metrics.json').read_text())
L=json.loads((R/'07_runs/board/current/dual_final_latency.json').read_text())
FONT='/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc'
plt.rcParams.update({'font.size':11,'axes.spines.top':False,'axes.spines.right':False,'axes.titleweight':'bold','svg.fonttype':'none','figure.facecolor':'white','axes.unicode_minus':False})
B='#315D87';G='#C19563';T='#73A69E';M='#66788A';PALE='#EFF4F7'
def save(fig,name):
 for t in fig.findobj(Text):t.set_fontproperties(font_manager.FontProperties(fname=FONT,size=t.get_fontsize(),weight=t.get_fontweight()))
 fig.savefig(str(O/(name+'.png')),dpi=180,bbox_inches='tight',facecolor='white');fig.savefig(str(O/(name+'.svg')),bbox_inches='tight');plt.close(fig);print('FIGURE',name,flush=True)
def box(ax,x,y,w,h,title,body,color=B):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.05,rounding_size=.07',facecolor=PALE,edgecolor=color,lw=1.2))
 ax.text(x+w/2,y+h-.24,title,ha='center',weight='bold',color=color,fontsize=12)
 ax.text(x+w/2,y+.20,body,ha='center',va='bottom',fontsize=10.5,color='#28384A',linespacing=1.45)
def arrow(ax,a,b,label=None):
 ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=13,color=B,lw=1.25))
 if label:ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+.12,label,ha='center',fontsize=9,color=M)
fig,ax=plt.subplots(figsize=(12.4,6));ax.set(xlim=(0,12.4),ylim=(0,6));ax.axis('off')
ax.text(.1,5.65,'控制板试产与返修的临时复测',fontsize=19,weight='bold',color=B)
ax.text(.1,5.15,'主核保持交互，副核运行后台计算；固定工序继续使用测试脚本',fontsize=11.5,color=M)
box(ax,.12,3.25,2.05,1.30,'工程师逐条输入','只关闭LED0\n其他LED保持不变')
box(ax,2.8,3.25,2.1,1.30,'主核接收与调度','54MHz · 五级RISC-V\nUART / 模型 / 外设')
box(ax,5.55,3.25,2.25,1.30,'语境与工具计算','位置语义 + 字符短语\n4MAC / 8MAC',G)
box(ax,8.45,3.25,2.25,1.30,'许可与参数核对','单工具 / 能力 / 数值\nLED位保持 · PWM20%')
for a,b in [((2.23,3.9),(2.74,3.9)),((4.96,3.9),(5.49,3.9)),((7.86,3.9),(8.39,3.9))]:arrow(ax,a,b)
box(ax,2.8,1.25,3.45,1.15,'独立副核与私有64KiB RAM','后台CoreMark · CRC · 运行状态',T)
arrow(ax,(3.85,3.19),(3.85,2.46),'邮箱启动 / 状态')
box(ax,8.45,1.25,2.25,1.15,'外设写入与读回','请求20% = 读回20%\n周期54000 / 高10800',T)
arrow(ax,(9.57,3.19),(9.57,2.46))
ax.plot([8.4,7.1,7.1,1.15,1.15],[1.8,1.8,.65,.65,3.18],color=T,lw=1.25)
arrow(ax,(1.15,3.0),(1.15,3.18));ax.text(4.5,.37,'按条保存请求、处理路径、返回值与回读',color=T,ha='center',fontsize=11)
ax.text(.12,.02,'当前以开发板自身复测；外接产品须适配工装与测量通道',color=M,fontsize=9.5)
save(fig,'应用_板卡复测')

fig,ax=plt.subplots(figsize=(12.4,5.5));ax.set(xlim=(0,12.4),ylim=(0,5.5));ax.axis('off')
ax.text(.1,5.1,'双核分工与中文请求的处理路径',fontsize=18,weight='bold',color=B)
box(ax,.15,2.8,2.15,1.25,'输入与主核','UART UTF-8\n长度 / 编码检查')
box(ax,3.0,3.65,2.45,1.1,'明确语法 / 语境','唯一工具、合法参数\n按需运行语境头')
box(ax,3.0,1.65,2.45,1.1,'完整语义模型','位置语义 + 短语记忆\n4MAC编码 / 8MAC语境',G)
box(ax,6.35,2.8,2.25,1.25,'同一道执行许可','工具 / 参数 / 能力\n拒绝不写外设')
box(ax,9.55,2.8,2.6,1.25,'执行与读回','LED / PWM / ADC\n返回本次结果与READY',T)
for a,b in [((2.35,3.6),(2.94,4.2)),((2.35,3.15),(2.94,2.2)),((5.51,4.2),(6.29,3.65)),((5.51,2.2),(6.29,3.15)),((8.66,3.4),(9.49,3.4))]:arrow(ax,a,b)
box(ax,6.35,.25,5.8,1.0,'副核后台计算自检','私有RAM与Cache · 无执行器权限 · CRC与计时独立返回',T)
arrow(ax,(7.5,2.74),(7.5,1.31),'后台启动')
save(fig,'项目_指令流程');
import shutil
shutil.copy2(O/'项目_指令流程.png',O/'系统架构.png')

fig,(ax,bx)=plt.subplots(1,2,figsize=(11.9,4.7),gridspec_kw={'width_ratios':[1.1,1]})
a=F['ai'];vals=[a['software_ms'],a['hardware_ms']]
ax.bar(['同镜像软件','硬件加速'],vals,color=[B,G],width=.52);ax.set(ylabel='完整模型计算时间 / ms',title='(a) 相同中文PWM输入')
for i,v in enumerate(vals):ax.text(i,v+14,f'{v:.3f}',ha='center',fontsize=13)
ax.set_ylim(0,780);ax.text(.5,740,f"{a['speedup']:.2f}×",ha='center',fontsize=19,color=G,weight='bold')
scores=[2.031489733,F['primary_score_per_mhz'],F['worker_score_per_mhz']]
bx.bar(['原主核\n40.5MHz','当前主核\n54MHz','当前副核\n54MHz'],scores,color=[M,B,T],width=.6)
bx.set(ylabel='CoreMark / MHz',title='(b) 各核单独计时',ylim=(0,4.8))
for i,v in enumerate(scores):bx.text(i,v+.1,f'{v:.4f}',ha='center',fontsize=12)
fig.text(.5,.01,'模型数组一致；双实例共同时间14.280421s，累计吞吐7.780660/MHz，另行统计。',ha='center',fontsize=10,color=M)
fig.tight_layout(rect=(0,.06,1,1));save(fig,'项目_计算性能')

fig,ax=plt.subplots(figsize=(10.8,4.1));labels=['LED 37','中文温度','中文PWM20%','中文计数器']
data=[x['metrics']['tready_ms']['all_samples']for x in L['summary'].values()]
bp=ax.boxplot(data,positions=range(4),widths=.38,showfliers=False,patch_artist=True)
for b in bp['boxes']:b.set(facecolor=PALE,edgecolor=B)
for i,values in enumerate(data):
 ax.scatter(i+np.linspace(-.12,.12,len(values)),values,c=G,s=24,zorder=3)
 ax.text(i,max(values)+.12,f"中位数 {np.median(values):.3f}",ha='center',fontsize=10,color=B)
ax.set(xticks=range(4),xticklabels=labels,ylabel='主机写入 → READY / ms',ylim=(0,4.35),title='原生UART控制往返：每句10次，保留全部样本')
ax.grid(axis='y',alpha=.16);fig.tight_layout();save(fig,'双核_控制往返')

fig,(ax,bx)=plt.subplots(1,2,figsize=(11.8,4.4));cats=['原单核\n40.5MHz','最终双核\n54MHz']
for a,vals,ttl in [(ax,[19456,55277],'LUT'),(bx,[19116,39035],'触发器')]:
 a.bar(cats,vals,color=[M,B],width=.5);a.set(title=ttl,ylim=(0,max(vals)*1.24))
 for i,v in enumerate(vals):a.text(i,v+max(vals)*.04,f'{v:,}',ha='center',fontsize=13)
fig.suptitle('整机布局布线资源：双核并行增加了计算与私有存储',fontsize=16,weight='bold')
fig.text(.5,.01,'最终：342.5 DRM36等效、40 APM；统计包含CPU、AI与存储逻辑。',ha='center',fontsize=10,color=M)
fig.tight_layout(rect=(0,.06,1,.92));save(fig,'双核_资源对照')

fig,ax=plt.subplots(figsize=(11,4.3));ax.axis('off')
ax.text(.02,.91,'中文PWM请求的实板返回',transform=ax.transAxes,fontsize=19,color=B,weight='bold')
rows=[['输入','请将PWM占空比设置为20%。'],['计算配置','54MHz · config6 · 完整模型'],['模型计算','2950565周期 / 54.640ms'],['执行与寄存器读回','请求20% / 读回20% / match=1'],['PWM计数','周期54000 / 高电平10800 / 使能1'],['并行检查','副核忙碌期间主核完成AI；模型数组与单独运行一致']]
t=ax.table(cellText=rows,colWidths=[.25,.73],loc='center',cellLoc='left',bbox=[.01,.02,.98,.73]);t.auto_set_font_size(False);t.set_fontsize(11.5)
for (i,j),c in t.get_celld().items():c.set_edgecolor('#D9E2EA');c.set_facecolor(PALE if j==0 else'white');c.set_text_props(color=B if j==0 else'#28384A')
save(fig,'报告_实板记录节选')
