#!/usr/bin/env bash
# Start / stop / restart retrace — resolves its own location, so it works wherever cloned.
#
#   ./start.sh            start on :8787 (or report if already up)
#   ./start.sh 9000       use a different port
#   ./start.sh stop       stop the server on :8787
#   ./start.sh restart    restart on :8787
#
# Requires only Python 3. Set OPEN_EXTERNAL=1 to also open your default browser.
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_PORT=8787

running_pid() { lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null; }

start() {
  local port="$1" pid; pid="$(running_pid "$port")"
  if [ -n "$pid" ]; then
    echo "already running (pid $pid) -> http://127.0.0.1:$port"
  else
    nohup python3 "$DIR/server.py" --port "$port" --no-open >/tmp/retrace.log 2>&1 &
    sleep 1
    echo "started -> http://127.0.0.1:$port"
  fi
  [ "${OPEN_EXTERNAL:-}" = "1" ] && command -v open >/dev/null && open "http://127.0.0.1:$port"
  return 0
}

stop() {
  local port="$1" pid; pid="$(running_pid "$port")"
  if [ -n "$pid" ]; then kill "$pid" && echo "stopped on :$port"; else echo "not running on :$port"; fi
}

case "${1:-}" in
  stop)    stop "${2:-$DEFAULT_PORT}" ;;
  restart) stop "${2:-$DEFAULT_PORT}"; sleep 1; start "${2:-$DEFAULT_PORT}" ;;
  "")      start "$DEFAULT_PORT" ;;
  *)       start "$1" ;;
esac
