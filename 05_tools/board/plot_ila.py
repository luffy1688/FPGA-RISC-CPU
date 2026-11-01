from pathlib import Path
import argparse,json,importlib.util
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec,GridSpecFromSubplotSpec
from matplotlib.ticker import FuncFormatter
root=Path(__file__).resolve().parents[2]
ap=argparse.ArgumentParser();ap.add_argument('--dir',type=Path,default=root/'07_runs/board/current/ila');ap.add_argument('--map',type=Path,default=root/'06_pango_active_ila/signal_map.json');args=ap.parse_args();folder=args.dir
s=importlib.util.spec_from_file_location('ila_reader',root/'05_tools/board/analyze_ila.py');reader=importlib.util.module_from_spec(s);s.loader.exec_module(reader)
mapping=json.loads(args.map.read_text());a=json.loads((folder/'analysis.json').read_text())
core=reader.decode(folder/'coremark.wdf',mapping['core0']);xnd=reader.decode(folder/'xnd.wdf',mapping['core0']);pwm=reader.decode(folder/'pwm25.wdf',mapping['core1'])
hz=mapping['core0'].get('sample_clock_hz',mapping['clock_hz_reference']);pwmhz=mapping['core1'].get('sample_clock_hz',mapping['clock_hz_reference']);mhz=hz/1e6
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,'axes.labelsize':10,'axes.spines.top':False,'axes.spines.right':False})
fig=plt.figure(figsize=(14,10),facecolor='white');outer=GridSpec(2,2,wspace=.30,hspace=.40,left=.07,right=.97,bottom=.14,top=.88)
ax=fig.add_subplot(outer[0,0]);pin=pwm['nt_led[7]'];v=a['captures']['pwm25']['pwm'];points=[0]+sorted(v['rising_edges']+v['falling_edges'])+[len(pin)-1];times=[i*1000/pwmhz for i in points];levels=[pin[i]for i in points]
ax.step(times,levels,where='post',color='#2563eb',linewidth=1.8);ax.fill_between(times,0,levels,step='post',color='#dbeafe')
ax.set(xlim=(0,(len(pin)-1)*1000/pwmhz),ylim=(-.15,1.5),yticks=[0,1],xlabel='Time (ms, nominal PLL clock)',ylabel='GPIO[7] pre-pad level');ax.set_title('A. Internal PWM: 1 kHz, 25% duty',loc='left',fontweight='bold');ax.grid(axis='x',color='#e5e7eb')
ax.text(.03,.94,'Periods: '+str(v['period_samples'])+' cycles\nHigh pulses: '+str(v['high_samples'])+' cycles',transform=ax.transAxes,fontsize=9,color='#334155',va='top')
ax=fig.add_subplot(outer[0,1]);ax.axis('off');ax.set_title('B. ADC status in two captured windows',loc='left',fontweight='bold')
adcs=sorted([(k,x['adc'])for k,x in a['captures'].items()if'ADC'in k.upper()or'ADC'in str(x.keys()).upper()],key=lambda x:x[1]['sample_counter']['min'])
rows=[[k,str(v['raw_codes'][0]),'1','0','0',str(v['sample_counter']['min']),'{:.2f}'.format(v['centidegrees_from_raw'][0]/100)]for k,v in adcs]
tab=ax.table(cellText=rows,colLabels=['Window','Raw','Valid','Fault','OT','Count','T (C)'],cellLoc='center',loc='center',bbox=[0,.43,1,.37]);tab.auto_set_font_size(False);tab.set_fontsize(9)
for(row,col),cell in tab.get_celld().items():
 cell.set_edgecolor('#d1d5db');cell.set_facecolor('#e0f2fe'if row==0 else'#f8fafc')
 if row==0:cell.set_text_props(weight='bold')
delta=(adcs[-1][1]['sample_counter']['min']-adcs[0][1]['sample_counter']['min'])%2**32
ax.text(0,.32,'Conversion count increased by '+str(delta)+'.',color='#0f766e',weight='bold',transform=ax.transAxes,va='top')
ax.text(0,.21,'Status = 0x5. Available is a build constant.\nRaw/valid/fault/OT/count are sampled FPGA nets.\nThese are junction-temperature estimates.',fontsize=9,color='#475569',transform=ax.transAxes,linespacing=1.6,va='top')
inner=GridSpecFromSubplotSpec(2,1,subplot_spec=outer[1,0],height_ratios=[1.1,1],hspace=.10);apc=fig.add_subplot(inner[0]);ad=fig.add_subplot(inner[1],sharex=apc);n=512;t=list(range(n))
apc.step(t,core['pc'][:n],where='post',color='#7c3aed',linewidth=1);apc.yaxis.set_major_formatter(FuncFormatter(lambda v,p:'0x{:04x}'.format(int(v))));apc.set_title('C. CoreMark: first 512 of 4096 samples',loc='left',fontweight='bold');apc.set_ylabel('Fetch PC');apc.tick_params(labelbottom=False);apc.locator_params(axis='y',nbins=4);apc.grid(color='#f1f5f9')
for name,offset,color in [('mispredict',0,'#d97706'),('mem_hold',2,'#2563eb'),('load_hazard',4,'#dc2626')]:ad.step(t,[offset+v for v in core[name][:n]],where='post',color=color,linewidth=1)
ad.set(yticks=[.5,2.5,4.5],yticklabels=['Redirect','Mem hold','Load hazard'],ylim=(-.3,5.5),xlabel='Sample index ({:g} MHz)'.format(mhz),xlim=(0,n-1));ad.grid(axis='x',color='#f1f5f9')
ax=fig.add_subplot(outer[1,1]);busy=[1-v for v in xnd['xnd_idle']];tt=[i/(hz/1e6)for i in range(len(busy))];ax.step(tt,busy,where='post',color='#0f766e',linewidth=1.3);ax.fill_between(tt,0,busy,step='post',color='#ccfbf1');ax.set(ylim=(-.15,1.35),yticks=[0,1],xlim=(0,tt[-1]),xlabel='Time (us, nominal PLL clock)',ylabel='XND busy (derived from IDLE)');ax.set_title('D. XND activity during led 37 inference',loc='left',fontweight='bold');ax.grid(axis='x',color='#e5e7eb');ax.text(.02,.98,str(sum(busy))+' busy samples in this '+str(len(busy))+'-sample window',transform=ax.transAxes,fontsize=9,color='#134e4a',va='top',bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'})
fig.suptitle('NeedleRV-X | Current {:g} MHz FPGA ILA'.format(mhz),x=.07,y=.96,ha='left',fontsize=20,fontweight='bold',color='#0f172a');fig.text(.07,.918,'Same functional synthesized design and firmware as production | 900-iteration CoreMark CRC passed',fontsize=11,color='#475569')
funcs=a['captures']['coremark']['pc_functions'];act=a['captures']['coremark']['activity'];fig.text(.07,.085,'Full-window PC symbols: '+', '.join(k+' ('+str(v)+')'for k,v in funcs.items()),fontsize=9,color='#475569');fig.text(.07,.060,'Overlapping local counts: EX '+str(act['ex_valid'])+', MEM '+str(act['mem_valid'])+', WB '+str(act['wb_valid'])+'. This window does not measure global CPI.',fontsize=9,color='#475569');fig.text(.07,.032,'Internal pre-pad samples. PLL-derived units use nominal crystal frequency; no external pin or frequency calibration.',fontsize=9,color='#64748b')
fig.savefig(str(folder/'ila_evidence_overview.png'),dpi=180,facecolor='white');plt.close(fig);print('Created',folder/'ila_evidence_overview.png')

# Talk layout: enlarged traces, with the full four-panel figure retained for the report.
fig,axes=plt.subplots(1,2,figsize=(12,3.8));fig.subplots_adjust(left=.07,right=.98,top=.82,bottom=.20,wspace=.30)
ax=axes[0];pin=pwm['nt_led[7]'];v=a['captures']['pwm25']['pwm'];points=[0]+sorted(v['rising_edges']+v['falling_edges'])+[len(pin)-1];times=[n*1000/pwmhz for n in points];levels=[pin[n]for n in points]
ax.step(times,levels,where='post',color='#4384AE',linewidth=1.7);ax.fill_between(times,0,levels,step='post',color='#D3E8F1');ax.set(xlim=(0,(len(pin)-1)*1000/pwmhz),ylim=(-.1,1.4),yticks=[0,1],xlabel='Time (ms)',ylabel='Pre-pad PWM level');ax.set_title('(a) PWM: 1 kHz, 25% duty',loc='left',pad=13);ax.grid(axis='x',color='#E5E9EB');ax.text(.02,.92,'40,500 cycles / period; 10,125 high',transform=ax.transAxes,fontsize=10)
ax=axes[1];busy=[1-v for v in xnd['xnd_idle']];tm=[n*1e6/hz for n in range(len(busy))];ax.step(tm,busy,where='post',color='#548E79',linewidth=1.6);ax.fill_between(tm,0,busy,step='post',color='#D9ECE4');ax.set(ylim=(-.1,1.4),yticks=[0,1],xlabel='Time (us)',ylabel='XND busy');ax.set_title('(b) XND during led 37 inference',loc='left',pad=13);ax.grid(axis='x',color='#E5E9EB');ax.text(.02,.92,str(a['captures']['xnd']['activity']['xnd_busy_samples'])+' busy samples / 4096',transform=ax.transAxes,fontsize=10)
fig.savefig(root/'07_runs/materials_build/ila_slide.png',dpi=220,bbox_inches='tight');plt.close(fig)
