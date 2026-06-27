#!/bin/bash
set -e

# Configurações
IMAGE_NAME="tse-base-image"
NUM_CONTAINERS=10
DOCKER_DIR=$(pwd)
SCRIPTS_DIR="$DOCKER_DIR/scripts"

echo "==================================================="
echo "1. Criando imagem docker..."
echo "==================================================="
docker build -t "$IMAGE_NAME" .

echo "==================================================="
echo "2. Criando $NUM_CONTAINERS containers..."
echo "==================================================="
cd "$SCRIPTS_DIR"
bash create_containers.sh

echo "==================================================="
echo "3. Copiando script run_organize_monit_exp.py para os containers..."
echo "==================================================="
# Substituindo a lógica do copy_to_containers.sh original 
# para copiar o run_organize_monit_exp.py para mds e rds
SRC_FILE="run_organize_monit_exp.py"
DEST_PATH_MDS="/home/mds/miningframework"
DEST_PATH_RDS="/home/rds/miningframework"

CONTAINERS=$(docker ps --format '{{.Names}}' | grep '^mbo2-tse-exp')
for C in $CONTAINERS; do
    echo "Copiando $SRC_FILE para $C ..."
    docker cp "$SRC_FILE" "$C:$DEST_PATH_MDS/" 
    docker cp "$SRC_FILE" "$C:$DEST_PATH_RDS/" 
done

echo "==================================================="
echo "4. Executando run_organize_monit_exp.py em todos os containers..."
echo "==================================================="
for C in $CONTAINERS; do
    echo "Iniciando execução no container: $C"
    docker exec "$C" sh -c "
        cd $DEST_PATH_MDS
        python3 run_organize_monit_exp.py > exp_mds.log 2>&1
        cd $DEST_PATH_RDS
        python3 run_organize_monit_exp.py > exp_rds.log 2>&1
    " &
done

echo "Aguardando a execução em todos os containers (isso pode demorar horas)..."
wait
echo "Execuções finalizadas em todos os containers."

echo "==================================================="
echo "5. Copiando resultados dos containers..."
echo "==================================================="
DEST_BASE_MDS="$SCRIPTS_DIR/resultados/mds"
DEST_BASE_RDS="$SCRIPTS_DIR/resultados/rds"

mkdir -p "$DEST_BASE_MDS"
mkdir -p "$DEST_BASE_RDS"

for C in $CONTAINERS; do
    num=$(echo "$C" | grep -o '[0-9]\+$')
    
    dest_dir_mds="${DEST_BASE_MDS}/results${num}"
    dest_dir_rds="${DEST_BASE_RDS}/results${num}"
    
    echo "Copiando de $C para $dest_dir_mds e $dest_dir_rds"
    mkdir -p "$dest_dir_mds"
    mkdir -p "$dest_dir_rds"
    
    docker cp "$C:$DEST_PATH_MDS/results/." "$dest_dir_mds/"
    docker cp "$C:$DEST_PATH_RDS/results/." "$dest_dir_rds/"
done

echo "==================================================="
echo "6. Executando scripts de análise de resultados..."
echo "==================================================="

# MDS Results
echo "-> Executando mds_results.py..."
cd "$SCRIPTS_DIR/results"
# Copia o contents do results1 para a pasta atual para o script mds_results encontrar as pastas icf, ioa, idfp
cp -r "$DEST_BASE_MDS/results1/"* .
python3 mds_results.py

# RDS Results
echo "-> Executando rds-results.py..."
# Assumimos que o rds-results lê da mesma forma
cp -r "$DEST_BASE_RDS/results1/"* .
python3 rds-results.py
cd "$DOCKER_DIR"

# MissRef MergeDataset
echo "-> Executando missRef MergeDataset..."
cd "$SCRIPTS_DIR/missRef/MergeDataset"
cp -r "$DEST_BASE_MDS/results1/"* .
python3 run_all_missref.py
cd "$DOCKER_DIR"

# MissRef RefDataset
echo "-> Executando missRef RefDataset..."
cd "$SCRIPTS_DIR/missRef/RefDataset"
cp -r "$DEST_BASE_RDS/results1/"* .
python3 run_all_missref.py
cd "$DOCKER_DIR"

# Estatísticas (MDS)
echo "-> Executando estatísticas MDS..."
cd "$SCRIPTS_DIR/statistics"
# merge_data.py procura por directories results1, results2...
# Vamos criar links simbólicos temporários para o MDS
for i in $(seq 1 $NUM_CONTAINERS); do
    ln -sfn "$DEST_BASE_MDS/results$i" "results$i"
done
python3 merge_data.py
python3 stats_results.py
python3 plot_results_v2.py
cp statistical_report.pdf statistical_report_mds.pdf

# Se precisarmos rodar estatísticas para o RDS depois:
echo "-> Executando estatísticas RDS..."
for i in $(seq 1 $NUM_CONTAINERS); do
    ln -sfn "$DEST_BASE_RDS/results$i" "results$i"
done
python3 merge_data.py
python3 stats_results.py
python3 plot_results_v2.py
cp statistical_report.pdf statistical_report_rds.pdf
cd "$DOCKER_DIR"

echo "==================================================="
echo "Processo completo com sucesso!"
echo "Resultados copiados em: $DEST_BASE_MDS e $DEST_BASE_RDS"
echo "Relatórios gerados dentro de docker/scripts/results e statistics."
echo "==================================================="
