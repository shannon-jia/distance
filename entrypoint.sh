#!/bin/bash
set -e

if [ "$1" = 'sam-distance' ]; then
    exec /app/sam-distance
fi

exec "$@"
