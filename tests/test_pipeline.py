"""Tests for the data refresh pipeline."""

import pytest

from src.db.connection import init_db
from src.db.repository import get_match_count, get_team_count, insert_competition, insert_match, insert_team
from src.db.validation import (
    check_completeness,
    check_rating_consistency,
    check_referential_integrity,
    validate_database,
)


class TestValidation:
    """Test data validation checks."""

    @pytest.fixture
    def db(self):
        conn = init_db(":memory:")
        yield conn
        conn.close()

    def test_clean_db_passes(self, db):
        """Empty database should pass all checks."""
        issues = validate_database(db)
        assert issues == []

    def test_referential_integrity_clean(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        db.commit()
        issues = check_referential_integrity(db)
        assert issues == []

    def test_rating_consistency_clean(self, db):
        issues = check_rating_consistency(db)
        assert issues == []

    def test_completeness_no_issues_for_european(self, db):
        """European competitions should not trigger completeness warnings."""
        c1 = insert_competition(db, "Champions League", tier=1, country="Europe")
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Bayern Munich")
        insert_match(db, "2024-01-15", t1, t2, 1, 2, "A", c1, "2324")
        db.commit()
        issues = check_completeness(db)
        assert issues == []


class TestPipelineIdempotency:
    """Test that pipeline operations are idempotent."""

    @pytest.fixture
    def db(self):
        conn = init_db(":memory:")
        yield conn
        conn.close()

    def test_duplicate_match_rejected(self, db):
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")

        mid1 = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        mid2 = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")

        assert mid1 is not None
        assert mid2 is None
        assert get_match_count(db) == 1

    def test_duplicate_team_returns_same_id(self, db):
        id1 = insert_team(db, "Arsenal")
        id2 = insert_team(db, "Arsenal")
        assert id1 == id2
        assert get_team_count(db) == 1

    def test_duplicate_competition_returns_same_id(self, db):
        id1 = insert_competition(db, "Premier League")
        id2 = insert_competition(db, "Premier League")
        assert id1 == id2

    def test_match_result_values(self, db):
        """Valid match results are H, D, and A."""
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        # H, D, A should all succeed
        mid_h = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        mid_d = insert_match(db, "2024-02-15", t1, t2, 1, 1, "D", c1, "2324")
        mid_a = insert_match(db, "2024-03-15", t1, t2, 0, 1, "A", c1, "2324")
        assert mid_h is not None
        assert mid_d is not None
        assert mid_a is not None

    def test_empty_db_counts(self, db):
        """Empty database should have zero counts."""
        assert get_match_count(db) == 0
        assert get_team_count(db) == 0

    def test_multiple_matches_same_teams(self, db):
        """Same teams can play in different competitions on different dates."""
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        c2 = insert_competition(db, "FA Cup")
        mid1 = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        mid2 = insert_match(db, "2024-02-15", t1, t2, 1, 0, "H", c2, "2324")
        assert mid1 is not None
        assert mid2 is not None
        assert get_match_count(db) == 2

    def test_same_date_different_competitions(self, db):
        """Same teams on same date in different competitions is valid."""
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        c2 = insert_competition(db, "Champions League")
        mid1 = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        mid2 = insert_match(db, "2024-01-15", t1, t2, 1, 0, "H", c2, "2324")
        assert mid1 is not None
        assert mid2 is not None


class TestValidationEdgeCases:
    """Additional validation tests."""

    @pytest.fixture
    def db(self):
        conn = init_db(":memory:")
        yield conn
        conn.close()

    def test_completeness_checks_all_leagues(self, db):
        """All 5 domestic leagues should be checked."""
        from src.db.validation import EXPECTED_MATCHES_PER_SEASON
        expected_leagues = {"Premier League", "La Liga", "Serie A",
                            "Bundesliga", "Ligue 1"}
        assert set(EXPECTED_MATCHES_PER_SEASON.keys()) == expected_leagues

    def test_extreme_ratings_flagged(self, db):
        from src.db.validation import check_rating_consistency
        t1 = insert_team(db, "Arsenal")
        t2 = insert_team(db, "Chelsea")
        c1 = insert_competition(db, "Premier League")
        mid = insert_match(db, "2024-01-15", t1, t2, 2, 1, "H", c1, "2324")
        from src.db.repository import insert_rating
        insert_rating(db, t1, mid, "2024-01-15", 2500.0, 100.0)
        db.commit()
        issues = check_rating_consistency(db)
        assert any("Extreme" in issue for issue in issues)
