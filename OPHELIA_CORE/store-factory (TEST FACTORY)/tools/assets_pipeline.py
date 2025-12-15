#!/usr/bin/env python3
"""Store-factory assets pipeline.

Downloads images from whitelisted domains, produces sizes/crops, manifests and QA report.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageOps
import requests


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def download_image(url, dest):
    r = requests.get(url, stream=True, timeout=30)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)


def ensure_dir(p):
    os.makedirs(p, exist_ok=True)


def process_image(orig_path, out_dir, sizes=(1024, 2048)):
    ensure_dir(out_dir)
    img = Image.open(orig_path).convert("RGB")
    outputs = []
    for size in sizes:
        ratio = size / max(img.size)
        new_w = int(img.width * ratio)
        new_h = int(img.height * ratio)
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        out_path = os.path.join(out_dir, f"{size}.jpg")
        resized.save(out_path, format="JPEG", quality=85, optimize=True)
        outputs.append(out_path)
    base = Image.open(orig_path).convert("RGB")
    # crops
    c1 = ImageOps.fit(base, (sizes[-1], sizes[-1]), Image.LANCZOS)
    out1 = os.path.join(out_dir, f"crop_1x1_{sizes[-1]}.jpg")
    c1.save(out1, format="JPEG", quality=85, optimize=True)
    outputs.append(out1)
    target_h = sizes[-1]
    target_w = int(target_h * 4 / 5)
    c2 = ImageOps.fit(base, (target_w, target_h), Image.LANCZOS)
    out2 = os.path.join(out_dir, f"crop_4x5_{sizes[-1]}.jpg")
    c2.save(out2, format="JPEG", quality=85, optimize=True)
    outputs.append(out2)
    return outputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=False)
    parser.add_argument("--out", required=False)
    parser.add_argument("--bundle-dir", required=False)
    parser.add_argument("--min-width", type=int, default=1200)
    parser.add_argument("--sizes", nargs="+", type=int, default=[1024, 2048])
    parser.add_argument("--whitelist-domains", nargs="+", required=False)
    args = parser.parse_args()

    # Determine output root and rows to process
    if args.bundle_dir:
        bundle = Path(args.bundle_dir)
        out_root = bundle / "images"
        manifest_path = bundle / "manifest.json"
        if not manifest_path.exists():
            print(f"FAIL_REASON=manifest_missing path={manifest_path} NEXT_FIX=Run copy_normalize first", file=sys.stderr)
            sys.exit(2)
        with open(manifest_path, encoding="utf-8") as mf:
            manifest = json.load(mf)
        rows = []
        for prod in manifest:
            sku = prod.get("sku")
            urls = prod.get("image_urls") or []
            if urls:
                # use first URL for processing (pipeline can be extended to multiple)
                rows.append({"sku": sku, "image_url": urls[0]})
        raw_root = bundle / "assets_raw"
        whitelist_domains = None
    else:
        out_root = Path(args.out)
        raw_root = Path("assets_raw")
        # read rows from csv
        if not args.input:
            print("FAIL_REASON=invalid_args NEXT_FIX=Provide --input CSV or --bundle-dir", file=sys.stderr)
            sys.exit(1)
        with open(args.input, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            rows = [r for r in reader]
        whitelist_domains = args.whitelist_domains
    ensure_dir(out_root)
    ensure_dir(raw_root)

    qa_report = {"processed": 0, "skipped": 0, "upscaled": 0, "per_sku": {}}

    # load whitelist from rules if not provided
    if not whitelist_domains:
        whitelist_domains = []
        try:
            with open("rules/whitelist_domains.txt", encoding="utf-8") as wf:
                for l in wf:
                    l = l.strip()
                    if l and not l.startswith('#'):
                        whitelist_domains.append(l)
        except Exception:
            pass

    for row in rows:
        sku = row.get("sku") or row.get("SKU") or row.get("id")
        url = row.get("image_url") or row.get("image")
        if not sku or not url:
            continue
        parsed = urlparse(url)
        if parsed.hostname not in whitelist_domains:
            qa_report["skipped"] += 1
            qa_report["per_sku"][sku] = {"status": "skipped", "reason": "domain_not_whitelisted"}
            continue
        sku_raw_dir = raw_root / sku
        ensure_dir(sku_raw_dir)
        orig_path = sku_raw_dir / os.path.basename(parsed.path)
        try:
            download_image(url, orig_path)
        except Exception as e:
            qa_report["skipped"] += 1
            qa_report["per_sku"][sku] = {"status": "skipped", "reason": f"download_failed: {e}"}
            continue
        try:
            with Image.open(orig_path) as im:
                width, height = im.size
        except Exception as e:
            qa_report["skipped"] += 1
            qa_report["per_sku"][sku] = {"status": "skipped", "reason": f"invalid_image: {e}"}
            continue
        upscale_used = False
        if width < args.min_width:
            upscale_used = True
            qa_report["upscaled"] += 1
            base = Image.open(orig_path).convert("RGB")
            new_w = args.min_width
            new_h = int(base.height * (new_w / base.width))
            up = base.resize((new_w, new_h), Image.LANCZOS)
            up.save(orig_path, format="JPEG", quality=90)
        out_dir = out_root / sku
        ensure_dir(out_dir)
        outputs = process_image(orig_path, out_dir, sizes=args.sizes)
        manifest = {
            "sku": sku,
            "sources": [url],
            "outputs": outputs,
            "checksums": {str(p): sha256_file(p) for p in outputs},
            "upscaled": upscale_used,
        }
        with open(out_dir / "manifest.json", "w", encoding="utf-8") as mf:
            json.dump(manifest, mf, indent=2)
        qa_report["processed"] += 1
        qa_report["per_sku"][sku] = {"status": "ok", "outputs": outputs, "upscaled": upscale_used}

    with open(out_root / "qa_report.json", "w", encoding="utf-8") as qf:
        json.dump(qa_report, qf, indent=2)
    print("QA report written to", out_root / "qa_report.json")


if __name__ == "__main__":
    main()
