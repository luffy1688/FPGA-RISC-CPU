"""Encode the current 2x 3D record-replay explainer; no serial connection or board actions."""
from pathlib import Path
import json,subprocess
r=Path(__file__).resolve().parents[2];out=r/'参赛材料/展示素材';video=out/'三维流程演示_2倍速.mp4';gif=out/'三维流程演示_2倍速.gif'
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration:stream=codec_type,width,height,nb_frames,r_frame_rate','-of','json',str(video)]))
stream=next(v for v in probe['streams']if v['codec_type']=='video');assert stream['width']==1600 and stream['height']==900 and abs(float(probe['format']['duration'])-30)<.05 and int(stream['nb_frames'])==360
assert not any(v['codec_type']=='audio'for v in probe['streams'])
subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error','-i',str(video),'-filter_complex','[0:v]fps=8,scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=96:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4','-loop','0',str(gif)],check=True)
from PIL import Image
im=Image.open(gif);assert im.size==(960,540)and im.n_frames==240
duration=sum(im.seek(i)or im.info.get('duration',0)for i in range(im.n_frames));assert abs(duration-30000)<150
info=dict(scope='Rendered 3D structural explainer with actual accepted UART-record replay; not a new live board or second-screen recording.',firmware='experimental_position_fusion_oct30',date='2026-10-31',pace_factor=2,source_teaching_duration_seconds=60,seconds=30,dimensions=[1600,900],video_fps=12,gif_dimensions=[960,540],gif_fps=8,gif_frames=im.n_frames,burned_in_captions=True,audio=False,sidecar_subtitle='展示字幕.srt',narration_script='展示解说稿.md',video=video.name,gif=gif.name,webpage='成果展示.html',native_model='NeedleRV-X_逻辑结构.glb',record_case_ids={key:value['wire_result']['case']for key,value in json.loads((r/'05_tools/console/showcase_data.json').read_text())['records'].items()},timing_scope='Animation stage duration does not measure FPGA execution; measured native/model/CoreMark times are displayed separately.',real_webgl_rendered=True,serial_opened=False,powerpoint_native_rotation_scope='Editing mode in compatible PowerPoint; slideshow free-orbit via offline HTML link.')
(out/'media_info.json').write_text(json.dumps(info,ensure_ascii=False,indent=2)+'\n')
(out/'展示解说稿.md').write_text("""# 三十秒展示解说稿

成片为2倍速结构讲解与2026年10月31日实测记录回放，无预置配音。字幕已写入MP4和GIF，旁白可后期录制。动画阶段时长不是FPGA执行时间。

## 连贯配音

这是NeedleRV-X的板上运维链路。明确命令先过语法与许可，执行后回读。模糊表达进入位置语义分支，用八路MAC和常驻缓存判断语境；需要时再运行四路低比特编码器。最终工具仍受参数和能力约束。伪造成绩被拒绝。CoreMark返回真实CRC与计时。快路径、模型与基准耗时分别记录。

## 画面顺序

|成片时间|画面与讲解重点|
|---|---|
|0—7.5秒|整体结构、显式快路径、LED37的真实回读|
|7.5—12.5秒|全局与首尾位置特征、8MAC语义头与常驻缓存|
|12.5—17.5秒|学习型短语记忆、4MAC字节编码器|
|17.5—22.5秒|工具许可、PWM周期40500与高电平8100回读|
|22.5—25秒|拒绝伪造CoreMark成绩|
|25—30秒|真实基准证据与三种时间口径|

快路径1.40—5.16ms是四句各n10的原生往返中位数；完整PWM模型74.567ms，其中语义区间0.837ms。CoreMark1200迭代约14.585173秒，四次CRC均通过。30秒视频没有重新运行基准，也不代替连续实板原片。
""",encoding='utf-8')
for name in ['实测截图讲解.mp4','实测截图讲解.gif']:
 old=out/name
 if old.exists():old.unlink()
print(json.dumps(dict(mp4_seconds=probe['format']['duration'],frames=stream['nb_frames'],gif_frames=im.n_frames,gif_duration_ms=duration,mp4_bytes=video.stat().st_size,gif_bytes=gif.stat().st_size)))
