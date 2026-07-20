#!/bin/bash

DATASET=${1:-mds}
BASE_DIR="/home/$DATASET/miningframework"
SCRIPT_NAME="run_organize_monit_exp.py"
LOG_FILE_NAME="logs.log"

# Lista somente containers ativos com prefixo mbo2-tse-exp
CONTAINERS=$(docker ps --format '{{.Names}}' | grep '^mbo2-tse-exp')

if [ -z "$CONTAINERS" ]; then
    echo "No active container found with prefix mbo2-tse-exp"
    exit 1
fi

echo "Detected containers:"
echo "$CONTAINERS"
echo ""

echo "Starting executions in containers in background..."

for C in $CONTAINERS; do
    LOG_FILE="$BASE_DIR/${C}_${LOG_FILE_NAME}"

    echo "Starting script in container: $C"
    echo "Log: $LOG_FILE"

    # Not using -d so we can block, but running the docker exec itself in background (&)
    docker exec "$C" sh -c "
        cd $BASE_DIR
        mkdir -p $BASE_DIR
        echo \"[START] \$(date) - Executing script on dataset $DATASET\" >> $LOG_FILE
        python3 $SCRIPT_NAME >> $LOG_FILE 2>&1
    " &
done

echo ""
echo "All executions started. Waiting for completion (this may take a long time)..."
wait
echo "All executions finished."
