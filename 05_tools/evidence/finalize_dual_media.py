from pathlib import Path
import json,re
R=Path('D:/Desktop/FPGA');E=R/'上板交付/工程';O=R/'参赛材料/展示素材'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
f=read(E/'07_runs/board/current/final_metrics.json');p=read(E/'07_runs/board/current/dual_final_console.json');b=read(E/'07_runs/board/current/dual_final_four_batches.json');a=read(E/'07_runs/frequency_current/dual54/physical_acceptance_final.json');l=read(E/'07_runs/board/current/dual_final_latency.json')
def record(text,v,timing,source):
 wire=dict(v)
 for k,x in (v.get('receipt')or{}).items():wire['receipt_'+k]=x
 return dict(text=text,wire_result=wire,result=v,timing_ms=timing,evidence_file=source)
model=next(x for x in a['samples']if x['phase']=='hardware_reference'and x['text'].startswith('请将PWM'))
led=next(x for x in l['samples']if x.get('phase')=='measure'and x['text']=='led 37')
reject=next(x for x in b['samples']if x['text']=='把PWM频率改成2kHz。')
ui=next(x for x in p['page_evidence']['requests']if x.get('dual_benchmark'))
data=dict(firmware=f['brand'],date=f['date'],build=p['page_evidence']['firmware_build'],coremark=dict(seconds=f['common_seconds'],iterations=3000,primary=f['primary_score_per_mhz'],worker=f['worker_score_per_mhz'],aggregate=f['aggregate_per_mhz']),records={
 'model':record(model['text'],model['result'],dict(tready_ms=model['tready_ms']),'physical_acceptance_final.json'),
 'fast':record(led['text'],led['result'],dict(tready_ms=led['tready_ms']),'dual_final_latency.json'),
 'reject':record(reject['text'],reject['result'],dict(tready_ms=reject['tready_ms']),'dual_final_four_batches.json'),
 'coremark':record(ui['command'],ui['result'],dict(tready_ms=ui['ready_ms']),'dual_final_console.json')})
q=O/'成果展示.html';s=q.read_text(encoding='utf-8')
s=re.sub(r'<script>var NeedleScene3D=.*?</script>',lambda m:'<script>'+ (E/'05_tools/console/vendor/architecture-scene.min.js').read_text(encoding='utf-8')+'</script>',s,count=1,flags=re.S)
i=s.index('const DATA=');j=s.index('const STEPS=',i);s=s[:i]+'const DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n'+s[j:]
for x,y in {'周期40500、高电平8100':'周期54000、高电平10800','周期40500，高8100':'周期54000，高10800','1200迭代CoreMark，CRC五项通过；约14.585秒，2.031490/MHz':'两核各3000迭代，CRC均通过；共同时间14.280421秒，累计7.780660/MHz','为74.567ms':'为54.640ms','/40500':'/54000',"'1200迭代 / CRC5项通过'":"'每核3000迭代 / 两核CRC通过'"}.items():s=s.replace(x,y)
s=s.replace('["cpu","临时复测"','["worker","双核复测"').replace('试产与返修时，工程师逐条检查状态或调整输出；这里讲解板卡已有返回记录。','主核处理中文与外设，副核在私有64KiB存储中运行后台计算自检。').replace('单项复测与局部调参','副核后台自检，主核继续交互')
s=s.replace('"io"],[]]','"io","worker"],[]]',1)
s=s.replace('semanticCache:true,contextHead:true,teaching:playing','semanticCache:true,contextHead:true,dualCore:true,teaching:playing')
s=s.replace('index>=3&&index<=7','index<=1')
q.write_text(s,encoding='utf-8');(E/'05_tools/console/showcase_data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

q=E/'05_tools/evidence/render_ppt_model_gif.cjs';s=q.read_text(encoding='utf-8').replace('demo_hardware_report.json','dual_final_console.json').replace('!==40500','!==54000').replace('!==8100','!==10800').replace('40500','54000').replace('8100','10800').replace('74.567ms','54.640ms').replace('九个模块','十个模块').replace('modules:9','modules:10')
s=s.replace("'permit','io'];if(keys", "'permit','io','worker'];if(keys")
s=s.replace("contextHead:true,active:","contextHead:true,dualCore:true,active:").replace("contextHead:true,muted:","contextHead:true,dualCore:true,muted:")
s=s.replace("uart:3.8,cpu:3.4", "worker:3.0,uart:3.8,cpu:3.4").replace("uart:[0,1,0]", "worker:[0,1.2,0],uart:[0,1,0]")
s=s.replace("x:24,y:156", "x:24,y:150").replace("x:24,y:250", "x:24,y:238").replace("x:24,y:344", "x:24,y:326").replace("x:24,y:438", "x:24,y:414")
s=s.replace("{k:'guard',n:'05'", "{k:'worker',n:'10',title:'独立副核与私有RAM',lines:['后台计算自检 · 64KiB RAM','无LED / PWM写权限'],x:24,y:502},\n    {k:'guard',n:'05'")
s=s.replace("a:['uart','cpu','permit','io'],title:'控制层", "a:['uart','cpu','worker','permit','io'],title:'控制层").replace('CPU调度请求，工具通过许可后操作外设。','主核处理交互；副核独立运行后台计算自检。')
s=s.replace('逻辑结构 · 运行记录讲解 · 3×','逻辑结构 · 运行记录讲解 · 20秒')
q.write_text(s,encoding='utf-8')
for name in ['render_report_board.cjs','render_frozen_ppt_views.cjs']:
 q=E/'05_tools/evidence'/name;s=q.read_text(encoding='utf-8')
 s=s.replace('contextHead:true,active:', 'contextHead:true,dualCore:true,active:')
 if name.startswith('render_frozen'):s=s.replace('NRShowcase.api.setExploded(false)',"NRShowcase.api.update({dualCore:true,semanticCache:true,contextHead:true});NRShowcase.api.setExploded(false)")
 else:
  s=s.replace("'permit','io'],lift=[3.8,3.4,1.8,2.2,3.4,2.1,2.2,3.4,3]","'permit','io','worker'],lift=[3.8,3.4,1.8,2.2,3.4,2.1,2.2,3.4,3,3]")
  s=s.replace('c.height=640','c.height=700').replace('1000,640','1000,700').replace('permit:1,io:1','permit:1,io:1,worker:1.2')
  s=s.replace("'GPIO / PWM / ADC'];","'GPIO / PWM / ADC','独立副核与64KiB'];")
 q.write_text(s,encoding='utf-8')
print('CURRENT_DUAL_SHOWCASE_AND_MEDIA_SOURCES_UPDATED')
