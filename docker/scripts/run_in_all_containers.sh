#!/bin/bash

DATASET=${1:-mds}
BASE_DIR="/home/$DATASET/miningframework"
SCRIPT_NAME="run_organize_monit_exp.py"
LOG_FILE_NAME="logs.log"

# Lista somente containers ativos com prefixo mbo2-tse-exp
CONTAINERS=$(docker ps --format '{{.Names}}' | grep '^mbo2-tse-exp')

if [ -z "$CONTAINERS" ]; then
    echo "Nenhum container ativo encontrado com prefixo mbo2-tse-exp"
    exit 1
fi

echo "Containers detectados:"
echo "$CONTAINERS"
echo ""

echo "Iniciando execucoes nos containers em background..."

for C in $CONTAINERS; do
    LOG_FILE="$BASE_DIR/${C}_${LOG_FILE_NAME}"

    echo "Iniciando script no container: $C"
    echo "Log: $LOG_FILE"

    # Not using -d so we can block, but running the docker exec itself in background (&)
    docker exec "$C" sh -c "
        cd $BASE_DIR
        mkdir -p $BASE_DIR
        echo \"[START] \$(date) - Executando script no dataset $DATASET\" >> $LOG_FILE
        python3 $SCRIPT_NAME >> $LOG_FILE 2>&1
    " &
done

echo ""
echo "Todas as execucoes foram iniciadas. Aguardando finalizacao (isso pode demorar muito)..."
wait
echo "Todas as execucoes finalizaram."
