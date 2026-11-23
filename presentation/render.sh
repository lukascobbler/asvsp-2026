#!/bin/bash

set -e

INPUT_DIR="./diagrams"
OUTPUT_DIR="./diagrams"

for file in "$INPUT_DIR"/*.mmd; do
    [ -f "$file" ] || continue

    base=$(basename "$file")
    filename=$(basename "$file" .mmd)

    if [ "$base" = ".keep" ] || [ "$filename" = ".keep" ]; then
        continue
    fi

    mmdc -i "$file" -o "$OUTPUT_DIR/$filename.svg" \
        -b transparent -t neutral

    echo "Converted: $filename.mmd"
done

quarto render Eventify.qmd --to revealjs && npx --yes decktape reveal --chrome-arg=--lang=en-US Eventify.html Eventify.pdf
