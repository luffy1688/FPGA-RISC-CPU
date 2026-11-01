#!/usr/bin/env python3
"""Small OOXML material-only edit. Preserve native GLB and existing chart workbooks.
Run after the 15-page frozen deck and the three explanatory GIFs have been made.
No PowerPoint COM, UI automation, hashes, firmware modification or serial access.
"""
from pathlib import Path
from lxml import etree as E
from PIL import Image
import copy,io,json,posixpath,re,tempfile,zipfile
P='http://schemas.openxmlformats.org/presentationml/2006/main';A='http://schemas.openxmlformats.org/drawingml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';REL='http://schemas.openxmlformats.org/package/2006/relationships';CT='http://schemas.openxmlformats.org/package/2006/content-types';N={'p':P,'a':A,'r':R}
ROOT=Path('D:/Desktop/FPGA/参赛材料');FILE=ROOT/'NeedleRV-X_答辩演示.pptx';TMP=Path(tempfile.gettempdir())/'needlervx_ppt_gifs';TMP.mkdir(exist_ok=True)
BLUE='143295';GOLD='C89B61';INK='28384A';MUT='65758A';WHITE='FFFFFF'
def parse(b):return E.fromstring(b,E.XMLParser(resolve_entities=False,no_network=True))
def xml(t):return E.tostring(t,xml_declaration=True,encoding='UTF-8',standalone=True)
def add(p,ns,t,**a):return E.SubElement(p,'{'+ns+'}'+t,{k:str(v)for k,v in a.items()})
def coord(v):return str(round(v*9525))
def geometry(sp,x,y,w,h):
 f=add(sp,A,'xfrm');add(f,A,'off',x=coord(x),y=coord(y));add(f,A,'ext',cx=coord(w),cy=coord(h));add(add(sp,A,'prstGeom',prst='rect'),A,'avLst')
def textshape(parent,id,name,text,x,y,w,h,size=22,color=INK,bold=False,fill=None,link=None,action=None):
 sp=add(parent,P,'sp');nv=add(sp,P,'nvSpPr');cnv=add(nv,P,'cNvPr',id=id,name=name)
 if link:
  hl=add(cnv,A,'hlinkClick');hl.set('{'+R+'}id',link)
  if action:hl.set('action',action)
 add(nv,P,'cNvSpPr',txBox=1);add(nv,P,'nvPr');pr=add(sp,P,'spPr');geometry(pr,x,y,w,h)
 if fill:add(add(pr,A,'solidFill'),A,'srgbClr',val=fill)
 else:add(pr,A,'noFill')
 add(add(pr,A,'ln',w='0'),A,'noFill')
 tx=add(sp,P,'txBody');add(tx,A,'bodyPr',lIns=0,rIns=0,tIns=0,bIns=0,anchor='ctr');add(tx,A,'lstStyle')
 for line in text.split('\n'):
  pa=add(tx,A,'p');add(pa,A,'pPr',algn='ctr'if fill else'l')
  run=add(pa,A,'r');rp=add(run,A,'rPr',lang='zh-CN',sz=round(size*75),b=1 if bold else 0);add(add(rp,A,'solidFill'),A,'srgbClr',val=color)
  for typ in ['latin','ea','cs']:add(rp,A,typ,typeface='Microsoft YaHei')
  add(run,A,'t').text=line
 return sp

def picture(parent,id,relid,name,x,y,w,h):
 pic=add(parent,P,'pic');nv=add(pic,P,'nvPicPr');add(nv,P,'cNvPr',id=id,name=name,descr='Embedded explanatory GIF; not measured execution timing.');add(add(nv,P,'cNvPicPr'),A,'picLocks',noChangeAspect=1);add(nv,P,'nvPr')
 fill=add(pic,P,'blipFill');add(fill,A,'blip').set('{'+R+'}embed',relid);add(add(fill,A,'stretch'),A,'fillRect');geometry(add(pic,P,'spPr'),x,y,w,h)

def position(sp):
 x=sp.find('p:spPr/a:xfrm/a:off',N);return (int(x.get('x'))/9525,int(x.get('y'))/9525)if x is not None else(None,None)
def set_text(sp,text):
 ts=sp.findall('.//a:t',N)
 if ts:ts[0].text=text
 for t in ts[1:]:t.text=''
def rid(rels):return 'rId'+str(max([int(x.get('Id')[3:])for x in rels if re.fullmatch(r'rId\d+',x.get('Id',''))]+[0])+1)

def main():
 with zipfile.ZipFile(FILE)as z:parts={p:z.read(p)for p in z.namelist()}
 slides=[p for p in parts if re.fullmatch(r'ppt/slides/slide\d+\.xml',p)];assert len(slides)==15,'Material patch expects the 15-page frozen deck, refuses to append duplicate pages'
 preserved={p:parts[p]for p in parts if p.endswith(('.glb','.xlsx'))or '/charts/'in p}
 ct=parse(parts['[Content_Types].xml']);pres=parse(parts['ppt/presentation.xml']);pr=parse(parts['ppt/_rels/presentation.xml.rels']);ids=pres.find('p:sldIdLst',N);assert len(ids)==15
 clone=parse(parts['ppt/slides/slide13.xml']);clone_rels=parse(parts['ppt/slides/_rels/slide13.xml.rels'])
 names=[('双路径流程_讲解动画.gif',13,'双路径流程动画','结构讲解：显式快路径与模型路径共用执行许可、回读和审计。'),('三维模型_旋转分层.gif',16,'模块分层与指令闭环','先分层认模块，再合拢演示PWM20%指令至实际回读。'),('模型与资源_证据动画.gif',17,'模型与资源的证据动画','神经分类与同模型资源优化的端点对照。')]
 if not any(x.get('Extension')=='gif'for x in ct):add(ct,CT,'Default',Extension='gif',ContentType='image/gif')
 reports=[]
 for name,num,title,sub in names:
  tree=copy.deepcopy(clone);rels=copy.deepcopy(clone_rels);sp=tree.find('p:cSld/p:spTree',N)
  for q in list(sp):
   x,y=position(q)
   if y is not None:
    if 155<=y<659:sp.remove(q)
    elif y==37:set_text(q,title)
    elif y==103:set_text(q,sub)
  if num==13:
   nr=next(x for x in rels if x.get('Type')==R+'/notesSlide');npart=nr.get('Target').lstrip('/');nt=parse(parts[npart])
   for q in nt.findall('.//p:sp',N):
    ph=q.find('p:nvSpPr/p:nvPr/p:ph',N)
    if ph is not None and ph.get('type')=='body':set_text(q,'本页嵌入8秒双路径结构讲解GIF，非实测运行时序。右侧链接仍是30秒2倍速真实记录回放MP4与离线交互HTML，均非新实板录屏。')
   parts[npart]=xml(nt)
  if num!=13:
   # Copy notes to a new notes part and correct its back-reference.
   nr=next(x for x in rels if x.get('Type')==R+'/notesSlide');old_notes=nr.get('Target').lstrip('/')if nr.get('Target').startswith('/')else posixpath.normpath('ppt/slides/'+nr.get('Target'));notes=parse(parts[old_notes]);new_notes=f'ppt/notesSlides/notesSlide{num}.xml'
   for q in notes.findall('.//p:sp',N):
    ph=q.find('p:nvSpPr/p:nvPr/p:ph',N)
    if ph is not None and ph.get('type')=='body':set_text(q,sub+' 讲解动画，非实时硬件执行。原始指标来源07_runs/board/current与resource_trials/selection.json；PowerPoint放映通常播放GIF，其他阅读器可能只显示首帧。')
   old_nr=posixpath.dirname(old_notes)+'/_rels/'+posixpath.basename(old_notes)+'.rels';nrels=parse(parts[old_nr])
   for r in nrels:
    if r.get('Type')==R+'/slide':r.set('Target','../slides/slide'+str(num)+'.xml')
   parts[new_notes]=xml(notes);parts[posixpath.dirname(new_notes)+'/_rels/'+posixpath.basename(new_notes)+'.rels']=xml(nrels);nr.set('Target','../notesSlides/notesSlide'+str(num)+'.xml')
   add(ct,CT,'Override',PartName='/'+new_notes,ContentType='application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml')
   sr=rid(pr);add(pr,REL,'Relationship',Id=sr,Type=R+'/slide',Target='slides/slide'+str(num)+'.xml');new=add(ids,P,'sldId',id=max(int(x.get('id'))for x in ids)+1);new.set('{'+R+'}id',sr)
   add(ct,CT,'Override',PartName=f'/ppt/slides/slide{num}.xml',ContentType='application/vnd.openxmlformats-officedocument.presentationml.slide+xml')
  media=f'ppt/media/needlervx_explanation_{num}.gif';raw=(ROOT/'展示素材'/name).read_bytes();parts[media]=raw;ir=rid(rels);add(rels,REL,'Relationship',Id=ir,Type=R+'/image',Target='../media/'+Path(media).name)
  nextid=max(int(x.get('id'))for x in tree.findall('.//p:cNvPr',N))+1
  picture(sp,nextid,ir,'GIF_'+name,59,158,853,480);nextid+=1
  if num==13:
   lines=[('30秒真实记录快览',953,190,265,70,25,BLUE,True),('2倍速成片\n讲解字幕已嵌入',953,274,265,80,21,INK,False)]
   buttons=[('播放MP4','展示素材/三维流程演示_2倍速.mp4',False,953,403),('打开自由交互网页','展示素材/成果展示.html',False,953,481)]
  elif num==16:
   lines=[('结构与指令闭环',953,190,265,60,25,BLUE,True),('九个模块标注\n分层 → 合拢 → 指令闭环\n约30秒，非实测时序',953,276,265,135,21,INK,False)]
   buttons=[('原生3D与预设视角','slide12.xml',True,953,478)]
  else:
   lines=[('真实数据端点',953,190,265,60,27,BLUE,True),('神经效果与系统分开\n同模型资源阶段对照\n观察集不称盲测',953,276,265,135,21,INK,False)]
   buttons=[('模型对照图','slide5.xml',True,953,451),('资源对照图','slide8.xml',True,953,529)]
  for t,x,y,w,h,size,col,bold in lines:textshape(sp,nextid,'explanation_caption',t,x,y,w,h,size,col,bold);nextid+=1
  for text,target,internal,x,y in buttons:
   rr=rid(rels);rel=add(rels,REL,'Relationship',Id=rr,Type=R+('/slide'if internal else'/hyperlink'),Target=target)
   if not internal:rel.set('TargetMode','External')
   textshape(sp,nextid,'explanation_button',text,x,y,265,54,21,WHITE,True,BLUE,rr,'ppaction://hlinksldjump'if internal else None);nextid+=1
  parts[f'ppt/slides/slide{num}.xml']=xml(tree);parts[f'ppt/slides/_rels/slide{num}.xml.rels']=xml(rels)
  im=Image.open(io.BytesIO(raw));duration=0
  for i in range(im.n_frames):im.seek(i);duration+=im.info.get('duration',0)
  reports.append(dict(slide=num,name=name,frames=im.n_frames,duration_ms=duration,bytes=len(raw)))
 # Page count and footer labels are updated without changing any chart/model nodes.
 for num in range(1,18):
  p=f'ppt/slides/slide{num}.xml';t=parse(parts[p])
  for q in t.findall('./p:cSld/p:spTree/p:sp',N):
   x,y=position(q)
   if x is not None and x>=1160 and y==675:
    set_text(q,f'{num:02d} / 17');f=q.find('p:spPr/a:xfrm',N);f.find('a:off',N).set('x',coord(1100));f.find('a:ext',N).set('cx',coord(118))
  parts[p]=xml(t)
 parts['[Content_Types].xml']=xml(ct);parts['ppt/presentation.xml']=xml(pres);parts['ppt/_rels/presentation.xml.rels']=xml(pr)
 if 'docProps/app.xml'in parts:
  app=parse(parts['docProps/app.xml'])
  for e in app.iter():
   if E.QName(e).localname=='Slides':e.text='17'
  parts['docProps/app.xml']=xml(app)
 # Necessary acceptance: animated assets present, original GLB/workbook/chart parts preserved,
 # every new internal page and every external material target exists.
 for p,b in preserved.items():assert parts[p]==b,'Original native model/chart changed: '+p
 for p,b in parts.items():
  if not p.endswith('.rels'):continue
  for r in parse(b):
   target=r.get('Target')
   if r.get('TargetMode')=='External':
    if target.startswith('展示素材/'):assert (ROOT/target).is_file(),target
   else:
    base=posixpath.dirname(posixpath.dirname(p));resolved=target.lstrip('/')if target.startswith('/')else posixpath.normpath(base+'/'+target);assert resolved in parts,(p,resolved)
 assert sum(p.endswith('.glb')for p in parts)==3
 stage=TMP/'animated_final.pptx'
 with zipfile.ZipFile(stage,'w',compression=zipfile.ZIP_DEFLATED)as z:
  for p,b in parts.items():z.writestr(p,b)
 FILE.write_bytes(stage.read_bytes())
 receipt=dict(slides=17,embedded_gifs=reports,native_model_pages=[12,14,15],original_native_model_chart_workbook_bytes_preserved=True,hash_checks=False,slideshow_playback_not_ui_tested=True)
 (TMP/'ppt_gif_result.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(receipt,ensure_ascii=True,indent=2))

def refresh_model_animation():
 # Refresh the existing 17-page Artifact Tool deck without reimporting its native
 # GLB/chart extensions. This is a material-only replacement at unchanged geometry.
 with zipfile.ZipFile(FILE)as z:parts={p:z.read(p)for p in z.namelist()}
 assert len([p for p in parts if re.fullmatch(r'ppt/slides/slide\d+\.xml',p)])==17
 tree=parse(parts['ppt/slides/slide16.xml']);rels=parse(parts['ppt/slides/_rels/slide16.xml.rels'])
 media='ppt/media/needlervx_explanation_16.gif';assert media in parts
 raw=(ROOT/'展示素材/三维模型_旋转分层.gif').read_bytes();im=Image.open(io.BytesIO(raw));ms=0
 for frame in range(im.n_frames):im.seek(frame);ms+=im.info.get('duration',0)
 assert im.size==(1280,720)and 29_800<=ms<=30_200
 replacements={
  '三维模型旋转与分层':'模块分层与指令闭环',
  '观察模块层级与片内存储关系；模型为结构示意。':'先分层认模块，再合拢演示PWM20%指令至实际回读。',
  '模块旋转与分层':'结构与指令闭环',
  '旋转 + 分层':'九个模块标注',
  '约12秒循环':'分层 → 合拢 → 指令闭环',
  '结构讲解，非实测时序':'约30秒，非实测时序'
 }
 for t in tree.findall('.//a:t',N):
  if t.text in replacements:t.text=replacements[t.text]
 parts['ppt/slides/slide16.xml']=xml(tree);parts[media]=raw
 note_rel=next(x for x in rels if x.get('Type')==R+'/notesSlide');target=note_rel.get('Target');note=target.lstrip('/')if target.startswith('/')else posixpath.normpath('ppt/slides/'+target)
 nt=parse(parts[note])
 for q in nt.findall('.//p:sp',N):
  ph=q.find('p:nvSpPr/p:nvPr/p:ph',N)
  if ph is not None and ph.get('type')=='body':set_text(q,'30秒逻辑结构讲解：九模块分层标注、合拢、中文PWM20%完整模型请求至实际回读。采用已保存实板记录07_runs/board/current/demo_hardware_report.json的case103，model_used=1，完整模型3019961周期/40.5MHz=74.567ms，PWM回读period40500/high8100/enabled1/match1。非现场新录制，动画时长不代表硬件时延。')
 parts[note]=xml(nt)
 stage=TMP/'animated_final.pptx'
 with zipfile.ZipFile(stage,'w',compression=zipfile.ZIP_DEFLATED)as z:
  for name,data in parts.items():z.writestr(name,data)
 FILE.write_bytes(stage.read_bytes())
 print(json.dumps(dict(slide=16,frames=im.n_frames,duration_ms=ms,dimensions=im.size,bytes=len(raw),native_models_and_charts_unchanged=True),ensure_ascii=True))

if __name__=='__main__':
 import sys
 refresh_model_animation() if '--refresh-model' in sys.argv else main()
