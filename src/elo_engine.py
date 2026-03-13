"""Reusable Elo rating engine for football match data.

Decouples rating logic from visualization/reporting so it can be
unit-tested and reused across leagues.
"""

import bisect
import math
from dataclasses import dataclass

import pandas as pd

from src.config import EloSettings


@dataclass
class EloResult:
    """Container for Elo computation results."""

    ratings: dict[str, float]
    history: dict[str, list[tuple[pd.Timestamp, float]]]
    deltas: list[float]
    matches_processed: int


class EloEngine:
    """Configurable Elo rating engine for football matches.

    Args:
        settings: Tunable parameters (K-factor, spread, home advantage, etc.).
    """

    def __init__(self, settings: EloSettings | None = None) -> None:
        self.settings = settings or EloSettings()

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        """Probability that team A beats team B."""
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / self.settings.spread))

    def mov_multiplier(self, goal_diff: int, elo_diff: float) -> float:
        """Margin-of-victory K multiplier (FiveThirtyEight formula).

        Scales the update by goal difference while correcting for
        autocorrelation (strong teams beating weak teams by large margins).

        Args:
            goal_diff: Absolute goal difference (>= 0).
            elo_diff: Winner's Elo minus loser's Elo (can be negative for upsets).
        """
        s = self.settings
        ln_component = math.log(abs(goal_diff) + 1) / math.log(2)
        autocorr = s.mov_autocorr_coeff / (
            elo_diff * s.mov_autocorr_scale + s.mov_autocorr_coeff
        )
        return ln_component * autocorr

    def elo_update(
        self,
        r_home: float,
        r_away: float,
        result: str,
        home_goals: int = 0,
        away_goals: int = 0,
        tier: int = 5,
    ) -> tuple[float, float, float, float]:
        """Compute new ratings after a match.

        Home advantage is applied to the expected-score calculation only;
        stored ratings remain unbiased.

        Args:
            r_home: Home team's current Elo.
            r_away: Away team's current Elo.
            result: Match result — "H", "D", or "A".
            home_goals: Full-time home goals (for MoV adjustment).
            away_goals: Full-time away goals (for MoV adjustment).
            tier: Competition tier (1-5) for K multiplier. Default 5 (domestic).

        Returns:
            (new_home, new_away, delta_home, delta_away).
        """
        s = self.settings
        e_home = self.expected_score(r_home + s.home_advantage, r_away)
        e_away = 1.0 - e_home

        if result == "H":
            s_home, s_away = 1.0, 0.0
        elif result == "A":
            s_home, s_away = 0.0, 1.0
        else:
            s_home, s_away = 0.5, 0.5

        goal_diff = abs(home_goals - away_goals)
        k = s.k_factor * s.tier_weight(tier)

        if goal_diff > 0:
            # Winner's Elo minus loser's Elo for autocorrelation correction
            if result == "H":
                elo_diff = r_home - r_away
            elif result == "A":
                elo_diff = r_away - r_home
            else:
                elo_diff = 0.0
            k = k * self.mov_multiplier(goal_diff, elo_diff)

        dh = k * (s_home - e_home)
        da = k * (s_away - e_away)
        return r_home + dh, r_away + da, dh, da

    def apply_time_decay(
        self,
        team: str,
        current_date: pd.Timestamp,
        elo_ratings: dict[str, float],
        last_match: dict[str, pd.Timestamp],
    ) -> None:
        """Decay a team's rating toward initial_elo based on days since last match."""
        if team not in last_match:
            return
        days = (current_date - last_match[team]).days
        if days <= 0:
            return
        s = self.settings
        decay = s.decay_rate ** (days / 365.0)
        elo_ratings[team] = decay * elo_ratings[team] + (1 - decay) * s.initial_elo

    def compute_ratings(self, matches: pd.DataFrame) -> EloResult:
        """Run the Elo engine over a sorted DataFrame of matches.

        Expected columns: Date, HomeTeam, AwayTeam, FTR, FTHG, FTAG, Season.
        Optional: Tier (int 1-5, default 5 for domestic).
        The DataFrame must be sorted by Date ascending.

        Args:
            matches: Match data with required columns.

        Returns:
            EloResult with final ratings, per-team history, and per-match deltas.
        """
        s = self.settings
        elo: dict[str, float] = {}
        last_match_date: dict[str, pd.Timestamp] = {}
        history: dict[str, list[tuple[pd.Timestamp, float]]] = {}
        deltas: list[float] = []
        first_season = matches["Season"].iloc[0]
        has_tier = "Tier" in matches.columns

        for _, row in matches.iterrows():
            home = row["HomeTeam"]
            away = row["AwayTeam"]
            result = row["FTR"]
            date = row["Date"]
            season = row["Season"]
            home_goals = int(row.get("FTHG", 0))
            away_goals = int(row.get("FTAG", 0))
            tier = int(row["Tier"]) if has_tier else 5

            # Initialize new teams
            for team in (home, away):
                if team not in elo:
                    init_rating = (
                        s.initial_elo if season == first_season else s.promoted_elo
                    )
                    elo[team] = init_rating
                    history[team] = [(date, init_rating)]

            # Time decay
            self.apply_time_decay(home, date, elo, last_match_date)
            self.apply_time_decay(away, date, elo, last_match_date)

            # Update
            new_h, new_a, dh, da = self.elo_update(
                elo[home], elo[away], result, home_goals, away_goals, tier
            )
            elo[home] = new_h
            elo[away] = new_a
            last_match_date[home] = date
            last_match_date[away] = date
            history[home].append((date, new_h))
            history[away].append((date, new_a))
            deltas.append(dh)

        return EloResult(
            ratings=elo,
            history=history,
            deltas=deltas,
            matches_processed=len(deltas),
        )

    def get_rankings(self, ratings: dict[str, float]) -> list[tuple[str, float]]:
        """Return all teams sorted by Elo descending."""
        return sorted(ratings.items(), key=lambda x: -x[1])

    @staticmethod
    def get_ratings_at(
        history: dict[str, list[tuple[pd.Timestamp, float]]],
        date: str | pd.Timestamp,
    ) -> dict[str, float]:
        """Return all team ratings as of a given date.

        Uses binary search over each team's sorted history to find the
        most recent rating on or before the requested date.

        Args:
            history: Per-team history from EloResult.history.
            date: Target date (string or Timestamp).

        Returns:
            Dict mapping team name to rating at that date. Teams whose
            first match is after the date are excluded.
        """
        target = pd.Timestamp(date)
        ratings: dict[str, float] = {}

        for team, entries in history.items():
            dates = [d for d, _ in entries]
            idx = bisect.bisect_right(dates, target) - 1
            if idx >= 0:
                ratings[team] = entries[idx][1]

        return ratings
