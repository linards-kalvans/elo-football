#!/bin/bash
# Fetch match data CSVs for top-5 European domestic leagues from Football-Data.co.uk

set -uo pipefail

BASE_URL="https://www.football-data.co.uk/mmz4281"
SEASONS=(1617 1718 1819 1920 2021 2122 2223 2324 2425 2526)

# League configuration: key|code|dirname
declare -A LEAGUES=(
    ["epl"]="E0|epl"
    ["laliga"]="SP1|laliga"
    ["bundesliga"]="D1|bundesliga"
    ["seriea"]="I1|seriea"
    ["ligue1"]="F1|ligue1"
)

# Parse arguments
SELECTED_LEAGUES=()
if [ $# -eq 0 ]; then
    # No args: fetch all leagues
    SELECTED_LEAGUES=(epl laliga bundesliga seriea ligue1)
else
    # Args provided: fetch only those
    for arg in "$@"; do
        if [[ -v LEAGUES[$arg] ]]; then
            SELECTED_LEAGUES+=("$arg")
        else
            echo "Warning: Unknown league '$arg', skipping"
        fi
    done
fi

if [ ${#SELECTED_LEAGUES[@]} -eq 0 ]; then
    echo "Error: No valid leagues specified"
    exit 1
fi

echo "Fetching data for leagues: ${SELECTED_LEAGUES[*]}"
echo "Seasons: ${SEASONS[*]}"
echo ""

TOTAL_SUCCESS=0
TOTAL_FAIL=0

for league in "${SELECTED_LEAGUES[@]}"; do
    IFS='|' read -r code dirname <<< "${LEAGUES[$league]}"
    echo "=== $league ($code) ==="

    for season in "${SEASONS[@]}"; do
        url="$BASE_URL/$season/$code.csv"
        dir="$dirname/$season"
        file="$dir/$code.csv"

        mkdir -p "$dir"

        if curl -fsSL -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64)" "$url" -o "$file" 2>/dev/null; then
            echo "  ✓ $season -> $file"
            ((TOTAL_SUCCESS++))
        else
            echo "  ✗ $season (not available)"
            ((TOTAL_FAIL++))
            rm -f "$file"  # Remove empty/partial file
        fi
    done
    echo ""
done

echo "Summary: $TOTAL_SUCCESS downloaded, $TOTAL_FAIL failed"
