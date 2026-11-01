#!/usr/bin/env python3
"""Teaching animations from frozen architecture and actual endpoint metrics.
No runtime is simulated, no samples or scores are fabricated.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import json,math,subprocess
R=Path('/work/LUO/NeedleRV-X');TMP=Path('/tmp/needlervx_ppt_gifs');OUT=R/'参赛材料/展示素材'
S=json.loads((R/'07_runs/development/resource_trials/selection.json').read_text());A=json.loads((R/'07_runs/board/current/acceptance_report.json').read_text())
B='#143295';G='#C89B61';INK='#28384A';MUT='#65758A';GRID='#DCE3EC';PALE='#F3F6FA';WHITE='#FFFFFF';L='#A2B9CC'
F='/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc'
def font(size):return ImageFont.truetype(F,size)
def text(d,xy,t,size=22,c=INK):d.text(xy,t,font=font(size),fill=c)
def centre(d,xy,t,size=22,c=INK):
 box=d.textbbox((0,0),t,font=font(size))if hasattr(d,'textbbox')else(0,0,*d.textsize(t,font=font(size)))
 d.text((xy[0]-(box[2]-box[0])/2,xy[1]-(box[3]-box[1])/2),t,font=font(size),fill=c)
def arrow(d,pts,c=B,width=3):
 d.line(pts,fill=c,width=width)
 p,q=pts[-2:];a=math.atan2(q[1]-p[1],q[0]-p[0]);r=9
 tri=[q,(q[0]-r*math.cos(a-.5),q[1]-r*math.sin(a-.5)),(q[0]-r*math.cos(a+.5),q[1]-r*math.sin(a+.5))];d.polygon(tri,fill=c)
def save_gif(name,frames):
 out=OUT/name;OUT.mkdir(parents=True,exist_ok=True)
 # Frame count and 125ms frame delay preserve an exact 8fps teaching timeline.
 frames[0].save(out,save_all=True,append_images=frames[1:],duration=125,loop=0,optimize=True,disposal=2)
 print('GIF_READY',name,len(frames),out.stat().st_size,flush=True)
def flow():
 frames=[]
 for i in range(64):
  im=Image.new('RGB',(960,540),WHITE);d=ImageDraw.Draw(im)
  text(d,(30,23),'两条路径，共用执行许可与回读',31,B);text(d,(31,72),'语法处理与模型路径',18,MUT)
  model=i>=32;phase=(i%32)//8
  nodes=[('输入','中文请求',40,225,156,90,0),('显式语法','唯一工具 / 合法参数',260,143,200,90,1),('模型分支','位置语义 + 低比特编码',260,337,200,90,1),('执行许可','工具合同 / 参数',550,225,170,90,2),('动作与回读','寄存器 / READY',770,225,154,90,3)]
  for title,body,x,y,w,h,k in nodes:
   unused=(model and title=='显式语法')or(not model and title=='模型分支');active=not unused and k==phase
   c=GRID if unused else G if model else B
   d.rectangle((x,y,x+w,y+h),fill=PALE if active else WHITE,outline=c,width=4 if active else 2)
   centre(d,(x+w/2,y+26),title,24,c);centre(d,(x+w/2,y+64),body,16,MUT if unused else INK)
  arrow(d,[(196,260),(224,260),(224,188),(260,188)],GRID if model else B)
  arrow(d,[(196,280),(224,280),(224,382),(260,382)],G if model else GRID)
  arrow(d,[(460,188),(505,188),(505,250),(550,250)],GRID if model else B)
  arrow(d,[(460,382),(505,382),(505,290),(550,290)],G if model else GRID)
  arrow(d,[(720,270),(770,270)],G if model else B)
  title='模型路径'if model else'快路径';caption='中文模型给出候选，再核对工具与参数。'if model else'机器语法直接解析，完整编码器不参与。'
  text(d,(31,453),title,26,G if model else B);text(d,(176,457),caption,21,INK)
  text(d,(31,505),'两条处理路径共用执行接口与寄存器读回。',16,MUT)
  frames.append(im)
 save_gif('双路径流程_讲解动画.gif',frames)
def metrics():
 frames=[]
 data1138=S['observed_neural']['observed1138'];data900=S['observed_neural']['observed900'];ref=S['synthesis_refinement']
 assert data1138['correct']==1087 and data900['correct']==685 and A['resources']['lut']==19456
 for i in range(64):
  im=Image.new('RGB',(960,540),WHITE);d=ImageDraw.Draw(im)
  text(d,(30,23),'模型与资源版本对照',32,B);text(d,(31,72),'分类结果与RAM实现的版本对照',18,MUT)
  left=i<32
  d.rectangle((24,123,466,440),outline=B if left else GRID,width=3 if left else 1)
  d.rectangle((491,123,936,440),outline=G if not left else GRID,width=3 if not left else 1)
  text(d,(40,137),'开发评价集的神经正确数',22,B);text(d,(509,137),'同候选RAM端口优化',22,G)
  # Endpoint bars remain fixed; only emphasis changes with the narration.
  for y,label,old,new,n in [(210,'1138条',1058,1087,1138),(329,'900条',653,685,900)]:
   text(d,(41,y-32),label,20,INK)
   d.rectangle((142,y,142+275*old/n,y+22),fill=L);text(d,(143,y-25),str(old)+' / '+str(n),17,MUT)
   d.rectangle((142,y+39,142+275*new/n,y+61),fill=B);text(d,(143,y+65),str(new)+' / '+str(n),17,B)
  for y,label,old,new in [(210,'LUT',31208,19456),(329,'FF',43692,19116)]:
   text(d,(510,y-30),label,21,INK)
   d.rectangle((591,y,591+285*old/50000,y+22),fill=L);text(d,(592,y-24),format(old,','),17,MUT)
   d.rectangle((591,y+39,591+285*new/50000,y+61),fill=G);text(d,(592,y+65),format(new,','),17,G)
  captions=['位置特征与残差版本：合法指令195/196。','900条难例：神经正确685/900，误接受190条。','同步RAM端口：LUT 31208→19456，FF 43692→19116。','DRM36等效290.5→292.5；模块验证仍为355683周期。']
  text(d,(31,462),captions[i//16],22,INK)
  text(d,(31,507),'开发评价集 · 模型版本与RAM端口实现分别比较。',16,MUT)
  frames.append(im)
 save_gif('模型与资源_证据动画.gif',frames)
def encode_model_frames():
 pattern=TMP/'model/%03d.png'
 if not (TMP/'model/000.png').is_file():return
 out=OUT/'三维模型_旋转分层.gif'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','8','-i',str(pattern),'-filter_complex','[0:v]split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=3','-loop','0',str(out)],check=True)
 print('MODEL_GIF_READY',out.stat().st_size,flush=True)
if __name__=='__main__':flow();metrics()
