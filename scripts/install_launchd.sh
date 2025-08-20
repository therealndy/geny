#!/usr/bin/env bash
set -euo pipefail

# Install a launchd plist that runs the backend start script at login/boot
PLIST_PATH="$HOME/Library/LaunchAgents/com.geny.backend.plist"
SCRIPT_PATH="$PWD/scripts/start_backend.sh"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple Computer//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.geny.backend</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/bash</string>
      <string>-lc</string>
      <string>"$SCRIPT_PATH"</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PWD/backend/launchd.out</string>
    <key>StandardErrorPath</key>
    <string>$PWD/backend/launchd.err</string>
  </dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "Installed launchd plist at $PLIST_PATH"
