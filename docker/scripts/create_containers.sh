#!/bin/bash

NUM_CONTAINERS=${NUM_CONTAINERS:-10}
IMAGE="tse-base-image"

MEMORY="20g"                 # limite de RAM
CPUS_PER_CONTAINER=4

echo "== Criando $NUM_CONTAINERS containers =="

for ((i=1; i<=NUM_CONTAINERS; i++)); do
    name="mbo2-tse-exp$i"

    start_cpu=$(((i-1) * CPUS_PER_CONTAINER))
    end_cpu=$((start_cpu + CPUS_PER_CONTAINER - 1))
    cpu_set="${start_cpu}-${end_cpu}"

    echo "? Criando $name  | CPUs: $cpu_set | Memria: $MEMORY"

    # Remove o container se ele já existir (para evitar erro de conflito)
    docker rm -f "$name" 2>/dev/null || true

    docker run -itd \
        --entrypoint "sh" \
        --name "$name" \
        --cpus="$CPUS_PER_CONTAINER" \
        --memory="$MEMORY" \
        --memory-reservation="$MEMORY" \
        --memory-swap="$MEMORY" \
        "$IMAGE"

    if [ $? -eq 0 ]; then
        echo "? $name criado com sucesso"
    else
        echo "? Erro ao criar $name"
    fi
done

echo "== Finalizado =="
