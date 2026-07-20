#!/bin/bash

DATASET=${1:-mds}
# Pasta onde os resultados serao salvos (use "." para salvar na pasta atual)
DEST_BASE=${2:-"./results"}

# Lista todos containers que comecam com mbo2-tse-exp
containers=$(docker ps --format "{{.Names}}" | grep '^mbo2-tse-exp')

for container in $containers; do
    # extrai numero do container (ex: mbo2-tse-exp7 -> 7)
    num=$(echo "$container" | grep -o '[0-9]\+$')

    dest_dir="${DEST_BASE}/results${num}"

    echo "Copying from container $container (dataset $DATASET) -> $dest_dir"

    # cria diretorio local
    mkdir -p "$dest_dir"

    # copia apenas o conteudo da pasta results
    docker cp "${container}:/home/$DATASET/miningframework/results/." "$dest_dir/"
done

echo "Copied successfully!"
