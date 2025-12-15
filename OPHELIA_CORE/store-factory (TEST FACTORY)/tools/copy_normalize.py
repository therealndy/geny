import sys, os, json
import argparse
from tools.log_writer import log_event


def normalize_sv(text):
    # Dummy: Replace with real SV normalization
    return text.strip()


def strip_claims(text, blocklist):
    for claim in blocklist:
        text = text.replace(claim, "")
    return text


def write_atomic(path, data):
    tmp = path + ".tmp"
    try:
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle-dir', required=True, help='Path to bundle directory')
    parser.add_argument('--blocklist', required=True, help='Path to claims blocklist file')
    args = parser.parse_args()
    bundle_dir = args.bundle_dir
    blocklist_path = args.blocklist

    try:
        os.makedirs(bundle_dir, exist_ok=True)
    except Exception as e:
        print(f"FAIL_REASON=manifest_write_failed reason=mkdir_failed error={e} NEXT_FIX=Ensure writable parent directories", file=sys.stderr)
        sys.exit(1)

    decision_path = os.path.join(bundle_dir, "decision_log.json")
    if not os.path.isfile(decision_path):
        print(f"FAIL_REASON=decision_log_missing path={decision_path} NEXT_FIX=Run candidate selection first", file=sys.stderr)
        sys.exit(1)

    try:
        with open(decision_path) as f:
            decisions = json.load(f)
    except Exception as e:
        print(f"FAIL_REASON=decision_read_failed error={e} NEXT_FIX=Inspect decision_log.json", file=sys.stderr)
        sys.exit(1)

    # Accept either a top-level list of decisions or a dict with a "decisions" key
    if isinstance(decisions, dict):
        decisions = decisions.get("decisions", [])
    if not isinstance(decisions, list):
        print(f"FAIL_REASON=decision_format_invalid path={decision_path} NEXT_FIX=Ensure decision_log.json contains a list or a 'decisions' array", file=sys.stderr)
        sys.exit(1)

    try:
        with open(blocklist_path) as f:
            blocklist = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except Exception as e:
        print(f"FAIL_REASON=claims_blocklist_missing error={e} NEXT_FIX=Create {blocklist_path}", file=sys.stderr)
        sys.exit(1)

    manifest = []
    for d in decisions:
        # support both older format (d.status == 'APPROVED') and newer 'decision' strings
        status_val = d.get("status") or d.get("decision")
        if isinstance(status_val, str):
            ok = status_val.upper() == "APPROVED" or "APPROVE" in status_val.upper()
        else:
            ok = False
        if not ok:
            continue

        # signal payload may be nested under 'signal' or be top-level
        signal = d.get("signal") if isinstance(d, dict) and d.get("signal") else d

        title = signal.get("title") or signal.get("name") or signal.get("sku")
        description = signal.get("description") or signal.get("desc") or d.get("reason") or ""

        # normalize image fields into a list
        image_field = signal.get("image_urls") or signal.get("image_url") or d.get("image_urls") or d.get("image_url")
        if isinstance(image_field, list):
            image_urls = image_field
        elif image_field:
            image_urls = [image_field]
        else:
            image_urls = []

        prod = {
            "sku": d.get("sku") or signal.get("sku"),
            "title": normalize_sv(title) if title else "",
            "description": strip_claims(description, blocklist),
            "image_urls": image_urls,
            "vendor": d.get("vendor") or signal.get("vendor") or "",
            "ugc_url": d.get("ugc_url") or signal.get("ugc_url"),
            "license": d.get("license") or signal.get("license")
        }
        manifest.append(prod)

    manifest_path = os.path.join(bundle_dir, "manifest.json")
    try:
        write_atomic(manifest_path, manifest)
    except Exception as e:
        print(f"FAIL_REASON=manifest_write_failed error={e} NEXT_FIX=Check filesystem and permissions", file=sys.stderr)
        sys.exit(1)

    print(f"[COPY] manifest_written={manifest_path}")
    log_event(bundle_dir, "Copy normalization complete.")


if __name__ == "__main__":
    main()
