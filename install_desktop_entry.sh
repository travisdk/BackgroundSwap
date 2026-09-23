#!/usr/bin/env bash
# Add "Background Swap" to the Linux application menu (freedesktop .desktop entry).
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${XDG_DATA_HOME:-$HOME/.local/share}/applications/background-swap.desktop"
mkdir -p "$(dirname "$TARGET")"
cat > "$TARGET" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Background Swap
Comment=Replace a photo's background with a stock photo
Exec="$DIR/.venv/bin/python" "$DIR/desktop.py"
Path=$DIR
Icon=$DIR/assets/icon.png
Terminal=false
Categories=Graphics;Photography;
StartupWMClass=desktop.py
DESKTOP
chmod +x "$TARGET"
command -v update-desktop-database >/dev/null && update-desktop-database "$(dirname "$TARGET")" || true
echo "Installed $TARGET"
