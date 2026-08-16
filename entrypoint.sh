#!/bin/sh
set -e

rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99

exec "$@"
