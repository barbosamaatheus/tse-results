#!/bin/bash
set -e

# Configuracoes
IMAGE_NAME="tse-base-image"
export NUM_CONTAINERS=${1:-10}
TARGET_DATASET=${2:-all} # pode ser 'all', 'mds' ou 'rds'
DOCKER_DIR=$(pwd)
SCRIPTS_DIR="$DOCKER_DIR/scripts"

# TIMESTAMP removido a pedido
OUTPUT_DIR="$DOCKER_DIR/experiment_out_20260718_110306"

mkdir -p "$OUTPUT_DIR/mergedataset"
mkdir -p "$OUTPUT_DIR/refdataset"

echo "==================================================="
echo "1. Criando imagem docker..."
echo "==================================================="
docker build -t "$IMAGE_NAME" .

echo "==================================================="
echo "2. Criando $NUM_CONTAINERS containers..."
echo "==================================================="
cd "$SCRIPTS_DIR"
bash create_containers.sh

# Funcao para executar o pipeline de um dataset
run_dataset_pipeline() {
    local dataset=$1
    local out_folder=$2
    local out_dest="$OUTPUT_DIR/$out_folder"
    
    echo "==================================================="
    echo ">>> INICIANDO PIPELINE: $dataset <<<"
    echo "==================================================="
    
    echo "[$dataset] Limpando containers..."
    bash clear_containers.sh "$dataset"
    bash reset_results.sh "$dataset"
    
    echo "[$dataset] Executando analise nos containers..."
    bash run_in_all_containers.sh "$dataset"
    
    echo "[$dataset] Copiando resultados..."
    bash copy_results.sh "$dataset" "$out_dest"
}

# Executa MDS (saida mapeada para mergedataset)
if [ "$TARGET_DATASET" == "all" ] || [ "$TARGET_DATASET" == "mds" ]; then
    run_dataset_pipeline "mds" "mergedataset"
fi

# Executa RDS (saida mapeada para refdataset)
if [ "$TARGET_DATASET" == "all" ] || [ "$TARGET_DATASET" == "rds" ]; then
    run_dataset_pipeline "rds" "refdataset"
fi

echo "==================================================="
echo "3. Executando scripts de analise de resultados..."
echo "==================================================="

if [ "$TARGET_DATASET" == "all" ] || [ "$TARGET_DATASET" == "mds" ]; then
    echo "-> Configurando ambiente de analise do MDS..."
    cd "$OUTPUT_DIR/mergedataset"
    
    # Elevar as pastas icf, idfp, ioa do results1 para a raiz do mergedataset
    cp -r results1/* . 2>/dev/null || true
    
    # Executar mds_results.py
    echo "-> Executando mds_results.py (MDS)..."
    cp "$SCRIPTS_DIR/results/mds_results.py" .
    cp "$SCRIPTS_DIR/results/loi.csv" . 2>/dev/null || true
    python3 mds_results.py
    
    # Executar MissRef MergeDataset
    echo "-> Executando missRef MergeDataset..."
    mkdir -p missref_run
    cp -r "$SCRIPTS_DIR/missRef/MergeDataset/"* missref_run/
    cp "$SCRIPTS_DIR/missRef/soot-results-with-lines.csv" missref_run/ 2>/dev/null || true
    cd missref_run
    python3 run_all_missref.py
    # Move outputs e limpa
    mkdir -p ../missref
    cp -r CF DF OA ../missref/ 2>/dev/null || true
    cd ..
    rm -rf missref_run
    
    # Executar Estatisticas
    echo "-> Executando estatisticas MDS..."
    cp "$SCRIPTS_DIR/statistics/merge_data.py" .
    cp "$SCRIPTS_DIR/statistics/stats_results.py" .
    cp "$SCRIPTS_DIR/statistics/plot_results_v2.py" .
    python3 merge_data.py
    python3 stats_results.py
    python3 plot_results_v2.py
    
    # Limpeza final de scripts copiados (opcional, mantendo apenas os dados)
    rm -f mds_results.py loi.csv merge_data.py stats_results.py plot_results_v2.py
    
    cd "$DOCKER_DIR"
fi

if [ "$TARGET_DATASET" == "all" ] || [ "$TARGET_DATASET" == "rds" ]; then
    echo "-> Configurando ambiente de analise do RDS..."
    cd "$OUTPUT_DIR/refdataset"
    
    # Para o rds-results, copiamos os resultados temporariamente para simular a pasta original
    echo "-> Executando rds-results.py (RDS)..."
    cp -r results1/* . 2>/dev/null || true
    cp "$SCRIPTS_DIR/results/rds-results.py" .
    python3 rds-results.py
    
    # Executar MissRef RefDataset
    echo "-> Executando missRef RefDataset..."
    mkdir -p missref_run
    cp -r "$SCRIPTS_DIR/missRef/RefDataset/"* missref_run/
    cp "$SCRIPTS_DIR/missRef/soot-results-with-lines.csv" missref_run/ 2>/dev/null || true
    cd missref_run
    python3 run_all_missref.py
    # Move outputs e limpa
    for folder in results*; do
        if [ -d "$folder/CF" ] || [ -d "$folder/DF" ] || [ -d "$folder/OA" ]; then
            mkdir -p "../missref/$folder"
            cp -r "$folder/CF" "$folder/DF" "$folder/OA" "../missref/$folder/" 2>/dev/null || true
        fi
    done
    cp -r CF DF OA ../missref/ 2>/dev/null || true
    cd ..
    rm -rf missref_run
    
    # Executar Estatisticas
    echo "-> Executando estatisticas RDS..."
    cp "$SCRIPTS_DIR/statistics/merge_data.py" .
    cp "$SCRIPTS_DIR/statistics/stats_results.py" .
    cp "$SCRIPTS_DIR/statistics/plot_results_v2.py" .
    python3 merge_data.py
    python3 stats_results.py
    python3 plot_results_v2.py
    
    # Limpeza final de scripts copiados
    rm -f rds-results.py merge_data.py stats_results.py plot_results_v2.py
    
    cd "$DOCKER_DIR"
fi

echo "==================================================="
echo "Processo completo com sucesso!"
echo "Resultados disponiveis em: $OUTPUT_DIR"
echo "Estrutura final baseada na tse2026 configurada com sucesso."
echo "==================================================="
