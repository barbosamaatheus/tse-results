#!/bin/bash

set -e

PREFIX="^mbo2-tse-exp"

CONTAINERS=$(docker ps --format '{{.Names}}' | grep "$PREFIX" || true)

if [ -z "$CONTAINERS" ]; then
    echo "No container found with prefix mbo2-tse-exp"
    exit 0
fi

echo "Containers found:"
echo "$CONTAINERS"
echo ""

for C in $CONTAINERS; do
    echo "----------------------------------------"
    echo "Installing psutil in container: $C"

    docker exec "$C" sh -c "
        python3 - << 'EOF'
try:
    import psutil
    print('psutil already installed')
except ImportError:
    print('psutil not found, installing...')
    import os
    os.system('pip3 install psutil || (apt update && apt install -y python3-pip && pip3 install psutil)')
EOF
    "
done

echo ""
echo "psutil installation completed in all containers."
