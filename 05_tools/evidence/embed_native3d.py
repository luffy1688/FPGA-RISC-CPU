"""Embed one GLB + PNG fallback in an existing PPTX without rewriting its design.

Independent implementation of Microsoft MS-ODRAWXML section 5.29.
https://learn.microsoft.com/en-us/openspecs/office_standards/ms-odrawxml/6c414e62-4825-4100-9ca1-88fefc5fb699
The relationship and MIME spellings were checked against a PowerPoint-authored
GLB fixture; no third-party slide content or source implementation is included.

PowerPoint 2019+ provides native model rotation in editing mode. This package
check is not an Office UI test and does not promise free drag rotation during
slide show; link to the actual HTML 3D viewer for that interaction.
The supplied GLB must be centred at the origin. Camera coordinates are metres.
"""
from pathlib import Path
from lxml import etree as E
import argparse,io,json,math,re,struct,zipfile

P='http://schemas.openxmlformats.org/presentationml/2006/main'
A='http://schemas.openxmlformats.org/drawingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
MC='http://schemas.openxmlformats.org/markup-compatibility/2006'
M='http://schemas.microsoft.com/office/drawing/2017/model3d'
REL='http://schemas.openxmlformats.org/package/2006/relationships'
CT='http://schemas.openxmlformats.org/package/2006/content-types'
N={'p':P,'a':A,'r':R,'mc':MC,'am3d':M}
NS={'p':P,'a':A,'r':R,'mc':MC,'am3d':M}
UNITS=36000000

def node(parent,ns,tag,**attrs):
 return E.SubElement(parent,'{'+ns+'}'+tag,{k:str(v)for k,v in attrs.items()})
def xml(data):return E.fromstring(data,E.XMLParser(resolve_entities=False,no_network=True))
def serialize(t):return E.tostring(t,xml_declaration=True,encoding='UTF-8',standalone=True)
def frame(parent,ns,x,y,w,h):
 t=node(parent,ns,'xfrm');node(t,A,'off',x=x,y=y);node(t,A,'ext',cx=w,cy=h);return t

def glb_check(data):
 assert len(data)>=20,'GLB too short'
 magic,version,size=struct.unpack_from('<4sII',data)
 assert magic==b'glTF'and version==2 and size==len(data),'Invalid GLB2 header'
 length,kind=struct.unpack_from('<II',data,12);assert kind==0x4e4f534a and 20+length<=size,'Missing GLB JSON chunk'
 manifest=json.loads(data[20:20+length]);assert manifest.get('asset',{}).get('version')=='2.0'and manifest.get('meshes'),'GLB2 has no meshes'
 assert all('uri'not in x for x in manifest.get('buffers',[])),'External buffer URI not allowed in portable GLB'
 return dict(meshes=len(manifest['meshes']),nodes=len(manifest.get('nodes',[])),bytes=len(data))

def model_alternate(shape_id,name,description,rect,model_rid,image_rid,meter_per_unit,camera,fov):
 x,y,w,h=rect
 ac=E.Element('{'+MC+'}AlternateContent',nsmap={'mc':MC})
 ch=E.SubElement(ac,'{'+MC+'}Choice',Requires='am3d',nsmap={'am3d':M})
 gf=node(ch,P,'graphicFrame');nv=node(gf,P,'nvGraphicFramePr')
 node(nv,P,'cNvPr',id=shape_id,name=name,descr=description)
 node(node(nv,P,'cNvGraphicFramePr'),A,'graphicFrameLocks');node(nv,P,'nvPr')
 frame(gf,P,x,y,w,h)
 graphic=node(gf,A,'graphic');gd=node(graphic,A,'graphicData',uri=M)
 model=node(gd,M,'model3d');model.set('{'+R+'}embed',model_rid)
 sp=node(model,M,'spPr');frame(sp,A,0,0,w,h);node(node(sp,A,'prstGeom',prst='rect'),A,'avLst')
 cam=node(model,M,'camera')
 node(cam,M,'pos',**{key:round(value*UNITS)for key,value in zip(('x','y','z'),camera)})
 node(cam,M,'up',dx=0,dy=UNITS,dz=0);node(cam,M,'lookAt',x=0,y=0,z=0)
 node(cam,M,'perspective',fov=round(fov*60000))
 trans=node(model,M,'trans')
 node(trans,M,'meterPerModelUnit',n=round(meter_per_unit*1000000),d=1000000)
 node(trans,M,'preTrans',dx=0,dy=0,dz=0);scale=node(trans,M,'scale')
 for axis in ['sx','sy','sz']:node(scale,M,axis,n=1000000,d=1000000)
 node(trans,M,'rot');node(trans,M,'postTrans',dx=0,dy=0,dz=0)
 # Renderer metadata describes our externally rendered cached raster honestly.
 raster=node(model,M,'raster',rName='NeedleRVX_ThreeJS_preview',rVer='1.0')
 node(raster,M,'blip').set('{'+R+'}embed',image_rid)
 node(model,M,'objViewport',viewportSz=max(w,h))
 ambient=node(model,M,'ambientLight');node(node(ambient,M,'clr'),A,'scrgbClr',r=65000,g=65000,b=65000)
 node(ambient,M,'illuminance',n=750000,d=1000000)
 light=node(model,M,'ptLight',rad=0)
 node(node(light,M,'clr'),A,'scrgbClr',r=100000,g=100000,b=100000)
 node(light,M,'intensity',n=10000000,d=1000000);node(light,M,'pos',x=UNITS,y=2*UNITS,z=2*UNITS)
 fallback=node(ac,MC,'Fallback');pic=node(fallback,P,'pic');nv=node(pic,P,'nvPicPr')
 node(nv,P,'cNvPr',id=shape_id,name=name,descr=description)
 locks=node(node(nv,P,'cNvPicPr'),A,'picLocks',noChangeAspect=1,noCrop=1);node(nv,P,'nvPr')
 fill=node(pic,P,'blipFill');node(fill,A,'blip').set('{'+R+'}embed',image_rid)
 node(node(fill,A,'stretch'),A,'fillRect');sp=node(pic,P,'spPr');frame(sp,A,x,y,w,h)
 node(node(sp,A,'prstGeom',prst='rect'),A,'avLst')
 return ac

def embed(source,dest,glb,preview,slide,rect,meter_per_unit,camera=(1.35,1.1,1.93),fov=45,name='NeedleRV-X native 3D',replace_name=None):
 source=Path(source);dest=Path(dest);assert source.resolve()!=dest.resolve(),'Use a distinct build output; copy validated final back separately'
 assert not dest.exists(),'Refusing overwrite of a build output'
 assert math.isfinite(meter_per_unit)and meter_per_unit>=0.0000005
 assert all(math.isfinite(v)for v in camera)and 0<fov<180
 assert all(math.isfinite(v)for v in rect)and rect[2]>0 and rect[3]>0
 # Geometry arrives in CSS pixels at 96dpi, as in artifact-tool.
 rect=tuple(round(v*9525)for v in rect)
 glb_data=Path(glb).read_bytes();manifest=glb_check(glb_data)
 png=Path(preview).read_bytes();assert png.startswith(b'\x89PNG\r\n\x1a\n'),'Fallback must be PNG'
 with zipfile.ZipFile(source)as src:
  slide_path=f'ppt/slides/slide{slide}.xml';rel_path=f'ppt/slides/_rels/slide{slide}.xml.rels'
  assert slide_path in src.namelist(),'Slide not found'
  tree=xml(src.read(slide_path));sp_tree=tree.find('p:cSld/p:spTree',N);assert sp_tree is not None
  relationships=xml(src.read(rel_path))if rel_path in src.namelist()else E.Element('{'+REL+'}Relationships',nsmap={None:REL})
  types=xml(src.read('[Content_Types].xml'))
  used_ids=[int(x.get('id'))for x in tree.xpath('.//p:cNvPr',namespaces=N)]
  shape_id=max(used_ids+[1])+1
  rids={x.get('Id')for x in relationships};next_rid=max([int(x[3:])for x in rids if re.fullmatch(r'rId\d+',x)]+[0])+1
  model_rid='rId'+str(next_rid);image_rid='rId'+str(next_rid+1)
  suffix=1
  while f'ppt/media/needlervx_board3d_{suffix}.glb'in src.namelist():suffix+=1
  model_path=f'ppt/media/needlervx_board3d_{suffix}.glb';png_path=f'ppt/media/needlervx_board3d_{suffix}.png'
  node(relationships,REL,'Relationship',Id=model_rid,Type='http://schemas.microsoft.com/office/2017/06/relationships/model3d',Target='../media/'+Path(model_path).name)
  node(relationships,REL,'Relationship',Id=image_rid,Type=R+'/image',Target='../media/'+Path(png_path).name)
  for path,content in [(model_path,'model/gltf.binary'),(png_path,'image/png')]:
   node(types,CT,'Override',PartName='/'+path,ContentType=content)
  insertion=len(sp_tree)
  if replace_name:
   targets=sp_tree.xpath('./p:pic[p:nvPicPr/p:cNvPr/@name=$name]|./p:sp[p:nvSpPr/p:cNvPr/@name=$name]',namespaces=N,name=replace_name)
   assert len(targets)==1,'replace_name must identify exactly one direct picture/shape'
   insertion=list(sp_tree).index(targets[0]);sp_tree.remove(targets[0])
  description='FPGA logical board and execution structure. Native GLB model; rotate in supported PowerPoint editing mode. Browser viewer provides slide-show interaction.'
  sp_tree.insert(insertion,model_alternate(shape_id,name,description,rect,model_rid,image_rid,meter_per_unit,camera,fov))
  replacements={slide_path:serialize(tree),rel_path:serialize(relationships),'[Content_Types].xml':serialize(types),model_path:glb_data,png_path:png}
  dest.parent.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_DEFLATED)as out:
   for item in src.infolist():out.writestr(item,replacements.pop(item.filename,src.read(item.filename)))
   for path,data in replacements.items():out.writestr(path,data)
 with zipfile.ZipFile(dest)as out:
  tree=xml(out.read(slide_path));models=tree.xpath('.//am3d:model3d',namespaces=N)
  assert any(m.get('{'+R+'}embed')==model_rid for m in models)
  assert tree.xpath('.//mc:Choice[@Requires="am3d"]/p:graphicFrame',namespaces=N)
  assert len(out.read(model_path))==manifest['bytes']
  fallback=tree.xpath('.//mc:AlternateContent[mc:Choice/p:graphicFrame/a:graphic/a:graphicData/am3d:model3d]/mc:Fallback/p:pic',namespaces=N)
  assert fallback,'Missing fallback'
 return dict(output=str(dest),slide=slide,shape_id=shape_id,model_part=model_path,fallback_part=png_path,model_relationship=model_rid,preview_relationship=image_rid,glb=manifest,meter_per_unit=meter_per_unit,camera_metres=camera,verified='Native part/relationship/GLB/fallback structure only; Office interaction not UI-tested')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('dest');p.add_argument('--glb',required=True);p.add_argument('--preview',required=True);p.add_argument('--slide',required=True,type=int)
 p.add_argument('--rect',required=True,nargs=4,type=float,metavar=('X','Y','W','H'));p.add_argument('--meter-per-unit',required=True,type=float);p.add_argument('--camera',nargs=3,type=float,default=(1.35,1.1,1.93));p.add_argument('--fov',type=float,default=45);p.add_argument('--name',default='NeedleRV-X native 3D');p.add_argument('--replace-name')
 a=p.parse_args();print(json.dumps(embed(a.source,a.dest,a.glb,a.preview,a.slide,a.rect,a.meter_per_unit,a.camera,a.fov,a.name,a.replace_name),ensure_ascii=True,indent=2))
