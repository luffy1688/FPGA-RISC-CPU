from pathlib import Path
import json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch
root=Path(__file__).resolve().parents[2];out=root/'08_release/docs/图表';out.mkdir(parents=True,exist_ok=True)
font=fm.FontProperties(fname='/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc')
fm.fontManager.ttflist.append(fm.FontEntry(fname=font.get_file(),name='NeedleCJK'))
plt.rcParams.update({'font.family':'NeedleCJK','font.size':12,'axes.spines.top':False,'axes.spines.right':False,'axes.labelcolor':'#25313B','text.color':'#25313B','axes.edgecolor':'#697682','pdf.fonttype':42})
blue='#75B2E0';mint='#A5CAB5';rose='#B55A8B';line='#697682'
def save(fig,name):
 fig.savefig(out/(name+'.png'),dpi=190,facecolor='white',bbox_inches='tight');fig.savefig(out/(name+'.pdf'),facecolor='white',bbox_inches='tight');plt.close(fig)
def box(ax,x,y,w,h,text,color):
 ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.008,rounding_size=0.015',facecolor=color,edgecolor=line,lw=.8));ax.text(x+w/2,y+h/2,text,ha='center',va='center',fontproperties=font,fontsize=12,linespacing=1.5)
def arrow(ax,a,b,label=None):
 ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color=line,lw=1.2))
 if label:ax.text((a[0]+b[0])/2,(a[1]+b[1])/2+.025,label,ha='center',va='bottom',fontproperties=font,fontsize=10)
fig,ax=plt.subplots(figsize=(13,4.8));ax.set(xlim=(0,1),ylim=(0,1));ax.axis('off')
ax.add_patch(FancyBboxPatch((.23,.12),.75,.76,boxstyle='round,pad=0.012',facecolor='#F5F8FB',edgecolor='#AAB8C5',lw=1))
ax.text(.26,.83,'FPGA  40.5 MHz  ·  RV32IM + XND',fontproperties=font,fontsize=13,weight='bold')
box(ax,.015,.35,.17,.30,'PC 控制台\n中文输入 · 串口\n自检汇总 · 导出', '#E5F1F9')
box(ax,.27,.40,.16,.23,'输入与工具合同\n语境 · 能力\n唯一工具 · 参数','#E8EBF2')
box(ax,.49,.60,.18,.15,'显式 schema 命中\n规则快路径',mint)
box(ax,.49,.28,.18,.20,'未命中进入模型\n47 KB 字节编码器\nXND 低比特计算',blue)
box(ax,.74,.40,.18,.23,'共享执行与回读\nLED / PWM / ADC\n计数器 / CoreMark','#EFE5EC')
arrow(ax,(.185,.50),(.265,.50),'UART');arrow(ax,(.435,.57),(.485,.675),'命中');arrow(ax,(.435,.43),(.485,.38),'未命中')
arrow(ax,(.675,.675),(.74,.57));arrow(ax,(.675,.38),(.74,.43));arrow(ax,(.83,.39),(.83,.19));arrow(ax,(.83,.19),(.10,.19));arrow(ax,(.10,.19),(.10,.345))
ax.text(.48,.205,'真实结果、路径、回读与区间计时',ha='center',fontproperties=font,fontsize=11)
ax.text(.5,.035,'两条路径受相同合同约束；控制台自检只串行组织单工具请求。',ha='center',fontproperties=font,fontsize=11)
save(fig,'系统架构')
j=json.loads((root/'07_runs/board/current/measurement_summary.json').read_text());lat=j['latency'];fig,axes=plt.subplots(1,2,figsize=(13.2,4.7),gridspec_kw={'width_ratios':[.85,1.45]})
a=axes[0];v=[9381872/1e6,751883/1e6];a.bar([0,1],v,color=[blue,mint],width=.55);a.set_xticks([0,1]);a.set_xticklabels(['软件','XND']);a.set_ylabel('模型推理周期 / 百万');a.set_ylim(0,11.8);a.set_title('A  同镜像 led 37 模型推理',fontproperties=font,pad=15)
for x,y in enumerate(v):a.text(x,y+.15,'%.3f'%y,ha='center')
a.text(.5,10.4,'12.478 倍 · 整数分数一致',ha='center',fontproperties=font,fontsize=11)
a=axes[1];xs=np.arange(3);labels=['led 37','中文读温度','中文设置 PWM'];text_order=['led 37','请读取FPGA当前温度。','请将PWM占空比设置为20%。']
for fast,c,offset,label in [(0,blue,-.18,'模型路径 + 完整帧'),(1,mint,.18,'规则快路径 + 紧凑帧')]:
 rows=[next(x for x in lat if x['fast']==fast and x['text']==t)for t in text_order];ys=[x['native_ready_ms_median']for x in rows];lo=[y-x['native_ready_ms_min']for y,x in zip(ys,rows)];hi=[x['native_ready_ms_max']-y for y,x in zip(ys,rows)]
 a.bar(xs+offset,ys,width=.34,color=c,label=label,yerr=[lo,hi],capsize=3,error_kw={'lw':.8,'ecolor':line})
 for x,y in zip(xs+offset,ys):a.text(x,y+5,'%.1f'%y,ha='center',fontsize=10)
a.set_xticks(xs);a.set_xticklabels(labels);a.set_ylim(0,275);a.set_ylabel('原生串口 TX 至 READY / ms');a.set_title('B  相同句子各 3 次实测',fontproperties=font,pad=15);a.legend(frameon=False,fontsize=10,loc='upper left');a.grid(axis='y',alpha=.15);a.set_axisbelow(True)
fig.subplots_adjust(bottom=.20,wspace=.35);fig.text(.5,.025,'115200 / 8N1；柱为中位数，误差线为本组最小至最大值；两项改动共同生效，不是浏览器计时。',ha='center',fontproperties=font,fontsize=10)
save(fig,'性能与资源对照')
model=json.loads((root/'07_runs/development/nlu_candidate/report.json').read_text());dev=next(v for v in model['selected'].values()if isinstance(v,dict)and v.get('examples')==192)
conf=np.array(dev['confusion']);assert conf.shape==(6,6)and conf.trace()==118 and conf.sum()==192
fig,axes=plt.subplots(1,2,figsize=(13.2,4.7),gridspec_kw={'width_ratios':[1,1.1]});a=axes[0];xx=np.arange(2)
for off,values,c,label in [(-.23,[73/80*100,118/192*100],blue,'原始模型'),(0,[100,189/192*100],'#9C8BB7','透明规则'),(.23,[100,189/192*100],mint,'快路径系统')]:
 a.bar(xx+off,values,width=.21,color=c,label=label)
 for i,(x,y)in enumerate(zip(xx+off,values)):a.text(x,y+1.5,('73/80'if i==0 else'118/192')if label=='原始模型'else('80/80'if i==0 else'189/192'),ha='center',fontsize=9,rotation=0)
a.set_xticks(xx);a.set_xticklabels(['原 80 开发集','新 192 开发集']);a.set_ylim(0,121);a.set_ylabel('正确比例 / %');a.set_title('A  分类与系统任务分别统计',fontproperties=font,pad=15);a.legend(frameon=False,loc='upper center',bbox_to_anchor=(.5,-.12),ncol=3,fontsize=9);a.grid(axis='y',alpha=.15);a.set_axisbelow(True)
a=axes[1];im=a.imshow(conf,cmap='BuPu',vmin=0,vmax=32);names=['温度','PWM','CoreMark','计数','LED','拒绝'];a.set_xticks(range(6));a.set_xticklabels(names,fontsize=10);a.set_yticks(range(6));a.set_yticklabels(names,fontsize=10);a.set_xlabel('原始预测');a.set_ylabel('原始意图标签');a.set_title('B  原始模型混淆矩阵  118 / 192',fontproperties=font,pad=15)
for y in range(6):
 for x in range(6):a.text(x,y,str(conf[y,x]),ha='center',va='center',color='white'if conf[y,x]>16 else'#25313B',fontsize=10)
fig.subplots_adjust(bottom=.24,wspace=.35);fig.text(.5,.025,'Host / offline，已观察开发集；系统统计包含工具、参数与 operation。透明规则同分，未证明神经净优势。',ha='center',fontproperties=font,fontsize=10)
save(fig,'中文识别评价')
print('Updated 3 existing scientific figures, PNG/PDF')
