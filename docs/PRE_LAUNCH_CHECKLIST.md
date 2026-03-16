# Pre-Launch Checklist

**Launch Target:** After Sprint 11 completion
**Launch Type:** Public (production deployment to Hetzner VPS)

---

## ✅ Completed (Sprint 1-7)

- [x] **M1-M3:** Elo algorithm, data pipeline, database
- [x] **Sprint 4:** European competitions integrated
- [x] **Sprint 5:** Database persistence, prediction API
- [x] **Sprint 6:** FastAPI backend, API documentation
- [x] **Sprint 7:** Frontend (rankings, team detail, prediction widget)

---

## 🚧 Required for Launch (Sprint 9-11)

### Sprint 9: M8 — Live Data & Fixtures

- [ ] **Data source selected:** football-data.org (free tier)
- [ ] **API integration working:**
  - [ ] Fetch upcoming fixtures (7 days ahead)
  - [ ] Fetch completed results (post-matchday)
  - [ ] Handle rate limits (10 calls/min)
- [ ] **Database schema updated:**
  - [ ] `fixtures` table created
  - [ ] `match_status` enum (Scheduled, Completed, Postponed)
- [ ] **Automation deployed:**
  - [ ] Daily cron job fetches fixtures
  - [ ] Daily cron job fetches results and updates ratings
- [ ] **Frontend displays:**
  - [ ] Upcoming fixtures page
  - [ ] Predictions for next 7 days
- [ ] **Testing:**
  - [ ] API integration tests pass
  - [ ] Rate limit handling works
  - [ ] Fallback on API failure (show last-fetched data)

---

### Sprint 10: M10 — Initial Elo Calibration Fix

- [ ] **Historical data ingested:**
  - [ ] 2010-2014 EPL data fetched
  - [ ] 2010-2014 La Liga data fetched
  - [ ] 2010-2014 Bundesliga data fetched
  - [ ] 2010-2014 Serie A data fetched
  - [ ] 2010-2014 Ligue 1 data fetched
  - [ ] 2011-2014 CL/EL data (already have, verify)
- [ ] **Warm-up period implemented:**
  - [ ] Elo runs from 2010-2026
  - [ ] Public display starts from 2015
  - [ ] Config parameter `display_from_date = 2015-08-01`
- [ ] **Validation:**
  - [ ] Top teams (Bayern, Barca, Real) ~1750-1850 in Aug 2015
  - [ ] Mid-table teams ~1450-1550 in Aug 2015
  - [ ] Bottom teams ~1300-1450 in Aug 2015
  - [ ] No team starts at exactly 1500
- [ ] **ADR written:**
  - [ ] `docs/adr-initial-elo-calibration.md` documenting approach

---

### Sprint 11: M9 — Prediction Tracking [CRITICAL FOR LAUNCH]

- [ ] **Database schema:**
  - [ ] `predictions` table created
  - [ ] Columns: match_id, predicted_at, p_home, p_draw, p_away, home_elo, away_elo
- [ ] **Prediction storage:**
  - [ ] All fixture predictions stored automatically
  - [ ] Predictions timestamped before match kickoff
- [ ] **Outcome tracking:**
  - [ ] Predictions linked to actual results
  - [ ] Brier score calculated for each prediction
  - [ ] Aggregate accuracy metrics computed (rolling 7/30 days)
- [ ] **Frontend pages:**
  - [ ] "Recent Predictions" page (/predictions)
    - [ ] Shows last 7 days of predictions vs. outcomes
    - [ ] Color-coded: correct (green), incorrect (red)
  - [ ] Accuracy badge on prediction widget
    - [ ] "Our model: 58% accurate this month" (or current accuracy)
  - [ ] About page explaining methodology
- [ ] **Testing:**
  - [ ] Prediction storage tests pass
  - [ ] Accuracy calculation tests pass
  - [ ] Frontend displays correct metrics

---

## 🎨 Polish (Before Launch)

### Sprint 7 Carryover

- [ ] **SEO optimization:**
  - [ ] Meta tags on all pages
  - [ ] Open Graph tags for social sharing
  - [ ] Sitemap.xml generated
- [ ] **Accessibility:**
  - [ ] ARIA labels on interactive elements
  - [ ] Keyboard navigation works
  - [ ] Color contrast meets WCAG AA
- [ ] **Error pages:**
  - [ ] Custom 404 page
  - [ ] Custom 500 page
  - [ ] Graceful API timeout handling
- [ ] **Branding:**
  - [ ] Favicon
  - [ ] Logo (if any)
  - [ ] Footer with data attribution

---

## 🔒 Security & Performance

- [ ] **API security:**
  - [ ] Rate limiting on public endpoints (100 req/min per IP)
  - [ ] CORS restricted to production domain
  - [ ] No sensitive data in error messages
- [ ] **Database:**
  - [ ] Regular backups configured (daily)
  - [ ] WAL mode enabled
  - [ ] Indexes on frequently queried columns
- [ ] **Performance:**
  - [ ] Page load time <2s on 3G
  - [ ] API response time <200ms p95
  - [ ] Gzip compression enabled
  - [ ] Static assets cached (1 year)

---

## 📊 Monitoring & Observability

- [ ] **Health checks:**
  - [ ] `/api/health` monitored (uptime check)
  - [ ] Alert if health check fails >5 minutes
- [ ] **Logging:**
  - [ ] Application logs to file (last 7 days retained)
  - [ ] Error logs to separate file
  - [ ] Log rotation configured
- [ ] **Metrics (optional for MVP):**
  - [ ] API request count
  - [ ] Prediction accuracy over time
  - [ ] User traffic (page views, unique visitors)

---

## 📝 Documentation

- [ ] **User-facing:**
  - [ ] About page (what is Elo, how it works)
  - [ ] FAQ (common questions)
  - [ ] Data sources attribution
- [ ] **Developer-facing:**
  - [ ] README updated with deployment instructions
  - [ ] API documentation (already done in Sprint 6)
  - [ ] Environment variables documented

---

## 🚀 Deployment

- [ ] **Docker:**
  - [ ] Dockerfile builds successfully
  - [ ] docker-compose.yml works locally
  - [ ] Image size optimized (<500MB)
- [ ] **Hetzner VPS:**
  - [ ] Docker installed on VPS
  - [ ] SSL certificate (Let's Encrypt)
  - [ ] Domain configured (DNS A record)
  - [ ] Firewall rules (only 80, 443, 22 open)
- [ ] **CI/CD:**
  - [ ] GitHub Actions workflow
  - [ ] Runs on push to `main`
  - [ ] Steps: lint → test → build → deploy
  - [ ] Deployment key configured

---

## ✅ Launch Readiness Criteria

**All must be TRUE before public launch:**

1. ✅ Sprints 7, 9, 10, 11 completed
2. ✅ Live data fetching working (fixtures + results)
3. ✅ Initial Elo ratings validated (warm-up period)
4. ✅ Prediction tracking live (users can see accuracy)
5. ✅ No critical bugs in issue tracker
6. ✅ SSL certificate valid
7. ✅ Backups configured and tested (restore works)
8. ✅ Monitoring alerts working (test by breaking health check)

---

## 🎯 Success Metrics (Week 1 Post-Launch)

**Track these to validate launch:**

- **Uptime:** >99% (max 1.4 hours downtime)
- **API errors:** <1% of requests
- **Page load time:** <2s average
- **Prediction accuracy:** Brier score <0.26 (track for 7 days)
- **User engagement:** (baseline — no target yet)
  - Unique visitors
  - Pages per session
  - Prediction widget usage

---

## 📅 Timeline

| Week | Sprint | Focus | Launch Readiness |
|------|--------|-------|------------------|
| Week 1 | Sprint 7 | Frontend + Deploy | 40% (Backend + Frontend done) |
| Week 2 | Sprint 9 | Live Data | 60% (Data pipeline ready) |
| Week 3 | Sprint 10 | Initial Elo Fix | 75% (Historical accuracy improved) |
| Week 4 | Sprint 11 | Prediction Tracking | 90% (Core features complete) |
| Week 4-5 | Polish | SEO, monitoring, docs | 100% ✅ |
| **Week 5** | **🚀 PUBLIC LAUNCH** | | |

---

## ⚠️ Launch Blockers (Don't Launch If...)

- [ ] Prediction tracking not working (M9 incomplete)
- [ ] Live data API failing >10% of requests
- [ ] Critical bug in production
- [ ] Backups not configured
- [ ] SSL certificate invalid or expired
- [ ] Page load time >5 seconds

---

## 📧 Pre-Launch Communication

**1 week before launch:**
- [ ] Announce on social media (Twitter, Reddit, etc.)
- [ ] Soft launch to small audience (friends, beta testers)
- [ ] Monitor for bugs

**Launch day:**
- [ ] Public announcement
- [ ] Monitor server load and errors
- [ ] Be ready to rollback if critical issues

**Week 1 post-launch:**
- [ ] Gather user feedback
- [ ] Fix any critical bugs
- [ ] Plan Sprint 12+ based on user requests
