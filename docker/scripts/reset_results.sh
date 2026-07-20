#!/bin/bash

# Script para limpar resultados e arquivos residuais em todos os containers mbo2-tse-exp
# Uso: ./reset_results.sh [dataset]

CONTAINERS_PREFIX="mbo2-tse-exp"
NUM_CONTAINERS=10
DATASET=${1:-mds}
RESULTS_DIR="/home/$DATASET/miningframework/results"

# Arquivos grandes/residuais a remover (OOM, logs antigos, dumps)
EXTRA_PATHS=(
  "/home/$DATASET/miningframework/java_pid*.hprof"
  "/home/$DATASET/miningframework/logs.log"
  "/home/$DATASET/miningframework/logs.txt"
  "/home/$DATASET/miningframework/mbo2-tse-exp*_logs.log"
  "/home/$DATASET/miningframework/AnalysisRecords.csv"
  "/home/$DATASET/miningframework/conflicts_log.txt"
  "/home/$DATASET/miningframework/outConsole.txt"
  "/home/$DATASET/miningframework/out.txt"
  "/home/$DATASET/miningframework/out.json"
  "/home/$DATASET/miningframework/HasMainMethod.csv"
  "/home/$DATASET/miningframework/PANotResolve.csv"
  "/home/$DATASET/miningframework/visited_methods.txt"
  "/home/$DATASET/miningframework/time.txt"
  "/home/$DATASET/miningframework/output/data/soot-results.csv"
)

echo "== Clearing results and residuals in ${NUM_CONTAINERS} containers for dataset ${DATASET} =="

for ((i=1; i<=NUM_CONTAINERS; i++)); do
  CONTAINER="${CONTAINERS_PREFIX}${i}"
  echo "-> Clearing ${CONTAINER}"

  # Limpa diretorio de resultados
  docker exec "$CONTAINER" sh -c "mkdir -p ${RESULTS_DIR} && rm -rf ${RESULTS_DIR}/*"

  # Remove arquivos residuais especificos
  for path in "${EXTRA_PATHS[@]}"; do
    docker exec "$CONTAINER" sh -c "rm -f ${path}" >/dev/null 2>&1
  done

  if [ $? -eq 0 ]; then
    echo "   OK: ${CONTAINER} cleared"
  else
    echo "   ERROR: failed to clear ${CONTAINER}"
  fi
done

echo "== Finished =="
