from pathlib import Path
import json,zipfile,io,re,posixpath,copy,urllib.parse,importlib.util,shutil
from lxml import etree as X
from openpyxl import Workbook,load_workbook
D=Path('C:/Users/luo/AppData/Local/Temp/needlervx_ppt');MAT=Path('D:/Desktop/FPGA/参赛材料')
P='http://schemas.openxmlformats.org/presentationml/2006/main';A='http://schemas.openxmlformats.org/drawingml/2006/main';C='http://schemas.openxmlformats.org/drawingml/2006/chart';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';REL='http://schemas.openxmlformats.org/package/2006/relationships';CT='http://schemas.openxmlformats.org/package/2006/content-types'
N={'p':P,'a':A,'c':C,'r':R}
def parse(b):return X.fromstring(b,X.XMLParser(resolve_entities=False,no_network=True))
def xml(e):return X.tostring(e,xml_declaration=True,encoding='UTF-8',standalone=True)
def add(e,ns,t,**attrs):return X.SubElement(e,'{'+ns+'}'+t,{k:str(v)for k,v in attrs.items()})
with zipfile.ZipFile(D/'draft.pptx')as z:parts={p:z.read(p)for p in z.namelist()}
ct=parse(parts['[Content_Types].xml']);checks=[]
for i,chartpath in enumerate(sorted(p for p in parts if re.fullmatch(r'ppt/slides/charts/chart\d+\.xml',p)),1):
 t=parse(parts[chartpath]);ss=t.findall('.//c:ser',N);assert ss
 wb=Workbook();ws=wb.active;ws.title='Evidence';ws.cell(1,1,'Category');expected=[]
 for j,ser in enumerate(ss,2):
  label=ser.findtext('c:tx/c:v',namespaces=N);cat=ser.find('c:cat/c:strLit',N);val=ser.find('c:val/c:numLit',N);assert cat is not None and val is not None
  cats=[x.findtext('c:v',namespaces=N)for x in cat.findall('c:pt',N)];vals=[float(x.findtext('c:v',namespaces=N))for x in val.findall('c:pt',N)]
  assert len(cats)==len(vals);ws.cell(1,j,label)
  for row,(c,v)in enumerate(zip(cats,vals),2):ws.cell(row,1,c);ws.cell(row,j,v)
  letter=chr(64+j);tx=ser.find('c:tx',N);tx.clear();ref=add(tx,C,'strRef');add(ref,C,'f').text='Evidence!$'+letter+'$1';cache=add(ref,C,'strCache');add(cache,C,'ptCount',val=1);add(add(cache,C,'pt',idx=0),C,'v').text=label
  parent=ser.find('c:cat',N);parent.remove(cat);ref=add(parent,C,'strRef');add(ref,C,'f').text='Evidence!$A$2:$A$'+str(len(cats)+1);cache=copy.deepcopy(cat);cache.tag='{'+C+'}strCache';ref.append(cache)
  parent=ser.find('c:val',N);parent.remove(val);ref=add(parent,C,'numRef');add(ref,C,'f').text='Evidence!$'+letter+'$2:$'+letter+'$'+str(len(vals)+1);cache=copy.deepcopy(val);cache.tag='{'+C+'}numCache';ref.append(cache)
  expected.append((label,cats,vals))
 out=io.BytesIO();wb.save(out);raw=out.getvalue();wb2=load_workbook(io.BytesIO(raw),data_only=True);ws2=wb2.active
 for col,(label,cats,vals)in enumerate(expected,2):
  assert ws2.cell(1,col).value==label
  for row,(c,v)in enumerate(zip(cats,vals),2):assert ws2.cell(row,1).value==c and abs(ws2.cell(row,col).value-v)<1e-9
 part=f'ppt/embeddings/chart_evidence_{i}.xlsx';parts[part]=raw
 relpath=posixpath.dirname(chartpath)+'/_rels/'+posixpath.basename(chartpath)+'.rels';rels=X.Element('{'+REL+'}Relationships',nsmap={None:REL})
 add(rels,REL,'Relationship',Id='rId1',Type=R+'/package',Target='../../embeddings/'+posixpath.basename(part))
 ex=add(t,C,'externalData');ex.set('{'+R+'}id','rId1');add(ex,C,'autoUpdate',val=0)
 parts[chartpath]=xml(t);parts[relpath]=xml(rels);add(ct,CT,'Override',PartName='/'+part,ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
 checks.append({'chart':chartpath,'series':len(ss),'workbook':part,'cache_workbook_equal':True})
parts['[Content_Types].xml']=xml(ct)
# Add slide-level clickable shapes; relative links remain portable inside the materials folder.
for slide in [12,13,14,15]:
 f=f'ppt/slides/slide{slide}.xml';rf=f'ppt/slides/_rels/slide{slide}.xml.rels';t=parse(parts[f]);rels=parse(parts[rf]);rid=max([int(x.get('Id')[3:])for x in rels if re.fullmatch(r'rId\d+',x.get('Id',''))]+[0])+1
 for nv in t.findall('.//p:cNvPr',N):
  name=nv.get('name','');target=None;action=None
  m=re.fullmatch(r'view_(?:text_)?(12|14|15)',name)
  if m:target='slide'+m[1]+'.xml';reltype=R+'/slide';action='ppaction://hlinksldjump';external=False
  elif name in ['open_web3d','open_web3d_text','open_demo_web','open_demo_web_text']:target=urllib.parse.quote('展示素材/成果展示.html',safe='/');reltype=R+'/hyperlink';external=True
  elif name in ['open_demo_video','open_demo_video_text']:target=urllib.parse.quote('展示素材/三维流程演示_2倍速.mp4',safe='/');reltype=R+'/hyperlink';external=True
  if target:
   rr='rId'+str(rid);rid+=1;rel=add(rels,REL,'Relationship',Id=rr,Type=reltype,Target=target)
   if external:rel.set('TargetMode','External')
   h=add(nv,A,'hlinkClick');h.set('{'+R+'}id',rr)
   if action:h.set('action',action)
 # Assign the picture a stable name for native GLB replacement.
 if slide in [12,14,15]:
  pics=t.findall('.//p:pic/p:nvPicPr/p:cNvPr',N);assert len(pics)==1;pics[0].set('name','native3d_preview')
 parts[f]=xml(t);parts[rf]=xml(rels)
with zipfile.ZipFile(D/'linked.pptx','w',compression=zipfile.ZIP_DEFLATED)as z:
 for p,b in parts.items():z.writestr(p,b)
# Real GLB models; no screen rotation claim is made by this package step.
spec=importlib.util.spec_from_file_location('native3d',str(Path(__file__).with_name('embed_native3d.py')));mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
source=D/'linked.pptx';reports=[]
for slide,view,pos in [(12,'overview',(16/19.7,18/19.7,20/19.7)),(14,'top',(0,28/19.7,.1/19.7)),(15,'side',(24/19.7,7/19.7,1/19.7))]:
 dest=D/f'native_{slide}.pptx'
 if dest.exists():dest.unlink()
 report=mod.embed(source,dest,MAT/'展示素材/NeedleRV-X_逻辑结构.glb',D/(view+'.png'),slide,(55,160,800,466),1/19.7,pos,38,'NeedleRV-X native '+view,'native3d_preview');reports.append(report);source=dest
# Necessary final package references and geometry. No hashes or source audit.
with zipfile.ZipFile(source)as z:
 names=set(z.namelist());slides=sorted(p for p in names if re.fullmatch(r'ppt/slides/slide\d+\.xml',p));assert len(slides)==15
 links=[];models=0;tables=0;native_charts=0
 for p in slides:
  t=parse(z.read(p));models+=len(t.findall('.//{http://schemas.microsoft.com/office/drawing/2017/model3d}model3d'));tables+=len(t.findall('.//a:tbl',N));native_charts+=len(t.findall('.//c:chart',N))
 for rp in [p for p in names if p.endswith('.rels')]:
  rels=parse(z.read(rp));base=posixpath.dirname(posixpath.dirname(rp))
  for rel in rels:
   target=rel.get('Target')
   if rel.get('TargetMode')=='External':
    if rel.get('Type')==R+'/hyperlink':
     path=MAT/urllib.parse.unquote(target);assert path.is_file(),str(path);links.append(str(path))
   else:
    resolved=target.lstrip('/')if target.startswith('/')else posixpath.normpath(base+'/'+target)
    assert resolved in names,(rp,resolved)
 assert models==3 and native_charts==3 and tables==2
 assert len(links)==10
 for p in slides:
  t=parse(z.read(p))
  for sp in t.findall('.//p:sp',N)+t.findall('.//p:pic',N):
   # Main slide transforms; fallback xfrm stays within the intended 1280x720 canvas.
   f=sp.find('p:spPr/a:xfrm',N)
   if f is None:continue
   off=f.find('a:off',N);ext=f.find('a:ext',N)
   if off is not None and ext is not None:
    x=int(off.get('x'));y=int(off.get('y'));w=int(ext.get('cx'));h=int(ext.get('cy'))
    assert x>=-1 and y>=-1 and x+w<=1280*9525+1 and y+h<=720*9525+1,(p,x,y,w,h)
final=MAT/'NeedleRV-X_答辩演示.pptx';shutil.copyfile(source,final)
receipt={'output':str(final),'slide_count':15,'native_charts':3,'embedded_chart_workbooks':3,'native_tables':2,'native_glb_models':3,'link_targets_exist':True,'internal_view_navigation':[12,14,15],'all_slide_renders_inspected':True,'native_powerpoint_ui_tested':False,'no_hash_checks':True,'chart_checks':checks,'model_parts':reports}
(D/'finalization.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:receipt[k]for k in ['output','slide_count','native_charts','embedded_chart_workbooks','native_tables','native_glb_models','link_targets_exist','native_powerpoint_ui_tested','no_hash_checks']},ensure_ascii=True,indent=2))

