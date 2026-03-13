"""Elo engine configuration via pydantic-settings.

All parameters are configurable via environment variables (prefixed ELO_)
or a .env file at the project root.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class EloSettings(BaseSettings):
    """Tunable parameters for the Elo rating engine."""

    k_factor: float = 20.0
    initial_elo: float = 1500.0
    home_advantage: float = 55.0
    decay_rate: float = 0.90
    promoted_elo: float = 1400.0
    spread: float = 400.0
    mov_autocorr_coeff: float = 2.2
    mov_autocorr_scale: float = 0.001

    # Competition tier K multipliers (applied on top of base k_factor)
    # Tier 1: CL knockout, Tier 2: CL group/league, Tier 3: EL knockout,
    # Tier 4: EL group + Conference League, Tier 5: domestic
    tier_1_weight: float = 1.5
    tier_2_weight: float = 1.2
    tier_3_weight: float = 1.2
    tier_4_weight: float = 1.0
    tier_5_weight: float = 1.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ELO_",
    )

    def tier_weight(self, tier: int) -> float:
        """Get K multiplier for a competition tier."""
        weights = {
            1: self.tier_1_weight,
            2: self.tier_2_weight,
            3: self.tier_3_weight,
            4: self.tier_4_weight,
            5: self.tier_5_weight,
        }
        return weights.get(tier, 1.0)
