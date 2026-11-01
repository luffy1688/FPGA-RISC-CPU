from pathlib import Path
import json,importlib.util
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
r=Path('/work/LUO/NeedleRV-X');f=r/'07_runs/board/20261028_review_acceptance/ila'
s=importlib.util.spec_from_file_location('reader',r/'05_tools/board/analyze_ila.py');reader=importlib.util.module_from_spec(s);s.loader.exec_module(reader)
m=json.loads((r/'06_pango_review_ila_20261028/signal_map_bound.json').read_text());a=json.loads((f/'analysis.json').read_text());phase=json.loads((f.parent/'ila_capture_report.json').read_text())
core=reader.decode(f/'coremark.wdf',m['core0']);xnd=reader.decode(f/'xnd.wdf',m['core0']);pwm=reader.decode(f/'pwm25.wdf',m['core1'])
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(3,2,figsize=(14,12));fig.subplots_adjust(top=.87,bottom=.12,hspace=.62,wspace=.30)
ax=axes[0,0];v=pwm['nt_led[7]'];z=a['captures']['pwm25']['pwm'];pts=[0]+sorted(z['rising_edges']+z['falling_edges'])+[len(v)-1];ax.step([i/27 for i in pts],[v[i]for i in pts],where='post',color='#2563eb');ax.set(ylim=(-.1,1.4),yticks=[0,1],xlabel='Time (us, nominal 27 MHz)',ylabel='GPIO7 before pad',title='A. Physical internal PWM')
ax.text(0,-.30,'Periods: '+str(z['period_samples'])+' samples; high: '+str(z['high_samples']),transform=ax.transAxes,fontsize=8)
ax=axes[0,1];ax.axis('off');ax.set_title('B. ADC snapshots: captured live nets',loc='left');rows=[]
for tag in ['adc_a','adc_b']:
 q=a['captures'][tag]['adc'];rows.append([tag,str(q['raw_codes']),str(q['sample_counter']['min']),str(q['centidegrees_from_raw'])])
tab=ax.table(cellText=rows,colLabels=['Capture','Raw','Counter','T (0.01 C)'],cellLoc='center',bbox=[0,.32,1,.5]);tab.auto_set_font_size(False);tab.set_fontsize(9)
ax.text(0,.16,'Counter delta (mod 32 bits): '+str(a['adc_sample_counter_delta_mod32']),transform=ax.transAxes)
ax=axes[1,0];n=512;ax.step(range(n),core['pc'][:n],where='post',color='#7c3aed',lw=1);ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:'0x%x'%int(v)));ax.set(xlabel='Sample index',ylabel='CPU PC',title='C. Current CoreMark / current ELF (512 samples)');functions=a['captures']['coremark']['pc_functions'];ax.text(0,-.32,', '.join('%s: %s'%(k,v)for k,v in list(functions.items())[:3]),transform=ax.transAxes,fontsize=8)
ax=axes[1,1];names=['fetch_active','id_valid','ex_valid','mem_valid','wb_valid']
for off,name in enumerate(names):ax.step(range(n),[off*2+x for x in core[name][:n]],where='post',lw=.9)
ax.set(yticks=[i*2+.5 for i in range(5)],yticklabels=names,xlabel='Sample index',title='D. Pipeline validity (occupancy, not IPC/CPI)',xlim=(0,n-1))
ax=axes[2,0];v=[1-x for x in xnd['xnd_idle']];ax.step([i/27 for i in range(len(v))],v,where='post',color='#0f766e',lw=1);ax.set(ylim=(-.1,1.3),yticks=[0,1],xlabel='Time (us, nominal 27 MHz)',ylabel='XND busy from IDLE',title='E. Actual led 37 XND activity');ax.text(0,-.28,'Busy samples: %d / %d'%(sum(v),len(v)),transform=ax.transAxes)
ax=axes[2,1];ax.axis('off');activity=a['captures']['coremark']['activity'];rows=[[k,str(v)]for k,v in activity.items()if k in names+['mispredict','mem_hold','load_hazard']];table=ax.table(cellText=rows,colLabels=['CoreMark captured signal','High samples / 4096'],cellLoc='left',bbox=[0,0,1,.95]);table.auto_set_font_size(False);table.set_fontsize(9);ax.set_title('F. Local-window counts; counters may overlap',loc='left')
for ax in axes.flat:
 if ax.axison:ax.grid(axis='x',color='#e5e7eb')
fig.suptitle('NeedleRV-X | current same-source ILA evidence',x=.07,y=.97,ha='left',fontsize=20,fontweight='bold')
fig.text(.07,.93,'Production '+phase['production_sbit_sha256'][:16]+'...  |  ILA '+phase['ila_sbit_sha256'][:16]+'...',fontsize=10)
fig.text(.07,.90,'Same functional RTL / ROM; current ELF matched to ROM. Whole-program CoreMark CRC is checked in UART separately.',fontsize=10)
fig.text(.07,.025,'Internal FPGA samples. Clock units use nominal 27 MHz; no external pin waveform, measured FMAX, or global CPI claim from these windows.',fontsize=9,color='#475569')
fig.savefig(f/'ila_evidence_overview.png',dpi=180,facecolor='white');plt.close(fig);print(f/'ila_evidence_overview.png')
