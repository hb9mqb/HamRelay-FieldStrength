#!/bin/sh
set -eu

python /app/docker/prepare_itu_maps.py
exec "$@"
