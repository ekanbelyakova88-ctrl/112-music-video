#!/usr/bin/env python3
"""Import separately generated scene_NNN images, normalizing them for the edit."""
import argparse
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory',type=Path)
    ap.add_argument('--replace',action='store_true',help='Explicitly allow replacing existing scene files')
    args=ap.parse_args()
    dest=ROOT/'assets/images';dest.mkdir(parents=True,exist_ok=True)
    for i in range(1,53):
        stem=f'scene_{i:03}'
        sources=[p for ext in ['png','jpg','jpeg'] if (p:=args.directory/f'{stem}.{ext}').is_file()]
        if not sources: continue
        if len(sources)>1: raise ValueError(f'Ambiguous source for {stem}')
        out=dest/f'{stem}.png'
        if out.exists() and not args.replace: raise FileExistsError(f'{out}; use --replace deliberately')
        if sources[0].resolve()==out.resolve(): raise ValueError('Input and output must differ')
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(sources[0]),'-vf',
            'scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1',
            '-frames:v','1',str(out)],check=True)
        print(out)

if __name__=='__main__':
    main()
