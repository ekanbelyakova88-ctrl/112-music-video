#!/usr/bin/env python3
"""Validate actual image assets, video decode, runtime, and soundtrack continuity."""
import hashlib
import json
import subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.signal import correlate

ROOT=Path(__file__).resolve().parents[1]

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(path)]))

def pcm(path):
    return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0','-ac','1','-ar','16000','-f','f32le','-']),dtype='<f4')

def main():
    t=json.loads((ROOT/'storyboard/timeline.json').read_text())
    images=[]
    for s in t['scenes']:
        p=ROOT/s['image']
        with Image.open(p) as im:
            im.verify()
        with Image.open(p) as im:
            assert im.size==(1920,1080),(str(p),im.size)
        images.append(dict(id=s['id'],file=s['image'],width=1920,height=1080,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    assert len(images)==52
    assert len({i['sha256'] for i in images})==52,'Duplicated image files'
    movie=ROOT/'output/112_music_video_final.mp4'
    meta=probe(movie)
    video=next(s for s in meta['streams'] if s['codec_type']=='video')
    audio=next(s for s in meta['streams'] if s['codec_type']=='audio')
    assert video['codec_name']=='h264' and audio['codec_name']=='aac'
    assert (video['width'],video['height'])==(1920,1080)
    assert video['avg_frame_rate']=='25/1'
    assert int(video['nb_frames'])==round(t['duration']*25)
    assert abs(float(meta['format']['duration'])-t['audio_duration'])<=.05
    decode=subprocess.run(['ffmpeg','-v','error','-i',str(movie),'-map','0:v:0','-map','0:a:0','-f','null','-'],capture_output=True,text=True)
    assert decode.returncode==0 and not decode.stderr,decode.stderr
    original=pcm(ROOT/t['audio']); rendered=pcm(movie)
    assert len(rendered)>=len(original)-160,'Output soundtrack is truncated'
    count=min(len(original),len(rendered))
    full_score=float(np.dot(original[:count],rendered[:count])/(np.linalg.norm(original[:count])*np.linalg.norm(rendered[:count])))
    assert full_score>.97,('Full soundtrack mismatch',full_score)
    checks=[]
    # Compare three separated portions: no speed change, missing verse, or wrong music.
    for start in [3, len(original)/16000/2, len(original)/16000-9]:
        pos=int(start*16000); a=original[pos:pos+5*16000]
        b=rendered[pos-1600:pos+len(a)+1600]
        c=correlate(b,a,mode='valid',method='fft')
        at=int(np.argmax(c)); match=b[at:at+len(a)]
        score=float(np.dot(a,match)/(np.linalg.norm(a)*np.linalg.norm(match)))
        lag=at-1600
        assert score>.97,(start,score)
        assert abs(lag)<160,(start,lag)
        checks.append(dict(at_seconds=start,correlation=score,offset_samples_16khz=lag))
    report=dict(status='passed',image_count=len(images),images=images,
                full_decode='passed, no decoding errors',video_codec=video['codec_name'],audio_codec=audio['codec_name'],
                resolution=[video['width'],video['height']],fps=video['avg_frame_rate'],frames=int(video['nb_frames']),
                video_duration=float(meta['format']['duration']),source_duration=t['audio_duration'],
                decoded_source_audio_seconds=len(original)/16000,decoded_output_audio_seconds=len(rendered)/16000,
                full_track_audio_correlation=full_score,audio_continuity=checks,bytes=movie.stat().st_size,
                movie_sha256=hashlib.sha256(movie.read_bytes()).hexdigest(),
                source_audio_sha256=hashlib.sha256((ROOT/t['audio']).read_bytes()).hexdigest(),
                note='Technical checks do not certify visual anatomy, signage or geographic accuracy; those require visual review.')
    (ROOT/'output/validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='images'},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
