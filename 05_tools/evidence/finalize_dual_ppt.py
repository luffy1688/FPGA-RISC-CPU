"""Update the existing deck, preserving its native models and editable charts."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from io import BytesIO
import json, copy
from openpyxl import load_workbook

helper=Path(__file__).with_name('refresh_lumarv_ppt.py').read_text(encoding='utf-8')
exec(helper.split('with ZipFile(SRC)as z:')[0])
with ZipFile(SRC)as z:parts={p:z.read(p)for p in z.namelist()}
slides={n:tree(n)for n in range(1,18)}

text(1,6,'语境感知调试与双核后台自检',25)
text(1,8,'主核处理中文与外设，副核独立计算，操作后核对读回',20)
text(1,14,'12.04×');text(1,15,'完整中文PWM模型加速')
text(2,3,'临时调参和后台计算并行，每条请求完成后核对读回。',16)
sp=clearbody(2);image(2,'应用_板卡复测.png',110,157,1060,500)
im=Image.open(ROOT/'图表/应用_板卡复测.png')
xf=slides[2].find('.//p:pic/p:spPr/a:xfrm',N);xf.find('a:ext',N).set('cy',str(co(1060*im.height/im.width)))
text(3,418,'完整中文PWM模型：658.079ms → 54.640ms，12.04×',20)
text(8,2,'双核分工与整机资源')
text(8,3,'旧单核整机与54MHz双核整机对照，新增独立副核、Cache及私有RAM。',16)
text(8,9,'双核整机：342.5 DRM36等效，40 APM；慢角setup +0.569ns。',18)
tab=slides[8].find('.//a:tbl',N)
for row,col,val in [(1,1,'54 MHz'),(2,1,'0.569 / 7.529 ns'),(3,1,'0.141 / 0.100 ns'),(5,1,'342.5'),(6,1,'40')]:
 ts=tab.findall('a:tr',N)[row].findall('a:tc',N)[col].findall('.//a:t',N);ts[0].text=val
 for t in ts[1:]:t.text=''
clearbody(9);text(9,3,'54MHz实板，四句各10次；散点为全部样本，包含USB及主机调度。',16)
image(9,'双核_控制往返.png',125,155,1030,485)
im=Image.open(ROOT/'图表/双核_控制往返.png')
xf=slides[9].find('.//p:pic/p:spPr/a:xfrm',N);xf.find('a:ext',N).set('cy',str(co(1030*im.height/im.width)))
text(10,3,'54MHz同镜像，config0与config6分别运行完整模型；输出数组一致。',16)
text(10,8,'主核 / 副核 / 双核累计',18)
text(10,9,'4.038 / 3.890 / 7.781',24)
text(10,10,'CoreMark/MHz · 两核各3000次',17)
text(10,11,'共同计时14.280秒，双核CRC通过',17)
text(10,13,'中文PWM模型加速12.04×',21)
text(10,14,'主核19次CRC通过；54.640ms为完整模型，控制往返另计。',16)
text(11,11,'PWM 20%\n54000周期 / 10800高电平',20)
tbl=slides[11].find('.//a:tbl',N);trs=tbl.findall('a:tr',N)
for row,col,val in [(2,0,'后台自检期间完整AI / IO'),(2,1,'模型数组一致，PWM读回匹配'),(3,0,'19次主核CoreMark'),(3,1,'各3000次，CRC均通过'),(4,0,'网页程序 + 真实UART'),(4,1,'15个事务通过'),(6,0,'原生UART控制往返'),(6,1,'四句各10次，全部返回')]:
 ts=trs[row].findall('a:tc',N)[col].findall('.//a:t',N);ts[0].text=val
 for t in ts[1:]:t.text=''
text(12,3,'十个模块：主核负责交互与外设，副核使用私有存储独立计算。',16)
text(12,8,'4 MAC 编码器\n8 MAC 语义侧核\n512 KiB 主SRAM\n128 KiB 权重缓存\n副核 + 64 KiB私有RAM',18)
text(13,3,'中文请求经过语境与许可；副核后台计算不占用执行器。',16)
text(16,19,'十个模块标注\n分层、合拢、PWM流程\n20秒讲解',18)
text(17,2,'模型版本与双核资源对照')
text(17,3,'语料与模型保持不变，双核扩展用于分离交互控制和后台计算。',16)
text(17,19,'模型组合版本比较\n旧单核与双核整机\n分类集合已参与开发',18)

C='http://schemas.openxmlformats.org/drawingml/2006/chart';CN={'c':C}
def chart(num,labels,series,maximum,unit):
 name='ppt/slides/charts/chart%d.xml'%num;t=parse(parts[name])
 for s,(title,values) in zip(t.findall('.//c:ser',CN),series):
  s.find('c:tx/c:strRef/c:strCache/c:pt/c:v',CN).text=title
  for v,label in zip(s.findall('c:cat/c:strRef/c:strCache/c:pt/c:v',CN),labels):v.text=label
  for v,value in zip(s.findall('c:val/c:numRef/c:numCache/c:pt/c:v',CN),values):v.text=str(value)
 t.find('.//c:valAx/c:scaling/c:max',CN).set('val',str(maximum))
 t.find('.//c:valAx/c:majorUnit',CN).set('val',str(unit))
 parts[name]=xml(t)
 name='ppt/embeddings/chart_evidence_%d.xlsx'%num
 wb=load_workbook(BytesIO(parts[name]));ws=wb['Evidence'];ws.cell(1,1,'指标')
 for i,label in enumerate(labels,2):ws.cell(i,1,label)
 for j,(title,values)in enumerate(series,2):
  ws.cell(1,j,title)
  for i,v in enumerate(values,2):ws.cell(i,j,v)
 b=BytesIO();wb.save(b);parts[name]=b.getvalue()

chart(2,['LUT','FF'],[('旧单核',[19456,19116]),('54MHz双核',[55277,39035])],60000,10000)
chart(3,['led 37','中文PWM'],[('软件',[6221770/54000,35536262/54000]),('硬件',[423751/54000,2950565/54000])],800,200)
for n in slides:store(n)
for n,name in [(13,'双路径流程_讲解动画.gif'),(16,'三维模型_旋转分层.gif'),(17,'模型与资源_证据动画.gif')]:
 parts['ppt/media/needlervx_explanation_%d.gif'%n]=(ROOT/'展示素材'/name).read_bytes()
for name in list(parts):
 if name.endswith('.glb'):parts[name]=(ROOT/'展示素材/LumaRV_逻辑结构.glb').read_bytes()
for n,view in [(1,'overview'),(2,'top'),(3,'side')]:
 parts['ppt/media/needlervx_board3d_%d.png'%n]=(Path('C:/Users/luo/AppData/Local/Temp/needlervx_ppt')/(view+'.png')).read_bytes()
notes={1:'本版采用54MHz双核。主核处理中文、执行许可与IO，副核在私有存储中执行后台计算自检。模型权重197816字节，训练文本25014条。',8:'旧单核19456LUT、19116FF。最终双核整机55277LUT、39035FF、342.5 DRM36等效、40APM。两版功能不同，不将资源增长归因为某一项优化。54MHz全部时序约束通过。',9:'四句各10次原生UART往返，结果到READY。中位数LED1.3167ms、温度3.65915ms、PWM1.9061ms、计数1.93675ms。',10:'主核19次CoreMark均通过CRC，中位数4.038436612/MHz。副核3.890410775/MHz。两个独立实例各3000次，共同计时14.280421481秒，累计吞吐7.780660484/MHz。累计值不是单核成绩。完整中文PWM软件658.078926ms，硬件54.640093ms，输出数组一致。',11:'四批原文结果24/25、25/25、25/25、25/25，范围内98/99。一条成绩询问保守拒绝，另有强制完整模型的LED0置位误拒绝；默认混合路径20项位保持均通过。PWM周期54000，高电平10800。',12:'十个模块中，新增独立副核及64KiB私有RAM。原生3D可在兼容PowerPoint中选择旋转；放映时通过链接打开网页旋转与分层。',16:'十模块分层、合拢、完整PWM请求至寄存器回读。20秒三倍速讲解动画，不用动画长度计算FPGA耗时。',17:'模型分类已观察集合1087/1138、685/900。本次CPU与双核优化不改变模型权重；资源比较旧单核与最终双核，后台自检期间主核模型结果一致。'}
for n,body in notes.items():
 name='ppt/notesSlides/notesSlide%d.xml'%n
 if name not in parts:continue
 t=parse(parts[name]);ss=t.findall('.//p:sp',N)
 for s in ss:
  ph=s.find('p:nvSpPr/p:nvPr/p:ph',N)
  if ph is not None and ph.get('type')=='body':settext(s,body)
 parts[name]=xml(t)
with ZipFile(DST,'w',ZIP_DEFLATED)as z:
 for name,b in parts.items():z.writestr(name,b)
print(json.dumps({'output':str(DST),'slides':17,'native_models':sum(n.endswith('.glb')for n in parts),'editable_charts':3},ensure_ascii=False))
