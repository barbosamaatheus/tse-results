#!/bin/bash
set -euo pipefail

DATASET=${1:-mds}
BASE_DIR="/home/$DATASET/miningframework"

# Lista somente containers ativos com prefixo mbo2-tse-exp
CONTAINERS=$(docker ps --format '{{.Names}}' | grep '^mbo2-tse' || true)

if [ -z "$CONTAINERS" ]; then
    echo "No active container found with prefix mbo2-tse-exp"
    exit 1
fi

echo "Detected containers:"
echo "$CONTAINERS"
echo "----------------------------------------"

for C in $CONTAINERS; do
    echo "Clearing files in container: $C"

    docker exec "$C" bash -c "
        set -e
        cd '$BASE_DIR'

        rm -f \
            conflicts_log.txt \
            execution_err.txt \
            execution_log.txt \
            logs.log \
            out.json \
            out.txt \
            outConsole.txt \
            performance_summary.json \
            resource_usage_series.csv \
            time.txt \
            visited_methods.txt

        rm -rf results
    "

    echo "Container $C cleared successfully"
    echo "----------------------------------------"
done

echo "Clearance finished in all containers."
