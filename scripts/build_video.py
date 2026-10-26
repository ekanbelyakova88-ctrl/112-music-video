#!/usr/bin/env python3
"""Reproducible 1080p music-video renderer. Real inputs only; no fallback images."""
import argparse
import concurrent.futures
import hashlib
import json
import math
import subprocess
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT/'output/.render'

def run(args, log):
    with open(log, 'w') as f:
        p = subprocess.run(['ffmpeg','-hide_banner','-nostdin','-y',*args],stdout=f,stderr=subprocess.STDOUT)
    if p.returncode:
        raise RuntimeError(f'FFmpeg failed; see {log}\n'+Path(log).read_text()[-3500:])

def signature(parts):
    h=hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p,bytes) else str(p).encode())
    return h.hexdigest()

def cached(target, sig):
    stamp=target.with_suffix('.sha256')
    return target.exists() and stamp.exists() and stamp.read_text()==sig

def stamp(target,sig):
    target.with_suffix('.sha256').write_text(sig)

def check_inputs(timeline):
    for s in timeline['scenes']:
        p=ROOT/s['image']
        if not p.exists():
            raise FileNotFoundError(f'Missing real generated image: {p}')
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            if im.size!=(1920,1080):
                raise ValueError(f'{p}: expected 1920x1080, got {im.size}')

def render_scene(s,timeline,preset):
    fps=timeline['fps']; overlap=round(timeline['transition']*fps)
    # Extra frames after the outgoing cut feed the next scene's dissolve.
    members=[x for x in timeline['scenes'] if x['section']==s['section']]
    n=s['end_frame']-s['start_frame']+(overlap if s!=members[-1] else 0)
    p=ROOT/s['image']; target=CACHE/f"scene_{s['id']:03}.mp4"
    sig=signature([p.read_bytes(),n,s['motion'],preset,'zoom-v3'])
    if cached(target,sig): return target
    progress=f'on/{max(n-1,1)}'
    if s['motion']=='pull_back':
        z=f'1.10-0.07*{progress}'; x='iw/2-iw/zoom/2'; y='ih/2-ih/zoom/2'
    elif s['motion']=='drift_left':
        z='1.075'; x=f'(iw-iw/zoom)*(0.85-0.70*{progress})'; y='ih/2-ih/zoom/2'
    elif s['motion']=='drift_right':
        z='1.075'; x=f'(iw-iw/zoom)*(0.15+0.70*{progress})'; y='ih/2-ih/zoom/2'
    else:
        z=f'1.025+0.075*{progress}'; x='iw/2-iw/zoom/2'; y='ih/2-ih/zoom/2'
    # Upscale before zoompan for subpixel-smooth motion; image itself stays separate.
    vf=f"scale=2880:1620:flags=lanczos,zoompan=z='{z}':x='{x}':y='{y}':d={n}:s=1920x1080:fps={fps},setsar=1,format=yuv420p"
    run(['-threads','1','-i',str(p),'-vf',vf,'-frames:v',str(n),'-an',
         '-c:v','libx264','-preset',preset,'-crf','18','-threads','2','-filter_threads','1',
         '-pix_fmt','yuv420p','-r',str(fps),'-video_track_timescale','12800',str(target)],target.with_suffix('.log'))
    stamp(target,sig)
    return target

def render_chapter(group,clips,timeline,preset):
    target=CACHE/f"chapter_{group[0]['section']:02}.mp4"
    sig=signature([*(p.with_suffix('.sha256').read_text() for p in clips),timeline['transition'],preset,'xfade-v4-cfr'])
    if cached(target,sig): return target
    args=[]
    for p in clips: args+=['-threads','1','-i',str(p)]
    graph=[]
    for i in range(len(clips)):
        # Scene clips already start at PTS zero. setpts would strip frame-rate
        # metadata in FFmpeg 7.1, so retain timestamps and set an exact frame base.
        graph.append(f'[{i}:v]fps={timeline["fps"]},settb=1/{timeline["fps"]}[v{i}]')
    last='v0'; elapsed=0
    for i in range(1,len(clips)):
        elapsed+=group[i-1]['duration']
        label=f'x{i}'
        graph.append(f'[{last}][v{i}]xfade=transition=fade:duration={timeline["transition"]}:offset={elapsed:.6f},fps={timeline["fps"]}[{label}]')
        last=label
    n=sum(s['end_frame']-s['start_frame'] for s in group)
    run([*args,'-filter_complex_threads','1','-filter_complex',';'.join(graph),'-map',f'[{last}]',
         '-frames:v',str(n),'-an','-c:v','libx264','-preset',preset,'-crf','18','-threads','2',
         '-pix_fmt','yuv420p','-r',str(timeline['fps']),'-video_track_timescale','12800',str(target)],target.with_suffix('.log'))
    stamp(target,sig)
    return target

def ass_time(t):
    cs=round(t*100); h,cs=divmod(cs,360000); m,cs=divmod(cs,6000); s,cs=divmod(cs,100)
    return f'{h}:{m:02}:{s:02}.{cs:02}'

def titles(duration):
    head='''[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Noto Sans,57,&H00F7F4ED,&H000000FF,&HAD17120D,&H90000000,-1,0,0,0,100,100,1,0,1,2,2,2,90,90,110,1
Style: Small,Noto Sans,34,&H00F7F4ED,&H000000FF,&HAD17120D,&H90000000,0,0,0,0,100,100,5,0,1,2,1,2,90,90,70,1
Style: Hero,Noto Sans,220,&H00F7F4ED,&H000000FF,&HA017120D,&H90000000,-1,0,0,0,100,100,5,0,1,2,2,5,90,90,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    cues=[(1,8,'Main','112. НА ЛИНИИ ЖИЗНИ'),(1.8,8,'Small','ВЛАДИМИРСКАЯ ОБЛАСТЬ'),
          (43,50,'Main','МЫ РЯДОМ, КОГДА НУЖНА ПОМОЩЬ'),
          (118,125,'Main','ЗА КАЖДЫМ ЗВОНКОМ — ЧЬЯ-ТО ЖИЗНЬ'),
          (155,163,'Main','10 ЛЕТ НА СВЯЗИ'),
          (duration-16,duration-9,'Hero','112'),
          (duration-8.5,duration-.4,'Main','МЫ НА СВЯЗИ. ВСЕГДА')]
    path=CACHE/'titles.ass'
    events=[f'Dialogue: 0,{ass_time(a)},{ass_time(b)},{style},,0,0,0,,{{\\fad(800,800)}}{text}' for a,b,style,text in cues]
    path.write_text(head+'\n'.join(events)+'\n')
    return path

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--workers',type=int,default=2); ap.add_argument('--preset',default='fast'); ap.add_argument('--check-only',action='store_true')
    args=ap.parse_args()
    timeline=json.loads((ROOT/'storyboard/timeline.json').read_text())
    check_inputs(timeline)
    if args.check_only:
        print(f"All {len(timeline['scenes'])} full-size input images validated"); return
    CACHE.mkdir(parents=True,exist_ok=True)
    scenes=timeline['scenes']
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(render_scene,s,timeline,args.preset):s for s in scenes}
        for future in concurrent.futures.as_completed(futures):
            future.result(); print(f"Rendered scene {futures[future]['id']:03}",flush=True)
    chapters=[]
    for section in range(1,8):
        group=[s for s in scenes if s['section']==section]
        clips=[CACHE/f"scene_{s['id']:03}.mp4" for s in group]
        chapters.append(render_chapter(group,clips,timeline,args.preset))
        print(f'Rendered chapter {section}',flush=True)
    concat=CACHE/'chapters.txt'
    concat.write_text(''.join(f"file '{p}'\n" for p in chapters))
    ass=titles(timeline['duration'])
    output=ROOT/'output/112_music_video_final.mp4'
    d=timeline['duration']
    vf=f"ass=filename='{ass}',fade=t=in:st=0:d=0.8,fade=t=out:st={d-1.2:.3f}:d=1.2,format=yuv420p"
    run(['-f','concat','-safe','0','-i',str(concat),'-i',str(ROOT/timeline['audio']),
         '-map','0:v:0','-map','1:a:0','-vf',vf,'-filter_threads','1',
         '-c:v','libx264','-preset',args.preset,'-crf','18','-threads','4',
         '-pix_fmt','yuv420p','-r',str(timeline['fps']),'-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709',
         '-c:a','aac','-b:a','256k','-ar','48000',
         '-af','apad','-t',str(d),'-movflags','+faststart','-metadata','title=112. Мы на связи',
         '-metadata','comment=Художественный музыкальный клип. Вымышленные персонажи и ситуации.',str(output)],CACHE/'final.log')
    print(output,flush=True)

if __name__=='__main__':
    main()
