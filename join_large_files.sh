#!/bin/bash

find . -type f -name "*.part000" | while read -r part0; do

  base="${part0%.part000}"

  echo "Reconstruindo $base"

  # garante ordem correta (000, 001, 002...)
  parts=$(ls "${base}.part"* 2>/dev/null | sort)

  if [ -z "$parts" ]; then
    echo "⚠ Nenhuma parte encontrada para $base"
    continue
  fi

  cat $parts > "$base"

  echo "✔ $base reconstruído"
done

echo "✔ Processo concluído"