# Sprint 8 — Technical Debt & Code Quality

**Depends on:** Sprint 7 completed (frontend deployed)
**Status:** NOT STARTED
**Goal:** Address accumulated technical debt, improve code quality, and prepare for future development.

---

## Items

### 1. Pydantic Deprecation Warnings

**Priority:** P2 | **Impact:** Low | **Effort:** Small

Fix 54 Pydantic deprecation warnings in `backend/models.py`.

**Issue:**
```
PydanticDeprecatedSince20: Using extra keyword arguments on `Field` is deprecated
and will be removed. Use `json_schema_extra` instead. (Extra keys: 'example')
```

**Current pattern:**
```python
database_connected: bool = Field(
    ..., description="Database connected", example=True
)
```

**Target pattern:**
```python
database_connected: bool = Field(
    ...,
    description="Database connected",
    json_schema_extra={"example": True}
)
```

**Deliverables:**
- Update all `Field` definitions in `backend/models.py` to use `json_schema_extra`
- Verify OpenAPI spec still generates correctly at `/openapi.json`
- Confirm all 153 tests still pass without warnings
- Update `backend/main.py` Query parameters similarly if needed

**Acceptance criteria:**
- [ ] Zero Pydantic deprecation warnings when running tests
- [ ] OpenAPI documentation unchanged (verify with snapshot comparison)
- [ ] All tests passing

---

### 2. Tier Weight Optimization

**Priority:** P3 | **Impact:** Medium | **Effort:** Large

Optimize competition tier weights via parameter sweep instead of hand-picking.

**Current state:**
- Tier weights are hand-picked: T1=1.5x, T2=1.2x, T3=1.2x, T4/T5=1.0x
- No empirical validation that these are optimal

**Scope:**
- Extend `param_sweep.py` to include tier weights in sweep
- Test combinations: T1 ∈ [1.0, 1.2, 1.5, 2.0], T2 ∈ [1.0, 1.2, 1.5], etc.
- Evaluate on cross-league prediction accuracy (CL/EL matches)
- Document findings in experiment log

**Deliverables:**
- Tier weight sweep results
- Updated `EloSettings` defaults if better weights found
- ADR documenting tier weight selection

**Acceptance criteria:**
- [ ] Sweep completed across tier weight combinations
- [ ] Optimal weights identified or current weights validated
- [ ] ADR written: `docs/adr-tier-weights.md`

---

### 3. Test Coverage Gaps

**Priority:** P2 | **Impact:** Medium | **Effort:** Medium

Improve test coverage for edge cases and error paths.

**Known gaps:**
- European data parser: minimal coverage of edge cases (postponed matches, unusual formats)
- Team name normalization: no tests for ambiguous mappings
- Pipeline: no tests for partial failures (database locked, corrupted CSV)
- Prediction API: no tests for edge cases (teams with no rating history)

**Deliverables:**
- Add tests for European data edge cases
- Add tests for team name normalization failures
- Add integration tests for pipeline failure modes
- Achieve >85% code coverage (currently ~70% estimated)

**Acceptance criteria:**
- [ ] Coverage report generated and >85%
- [ ] All identified edge cases covered
- [ ] No decrease in test execution speed

---

### 4. Code Quality Improvements

**Priority:** P3 | **Impact:** Low | **Effort:** Small

Address minor code quality issues.

**Items:**
- Add type hints to all remaining functions (estimated ~10 missing)
- Fix pylint warnings (if any)
- Standardize docstring coverage (ensure all public functions have docstrings)
- Add pre-commit hooks: black, ruff, mypy

**Deliverables:**
- Pre-commit configuration file (`.pre-commit-config.yaml`)
- Type hints added where missing
- Docstring coverage at 100% for public APIs

**Acceptance criteria:**
- [ ] Pre-commit hooks configured and passing
- [ ] `mypy src/ backend/` passes with no errors
- [ ] All public functions have docstrings

---

### 5. Database Index Performance

**Priority:** P2 | **Impact:** Medium | **Effort:** Small

Add missing database indexes for common API query patterns.

**Analysis needed:**
- Profile slow queries using SQLite's `EXPLAIN QUERY PLAN`
- Identify missing indexes on frequently queried columns

**Likely candidates:**
- `ratings_history (team_id, date)` — for team history queries
- `matches (date)` — for historical rankings
- `teams_fts` — ensure FTS5 index is optimal

**Deliverables:**
- Index analysis report
- Migration script to add indexes
- Before/after query performance benchmarks

**Acceptance criteria:**
- [ ] Slow query analysis completed
- [ ] Indexes added where beneficial (>20% speedup)
- [ ] API response times < 100ms for p95

---

## Acceptance Criteria (Sprint 8 Overall)

- [ ] All Pydantic deprecation warnings resolved
- [ ] Test suite runs clean (no warnings, >85% coverage)
- [ ] Code quality tools (pre-commit) configured and passing
- [ ] Database query performance validated and optimized
- [ ] Tier weight optimization decision documented

## Out of Scope

- Two-leg tie modeling (deferred to M7)
- Full UEFA league coverage (M6)
- Advanced parameter optimization framework (M5)

---

## Estimated Effort

| Item | Priority | Effort | Impact |
|------|----------|--------|--------|
| Pydantic warnings | P2 | 1 hour | Low |
| Tier weight optimization | P3 | 8 hours | Medium |
| Test coverage | P2 | 6 hours | Medium |
| Code quality | P3 | 3 hours | Low |
| Database indexes | P2 | 2 hours | Medium |

**Total:** ~20 hours (2-3 days part-time)

---

## Notes

This sprint can be tackled incrementally alongside Sprint 7 or as a dedicated cleanup sprint after deployment. Items can be re-prioritized based on production feedback.
