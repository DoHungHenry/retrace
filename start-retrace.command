#!/usr/bin/env bash
# macOS: double-click to start retrace. Checks for Python 3 and guides if it's missing.
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  cat <<'MSG'

  retrace needs Python 3 — it isn't installed on this Mac yet.

  Easiest fix (do this once):
    1. This window is a Terminal. Copy–paste the line below and press Return:

         xcode-select --install

    2. Click "Install" in the popup and wait for it to finish.
    3. Double-click "start-retrace.command" again.

  Prefer a download instead? Get it here, run the installer, then try again:
    https://www.python.org/downloads/

MSG
  read -n 1 -s -r -p "Press any key to close…"
  exit 1
fi

echo "Starting retrace…"
OPEN_EXTERNAL=1 bash ./start.sh
echo
echo "retrace is running. It should have opened in your browser."
echo "To stop it later: double-click nothing — just run  ./start.sh stop"
read -n 1 -s -r -p "Press any key to close this window…"
