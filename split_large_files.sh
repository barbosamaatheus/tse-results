#!/bin/bash

MAX_SIZE="90M"   # tamanho máximo por parte
LIMIT_SIZE="+90M" # arquivos maiores que isso serão divididos

find . -type f -size $LIMIT_SIZE ! -name "*.part*" | while read -r file; do
  echo "Dividindo $file"

  split -b $MAX_SIZE \
    -d \
    --suffix-length=3 \
    --additional-suffix=".part" \
    "$file" \
    "$file."

  rm "$file"
done

echo "✔ Todos os arquivos grandes foram divididos"