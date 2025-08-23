#!/usr/bin/env bash
# macOS launchd installer for the autostart Geny background pinger + backend
set -euo pipefail

LAUNCH_LABEL=${LAUNCH_LABEL:-com.geny.autostart}
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/${LAUNCH_LABEL}.plist"
REPO_DIR=$(cd "$(dirname "$0")/.." && pwd -P)

mkdir -p "$PLIST_DIR"
cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${LAUNCH_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
      <string>${REPO_DIR}/scripts/autostart_geny.sh</string>
      <string>127.0.0.1</string>
      <string>8000</string>
      <string>600</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${REPO_DIR}/backend/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>${REPO_DIR}/backend/launchd.err.log</string>
    <key>WorkingDirectory</key>
    <string>${REPO_DIR}</string>
  </dict>
</plist>
EOF

# Load the job
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Installed and loaded launchd job at $PLIST_PATH"
