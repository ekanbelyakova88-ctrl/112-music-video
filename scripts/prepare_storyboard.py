#!/usr/bin/env python3
"""Measure the real soundtrack and build a frame-accurate editorial timeline."""
import json
import subprocess
from pathlib import Path
import numpy as np
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parents[1]
FPS = 25

def main():
    song = ROOT / 'assets/audio/song.mp3'
    meta = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(song)]))
    duration = float(meta['format']['duration'])
    pcm = subprocess.check_output(['ffmpeg','-v','error','-i',str(song),'-vn','-ac','1','-ar','16000','-f','f32le','-'])
    x = np.frombuffer(pcm, dtype='<f4')
    hop = 1600
    n = len(x)//hop
    rms = np.sqrt(np.mean(x[:n*hop].reshape(n,hop)**2, axis=1))
    novelty = np.maximum(0, np.diff(rms, prepend=rms[0]))
    peaks, _ = find_peaks(novelty, distance=3, prominence=.007)
    onsets = peaks/10
    scenes = json.loads((ROOT/'storyboard/scenes.json').read_text())
    # Seven narrative chapters; individual cuts follow nearby measured musical attacks.
    chapter_edges = [0,35,70,103,145,193,225,duration]
    frame_count = round(duration*FPS)
    previous = 0
    for group in range(7):
        members = [s for s in scenes if s['section']==group+1]
        a,b = chapter_edges[group:group+2]
        # Hold wide / concluding shots longer; shorten inserts for a varied rhythm.
        wide={1,2,3,4,5,8,30,38,43,45,46,50,51,52}
        inserts={9,10,13,29,36,37,48}
        weights = np.array([1.25 if s['id'] in wide else .70 if s['id'] in inserts else 1.0 for s in members])
        targets = a+(b-a)*np.cumsum(weights)/weights.sum()
        for j,s in enumerate(members):
            target = targets[j]
            candidates = onsets[np.abs(onsets-target)<.45]
            if j<len(members)-1 and len(candidates):
                target = min(candidates, key=lambda t: abs(t-target))
            end = round(target*FPS)
            if group==6 and j==len(members)-1:
                end=frame_count
            s.update(start_frame=previous,end_frame=end,start=previous/FPS,end=end/FPS,duration=(end-previous)/FPS,
                     motion=['push_in','drift_left','pull_back','drift_right'][s['id']%4])
            previous=end
    timeline = dict(fps=FPS,width=1920,height=1080,duration=frame_count/FPS,audio_duration=duration,
                    audio='assets/audio/song.mp3',transition=.64,scenes=scenes)
    (ROOT/'storyboard/timeline.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2)+'\n')
    analysis = dict(duration=duration,decoded_samples=len(x),analysis_sample_rate=16000,
                    method='100 ms RMS positive-rise onset detection; editorial chapters, not a lyric transcription',
                    onset_seconds=onsets.tolist(),rms_10s=[float(np.mean(rms[i:i+100])) for i in range(0,n,100)])
    (ROOT/'storyboard/audio_analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
    lines=['# «112. Мы на связи» — раскадровка','',
           f'Музыка: {duration:.3f} с. Монтаж: {FPS} кадров/с, {frame_count} кадров, 1920 × 1080.',
           'Все сцены художественные, персонажи вымышлены. Помещение — по текстовому описанию заказчика; фотографий диспетчерской не предоставлено.',
           'Границы кадров привязаны к измеренным атакам звука в пределах 0,45 с от монтажного ритма. Это инструментальный анализ, а не расшифровка текста песни.',
           'Движение камеры создаётся из отдельных фотографических кадров; исходных движущихся видеосцен нет.','',
           '| № | Начало, с | Конец, с | Часть | Кадр | Файл |','|---|---:|---:|---|---|---|']
    for s in scenes:
        lines.append(f"| {s['id']:03} | {s['start']:.2f} | {s['end']:.2f} | {s['chapter']} | {s['title']} | {s['image']} |")
    (ROOT/'storyboard/README.md').write_text('\n'.join(lines)+'\n')
    prompts=['# Индивидуальные запросы генерации','', 'Один запрос — один самостоятельный кадр. Никаких коллажей.','']
    for s in scenes:
        prompts += [f"## {s['id']:03}. {s['title']}",'',s['prompt'],'']
    (ROOT/'storyboard/prompts.md').write_text('\n'.join(prompts))
    print(f'{len(scenes)} scenes, {frame_count} frames, {duration:.3f}s')

if __name__=='__main__':
    main()
