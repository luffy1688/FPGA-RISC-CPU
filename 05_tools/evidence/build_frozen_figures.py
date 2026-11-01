#!/usr/bin/env python3
"""Frozen engineering figures from actual JSON evidence. No synthetic measurements."""
from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import gridspec, colors, font_manager
from matplotlib.patches import Rectangle, FancyArrowPatch
from matplotlib.text import Text

ROOT=Path('/work/LUO/NeedleRV-X')
OUT=ROOT/'参赛材料/图表'
CURRENT=ROOT/'07_runs/board/current'
SELECTION=json.loads((ROOT/'07_runs/development/resource_trials/selection.json').read_text())
ACCEPT=json.loads((CURRENT/'acceptance_report.json').read_text())
NATIVE={p:json.loads((CURRENT/('native_'+p+'_921600.json')).read_text())for p in ['text','framed']}
BLUE='#143295';GOLD='#C89B61';SECOND='#1455AF';PALE='#A2B9CC';INK='#28384A';GRID='#DFE5EC'
FONT='/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc'
assert Path(FONT).is_file()
plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#9CA8B4','axes.labelcolor':INK,'xtick.color':INK,'ytick.color':INK,'font.size':11,'axes.titlesize':13,'axes.titleweight':'bold','savefig.facecolor':'white','pdf.fonttype':42,'svg.fonttype':'none'})

def style_text(fig):
 for t in fig.findobj(Text):
  t.set_fontproperties(font_manager.FontProperties(fname=FONT,size=t.get_fontsize(),weight=t.get_fontweight(),style=t.get_fontstyle()))
def save(fig,name):
 OUT.mkdir(parents=True,exist_ok=True);style_text(fig)
 for ext in ['png','svg']:
  fig.savefig(str(OUT/(name+'.'+ext)),dpi=220,bbox_inches='tight',pad_inches=.16)
 # Overwrite an existing PDF rather than leave a same-name stale figure.
 fig.savefig(str(OUT/(name+'.pdf')),bbox_inches='tight',pad_inches=.16)
 plt.close(fig)
 print('FIGURE',name,flush=True)

def architecture():
 fig,ax=plt.subplots(figsize=(14.6,7.1));fig.subplots_adjust(left=.015,right=.99,top=.96,bottom=.05)
 ax.set_xlim(0,14);ax.set_ylim(0,7.6);ax.axis('off')
 ax.text(.12,7.3,'离线中文请求与板上执行链路',fontsize=17,weight='bold',color=BLUE)
 ax.text(3.05,6.75,'FPGA：40.5 MHz RV32IM · 主SRAM 512 KiB（CPU 128 + AI 384）',fontsize=11.5,color=INK)
 ax.add_patch(Rectangle((2.85,1.55),10.95,4.85,facecolor='#F7F9FC',edgecolor='#BCC8D6',linewidth=1))
 def box(x,y,title,body,w=2.15,h=1.25,color=BLUE):
  ax.add_patch(Rectangle((x-w/2,y-h/2),w,h,facecolor='white',edgecolor=color,linewidth=1.4))
  ax.text(x,y+.23,title,ha='center',va='center',fontsize=12.1,weight='bold',color=color)
  ax.text(x,y-.22,body,ha='center',va='center',fontsize=10.4,color=INK,linespacing=1.45)
 def arrow(points,label=None,label_xy=None,color=BLUE,dashed=False):
  for i,(p,q)in enumerate(zip(points[:-1],points[1:])):
   style='-|>'if i==len(points)-2 else '-'
   ax.add_patch(FancyArrowPatch(p,q,arrowstyle=style,mutation_scale=11,linewidth=1.2,color=color,linestyle='--'if dashed else '-'))
  if label:ax.text(*label_xy,label,ha='center',va='center',fontsize=10.1,color=color,backgroundcolor='white')
 box(1.35,5.25,'电脑输入','离线中文 / 串口\n≤64 UTF-8 字节',w=2.25)
 box(4.05,5.25,'输入与语境检查','UTF-8 / 引用 / 否定\n多动作 / 能力边界')
 box(6.8,5.25,'严格机器语法','整句语法 + 合法参数\n命中可 model_used = 0')
 box(9.55,5.25,'执行许可','工具合同 / 参数 / 操作\n模型与规则共用入口')
 box(12.3,5.25,'硬件工具','温度 / LED / PWM\n计数器 / CoreMark')
 box(4.05,2.75,'位置语义特征','全局1024 + 首512 + 尾512\nUnicode 2/3-gram',color=GOLD)
 box(6.8,2.75,'8 MAC 语义侧核','2048 → 64 → 16\n128 KiB 常驻权重缓存',color=GOLD)
 box(9.55,2.75,'语境后派发 / 编码','schema 或 4 MAC 编码器\n修复 / 级联 / 受限残差',color=GOLD)
 box(12.3,2.75,'实际回读与回执','LED/PWM 寄存器核对\nseq / CRC / READY')
 for x in [1.35,4.05,6.8,9.55]:arrow([(x+1.11,5.25),(x+1.57,5.25)])
 arrow([(6.8,4.60),(6.8,4.12),(4.05,4.12),(4.05,3.39)],'语法未命中',(5.3,4.12),color=GOLD)
 arrow([(5.17,2.75),(5.68,2.75)],color=GOLD)
 arrow([(7.92,2.75),(8.43,2.75)],color=GOLD)
 arrow([(9.55,3.39),(9.55,4.60)],'语境后工具决策',(9.55,3.95),color=GOLD)
 arrow([(12.3,4.60),(12.3,3.39)])
 arrow([(12.3,2.08),(12.3,1.0),(1.35,1.0),(1.35,4.60)],color='#7B8896',dashed=True)
 ax.text(6.55,1.0,'电脑审计：请求 → 处理路径 → 许可 → 实际回读 → 导出',ha='center',fontsize=11,color=INK,backgroundcolor='white')
 ax.text(.12,.32,'结构示意；连线表示计算与回执关系，不是芯片物理布图。语境拒绝可提前返回；未运行模型时不补填神经分数。',fontsize=10.5,color=INK)
 save(fig,'系统架构')

def performance():
 fig=plt.figure(figsize=(14.8,7.1));gs=gridspec.GridSpec(2,2,width_ratios=[1.65,1],height_ratios=[1,1],wspace=.4,hspace=.65)
 ax=fig.add_subplot(gs[:,0]);ax.set_title('(a) 显式控制的原生串口往返（含语境头）',loc='left',pad=14)
 command_names=list(NATIVE['text']['summary']);labels=['LED整体掩码 37','读取FPGA当前温度','PWM按20%占空比输出','PWM占空比设置为20%']
 for i,command in enumerate(command_names):
  for protocol,offset,color,marker in [('text',-.14,BLUE,'o'),('framed',.14,GOLD,'s')]:
   d=NATIVE[protocol];assert d['status']=='PASS'and d['repeat']==10
   met=d['summary'][command]['metrics']['tready_ms'];samples=np.asarray(met['all_samples']);assert len(samples)==10 and abs(np.median(samples)-met['median'])<1e-8
   yy=np.full(10,i+offset)+np.linspace(-.07,.07,10)
   ax.scatter(samples,yy,s=32,marker=marker,color=color,alpha=.6,label=('文本'if protocol=='text'else'二进制')if i==0 else None,zorder=3)
   ax.plot([min(samples),max(samples)],[i+offset]*2,color=color,linewidth=.9,alpha=.7)
   ax.scatter([met['median']],[i+offset],s=95,marker='|',color=color,linewidths=2.6,zorder=4)
   ax.text(max(samples)+.12,i+offset,'%.3f'%met['median'],va='center',fontsize=10.8,color=color)
 ax.set_yticks(np.arange(4));ax.set_yticklabels(labels);ax.invert_yaxis();ax.set_ylim(3.6,-.65)
 ax.set_xlim(0,6.1);ax.set_xticks(np.arange(0,7));ax.set_xlabel('WriteFile入口 → 真实READY接收（ms）',labelpad=10)
 ax.grid(axis='x',color=GRID,linewidth=.7);ax.legend(loc='upper left',frameon=False,ncol=2,bbox_to_anchor=(0,-.13))
 ax.text(0,-.24,'每句每协议 n=10；散点为全部样本，竖线为中位数\n含USB与主机调度，不含浏览器渲染；不是完整模型耗时。',transform=ax.transAxes,fontsize=10.4,color=INK,va='top')
 before=SELECTION['synthesis_refinement'];res=ACCEPT['resources']
 values1=[before['before_lut'],before['before_ff']];values2=[res['lut'],res['ff']]
 b=fig.add_subplot(gs[0,1]);b.set_title('(b) 同候选同步RAM端口优化',loc='left',pad=14)
 x=np.arange(2);w=.32
 for off,vals,color,label in [(-w/2,values1,PALE,'优化前'),(w/2,values2,BLUE,'优化后')]:
  bars=b.bar(x+off,vals,width=w,color=color,label=label)
  for bar,v in zip(bars,vals):b.text(bar.get_x()+w/2,v+1100,'{:,}'.format(v),ha='center',fontsize=10.5,color=INK)
 b.set_ylim(0,52000);b.set_xticks(x);b.set_xticklabels(['LUT','FF']);b.set_ylabel('PRR 元件数');b.grid(axis='y',color=GRID,linewidth=.7);b.set_axisbelow(True)
 b.legend(frameon=False,ncol=2,loc='upper center',bbox_to_anchor=(.5,-.16))
 c=fig.add_subplot(gs[1,1]);c.set_title('(c) 存储资源代价',loc='left',pad=14)
 drm=[before['before_drm36_equivalent'],res['drm36_equivalent']];assert drm==[290.5,292.5]
 bars=c.bar([0,1],drm,width=.47,color=[PALE,BLUE])
 for bar,v in zip(bars,drm):c.text(bar.get_x()+bar.get_width()/2,v+6,'%.1f'%v,ha='center',fontsize=11)
 c.set_ylim(0,350);c.set_xticks([0,1]);c.set_xticklabels(['优化前','优化后']);c.set_ylabel('DRM36 等效块');c.grid(axis='y',color=GRID,linewidth=.7);c.set_axisbelow(True)
 c.text(0,-.26,'同一模型、同一PRR统计阶段；模块验证仍为355683周期。',transform=c.transAxes,fontsize=10.4,va='top')
 fig.subplots_adjust(left=.16,right=.97,top=.92,bottom=.24)
 save(fig,'性能与资源对照')

def recognition():
 fig=plt.figure(figsize=(15.4,6.2));gs=gridspec.GridSpec(1,3,width_ratios=[1,1,1.05],wspace=.45)
 names=['温度','PWM','基准','计数','LED','拒绝'];cmap=colors.LinearSegmentedColormap.from_list('needleblue',['#FFFFFF','#DDE7F5',BLUE])
 for k,key in enumerate(['observed1138','observed900']):
  d=SELECTION['observed_neural'][key];matrix=np.asarray(d['confusion_true_rows_pred_columns']);assert matrix.shape==(6,6)and matrix.sum()==d['n']and matrix.trace()==d['correct']
  norm=matrix/matrix.sum(axis=1)[:,None];ax=fig.add_subplot(gs[0,k]);im=ax.imshow(norm,cmap=cmap,vmin=0,vmax=1,interpolation='nearest')
  ax.set_title('(%s) 观察集%d：%d/%d（%.2f%%）'%('ab'[k],d['n'],d['correct'],d['n'],100*d['correct']/d['n']),loc='left',fontsize=12.1,pad=14)
  for i in range(6):
   for j in range(6):
    v=matrix[i,j];text=str(v)+('\n%.1f%%'%(100*norm[i,j])if v else '')
    ax.text(j,i,text,ha='center',va='center',fontsize=9.5,color='white'if norm[i,j]>.57 else INK)
  ax.set_xticks(range(6));ax.set_xticklabels(names);ax.set_yticks(range(6));ax.set_yticklabels(names);ax.set_xlabel('预测类别');ax.set_ylabel('真实类别')
  ax.set_xticks(np.arange(-.5,6,1),minor=True);ax.set_yticks(np.arange(-.5,6,1),minor=True);ax.grid(which='minor',color='#D6DFE9',linewidth=.65);ax.tick_params(which='minor',length=0)
  ax.text(0,-.2,'颜色：行归一化召回；格内：原始条数与行占比。',transform=ax.transAxes,fontsize=9.7,va='top')
 ax=fig.add_subplot(gs[0,2]);ax.set_title('(c) 五类合法指令的神经召回',loc='left',fontsize=12.1,pad=14)
 for key,off,color,label in [('observed1138',-.18,BLUE,'1138观察集'),('observed900',.18,GOLD,'900观察集')]:
  d=SELECTION['observed_neural'][key];matrix=np.asarray(d['confusion_true_rows_pred_columns']);correct=np.diag(matrix)[:5];total=matrix.sum(axis=1)[:5];recall=100*correct/total
  ax.barh(np.arange(5)+off,recall,height=.28,color=color,label=label)
  for i,(v,good,n)in enumerate(zip(recall,correct,total)):ax.text(v+2,i+off,'%d/%d'%(good,n),va='center',fontsize=9.7,color=color)
 ax.set_yticks(range(5));ax.set_yticklabels(names[:5]);ax.invert_yaxis();ax.set_xlim(0,137);ax.set_xticks([0,50,100]);ax.set_xlabel('该类召回率（%）');ax.grid(axis='x',color=GRID,linewidth=.7);ax.set_axisbelow(True)
 ax.legend(frameon=False,loc='upper left',bbox_to_anchor=(0,-.11),fontsize=10)
 fig.text(.045,.105,'1138条：合法195/196，神经误接受50、误拒绝0；900条：合法175/200，神经误接受190、误拒绝24。',fontsize=11,color=INK)
 fig.text(.045,.045,'全部为已观察集合，已参与开发；95.52%不是独立盲测结论。原始神经与工具合同后的系统成绩分开统计。',fontsize=10.8,color=INK)
 fig.subplots_adjust(left=.045,right=.985,top=.84,bottom=.3)
 save(fig,'中文识别评价')

if __name__=='__main__':
 assert ACCEPT['accepted']and ACCEPT['program_frozen']and ACCEPT['firmware']=='experimental_position_fusion_oct30'
 architecture();performance();recognition()
