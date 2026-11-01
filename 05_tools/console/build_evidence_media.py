"""Encode the current 3x graphics explainers; does not touch board data."""
from pathlib import Path
import json,subprocess
from PIL import Image
r=Path('/work/LUO/NeedleRV-X');o=r/'参赛材料/展示素材'
videos=['三维流程演示_3倍速.mp4','三维模型_旋转分层.mp4']
reports=[]
for name in videos:
 p=o/name;d=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(p)],universal_newlines=True));v=next(x for x in d['streams']if x['codec_type']=='video')
 assert v['codec_name']=='h264'and abs(float(d['format']['duration'])-20)<.06 and not any(x['codec_type']=='audio'for x in d['streams'])
 g=p.with_suffix('.gif');scale='scale=960:-1:flags=lanczos,'if v['width']==1600 else''
 filt='[0:v]fps=8,'+scale+'split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle'
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(p),'-filter_complex',filt,'-loop','0',str(g)],check=True)
 im=Image.open(g);duration=0
 for f in range(im.n_frames):im.seek(f);duration+=im.info.get('duration',0)
 assert abs(duration-20000)<150
 reports.append(dict(video=name,gif=g.name,seconds=float(d['format']['duration']),dimensions=[v['width'],v['height']],gif_dimensions=list(im.size),gif_frames=im.n_frames,gif_duration_ms=duration,mp4_bytes=p.stat().st_size,gif_bytes=g.stat().st_size))

# The short animations retain their 8-second reading time.
subprocess.run(['python3',str(r/'05_tools/evidence/build_ppt_explanation_gifs.py')],check=True)
short=[]
for name in ['双路径流程_讲解动画.gif','模型与资源_证据动画.gif']:
 im=Image.open(o/name);duration=0
 for f in range(im.n_frames):im.seek(f);duration+=im.info.get('duration',0)
 assert abs(duration-8000)<100
 short.append(dict(gif=name,seconds=duration/1000,dimensions=list(im.size),frames=im.n_frames,bytes=(o/name).stat().st_size))

info=o/'media_info.json';m=json.loads(info.read_text());m.update(display_name='澄灯 LumaRV',scenario='工业检修照明与状态指示',date='2026-11-01',pace_factor=3,source_teaching_duration_seconds=60,seconds=20,video='三维流程演示_3倍速.mp4',gif='三维流程演示_3倍速.gif',gif_frames=reports[0]['gif_frames'],native_model='LumaRV_逻辑结构.glb')
m['scope']='Logical structure and request walkthrough using saved board results.'
m['labeled_model_animation'].update(duration_seconds=20,pace_factor=3,video='三维模型_旋转分层.mp4',gif='三维模型_旋转分层.gif',gif_frames=reports[1]['gif_frames'])
m['media_outputs']=reports;m['short_animations']=short
m['record_case_ids']['reject']=next(x for x in json.loads((r/'07_runs/board/current/all_four_batches_921600.json').read_text())['checks']if x['id']=='B4_09')['actual']['case']
info.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
(o/'展示解说稿.md').write_text('''# 二十秒结构展示解说

澄灯面向工业检修照明与状态指示。位置语境和短语记忆识别请求，八路语义侧核配合权重缓存，四路MAC计算编码。CPU核对工具与参数，PWM设置后读回；频率越界则拒绝，输出保持。

| 时间 | 画面 |
|---|---|
| 0—5秒 | 灯控任务、机器语法和LED37读回 |
| 5—10秒 | 首尾位置特征、8MAC语义核、字符短语记忆 |
| 10—15秒 | 4MAC编码、CPU修正与许可、PWM20%读回 |
| 15—20秒 | PWM频率修改被拒绝、CPU自检、请求返回 |

成片为3倍速逻辑结构与运行记录讲解，字幕已嵌入；无音轨，可后期配音。完整中文PWM模型74.567ms，控制往返1.40—5.16ms与CoreMark约14.585秒分别显示。
''',encoding='utf-8')
print(json.dumps(dict(main=reports,short=short,native_model_bytes=(o/'LumaRV_逻辑结构.glb').stat().st_size),ensure_ascii=False))
