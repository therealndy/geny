#!/usr/bin/env bash
set -euo pipefail
# Orchestrator: run full single-store pipeline up to unpublished push. Requires per-store .env.<store_id>
# Usage: sf_run_single_store.sh <store_id> <products.csv>


# Ensure we always run from repo root
cd "$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$(pwd)"
ROOT_DIR="$(pwd)"

STORE_ID="${1:-}"
PRODUCTS_CSV="${2:-}"

if [ -z "$STORE_ID" ] || [ -z "$PRODUCTS_CSV" ]; then
  echo "Usage: $0 <store_id> <products.csv>" >&2
  exit 2
fi

ENV_FILE="$ROOT_DIR/.env.$STORE_ID"
if [ -f "$ENV_FILE" ]; then
  set -o allexport; source "$ENV_FILE"; set +o allexport
fi

RUN_ID="$(date +%Y%m%d%H%M%S)-$(git rev-parse --short HEAD 2>/dev/null || echo local)"
OUT_BUNDLE="$ROOT_DIR/output/bundles/$STORE_ID/$RUN_ID"
REPORT_DIR="$ROOT_DIR/output/reports/$STORE_ID/$RUN_ID"
MANIFEST_DIR="$ROOT_DIR/output/manifests/$STORE_ID/$RUN_ID"
SNAPSHOT_DIR="$ROOT_DIR/state/snapshots/$STORE_ID/$RUN_ID"
LOGFILE="$ROOT_DIR/logs/deploy-$STORE_ID-$RUN_ID.log"

mkdir -p "$OUT_BUNDLE" "$REPORT_DIR" "$MANIFEST_DIR" "$SNAPSHOT_DIR" $(dirname "$LOGFILE")

echo "RUN_ID=$RUN_ID" | tee -a "$LOGFILE"
echo "BUNDLE_DIR=$OUT_BUNDLE" | tee -a "$LOGFILE"

mkdir -p "$OUT_BUNDLE" "$REPORT_DIR" "$MANIFEST_DIR" "$SNAPSHOT_DIR" $(dirname "$LOGFILE")

echo "Run ID: $RUN_ID" | tee -a "$LOGFILE"

echo "STEP 1 — Signals & Decisions" | tee -a "$LOGFILE"
python3 "$ROOT_DIR/tools/signals_and_decisions.py" --input "$PRODUCTS_CSV" --store "$STORE_ID" --run_id "$RUN_ID" --outdir "$MANIFEST_DIR" \
  --blocklist "$ROOT_DIR/rules/claims_blocklist.txt" \
  --whitelist "$ROOT_DIR/rules/whitelist_domains.txt" 2>&1 | tee -a "$LOGFILE"

echo "STEP 2 — Copy Normalization (write manifest into bundle)" | tee -a "$LOGFILE"
# ensure decision_log is available in bundle_dir for copy_normalize
mkdir -p "$OUT_BUNDLE"
if [ -f "$MANIFEST_DIR/decision_log.json" ]; then
  cp "$MANIFEST_DIR/decision_log.json" "$OUT_BUNDLE/decision_log.json"
else
  echo "FAIL_REASON=decision_log_missing path=$MANIFEST_DIR/decision_log.json" | tee -a "$LOGFILE"
  exit 3
fi

python3 "$ROOT_DIR/tools/copy_normalize.py" --bundle-dir "$OUT_BUNDLE" --blocklist "$ROOT_DIR/rules/claims_blocklist.txt" 2>&1 | tee -a "$LOGFILE"

# Ensure preview builder runs immediately after copy-normalize so it reads bundle/manifest.json deterministically
python3 "$ROOT_DIR/tools/preview_builder.py" --bundle-dir "$OUT_BUNDLE" --original "$PRODUCTS_CSV" 2>&1 | tee -a "$LOGFILE" || true

echo "STEP 3 — Asset Pipeline" | tee -a "$LOGFILE"
python3 "$ROOT_DIR/tools/assets_pipeline.py" --bundle-dir "$OUT_BUNDLE" --min-width 1200 --sizes 1024 2048 --whitelist-domains $(tr '\n' ' ' < "$ROOT_DIR/rules/whitelist_domains.txt") 2>&1 | tee -a "$LOGFILE"

echo "STEP 4 — UGC Pipeline" | tee -a "$LOGFILE"
python3 "$ROOT_DIR/tools/ugc_pipeline.py" --bundle-dir "$OUT_BUNDLE" --out "$OUT_BUNDLE/videos" 2>&1 | tee -a "$LOGFILE" || true

echo "STEP 5 — Preview Report (deterministic, from bundle)" | tee -a "$LOGFILE"
# preview_builder.py already ran after copy_normalize; ensure report exists or attempt again
python3 "$ROOT_DIR/tools/preview_builder.py" --bundle-dir "$OUT_BUNDLE" --original "$PRODUCTS_CSV" 2>&1 | tee -a "$LOGFILE" || true

echo "STEP 6 — Shopify Theme Preview (manual)" | tee -a "$LOGFILE"
echo "Run the preview in a separate terminal: $ROOT_DIR/scripts/sf_preview_theme.sh $STORE_ID" | tee -a "$LOGFILE"

echo "STEP 7 — Push theme (unpublished)" | tee -a "$LOGFILE"
echo "Pushing theme (unpublished). This will NOT publish the theme." | tee -a "$LOGFILE"
"$ROOT_DIR/scripts/sf_push.sh" "$STORE_ID" 2>&1 | tee -a "$LOGFILE" || true

# Create snapshot manifest
cat > "$SNAPSHOT_DIR/metadata.json" <<EOF
{
  "run_id": "$RUN_ID",
  "store_id": "$STORE_ID",
  "bundle_path": "$OUT_BUNDLE",
  "report_path": "$REPORT_DIR/index.html",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "Snapshot created at $SNAPSHOT_DIR" | tee -a "$LOGFILE"

echo "STEP 8 — Publish gate: HOLD" | tee -a "$LOGFILE"
echo "To publish, run: $ROOT_DIR/scripts/sf_publish.sh $STORE_ID <theme_id>" | tee -a "$LOGFILE"

echo "STEP 9 — ZIP export" | tee -a "$LOGFILE"
# Always invoke the zip script with bash using a repo-relative path to avoid accidental execution with python
bash scripts/sf_zip_bundle.sh "$STORE_ID" "$RUN_ID" 2>&1 | tee -a "$LOGFILE"

# --- Strict gates ---
if [ ! -f "$OUT_BUNDLE/manifest.json" ]; then
  echo "FAIL_REASON=manifest_missing path=$OUT_BUNDLE/manifest.json" | tee -a "$LOGFILE"
  exit 10
fi

if [ ! -f "$OUT_BUNDLE/images/qa_report.json" ]; then
  echo "FAIL_REASON=images_qa_missing path=$OUT_BUNDLE/images/qa_report.json" | tee -a "$LOGFILE"
  exit 11
fi
img_processed=$(jq -r '.processed // 0' "$OUT_BUNDLE/images/qa_report.json" 2>/dev/null || echo 0)
if [ "$img_processed" -eq 0 ]; then
  echo "FAIL_REASON=images_processed_zero path=$OUT_BUNDLE/images/qa_report.json" | tee -a "$LOGFILE"
  exit 11
fi

if [ ! -f "$OUT_BUNDLE/videos/qa_report.json" ]; then
  echo "FAIL_REASON=videos_qa_missing path=$OUT_BUNDLE/videos/qa_report.json" | tee -a "$LOGFILE"
  exit 12
fi

if [ ! -f "$REPORT_DIR/index.html" ] || [ ! -f "$OUT_BUNDLE/preview/index.html" ]; then
  echo "FAIL_REASON=preview_missing report=$REPORT_DIR/index.html bundle_preview=$OUT_BUNDLE/preview/index.html" | tee -a "$LOGFILE"
  exit 13
fi

# Expected zip path
ZIPPATH="$ROOT_DIR/output/bundles/$STORE_ID/storefactory_${STORE_ID}_${RUN_ID}.zip"
if [ ! -f "$ZIPPATH" ]; then
  echo "FAIL_REASON=zip_missing path=$ZIPPATH" | tee -a "$LOGFILE"
  exit 14
fi

echo "Run summary written to $MANIFEST_DIR" | tee -a "$LOGFILE"

echo "Completed run orchestration (unpublished). Review report at $REPORT_DIR/index.html" | tee -a "$LOGFILE"

echo "Run summary written to $MANIFEST_DIR" | tee -a "$LOGFILE"

echo "Completed run orchestration (unpublished). Review report at $REPORT_DIR/index.html" | tee -a "$LOGFILE"
