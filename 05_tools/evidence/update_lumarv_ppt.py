#!/usr/bin/env python3
"""Material-only OOXML edit preserving native PowerPoint 3D, charts and workbooks."""
from pathlib import Path
from lxml import etree as E
import argparse, copy, io, posixpath, re, urllib.parse, zipfile

P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
N={'p':P,'a':A,'r':R}
BLUE='143295'; GOLD='C89B61'; INK='28384A'; MUT='65758A'
def parse(b): return E.fromstring(b,E.XMLParser(resolve_entities=False,no_network=True))
def xml(t): return E.tostring(t,xml_declaration=True,encoding='UTF-8',standalone=True)
def add(p,ns,t,**a): return E.SubElement(p,'{'+ns+'}'+t,{k:str(v) for k,v in a.items()})
def c(v): return str(round(v*9525))
def xfrm(p,x,y,w,h):
 t=add(p,A,'xfrm');add(t,A,'off',x=c(x),y=c(y));add(t,A,'ext',cx=c(w),cy=c(h));return t
def textshape(parent,idx,text,x,y,w,h,size=22,color=INK,bold=False):
 sp=add(parent,P,'sp'); nv=add(sp,P,'nvSpPr');add(nv,P,'cNvPr',id=idx,name='lumarv_text_'+str(idx));add(nv,P,'cNvSpPr',txBox=1);add(nv,P,'nvPr')
 pr=add(sp,P,'spPr');xfrm(pr,x,y,w,h);add(add(pr,A,'prstGeom',prst='rect'),A,'avLst');add(pr,A,'noFill');add(add(pr,A,'ln'),A,'noFill')
 tx=add(sp,P,'txBody');add(tx,A,'bodyPr',lIns=0,rIns=0,tIns=0,bIns=0,anchor='ctr');add(tx,A,'lstStyle')
 for line in text.split('\n'):
  pa=add(tx,A,'p');add(pa,A,'pPr',algn='l');r=add(pa,A,'r');rp=add(r,A,'rPr',sz=round(size*75),b=int(bold),lang='zh-CN');add(add(rp,A,'solidFill'),A,'srgbClr',val=color)
  for k in ['latin','ea','cs']:add(rp,A,k,typeface='Microsoft YaHei')
  add(r,A,'t').text=line
 return sp
def settext(sp,text,size=None):
 ts=sp.findall('.//a:t',N)
 if not ts:return
 ts[0].text=text
 for t in ts[1:]:t.text=''
 if size:
  for rp in sp.findall('.//a:rPr',N)+sp.findall('.//a:defRPr',N):rp.set('sz',str(round(size*75)))
def pos(sp):
 off=sp.find('p:spPr/a:xfrm/a:off',N)
 return tuple(int(off.get(k))/9525 for k in ['x','y']) if off is not None else (None,None)
def replace_at(root,x,y,text,size=None):
 for q in root.findall('./p:cSld/p:spTree/p:sp',N):
  qx,qy=pos(q)
  if qx is not None and abs(qx-x)<.2 and abs(qy-y)<.2:settext(q,text,size);return
 raise ValueError(('missing shape',x,y,text))
def rid(rels):return 'rId'+str(max([int(r.get('Id')[3:])for r in rels if re.fullmatch(r'rId\d+',r.get('Id',''))]+[0])+1)
def pic(sp,idx,r,x,y,w,h,name):
 q=add(sp,P,'pic');nv=add(q,P,'nvPicPr');add(nv,P,'cNvPr',id=idx,name=name);add(add(nv,P,'cNvPicPr'),A,'picLocks',noChangeAspect=1);add(nv,P,'nvPr')
 f=add(q,P,'blipFill');add(f,A,'blip').set('{'+R+'}embed',r);add(add(f,A,'stretch'),A,'fillRect');pr=add(q,P,'spPr');xfrm(pr,x,y,w,h);add(add(pr,A,'prstGeom',prst='rect'),A,'avLst')
def bodyclear(root):
 sp=root.find('p:cSld/p:spTree',N)
 for q in list(sp):
  if E.QName(q).localname in ['nvGrpSpPr','grpSpPr']:continue
  x,y=pos(q)
  if y is not None and 150<=y<660:sp.remove(q)
 return sp
def table(parent,idx,rows,widths,x,y,rowheights,size=22):
 gf=add(parent,P,'graphicFrame');nv=add(gf,P,'nvGraphicFramePr');add(nv,P,'cNvPr',id=idx,name='reference_self_table');add(nv,P,'cNvGraphicFramePr');add(nv,P,'nvPr')
 t=add(gf,P,'xfrm');add(t,A,'off',x=c(x),y=c(y));add(t,A,'ext',cx=c(sum(widths)),cy=c(sum(rowheights)))
 data=add(add(gf,A,'graphic'),A,'graphicData',uri=A+'/table');tbl=add(data,A,'tbl');add(tbl,A,'tblPr',firstRow=1);grid=add(tbl,A,'tblGrid')
 for w in widths:add(grid,A,'gridCol',w=c(w))
 for rn,(row,rh) in enumerate(zip(rows,rowheights)):
  tr=add(tbl,A,'tr',h=c(rh))
  for text in row:
   tc=add(tr,A,'tc');tx=add(tc,A,'txBody');add(tx,A,'bodyPr');add(tx,A,'lstStyle')
   for line in text.split('\n'):
    p=add(tx,A,'p');add(p,A,'pPr',marL=0);r=add(p,A,'r');rp=add(r,A,'rPr',lang='zh-CN',sz=round(size*75),b=int(rn==0));add(add(rp,A,'solidFill'),A,'srgbClr',val='FFFFFF'if rn==0 else INK)
    for k in ['latin','ea','cs']:add(rp,A,k,typeface='Microsoft YaHei')
    add(r,A,'t').text=line
   pr=add(tc,A,'tcPr',marL=c(15),marR=c(12),marT=c(9),marB=c(7),anchor='ctr');add(add(pr,A,'solidFill'),A,'srgbClr',val=BLUE if rn==0 else ('F1F5FA'if rn%2 else'FFFFFF'))
   for edge in ['lnL','lnR','lnT','lnB']:add(add(add(pr,A,edge,w=6350),A,'solidFill'),A,'srgbClr',val='D8E0EC')
 return gf
def note(parts,num,text):
 rels=parse(parts[f'ppt/slides/_rels/slide{num}.xml.rels']);nr=next((r for r in rels if r.get('Type')==R+'/notesSlide'),None)
 if nr is None:return
 target=nr.get('Target');path=target.lstrip('/')if target.startswith('/')else posixpath.normpath('ppt/slides/'+target)
 t=parse(parts[path])
 for sp in t.findall('.//p:sp',N):
  ph=sp.find('p:nvSpPr/p:nvPr/p:ph',N)
  if ph is not None and ph.get('type')=='body':settext(sp,text)
 parts[path]=xml(t)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--media',action='store_true');args=ap.parse_args();root=Path(args.root)
 src=root/'NeedleRV-X_答辩演示.pptx';out=root/'LumaRV_答辩演示.pptx'
 with zipfile.ZipFile(src)as z:parts={n:z.read(n)for n in z.namelist()}
 assert len([n for n in parts if re.fullmatch('ppt/slides/slide[0-9]+.xml',n)])==17
 # Package changes touch text, material pictures and video links only.
 protected={n:b for n,b in parts.items()if n.endswith('.xlsx')or'/charts/'in n}
 native_count=sum(b.count(b'model3d:')for n,b in parts.items()if re.fullmatch('ppt/slides/slide[0-9]+.xml',n))
 for n in list(parts):
  if (n.startswith('ppt/slides/')or n.startswith('ppt/notesSlides/'))and n.endswith('.xml'):
   t=parse(parts[n])
   for q in t.findall('.//a:t',N):
    if q.text:q.text=q.text.replace('NeedleRV-X','澄灯 LumaRV').replace('2026.10.31','2026.11.01')
   for q in t.findall('.//p:cNvPr',N):
    for attr in ['name','descr','title']:
     if q.get(attr):q.set(attr,q.get(attr).replace('NeedleRV-X','LumaRV'))
   parts[n]=xml(t)
 def edit(num,repls):
  t=parse(parts[f'ppt/slides/slide{num}.xml'])
  for x,y,text,size in repls:replace_at(t,x,y,text,size)
  parts[f'ppt/slides/slide{num}.xml']=xml(t)
 edit(1,[(60,37,'澄灯 LumaRV',None),(60,168,'检修照明的中文控制与自检',49),(64,274,'自研位置语义头 + 受约束残差 + 低比特算子协同',31),(64,350,'中文请求 → 工具许可 → LED / PWM控制 → 寄存器回读',27),(64,480,'25,014',None),(64,553,'任务训练语料 / 条',None),(454,480,'197,816 B',None),(454,553,'学习权重总量',None),(844,480,'13.40×',None),(844,553,'同输入完整模型加速',None)])
 # Application figure contains its own hierarchy and explicit external-driver boundary.
 t=parse(parts['ppt/slides/slide2.xml']);sp=bodyclear(t);replace_at(t,60,37,'工业检修照明的控制与检查');replace_at(t,62,103,'检修人员用中文确认灯位与调光参数，同时检查控制器状态。',24)
 relpath='ppt/slides/_rels/slide2.xml.rels';rels=parse(parts[relpath]);rr=rid(rels);add(rels,REL,'Relationship',Id=rr,Type=R+'/image',Target='../media/lumarv_application.png')
 parts['ppt/media/lumarv_application.png']=(root/'图表/应用_检修照明.png').read_bytes();pic(sp,950,rr,95,150,1090,527,'工业检修照明应用结构')
 parts['ppt/slides/slide2.xml']=xml(t);parts[relpath]=xml(rels)
 # Native editable reference/self table replaces the duplicated flow illustration.
 t=parse(parts['ppt/slides/slide3.xml']);sp=bodyclear(t);replace_at(t,60,37,'自研AI的任务设计与实现');replace_at(t,62,103,'以有限工具控制为任务，补足语境判断、整数推理和执行接口。',24)
 rows=[['设计环节','参考基础','本项目实现'],['语义编码','Needle的嵌入式工具调用方法\nTransformer通用结构','任务语料25,014条，定义五种硬件工具与拒绝类'],['语境识别','词序与字符位置特征','全局 / 首部 / 尾部特征2048维\n位置语义头2048 → 64 → 16'],['候选修正','残差学习方法','CPU执行70 → 5身份残差\n只调整合法候选，保留语境拒绝'],['整数运行与硬件','整数乘加与片内缓存','4 MAC字节编码器 + 8 MAC语境侧核\nW1常驻缓存服务8 MAC侧核'],['控制链路','UART与GPIO外设接口','共用工具许可、参数边界与写后回读']]
 table(sp,950,rows,[205,332,600],62,164,[48,76,92,92,92,76],21)
 parts['ppt/slides/slide3.xml']=xml(t)
 edit(4,[(62,103,'197,816 B学习权重，分别识别工具身份与执行语境。',24),(1051,297,'CPU受约束融合',20),(1051,335,'70 → 5\n身份残差\n合法候选内修正',21),(368,575,'CPU执行身份残差；128 KiB W1缓存服务8 MAC语境侧核。',24)])
 edit(5,[(60,37,'组合方案版本对照',None),(62,103,'前一候选、当前神经模型与混合系统分别比较，保留两组观察集合。',24),(826,180,'神经分类正确数',None),(826,247,'1058 → 1087',40),(828,314,'观察集合A：1138条',24),(826,402,'653 → 685',40),(828,469,'较难集合B：900条',24),(62,598,'两组已用于开发选择，变化来自组合方案，不作单因素归因。',23)])
 edit(6,[(62,103,'行表示目标类别，列表示模型输出。颜色按每行归一，单元格保留样本数。',23),(82,606,'误接受50  /  误拒绝0  /  工具错分1',21),(690,606,'误接受190  /  误拒绝24  /  工具错分1',21)])
 edit(7,[(62,103,'8 MAC语境侧核的第一层权重常驻片内，输入按非零特征组计算。',24),(64,574,'缓存命中实测：1个任务，DMA读写0字节，硬件失败0。',24)])
 edit(8,[(62,103,'同模型、同PRR阶段比较，同步RAM替代异步数组读口。',24),(65,604,'模块计算355,683周期，优化前后输出逐项一致。',23)])
 edit(9,[(60,37,'控制路径串口往返：1.40–5.16 ms',None),(62,103,'每句每协议10次。散点保留全部样本，标注为中位数。',24),(800,589,'请求发送至接收READY',23)])
 edit(10,[(62,103,'同一固件、同一输入，完整模型比较软件与硬件计算。',24),(857,334,'1200次迭代，约14.585秒',24),(857,396,'15次运行，CRC均5/5通过',24),(857,496,'中文PWM 13.40×\nled 37  17.16×\n各类模型分数一致',23),(65,609,'中文PWM完整模型74.567 ms，其中语境侧核0.837 ms。',24)])
 t=parse(parts['ppt/slides/slide11.xml']);replace_at(t,62,103,'四批用户指令与保护用例均在实板运行，动作通过寄存器读回确认。',23);replace_at(t,65,601,'四批合计99/100，含1条超长输入拒绝；64字节范围内为98/99。',23)
 tbl=t.find('.//a:tbl',N);newrows=[['实板测试','执行结果'],['四批用户指令','24/25，25/25，25/25，25/25'],['CoreMark 1200次迭代','15次运行，CRC均5/5'],['40条语境拒绝 × 两模式','80/80，IO不变'],['6条伪造成绩 × 两模式','12/12，拒绝伪造成绩'],['局部否定 / 位保持','LED0改变，其他位保留'],['非法UTF-8 / 序号恢复','非法输入拒绝，合法请求恢复']]
 for row,values in zip(tbl.findall('a:tr',N),newrows):
  for cell,text in zip(row.findall('a:tc',N),values):settext(cell,text,20)
 parts['ppt/slides/slide11.xml']=xml(t)
 # Brand in document properties does not alter build paths in source references.
 if 'docProps/core.xml'in parts:
  q=parse(parts['docProps/core.xml'])
  for e in q.iter():
   if e.text:e.text=e.text.replace('NeedleRV-X','LumaRV')
  parts['docProps/core.xml']=xml(q)
 # Material hyperlinks point at the faster current cut, not the superseded 2x file.
 for n in list(parts):
  if not n.endswith('.rels'):continue
  q=parse(parts[n]);changed=False
  for r in q:
   target=r.get('Target','');un=urllib.parse.unquote(target)
   if '三维流程演示_2倍速.mp4'in un:
    r.set('Target',urllib.parse.quote('展示素材/三维流程演示_3倍速.mp4',safe='/'));changed=True
  if changed:parts[n]=xml(q)
 edit(13,[(953,190,'20秒流程快览',27),(953,274,'3倍速成片\n讲解字幕已嵌入',23)])
 edit(16,[(953,276,'九个模块逐一标注\n分层、合拢、完整指令\n20秒结构讲解',22)])
 edit(17,[(60,37,'模型效果与资源变化',None),(62,103,'组合方案的分类结果与同模型资源对照。',24),(953,190,'模型与资源对照',26),(953,276,'神经模型与系统分别计分\n同模型资源优化\n保留完整样本分母',22)])
 notes={1:'澄灯 LumaRV，面向工业检修照明的中文控制与控制器检查。训练语料25014条，学习权重197816B。13.39961倍为同输入中文PWM完整模型的软件/硬件周期比。',2:'现有板载LED和PWM输出代表灯光控制通道。外部灯具与功率驱动用虚线表示应用接入。温度为FPGA片内结温，不是灯具温度；PWM占空比不等于实测光照亮度。',3:'Needle的有限工具调用方法作为结构参考，通用Transformer和残差学习方法属于基础。任务语料、位置特征、受约束身份残差、整数运行时与4/8MAC接口由本项目实现。Needle官方：https://www.cactuscompute.com/needle 。',4:'语境头2048→64→16在8MAC侧核运行，W1缓存服务8MAC。原字节编码器使用4MAC。70→5身份残差在CPU运行，只调整合法候选。',5:'组合方案对照：前一64维候选1058/1138、653/900；本版1087/1138、685/900；混合系统1135/1138、884/900。集合已用于开发选择，不能视为独立测试或单因素消融。',6:'1138样本：1087正确，误接受50，误拒绝0，合法工具错分1。900样本：685正确，误接受190，误拒绝24，合法工具错分1。错分类别必须单列，不能并入误拒绝。',9:'原生串口往返在四条控制语句中按文本/二进制各测10次，中位数范围1.395–5.155ms。不是全部自然语言的完整模型推理时间。',10:'中文PWM完整模型40466391→3019968周期，软件999.170ms，硬件74.567ms，13.39961倍。语境子区间0.837ms。CoreMark15次1200迭代，CRC五项通过，14.58517242至14.58517336秒，2.031490/MHz。',11:'四批用户指令实板24/25、25/25、25/25、25/25。99/100包含一条81字节输入长度拒绝，64字节内98/99。第一批第19条成绩询问遭语境保守拒绝，IO不变。寄存器读回验证内部状态，不替代外部波形测量。',13:'8秒双路径结构讲解GIF，动画时长不代表硬件时延。20秒3倍速MP4依据既有实板记录制作，附字幕，非新现场录像。',16:'20秒逻辑结构讲解：九模块分层标注、合拢、中文PWM20%完整模型请求至实际回读。数据取自已保存实板结果case103，完整模型3019961周期/40.5MHz=74.567ms，PWM读回period40500/high8100/enabled1/match1。讲解动画时长不代表硬件时延。',17:'8秒模型效果与资源讲解。模型比较是组合方案版本变化，非单因素消融；资源对照保持同模型与相同PRR阶段。'}
 for num,text in notes.items():note(parts,num,text)
 if args.media:
  for num,name in [(13,'双路径流程_讲解动画.gif'),(16,'三维模型_旋转分层.gif'),(17,'模型与资源_证据动画.gif')]:parts[f'ppt/media/needlervx_explanation_{num}.gif']=(root/'展示素材'/name).read_bytes()
  glb=(root/'展示素材/LumaRV_逻辑结构.glb').read_bytes()
  for n in list(parts):
   if n.endswith('.glb'):parts[n]=glb
 ct=parse(parts['[Content_Types].xml'])
 if not any(e.get('Extension')=='png'for e in ct):add(ct,CT,'Default',Extension='png',ContentType='image/png')
 parts['[Content_Types].xml']=xml(ct)
 # Only the preservation checks relevant to this material edit.
 for n,b in protected.items():assert parts[n]==b,n
 assert sum(n.endswith('.glb')for n in parts)==3
 assert sum(b.count(b'model3d:')for n,b in parts.items()if re.fullmatch('ppt/slides/slide[0-9]+.xml',n))==native_count
 for n in parts:
  if n.endswith('.xml'):parse(parts[n])
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED)as z:
  for n,b in parts.items():z.writestr(n,b)
 print(str(out))
if __name__=='__main__':main()
