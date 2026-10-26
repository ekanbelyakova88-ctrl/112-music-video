#!/usr/bin/env python3
"""Package source, separate assets and finished film, excluding Git and render cache."""
import argparse
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=ROOT.parent/'112-music-video_project.zip')
    args=ap.parse_args()
    files=[ROOT/'README.md',ROOT/'requirements.txt',ROOT/'.gitignore']
    for directory in ['assets','scripts','storyboard']:
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for name in ['112_music_video_final.mp4','validation.json']:
        p=ROOT/'output'/name
        if not p.exists(): raise FileNotFoundError(p)
        files.append(p)
    with zipfile.ZipFile(args.output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
        for p in sorted(files): z.write(p,ROOT.name+'/'+p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(args.output) as z:
        bad=z.testzip()
        if bad: raise RuntimeError(f'Archive checksum failed: {bad}')
        print(f'{args.output}: {len(z.namelist())} files, {args.output.stat().st_size} bytes')

if __name__=='__main__':
    main()
