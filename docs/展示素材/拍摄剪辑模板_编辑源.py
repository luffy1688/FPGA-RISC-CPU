#!/usr/bin/env python3
"""165-second filming/editing scaffold, not a finished hardware demonstration.

Requirements: Python3/Pillow, ffmpeg, ffprobe; already present on the project server.
Default output: 拍摄剪辑模板.mp4 beside this script. No audio is read or copied.

Create the empty template:
  python3 拍摄剪辑模板_编辑源.py
Replace a chapter with a real landscape clip (chapter numbers 1..8):
  python3 拍摄剪辑模板_编辑源.py --clip '2=/path/board.mp4' --clip '3=/path/pwm.mp4' --output /path/review_cut.mp4
Use --font with a CJK font if not on the project server.

Edit the TIMELINE list below to change titles, durations or shooting notes.
Real operation clips are not looped, accelerated, or extended automatically.
If a real clip is too short for a chapter, supply a longer clip or deliberately
edit that chapter's duration; retain the complete CoreMark start/CRC/end.
Still images are accepted only for the title, board overview, 3D and ending.
GIFs may loop only in chapter6, explicitly a logical-structure animation.
No original example-video picture or audio is incorporated by this script.
Narration and formal subtitle files are separate; these cards show shot cues only.
"""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import argparse,json,math,subprocess,tempfile

TIMELINE=[{'key': 1, 'duration': 25, 'title': '任务与开发板原型', 'window': '板卡与控制台同框', 'cue': '固定测试后追加单项复测，保留其他状态。', 'placeholder': '待替换实拍'}, {'key': 2, 'duration': 30, 'title': '后台计算与中文PWM', 'window': '副核忙碌 → 完整模型返回', 'cue': '保留一段连续镜头，显示忙碌期间主核完成模型。', 'placeholder': '待替换实拍'}, {'key': 3, 'duration': 20, 'title': 'PWM寄存器读回', 'window': '请求20%与当次返回', 'cue': '周期54000、高电平10800；区分既有模型统计和当次读数。', 'placeholder': '待替换实拍'}, {'key': 4, 'duration': 25, 'title': '位保持与越界拒绝', 'window': '默认混合路径', 'cue': '拍37→36与拒绝前后的PWM设置。', 'placeholder': '待替换实拍'}, {'key': 5, 'duration': 25, 'title': 'CPU计算检查', 'window': '两核CRC与共同计时', 'cue': '各3000次，主核统计与双实例累计单列。', 'placeholder': '待替换实拍'}, {'key': 6, 'duration': 20, 'title': '三维逻辑结构', 'window': '分层、合拢、PWM流程', 'cue': '插入现有20秒成片，不再重复加速。', 'placeholder': '待替换逻辑结构与方法图'}, {'key': 7, 'duration': 10, 'title': '模型方法', 'window': '位置语义、工具残差与低比特计算', 'cue': '保留参考Needle和训练来源，不逐位朗读长数字。', 'placeholder': '待替换逻辑结构与方法图'}, {'key': 8, 'duration': 10, 'title': '日志与结束', 'window': '导出当次日志', 'cue': '回到作品题名；正式视频须替换占位镜头。', 'placeholder': '待替换实拍'}]
WIDTH,HEIGHT,FPS=1280,720,24
BOX=(64,110,1152,540)
BLUE='#143295';GOLD='#C89B61';INK='#28384A';MUT='#65758A';GRID='#DCE3EC';PALE='#F4F6F9'
def run(cmd):return subprocess.run([str(x)for x in cmd],check=True)
def fontfile(explicit):
 options=[explicit,'/usr/share/fonts/google-noto-cjk/NotoSansCJK-Regular.ttc','C:/Windows/Fonts/msyh.ttc']
 for x in options:
  if x and Path(x).is_file():return str(x)
 raise RuntimeError('Specify a readable CJK font with --font')
def probe(path):
 return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)],universal_newlines=True))
def tc(sec):return '%02d:%02d'%(sec//60,sec%60)
def draw_base(chapter,start,end,font_path,with_placeholder=True):
 im=Image.new('RGB',(WIDTH,HEIGHT),'white');d=ImageDraw.Draw(im)
 f=lambda size:ImageFont.truetype(font_path,size)
 def center(t,y,size,col):
  bounds=d.textbbox((0,0),t,font=f(size));d.text(((WIDTH-(bounds[2]-bounds[0]))/2,y),t,font=f(size),fill=col)
 d.text((64,21),chapter['title'],font=f(33),fill=BLUE)
 d.text((992,32),tc(start)+' — '+tc(end),font=f(21),fill=MUT)
 d.line((64,83,1216,83),fill=GOLD,width=3)
 x,y,w,h=BOX
 if with_placeholder:
  d.rectangle((x,y,x+w,y+h),fill=PALE,outline=GRID,width=2)
  center(chapter['placeholder'],y+181,34,BLUE)
  center(chapter['window'],y+242,27,INK)
  center('请替换为本项目素材，勿使用示例视频画面',y+299,19,MUT)
  if chapter['key']==1:center('澄灯 LumaRV',y+99,43,BLUE)
  # Timeline tag remains a shot marker, not a fabricated measurement.
  d.text((x+22,y+20),'镜头 %02d / 08'%chapter['key'],font=f(19),fill=MUT)
 d.text((64,666),chapter['cue'],font=f(21),fill=INK)
 d.text((64,702),'仅为拍摄剪辑模板 · 待替换真实素材 · 无配音',font=f(12),fill=MUT)
 return im

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,default=Path(__file__).with_name('拍摄剪辑模板.mp4'))
 parser.add_argument('--clip',action='append',default=[],metavar='CHAPTER=PATH')
 parser.add_argument('--font')
 args=parser.parse_args();font=fontfile(args.font);clips={}
 for item in args.clip:
  key,value=item.split('=',1);key=int(key);assert 1<=key<=8;clips[key]=Path(value).expanduser().resolve();assert clips[key].is_file()
 assert sum(x['duration']for x in TIMELINE)==165,'Default official-format scaffold is2m45s; change the bound only deliberately.'
 args.output.parent.mkdir(parents=True,exist_ok=True)
 with tempfile.TemporaryDirectory(prefix='needlervx_shooting_')as temp:
  temp=Path(temp);segments=[];start=0
  for chapter in TIMELINE:
   n=chapter['key'];dur=chapter['duration'];end=start+dur;clip=clips.get(n);segment=temp/('shot%02d.mp4'%n)
   bg=temp/('card%02d.png'%n);draw_base(chapter,start,end,font,with_placeholder=clip is None).save(bg)
   base=['ffmpeg','-hide_banner','-loglevel','error','-y']
   codec=['-r',str(FPS),'-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-an','-movflags','+faststart',str(segment)]
   if clip is None:
    run(base+['-loop','1','-framerate',str(FPS),'-i',bg,'-t',str(dur)]+codec)
   else:
    suffix=clip.suffix.lower();still=suffix in ['.png','.jpg','.jpeg','.webp'];gif=suffix=='.gif'
    if still and n not in [1,6,7,8]:raise RuntimeError('Action chapter%d requires a continuous video, not a still image.'%n)
    if gif and n!=6:raise RuntimeError('Do not loop action footage; animated loops are allowed only in the logical3D chapter.')
    info=probe(clip);stream=next(x for x in info['streams']if x['codec_type']=='video')
    if not still and not gif:
     actual=float(info['format'].get('duration',stream.get('duration',0)))
     if actual+1/FPS<dur:raise RuntimeError('Chapter%d needs%dseconds, but clip is%.3fseconds. Record more or deliberately change the chapter duration; no silent looping/speedup.'%(n,dur,actual))
    x,y,w,h=BOX
    source=(['-loop','1']if still else['-stream_loop','-1']if gif else[])+['-i',clip]
    filt='[1:v]scale=%d:%d:force_original_aspect_ratio=decrease,pad=%d:%d:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1[shot];[0:v][shot]overlay=%d:%d:shortest=1[v]'%(w,h,w,h,x,y)
    run(base+['-loop','1','-framerate',str(FPS),'-i',bg]+source+['-filter_complex',filt,'-map','[v]','-t',str(dur)]+codec)
   segments.append(segment);start=end;print('CHAPTER',n,tc(start),flush=True)
  listing=temp/'chapters.txt';listing.write_text('\n'.join("file '"+str(x).replace("'","'\\''")+"'"for x in segments)+'\n')
  run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',listing,'-map','0:v:0','-c','copy','-an','-movflags','+faststart',args.output])
 info=probe(args.output);video=next(x for x in info['streams']if x['codec_type']=='video');duration=float(info['format']['duration'])
 assert abs(duration-165)<.15 and video['codec_name']=='h264'and video['width']==1280 and video['height']==720 and not any(x['codec_type']=='audio'for x in info['streams'])
 assert args.output.stat().st_size<300_000_000
 print(json.dumps({'output':str(args.output),'duration_seconds':duration,'video_codec':video['codec_name'],'resolution':[1280,720],'frame_rate':video['r_frame_rate'],'audio_streams':0,'bytes':args.output.stat().st_size,'placeholder_template':not bool(clips),'real_hardware_footage':False if not clips else'provided_by_user'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
