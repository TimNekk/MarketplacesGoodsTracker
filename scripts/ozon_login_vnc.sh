#!/bin/sh
# Runs inside the container (via entrypoint.sh, so Xvfb is already up on
# :99). Exposes that display over VNC + noVNC so the manual phone/SMS login
# in scripts/ozon_login.py can be done from a browser on the host, producing
# a profile that was born on the same Linux/Camoufox build that will run it.
set -e

x11vnc -display "$DISPLAY" -nopw -forever -shared -rfbport 5900 &
websockify --web=/usr/share/novnc 6080 localhost:5900 &

exec python scripts/ozon_login.py
