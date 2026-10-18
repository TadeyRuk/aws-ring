#!/bin/sh
# Judge path: simulated doorbell on the alert page, then the Playground live view if a token is set.
cd "$(dirname "$0")/.."
export PYTHONPATH=src
export RINGDOOR_SOURCE="${RINGDOOR_SOURCE:-mock}"
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi
echo "Open http://127.0.0.1:8000"
echo "Press Simulate: Doorbell. The page flashes the alert."
if [ -n "$RING_ACCESS_TOKEN" ]; then
  echo "A Playground token is set. Watch the door opens the live H264 stream."
else
  echo "No RING_ACCESS_TOKEN. Alerts still run. Add a Playground token to .env for the live view."
fi
# Safari resolves localhost to IPv6. Listen on both stacks so either address opens.
.venv/bin/uvicorn ringdoor.main:app_factory --factory --host ::1 --port 8000 &
exec .venv/bin/uvicorn ringdoor.main:app_factory --factory --host 127.0.0.1 --port 8000
