"""EPL Elo Analysis — generates plots and narrative markdown.

Covers:
  1. Data preview (table head)
  2. Elo trajectory for sample clubs over time
  3. Distribution of Elo changes per match & goals per game
  4. Full rankings table (all teams sorted by Elo)

Outputs written to notebooks/outputs/:
  - fig1_data_preview.png
  - fig2_elo_trajectory.png
  - fig3_distributions.png
  - epl_elo_analysis.md
"""

import os
import sys

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from datetime import datetime, timezone

# Allow imports from src/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from src.config import EloSettings
from src.elo_engine import EloEngine

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "..", "data", "epl")
OUT_DIR = os.path.join(BASE, "outputs")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. Load all season CSVs
# ---------------------------------------------------------------------------
frames = []
for season_dir in sorted(os.listdir(DATA_DIR)):
    csv_path = os.path.join(DATA_DIR, season_dir, "E0.csv")
    if os.path.isfile(csv_path):
        df = pd.read_csv(csv_path, low_memory=False)
        df["Season"] = season_dir
        frames.append(df)

data = pd.concat(frames, ignore_index=True)

# Keep only core columns we need
core_cols = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "Season"]
data = data[[c for c in core_cols if c in data.columns]].copy()
data["Date"] = pd.to_datetime(data["Date"], dayfirst=True, errors="coerce")
data = data.dropna(subset=["Date", "HomeTeam", "AwayTeam", "FTR"]).sort_values("Date").reset_index(drop=True)
data["FTHG"] = pd.to_numeric(data["FTHG"], errors="coerce").fillna(0).astype(int)
data["FTAG"] = pd.to_numeric(data["FTAG"], errors="coerce").fillna(0).astype(int)

print(f"Loaded {len(data)} matches across {data['Season'].nunique()} seasons")
print(f"Teams: {data['HomeTeam'].nunique()} unique")

# ---------------------------------------------------------------------------
# FIGURE 1 — Data preview (first 10 rows as table)
# ---------------------------------------------------------------------------
preview = data.head(10).copy()
preview["Date"] = preview["Date"].dt.strftime("%Y-%m-%d")

fig1, ax1 = plt.subplots(figsize=(12, 3.5))
ax1.axis("off")
col_labels = list(preview.columns)
cell_vals = [list(row) for _, row in preview.iterrows()]
tbl = ax1.table(
    cellText=cell_vals,
    colLabels=col_labels,
    cellLoc="center",
    loc="center",
)
tbl.auto_set_font_size(False)
tbl.set_fontsize(8)
tbl.scale(1, 1.4)
# Style header
for j in range(len(col_labels)):
    tbl[0, j].set_facecolor("#2c3e50")
    tbl[0, j].set_text_props(color="white", fontweight="bold")
# Alternating row shading
for i in range(1, len(cell_vals) + 1):
    color = "#ecf0f1" if i % 2 == 0 else "white"
    for j in range(len(col_labels)):
        tbl[i, j].set_facecolor(color)

ax1.set_title("EPL Match Data — First 10 Rows", fontsize=12, fontweight="bold", pad=10)
fig1.tight_layout()
fig1_path = os.path.join(OUT_DIR, "fig1_data_preview.png")
fig1.savefig(fig1_path, dpi=150, bbox_inches="tight")
plt.close(fig1)
print(f"Saved: {fig1_path}")

# ---------------------------------------------------------------------------
# Run Elo engine
# ---------------------------------------------------------------------------
settings = EloSettings()
engine = EloEngine(settings)
print(f"\nElo settings: {settings.model_dump()}\n")

result = engine.compute_ratings(data)
elo = result.ratings
history = result.history
deltas = result.deltas

print(f"Computed Elo for {len(elo)} teams, {result.matches_processed} matches")

# ---------------------------------------------------------------------------
# FIGURE 2 — Elo trajectory for sample clubs
# ---------------------------------------------------------------------------
# Pick the 5 clubs with most appearances + Man City and Liverpool as anchors
top_clubs_by_matches = (
    pd.concat([data["HomeTeam"], data["AwayTeam"]])
    .value_counts()
    .head(8)
    .index.tolist()
)
# Prefer some well-known ones if available
preferred = ["Man City", "Liverpool", "Chelsea", "Arsenal", "Tottenham", "Man United"]
sample_clubs = [c for c in preferred if c in history]
for c in top_clubs_by_matches:
    if c not in sample_clubs:
        sample_clubs.append(c)
sample_clubs = sample_clubs[:6]

colors = plt.cm.tab10.colors

fig2, ax2 = plt.subplots(figsize=(12, 5))
for idx, club in enumerate(sample_clubs):
    dates, ratings = zip(*history[club])
    ax2.plot(dates, ratings, label=club, color=colors[idx % len(colors)], linewidth=1.8, alpha=0.85)

ax2.axhline(settings.initial_elo, color="gray", linewidth=0.8, linestyle="--", alpha=0.6, label=f"Start ({settings.initial_elo:.0f})")
ax2.set_xlabel("Date", fontsize=11)
ax2.set_ylabel("Elo Rating", fontsize=11)
ax2.set_title("Elo Rating Trajectory — Sample EPL Clubs (2016–2026)", fontsize=13, fontweight="bold")
ax2.legend(loc="upper left", fontsize=9, framealpha=0.8)
ax2.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:.0f}"))
ax2.grid(axis="y", linestyle=":", alpha=0.5)
fig2.tight_layout()
fig2_path = os.path.join(OUT_DIR, "fig2_elo_trajectory.png")
fig2.savefig(fig2_path, dpi=150, bbox_inches="tight")
plt.close(fig2)
print(f"Saved: {fig2_path}")

# ---------------------------------------------------------------------------
# FIGURE 3 — Distributions: Elo changes & goals per game
# ---------------------------------------------------------------------------
goals_per_game = data["FTHG"] + data["FTAG"]

fig3, axes = plt.subplots(1, 2, figsize=(12, 4.5))

# Left: Elo change distribution (home team perspective)
ax_elo = axes[0]
ax_elo.hist(deltas, bins=40, color="#3498db", edgecolor="white", linewidth=0.4, alpha=0.85)
ax_elo.axvline(0, color="crimson", linewidth=1.2, linestyle="--")
ax_elo.set_xlabel("Elo Δ (Home Team)", fontsize=11)
ax_elo.set_ylabel("Frequency", fontsize=11)
ax_elo.set_title("Distribution of Elo Changes per Match", fontsize=12, fontweight="bold")
mean_d = np.mean(deltas)
ax_elo.axvline(mean_d, color="darkorange", linewidth=1.2, linestyle="-.", label=f"Mean={mean_d:.2f}")
ax_elo.legend(fontsize=9)
ax_elo.grid(axis="y", linestyle=":", alpha=0.4)

# Right: Goals per game distribution
ax_g = axes[1]
max_goals = goals_per_game.max()
bins = np.arange(-0.5, max_goals + 1.5, 1)
ax_g.hist(goals_per_game, bins=bins, color="#2ecc71", edgecolor="white", linewidth=0.4, alpha=0.85)
ax_g.set_xlabel("Total Goals per Match", fontsize=11)
ax_g.set_ylabel("Frequency", fontsize=11)
ax_g.set_title("Distribution of Goals per Game", fontsize=12, fontweight="bold")
ax_g.axvline(goals_per_game.mean(), color="darkorange", linewidth=1.2, linestyle="-.",
             label=f"Mean={goals_per_game.mean():.2f}")
ax_g.legend(fontsize=9)
ax_g.grid(axis="y", linestyle=":", alpha=0.4)

fig3.suptitle("EPL Match Distributions (2016–2026)", fontsize=13, fontweight="bold", y=1.01)
fig3.tight_layout()
fig3_path = os.path.join(OUT_DIR, "fig3_distributions.png")
fig3.savefig(fig3_path, dpi=150, bbox_inches="tight")
plt.close(fig3)
print(f"Saved: {fig3_path}")

# ---------------------------------------------------------------------------
# Narrative stats for markdown
# ---------------------------------------------------------------------------
rankings = engine.get_rankings(elo)
top5_elo = rankings[:5]
bottom5_elo = rankings[-5:]
delta_std = np.std(deltas)
goals_mean = goals_per_game.mean()
goals_std = goals_per_game.std()

# Per-season avg goals
season_goals = data.groupby("Season").apply(
    lambda g: (g["FTHG"] + g["FTAG"]).mean(), include_groups=False
).round(2)

# ---------------------------------------------------------------------------
# MARKDOWN NARRATIVE
# ---------------------------------------------------------------------------
md_lines = [
    "# EPL Elo Analysis — Narrative Report",
    "",
    f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}  ",
    f"> Seasons: {data['Season'].nunique()} ({data['Season'].min()} – {data['Season'].max()})  ",
    f"> Total matches: {len(data):,}  ",
    f"> Unique clubs: {len(elo)}",
    "",
    "---",
    "",
    "## Figure 1 — Data Preview",
    "",
    "![Data Preview](fig1_data_preview.png)",
    "",
    "The table shows the first ten rows of the combined EPL dataset loaded from",
    "season-by-season CSV files (`data/epl/<season>/E0.csv`).  ",
    "Each row is a single match with columns for **Date**, **HomeTeam**, **AwayTeam**,",
    "full-time home goals (**FTHG**), full-time away goals (**FTAG**),",
    "and the result (**FTR**: H = Home win, D = Draw, A = Away win).",
    "The dataset spans the 2016/17 season through 2025/26, giving a rich ten-season window.",
    "",
    "---",
    "",
    "## Figure 2 — Elo Trajectories",
    "",
    "![Elo Trajectory](fig2_elo_trajectory.png)",
    "",
    f"All clubs begin at a neutral rating of **{settings.initial_elo:.0f}** (promoted teams enter at"
    f" **{settings.promoted_elo:.0f}**). The chart tracks six representative"
    f" clubs across all seasons using an Elo model with **K = {settings.k_factor:.0f}**,",
    f"**home advantage = {settings.home_advantage:.0f}**, **decay rate = {settings.decay_rate}** per year,",
    f"and **spread = {settings.spread:.0f}**. Margin-of-victory adjustment is enabled with",
    f"**autocorr_coeff = {settings.mov_autocorr_coeff}**, **autocorr_scale = {settings.mov_autocorr_scale}**.",
    "",
    "Key observations:",
    "",
]

for club, rating in top5_elo:
    md_lines.append(f"- **{club}** ended the period at **{rating:.0f}** Elo points.")

md_lines += [
    "",
    "The spread between the strongest and weakest clubs at season-end reflects how",
    "consistently dominant (or poor) those sides were — clubs that win many high-stakes",
    "matches accumulate large positive Elo swings. Promotions and relegations create",
    "visible discontinuities for mid-table clubs.",
    "",
    "---",
    "",
    "## Figure 3 — Distributions",
    "",
    "![Distributions](fig3_distributions.png)",
    "",
    "### Elo Change Distribution",
    f"The per-match Elo change (home team perspective) has a mean of **{np.mean(deltas):.2f}**",
    f"and a standard deviation of **{delta_std:.2f}**.",
    "The distribution is roughly symmetric around zero, but a slight positive skew",
    "for home teams reflects the **home advantage** embedded in EPL results.",
    "Extreme tails correspond to heavily surprising upsets.",
    "",
    "### Goals per Game Distribution",
    f"Matches average **{goals_mean:.2f} ± {goals_std:.2f}** total goals.",
    "The distribution is right-skewed (most games produce 1–3 goals) with a long tail",
    "for high-scoring fixtures. Per-season averages:",
    "",
    "| Season | Avg Goals/Game |",
    "|--------|---------------|",
]
for s, v in season_goals.items():
    md_lines.append(f"| {s} | {v} |")

md_lines += [
    "",
    "---",
    "",
    "## Full Rankings",
    "",
    "| Rank | Team | Elo |",
    "|------|------|-----|",
]
for rank, (team, rating) in enumerate(rankings, 1):
    md_lines.append(f"| {rank} | {team} | {rating:.0f} |")

md_lines += [
    "",
    "---",
    "",
    "## How to Reproduce Locally",
    "",
    "```bash",
    "# 1. Clone / enter the project",
    "cd elo-epl-project",
    "",
    "# 2. Install dependencies (requires uv)",
    "uv sync",
    "",
    "# 3. Run the analysis script",
    "uv run python notebooks/run_analysis.py",
    "",
    "# Outputs land in: notebooks/outputs/",
    "#   fig1_data_preview.png",
    "#   fig2_elo_trajectory.png",
    "#   fig3_distributions.png",
    "#   epl_elo_analysis.md  (this file)",
    "```",
    "",
    "> **Data source:** Football-Data.co.uk season CSVs (`data/epl/<season>/E0.csv`).",
    "> Run `data/fetch_epl_csvs.sh` to refresh the raw data.",
    "",
    "### Parameters",
    "",
    "| Parameter | Value | Description |",
    "|-----------|-------|-------------|",
    f"| `K` | {settings.k_factor} | Elo update factor |",
    f"| `INITIAL_ELO` | {settings.initial_elo} | Starting rating for established clubs |",
    f"| `PROMOTED_ELO` | {settings.promoted_elo} | Starting rating for newly promoted clubs |",
    f"| `HOME_ADVANTAGE` | {settings.home_advantage} | Elo offset added to home expected score |",
    f"| `DECAY_RATE` | {settings.decay_rate} | Annual rating decay toward mean (0-1) |",
    f"| `SPREAD` | {settings.spread} | Logistic curve spread (higher = less confident predictions) |",
    f"| `MOV_AUTOCORR_COEFF` | {settings.mov_autocorr_coeff} | MoV autocorrelation coefficient |",
    f"| `MOV_AUTOCORR_SCALE` | {settings.mov_autocorr_scale} | MoV autocorrelation scale |",
    "",
]

md_content = "\n".join(md_lines)
md_path = os.path.join(OUT_DIR, "epl_elo_analysis.md")
with open(md_path, "w") as fh:
    fh.write(md_content)
print(f"Saved: {md_path}")

print("\nAll done.")
print(f"  {fig1_path}")
print(f"  {fig2_path}")
print(f"  {fig3_path}")
print(f"  {md_path}")
