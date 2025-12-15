#!/usr/bin/env python3
"""UGC pipeline (basic).

Downloads supplier UGC videos, verifies license manifest, transcodes to 9:16 and 1:1.
This implementation is conservative and uses ffmpeg if available (recommended) or falls back to no-op.
"""
import argparse
import json
import os
import sys
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import requests


def download_file(url, dest):
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    with open(dest, 'wb') as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)


def ffmpeg_available():
    return subprocess.call(['which', 'ffmpeg'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def transcode(input_path, out_path, resolution):
    # resolution: (w,h)
    if not ffmpeg_available():
        raise RuntimeError('ffmpeg not available')
    w,h = resolution
    cmd = ['ffmpeg', '-y', '-i', str(input_path), '-vf', f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2', '-c:v', 'libx264', '-crf', '23', '-preset', 'medium', str(out_path)]
    subprocess.check_call(cmd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle-dir', required=False)
    parser.add_argument('--out', required=False)
    args = parser.parse_args()

    if args.bundle_dir:
        bundle = Path(args.bundle_dir)
        out_root = bundle / 'videos'
        manifest_path = bundle / 'manifest.json'
        if not manifest_path.exists():
            print(f"FAIL_REASON=manifest_missing path={manifest_path} NEXT_FIX=Run copy_normalize first", file=sys.stderr)
            sys.exit(2)
        with open(manifest_path, encoding='utf-8') as mf:
            manifest = json.load(mf)
    else:
        if not args.out:
            print("FAIL_REASON=invalid_args NEXT_FIX=Provide --bundle-dir or --out", file=sys.stderr)
            sys.exit(1)
        out_root = Path(args.out)
        manifest = []

    out_root.mkdir(parents=True, exist_ok=True)

    qa = {'processed': 0, 'skipped': 0, 'per_sku': {}}

    # Gate mode: STRICT_REAL_UGC (require supplier ugc_url), or ALLOW_TEMPLATE (allow generated montage)
    MODE = os.environ.get('MODE', 'ALLOW_TEMPLATE')

    for prod in manifest:
        sku = prod.get('sku')
        ugc_url = prod.get('ugc_url')
        license_field = prod.get('license')
        sku_dir = out_root / sku
        sku_dir.mkdir(parents=True, exist_ok=True)

        try:
            if ugc_url and license_field:
                # download supplier UGC
                parsed = urlparse(ugc_url)
                local = sku_dir / os.path.basename(parsed.path)
                download_file(ugc_url, local)
                # transcode
                out9 = sku_dir / 'ugc_9x16.mp4'
                out1 = sku_dir / 'ugc_1x1.mp4'
                transcode(local, out9, (1080, 1920))
                transcode(local, out1, (1080, 1080))
                qa['processed'] += 1
                qa['per_sku'][sku] = {'status': 'supplier', 'outputs': [str(out9), str(out1)], 'license': license_field}
            else:
                # generate montage from images in bundle/images/<sku>
                img_dir = Path(args.bundle_dir) / 'images' / sku
                imgs = sorted([str(p) for p in img_dir.glob('*.jpg')]) if img_dir.exists() else []
                if not imgs:
                    qa['skipped'] += 1
                    qa['per_sku'][sku] = {'status': 'no_images', 'reason': 'no images to generate UGC'}
                    print(f"WARN=ugc_generation_missing_images sku={sku} NEXT_FIX=Ensure images exist for SKU", file=sys.stderr)
                    continue
                # create 9:16
                out9 = sku_dir / 'ugc_9x16.mp4'
                out1 = sku_dir / 'ugc_1x1.mp4'
                # use ffmpeg to create slideshow
                # create 9:16 and 1:1 montages robustly by normalizing each input to the same canvas
                inputs = len(imgs)
                target9 = (1080, 1920)
                target1 = (1080, 1080)

                def build_slideshow(out_path, target_w, target_h):
                    cmd = ['ffmpeg', '-y']
                    for im in imgs:
                        cmd.extend(['-loop', '1', '-t', '3', '-i', im])

                    # per-input scale+pad to ensure identical frames, then concat
                    filter_parts = []
                    for i in range(inputs):
                        filter_parts.append(
                            f'[{i}:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]'
                        )
                    concat_inputs = ''.join(f'[v{i}]' for i in range(inputs))
                    filter_complex = ';'.join(filter_parts) + ';' + concat_inputs + f'concat=n={inputs}:v=1:a=0,format=yuv420p'

                    cmd.extend(['-filter_complex', filter_complex, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', '30', str(out_path)])
                    subprocess.check_call(cmd)

                # Build 9:16 slideshow
                try:
                    build_slideshow(out9, target9[0], target9[1])
                except subprocess.CalledProcessError as e:
                    raise
                # Build 1:1 slideshow
                try:
                    build_slideshow(out1, target1[0], target1[1])
                except subprocess.CalledProcessError as e:
                    raise
                qa['processed'] += 1
                qa['per_sku'][sku] = {'status': 'generated', 'outputs': [str(out9), str(out1)], 'ownership': 'generated'}
        except subprocess.CalledProcessError as e:
            print(f"FAIL_REASON=ugc_transcode_failed sku={sku} error={e} NEXT_FIX=Check ffmpeg output", file=sys.stderr)
            qa['skipped'] += 1
            qa['per_sku'][sku] = {'status': 'transcode_failed', 'reason': str(e)}
            continue
        except Exception as e:
            print(f"FAIL_REASON=ugc_failed sku={sku} error={e} NEXT_FIX=Investigate", file=sys.stderr)
            qa['skipped'] += 1
            qa['per_sku'][sku] = {'status': 'failed', 'reason': str(e)}
            continue

    with open(out_root / 'qa_report.json', 'w', encoding='utf-8') as f:
        json.dump(qa, f, indent=2)
    print('UGC QA written to', out_root / 'qa_report.json')


if __name__=='__main__':
    main()
