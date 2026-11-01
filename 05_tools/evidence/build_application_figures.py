"""Application and AI-design figures; factual interfaces, no invented physical device."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,FancyArrowPatch,Rectangle,Circle
from matplotlib.text import Text
from matplotlib import font_manager

ROOT=Path('/work/LUO/NeedleRV-X');OUT=ROOT/'参赛材料/图表';OUT.mkdir(exist_ok=True)
FONT='/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc'
BLUE='#143295';TEAL='#5E9691';GOLD='#BF914F';INK='#26384C';MUT='#65758A';GRID='#CCD7E1';PALE='#F4F7FA';ROSE='#B8657E'
plt.rcParams.update({'axes.spines.top':False,'axes.spines.right':False,'axes.edgecolor':'#A9B6C3','font.size':12,'savefig.facecolor':'white','svg.fonttype':'none'})

def save(fig,name):
 for t in fig.findobj(Text):
  t.set_fontproperties(font_manager.FontProperties(fname=FONT,size=t.get_fontsize(),weight=t.get_fontweight()))
 for ext in ['png','svg']:fig.savefig(str(OUT/(name+'.'+ext)),dpi=220,bbox_inches='tight',pad_inches=.16)
 plt.close(fig);print('FIGURE',name,flush=True)

def box(ax,x,y,w,h,title,body='',color=BLUE,fill='white',dashed=False,ts=12.4,bs=10.7):
 r=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=.06,rounding_size=.08',fc=fill,ec=color,lw=1.3,linestyle='--'if dashed else'-');ax.add_patch(r)
 ax.text(x+w/2,y+h-.26,title,ha='center',va='center',fontsize=ts,weight='bold',color=color)
 if body:ax.text(x+w/2,y+(h-.43)/2-.05,body,ha='center',va='center',fontsize=bs,color=INK,linespacing=1.5)
 return r

def arrow(ax,a,b,color=BLUE,dashed=False,label=None,offset=(0,.17),lw=1.4):
 ax.add_patch(FancyArrowPatch(a,b,arrowstyle='-|>',mutation_scale=13,lw=lw,color=color,linestyle='--'if dashed else'-',connectionstyle='arc3'))
 if label:ax.text((a[0]+b[0])/2+offset[0],(a[1]+b[1])/2+offset[1],label,ha='center',va='center',fontsize=10.5,color=color,backgroundcolor='white')

def application():
 fig,ax=plt.subplots(figsize=(12.4,6.0));fig.subplots_adjust(left=.01,right=.99,top=.98,bottom=.025)
 ax.set_xlim(0,12.4);ax.set_ylim(0,6.25);ax.axis('off')
 ax.text(.10,5.97,'控制板试产与返修：临时交互式复测',fontsize=18.5,weight='bold',color=BLUE)
 ax.text(.10,5.55,'固定工序使用测试脚本；中文交互处理单项检查、局部调参与状态复核',fontsize=11.8,color=MUT)
 ax.add_patch(FancyBboxPatch((2.9,1.40),6.94,3.63,boxstyle='round,pad=.12,rounding_size=.1',fc=PALE,ec=GRID,lw=1.1))
 ax.text(3.08,4.74,'当前原型：控制板自身',fontsize=12.3,color=BLUE,weight='bold')
 box(ax,.18,3.15,2.05,1.65,'工程师逐条输入','只关闭LED0\n其他LED保持不变\n\nPWM占空比设为20%',bs=10.7)
 box(ax,3.1,3.18,1.75,1.12,'RISC-V调度','接收中文\n调度模型与外设')
 box(ax,5.44,3.18,1.84,1.12,'语境与工具','操作 / 解释 / 否定\n工具类别与参数',color=GOLD)
 box(ax,7.86,3.18,1.73,1.12,'执行许可','工具 / 数值范围\n硬件能力')
 arrow(ax,(2.25,3.74),(3.03,3.74),label='UART')
 arrow(ax,(4.88,3.74),(5.37,3.74));arrow(ax,(7.31,3.74),(7.79,3.74))
 box(ax,7.86,1.75,1.73,.97,'输出复核','LED位保持 / PWM',color=TEAL,bs=10.1)
 arrow(ax,(8.72,3.12),(8.72,2.78))
 box(ax,3.1,1.75,3.10,.97,'基础状态与计算检查','片内结温 · 周期计数 · CoreMark',bs=10.4)
 arrow(ax,(3.97,3.12),(3.97,2.78),color=TEAL)
 box(ax,10.28,1.75,1.92,1.40,'单项结果记录','请求 / 处理路径\n返回值 / 寄存器回读',color=TEAL,bs=10.3)
 arrow(ax,(9.65,2.23),(10.21,2.23),color=TEAL)
 ax.plot([8.72,8.72,4.65],[1.68,1.02,1.02],color=TEAL,lw=1.4)
 arrow(ax,(4.65,1.02),(1.2,1.02),color=TEAL);ax.plot([1.2,1.2],[1.02,3.07],color=TEAL,lw=1.4)
 ax.text(4.96,1.10,'写后核对：请求20% / 读回20%',ha='center',fontsize=11.5,color=TEAL,backgroundcolor='white')
 ax.text(.18,.42,'逐条请求，保留其余输出；未开放的频率修改请求拒绝执行',fontsize=10.8,color=MUT)
 ax.text(12.2,.42,'逻辑功能关系图',fontsize=10.8,color=MUT,ha='right')
 save(fig,'应用_板卡复测')

def ai_design():
 fig=plt.figure(figsize=(12.4,6.7));ax=fig.add_axes([.01,.37,.98,.60]);ax.set_xlim(0,12.4);ax.set_ylim(0,4.3);ax.axis('off')
 ax.text(.10,4.03,'自研语境分支与组合方案版本对照',fontsize=18,weight='bold',color=BLUE)
 ax.text(.10,3.58,'(a) 特征、计算单元与合法工具修正',fontsize=12.2,color=INK,weight='bold')
 box(ax,.2,1.90,2.16,1.12,'Unicode位置特征','全局1024\n句首512 + 句尾512',color=GOLD,bs=11)
 box(ax,2.95,1.90,2.27,1.12,'位置语义头','2048 → 64 → 16\n独立8MAC语境侧核',color=GOLD,bs=11)
 box(ax,5.82,1.90,2.17,1.12,'语境头结果','隐藏向量64\n语境 / 工具分数',color=GOLD,bs=10.9)
 box(ax,8.64,1.90,3.43,1.12,'CPU受约束残差','隐藏向量64 + 编码器分数6\n70 → 5；仅修正合法工具',bs=11)
 arrow(ax,(2.42,2.46),(2.88,2.46),GOLD)
 arrow(ax,(5.28,2.46),(5.75,2.46),GOLD)
 arrow(ax,(8.05,2.46),(8.57,2.46),BLUE)
 box(ax,.2,.20,2.16,1.03,'字节编码与短语记忆','双层d64 / 4 heads\n学习型2/3-gram',bs=10.8)
 box(ax,2.95,.20,2.27,1.03,'编码计算','4MAC  INT4 / INT8\n产生六类意图分数',bs=10.8)
 box(ax,5.82,.20,2.17,1.03,'W1权重缓存','128KiB常驻\n服务8MAC语境侧核',color=TEAL,bs=10.8)
 box(ax,8.64,.20,3.43,1.03,'工具许可与执行','语境拒绝优先\n工具 / 参数 / 能力检查',color=TEAL,bs=10.8)
 arrow(ax,(2.42,.72),(2.88,.72))
 # The encoder scores feed the CPU residual; the cache serves semantic W1 only.
 ax.plot([5.28,5.56,5.56,8.32],[.72,.72,1.52,1.52],color=BLUE,lw=1.2)
 arrow(ax,(8.32,1.52),(8.57,2.08),BLUE)
 arrow(ax,(6.90,1.30),(4.12,1.83),TEAL)
 arrow(ax,(10.35,1.83),(10.35,1.30),TEAL)
 # Two grouped count comparisons with explicit denominators; not a one-factor ablation.
 b=fig.add_axes([.075,.17,.56,.16]);b.set_title('(b) 组合方案版本对照',loc='left',fontsize=12.3,fontweight='bold',color=INK,pad=9)
 ys=[0,1];old=[1058,653];new=[1087,685];totals=[1138,900]
 b.barh([y-.16 for y in ys],old,height=.28,color='#A9BBCB',label='前一64维方案')
 b.barh([y+.16 for y in ys],new,height=.28,color=BLUE,label='位置特征 + 受约束残差方案')
 for y,a,c,n in zip(ys,old,new,totals):
  b.text(a+13,y-.16,f'{a}/{n}',va='center',fontsize=10.4,color=INK)
  b.text(c+13,y+.16,f'{c}/{n}',va='center',fontsize=10.4,color=BLUE)
 b.set_yticks(ys);b.set_yticklabels(['1138条集合','900条难例']);b.invert_yaxis();b.set_xlim(0,1320);b.set_xticks([0,300,600,900,1200]);b.grid(axis='x',color=GRID,lw=.7);b.set_axisbelow(True);b.set_xlabel('神经分类正确条数',fontsize=10.8)
 c=fig.add_axes([.70,.11,.27,.22]);c.axis('off')
 c.text(0,.83,'+29 / +32',fontsize=24,color=BLUE,weight='bold')
 c.text(0,.48,'两套评价集的正确数增量',fontsize=11.8,color=INK)
 c.text(0,.10,'组合版本变化，不作单因素归因\n两组均为已用于开发选择的集合',fontsize=10.4,color=MUT,linespacing=1.65)
 # Legend belongs below its axis but stays above the final source/family line.
 handles,labels=b.get_legend_handles_labels();fig.legend(handles,labels,frameon=False,fontsize=10.2,ncol=2,loc='lower left',bbox_to_anchor=(.075,.046),borderaxespad=0)
 fig.text(.075,.012,'低比特工具调用与字符短语记忆参考Needle；位置语义、受约束残差、整数运行时及专用计算接口由本项目实现。',fontsize=10.4,color=MUT)
 save(fig,'AI_设计与版本对照')

if __name__=='__main__':application();ai_design()
