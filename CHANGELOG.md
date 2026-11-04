# Changelog

## 1.1.0

**Breaking**
- LinkedIn is now read through Claude in Chrome using your logged-in session. The `li_at` cookie and the Playwright MCP are removed; delete any cookie from your `job-search.yaml`.
- Scoring uses `scoring.criteria` and returns an APPLY / EVALUATE / SKIP verdict instead of weighted percentages.

**Fixes**
- The skill called the script with `--config`, which the script never accepted, so API results were always empty. The skill now passes the flags the script defines.
- GetOnBoard returned 401 on the old listing endpoint; it now uses the search endpoint.
- Himalayas switched to its search endpoint and respects country restrictions.

**Added**
- Ashby source (public posting API).
- `--exclude`, `--location-allow`, `--location-block` and `--search-queries` flags, and matching config fields.
- `profile.min_salary_usd_month`, and a `salary` field when a source publishes one.
- `docs/claude-in-chrome-setup.md` and offline tests (`python3 -m unittest discover -s tests`).
