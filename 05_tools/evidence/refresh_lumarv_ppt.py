#!/usr/bin/env python3
"""Refresh the existing slide deck without discarding native 3D or chart workbooks."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from PIL import Image
import posixpath,urllib.parse,copy,json,os
ROOT=Path(os.environ.get('LUMARV_MATERIALS','D:/Desktop/FPGA/参赛材料'))
SRC=Path(os.environ.get('LUMARV_SOURCE',str(ROOT/'LumaRV_答辩演示.pptx')));DST=ROOT/'LumaRV_答辩演示.pptx'
P='http://schemas.openxmlformats.org/presentationml/2006/main';A='http://schemas.openxmlformats.org/drawingml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';REL='http://schemas.openxmlformats.org/package/2006/relationships';CT='http://schemas.openxmlformats.org/package/2006/content-types';N={'p':P,'a':A,'r':R}
def parse(b):return E.fromstring(b,E.XMLParser(resolve_entities=False,no_network=True))
def xml(t):return E.tostring(t,xml_declaration=True,encoding='UTF-8',standalone=True)
def add(e,ns,t,**attrs):return E.SubElement(e,'{'+ns+'}'+t,{k:str(v)for k,v in attrs.items()})
def co(v):return round(v*9525)
def tree(n):return parse(parts[f'ppt/slides/slide{n}.xml'])
def shape(t,i):return next(s for s in t.findall('./p:cSld/p:spTree/p:sp',N) if s.find('p:nvSpPr/p:cNvPr',N).get('id')==str(i))
def settext(s,text,size=None):
 tx=s.find('p:txBody',N)
 if tx is None:return
 old=tx.find('a:p/a:r/a:rPr',N);props=copy.deepcopy(old)if old is not None else E.Element('{'+A+'}rPr')
 if size:props.set('sz',str(round(size*100)))
 for p in tx.findall('a:p',N):tx.remove(p)
 for line in text.split('\n'):
  p=add(tx,A,'p');run=add(p,A,'r');run.append(copy.deepcopy(props));add(run,A,'t').text=line
 defbp=tx.find('a:bodyPr',N)
 if defbp is not None:defbp.set('wrap','square')
def text(n,i,s,size=None):settext(shape(slides[n],i),s,size)
def store(n):parts[f'ppt/slides/slide{n}.xml']=xml(slides[n])
def newtext(parent,ident,txt,x,y,w,h,size=20,color='28384A',bold=False,fill=None):
 s=add(parent,P,'sp');nv=add(s,P,'nvSpPr');add(nv,P,'cNvPr',id=ident,name='LumaRV_'+str(ident));add(nv,P,'cNvSpPr',txBox=1);add(nv,P,'nvPr');pr=add(s,P,'spPr');xf=add(pr,A,'xfrm');add(xf,A,'off',x=co(x),y=co(y));add(xf,A,'ext',cx=co(w),cy=co(h));add(add(pr,A,'prstGeom',prst='rect'),A,'avLst')
 if fill:add(add(pr,A,'solidFill'),A,'srgbClr',val=fill)
 else:add(pr,A,'noFill')
 add(add(pr,A,'ln',w=0),A,'noFill');tx=add(s,P,'txBody');add(tx,A,'bodyPr',lIns=co(10),rIns=co(10),tIns=co(8),bIns=co(5),anchor='ctr');add(tx,A,'lstStyle')
 for line in txt.split('\n'):
  pa=add(tx,A,'p');rp=add(add(pa,A,'r'),A,'rPr',sz=round(size*100),b=int(bold),lang='zh-CN');add(add(rp,A,'solidFill'),A,'srgbClr',val=color)
  for typ in ['latin','ea','cs']:add(rp,A,typ,typeface='Microsoft YaHei')
  add(pa.find('a:r',N),A,'t').text=line
 return s

def clearbody(n):
 sp=slides[n].find('p:cSld/p:spTree',N)
 for s in list(sp):
  if s.tag in ['{'+P+'}nvGrpSpPr','{'+P+'}grpSpPr']:continue
  cn=s.find('p:nvSpPr/p:cNvPr',N)
  if cn is None or int(cn.get('id'))not in [2,3,4,5,6]:sp.remove(s)
 return sp

def image(n,name,x,y,w,h):
 data=(ROOT/'图表'/name).read_bytes();part='ppt/media/lumarv_'+name
 parts[part]=data;rf=f'ppt/slides/_rels/slide{n}.xml.rels';rr=parse(parts[rf]);rid='rIdLumaFigure'
 for old in list(rr):
  if old.get('Id')==rid:rr.remove(old)
 add(rr,REL,'Relationship',Id=rid,Type=R+'/image',Target='../media/'+Path(part).name);parts[rf]=xml(rr)
 sp=slides[n].find('p:cSld/p:spTree',N);pic=add(sp,P,'pic');nv=add(pic,P,'nvPicPr');add(nv,P,'cNvPr',id=300,name=name);add(add(nv,P,'cNvPicPr'),A,'picLocks',noChangeAspect=1);add(nv,P,'nvPr');bf=add(pic,P,'blipFill');add(bf,A,'blip').set('{'+R+'}embed',rid);add(add(bf,A,'stretch'),A,'fillRect');pr=add(pic,P,'spPr');xf=add(pr,A,'xfrm');add(xf,A,'off',x=co(x),y=co(y));add(xf,A,'ext',cx=co(w),cy=co(h));add(add(pr,A,'prstGeom',prst='rect'),A,'avLst')

with ZipFile(SRC)as z:parts={p:z.read(p)for p in z.namelist()}
slides={n:tree(n)for n in range(1,18)}
for n,t in slides.items():
 for tx in t.findall('.//a:t',N):
  if tx.text and 'NeedleRV-X' in tx.text:tx.text=tx.text.replace('NeedleRV-X  ·  2026.10.31','澄灯 LumaRV').replace('NeedleRV-X','澄灯 LumaRV')
text(1,2,'澄灯 LumaRV');text(1,6,'工业检修照明的语境感知控制',28)
text(1,7,'位置语义头、受约束残差与异构低比特推理',23)
text(1,8,'理解操作与限制，核对参数后执行并读回',21)
for i,s in {10:'25,014',11:'语境与工具训练文本',12:'197,816 B',13:'学习权重',14:'13.40×',15:'完整PWM模型加速'}.items():text(1,i,s)
clearbody(2);text(2,2,'检修照明与状态指示');text(2,3,'调光、位保持与控制器检查，围绕同一操作场景组织交互。',16)
image(2,'应用_检修照明.png',60,155,1156,577)
# Move the picture above the footer, retaining its aspect ratio.
pic=slides[2].find('.//p:pic/p:spPr/a:xfrm',N);pic.find('a:off',N).set('y',str(co(151)));pic.find('a:ext',N).set('cy',str(co(510)))
# Use original figure ratio within the allocated region.
im=Image.open(ROOT/'图表/应用_检修照明.png');ww=1020;hh=ww*im.height/im.width;pic.find('a:off',N).set('x',str(co(130)));pic.find('a:off',N).set('y',str(co(151)));pic.find('a:ext',N).set('cx',str(co(ww)));pic.find('a:ext',N).set('cy',str(co(hh)))
sp=clearbody(3);text(3,2,'参考思路与本项目设计');text(3,3,'借鉴低比特工具调用方法，围绕中文控制重新设计语料、分支和执行链路。',16)
rows=[('模块','参考思路','本项目实现'),('字节编码器','Needle低比特工具调用、短语记忆','双层d64整数编码器与学习型2/3-gram'),('语境判断','全局词特征','首尾位置特征；2048 → 64 → 16语义头'),('工具修正','残差学习','CPU标量70 → 5受约束工具残差'),('计算与数据复用','低比特乘累加','4MAC编码器、8MAC语义侧核、128KiB缓存'),('控制任务','意图与参数分离','25014条任务语料、位保持、能力检查与读回')]
widths=[180,370,590];x0=60;y0=175;rh=70;idx=400
for row,vals in enumerate(rows):
 x=x0
 for col,val in enumerate(vals):
  newtext(sp,idx,val,x,y0+row*rh,widths[col]-3,rh-3,18 if row else 20,'FFFFFF'if row==0 else'28384A',row==0,'143295'if row==0 else('F0F4F8'if row%2 else'FFFFFF'));idx+=1;x+=widths[col]
newtext(sp,idx,'完整中文PWM模型：999.170ms → 74.567ms，13.40×',65,610,1120,40,20,'143295',True)
text(4,3,'197816B学习权重；位置特征辅助区分操作请求与解释、否定及能力边界。',16)
text(4,30,'CPU工具残差',15);text(4,31,'70 → 5 标量计算\n合法候选约束',12.8);text(4,34,'W1权重缓存服务8MAC位置语义头；工具残差由CPU执行。',16)
text(5,3,'两组已参与开发的文本集合；分别评价原始神经分类与带许可的系统结果。',16)
text(5,13,'组合版本对照：1138条 +29；900条 +32。首次861/1138单独保留。',16)
text(6,3,'行表示真实类别，列表示预测类别；单元格保留原始样本数。',16)
text(6,179,'1138条：误接受50，误拒绝0，合法工具错分1',14)
text(6,180,'900条：误接受190，误拒绝24，合法工具错分1',14)
text(7,3,'128KiB权重常驻8MAC语义侧核，非零位图减少空特征计算。',16)
text(7,22,'该次语义侧核记录：1个任务，DMA读写0字节，硬件失败0',16)
text(8,2,'同步RAM端口减少逻辑资源');text(8,3,'同一模型、同一PRR阶段对照；改用同步读端口，计算周期保持不变。',16)
text(9,3,'四句各协议10次；全样本散点与中位数，包含USB及主机调度。',16)
text(10,11,'15次实际运行，CRC均5/5通过',18)
text(10,14,'PWM完整模型74.567ms，其中语义区间0.837ms；控制往返为另一条路径。',16)
text(11,3,'四批用户指令逐条实板运行；LED/PWM写入后读取寄存器。',16)
text(11,12,'四批24/25、25/25、25/25、25/25；范围内98/99，另1条超长拒绝。',15)
tbl=slides[11].find('.//a:tbl',N);trs=tbl.findall('a:tr',N)
for row,col,val in [(1,0,'四批用户指令'),(1,1,'24/25，25/25，25/25，25/25'),(3,0,'15次CoreMark运行'),(3,1,'CRC均5/5通过')]:
 cell=trs[row].findall('a:tc',N)[col];ts=cell.findall('.//a:t',N);ts[0].text=val
 for t in ts[1:]:t.text=''
text(12,3,'按计算、存储和控制模块展开逻辑结构。',16)
text(13,2,'请求处理路径');text(13,3,'机器语法、中文语境与完整编码器按需调用，共用许可和回读。',16)
text(13,18,'20秒流程快览',23);text(13,19,'3倍速讲解\n字幕随流程显示',18)
text(14,3,'俯视计算与存储模块，点击按钮切换视角。',16)
text(15,3,'侧视模块与缓存层级，网页支持自由旋转和分层。',16)
text(16,19,'九个模块标注\n分层、合拢、PWM流程\n20秒讲解',18)
text(17,2,'模型与资源的版本对照');text(17,3,'模型分类与RAM端口优化分别比较，保持相同评价口径。',16)
text(17,18,'分类与资源对照',22);text(17,19,'模型组合版本比较\n同模型RAM端口比较\n两组已观察开发集合',18)
for n in range(1,18):store(n)
# Replace embedded GIFs and GLB parts in place to preserve all relationships.
for n,name in [(13,'双路径流程_讲解动画.gif'),(16,'三维模型_旋转分层.gif'),(17,'模型与资源_证据动画.gif')]:parts[f'ppt/media/needlervx_explanation_{n}.gif']=(ROOT/'展示素材'/name).read_bytes()
for name in list(parts):
 if name.endswith('.glb'):parts[name]=(ROOT/'展示素材/LumaRV_逻辑结构.glb').read_bytes()
for num,view in [(1,'overview'),(2,'top'),(3,'side')]:
 q=Path('C:/Users/luo/AppData/Local/Temp/needlervx_ppt')/(view+'.png')
 part=f'ppt/media/needlervx_board3d_{num}.png'
 if q.exists()and part in parts:parts[part]=q.read_bytes()
for name in list(parts):
 if name.endswith('.rels'):
  rr=parse(parts[name]);changed=False
  for r in rr:
   target=urllib.parse.unquote(r.get('Target',''))
   if '三维流程演示_2倍速.mp4'in target:r.set('Target',urllib.parse.quote(target.replace('_2倍速','_3倍速'),safe='/'));changed=True
  if changed:parts[name]=xml(rr)
# Speaker notes describe the displayed material, with no stale timing/branding.
for name in list(parts):
 if name.startswith('ppt/notesSlides/notesSlide')and name.endswith('.xml'):
  rr=parse(parts[name])
  for t in rr.findall('.//a:t',N):
   if t.text:t.text=t.text.replace('NeedleRV-X','澄灯 LumaRV').replace('30秒2倍速','20秒3倍速').replace('30秒','20秒').replace('2倍速','3倍速').replace('离线语义控制','语境感知控制')
  parts[name]=xml(rr)
ct=parse(parts['[Content_Types].xml'])
assert any(x.get('Extension')=='png'for x in ct)
with ZipFile(DST,'w',ZIP_DEFLATED)as z:
 for p,b in parts.items():z.writestr(p,b)
print(json.dumps({'output':str(DST),'slides':17,'native_models':sum(p.endswith('.glb')for p in parts),'charts':sum('/charts/'in p and p.endswith('.xml')and'/_rels/'not in p for p in parts),'workbooks':sum(p.endswith('.xlsx')for p in parts),'bytes':DST.stat().st_size},ensure_ascii=False))
