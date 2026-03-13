from datetime import timezone
#!/usr/bin/env python3
"""
 EPL data ingest pipeline
 Primary source: Football-Data.co.uk (EPL CSVs)
 Backup: Kaggle CSV if primary missing or for reconciliation
 Writes output to elo_project_data.md with provenance notes
"""
import os
import glob
import csv
from datetime import datetime

# Configurable paths
PRIMARY_GLOB = os.environ.get("EPL_PRIMARY_GLOB", "data/epl/*.csv")
KAGGLE_BACKUP = os.environ.get("EPL_KAGGLE_BACKUP", "data/kaggle_backup/epl_backup.csv")
OUTPUT_MD = os.environ.get("ELO_OUTPUT_MD", "elo_project_data.md")
URL_PROVENANCE = "https://football-data.co.uk/"  # provenance reference

# Simple club name normalization map (extend as needed)
NORMALIZE = {
    "Man United": "Manchester United",
    "Man City": "Manchester City",
    "Newcastle Utd": "Newcastle United",
    "Wolves": "Wolverhampton Wanderers",
    # add more as needed
}


def load_csv(path):
    rows = []
    if not os.path.exists(path):
        return rows
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def normalize_club(name):
    if name in NORMALIZE:
        return NORMALIZE[name]
    return name


def merge(primary_rows, backup_rows):
    # naive merge by season+team+date, prefer primary; if missing, fill from backup
    merged = []
    # build index by key
    def key(r):
        return (r.get('Season'), r.get('Team'))
    primary_index = {key(r): r for r in primary_rows}
    backup_index = {key(r): r for r in backup_rows}
    all_keys = set(primary_index.keys()) | set(backup_index.keys())
    for k in sorted(all_keys):
        r = None
        if k in primary_index:
            r = dict(primary_index[k])
        elif k in backup_index:
            r = dict(backup_index[k])
        if r is None:
            continue
        # normalize team name in output row if field exists
        if 'Team' in r:
            r['Team'] = normalize_club(r['Team'])
        merged.append(r)
    return merged


def to_markdown(rows):
    if not rows:
        return "No data available."
    # derive headers from keys of first row
    headers = sorted(list(rows[0].keys()))
    lines = ["|" + "|".join(headers) + "|",
             "|" + "|".join(["-"*len(h) for h in headers]) + "|"]
    for r in rows:
        line = [str(r.get(h, "")) for h in headers]
        lines.append("|" + "|".join(line) + "|")
    return "\n".join(lines)


def main():
    primary_files = glob.glob(PRIMARY_GLOB)
    primary_rows = load_csv(primary_files[0]) if primary_files and os.path.exists(primary_files[0]) else []
    # Fallback safe: try common EPL csv names
    if not primary_rows:
        primary_rows = load_csv("data/epl/ENG_Premier_League.csv")
    backup_rows = load_csv(KAGGLE_BACKUP) if os.path.exists(KAGGLE_BACKUP) else []

    # Normalize and merge
    # ensure all rows have Team field; if not, skip merging heuristics
    merged = merge(primary_rows, backup_rows)

    md = to_markdown(merged)
    provenance = f"Data ingest run: {datetime.now(timezone.utc).isoformat()} UTC\nSource: Football-Data.co.uk EPL CSVs (primary) ; Kaggle backup (if used)\nProvenance: {URL_PROVENANCE}"

    out = f"# EPL Data Ingest\n\nProvenance: {provenance}\n\n## Ingested data\n\n{md}\n"
    with open(OUTPUT_MD, 'w', encoding='utf-8') as f:
        f.write(out)
    print(f"Wrote {OUTPUT_MD}")

if __name__ == '__main__':
    main()
