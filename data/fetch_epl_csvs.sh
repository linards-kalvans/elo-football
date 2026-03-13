#!/bin/bash
set -euo pipefail
BASE_URL="https://www.football-data.co.uk/mmz4281"
OUTROOT="epl"
declare -a YEARS=("1617" "1718" "1819" "1920" "2021" "2122" "2223" "2324" "2425" "2526")

for Y in "${YEARS[@]}"; do
  DEST_DIR="$OUTROOT/$Y"
  mkdir -p "$DEST_DIR"
  echo "Downloading $BASE_URL/$Y/E0.csv..."
  if curl -fsSL -o "$DEST_DIR/E0.csv" "$BASE_URL/$Y/E0.csv"; then
    echo "Saved $DEST_DIR/E0.csv"
  else
    echo "Not found: $BASE_URL/$Y/E0.csv" >&2
  fi
done
