# Job Search Skill for Claude Code

Automated job search across LinkedIn, ATS APIs, and web boards with configurable match scoring. Works for any profession — engineers, PMs, designers, data scientists, and more.

## Features

- Searches 8 sources (Greenhouse, Lever, Ashby, RemoteOK, GetOnBoard, Himalayas, WorkingNomads, WeWorkRemotely)
- LinkedIn search through **Claude in Chrome** using your own logged-in session (no cookies stored)
- Location and title filters, so results are roles you can actually be hired for
- Optional salary floor, and a clear APPLY / EVALUATE / SKIP verdict with a reason
- Company watchlist for direct ATS monitoring
- Tracks opportunities with lifecycle management (Pending → Applied → Discarded → Closed)
- Multi-language support (English default, configurable)

## Requirements

- **[Claude in Chrome](docs/claude-in-chrome-setup.md) installed and connected.** Required for LinkedIn search and for reading job pages that need JavaScript or a login. Without it only `/job-search apis` works.
- **LinkedIn already logged in** in that same Chrome profile before you run the skill. The skill never asks for your password or cookies and never logs in for you.
- [Claude Code](https://claude.com/claude-code) CLI
- Python 3.9+ (standard library only, no pip installs)

Step-by-step install and troubleshooting: **[docs/claude-in-chrome-setup.md](docs/claude-in-chrome-setup.md)**.

## Quick Start

### Install

```bash
# Add marketplace (one-time)
claude plugin marketplace add zerofeed/job-search-skill

# Install plugin
claude plugin install job-search
```

### Run

```bash
# In any directory — the wizard will guide you through setup
claude
> /job-search
```

On first run without a config file, the skill offers 3 setup options:
1. **Manual YAML** — copy a template and fill it in
2. **Interactive Wizard** — answer questions, config is generated
3. **Resume Parser** — point to your resume (PDF/YAML/MD), profile is extracted automatically

## Configuration

After setup, your config lives in `job-search.yaml` in your working directory. See `templates/config.example.yaml` for the full schema.

### Presets

Start from a preset that matches your profile:

| Preset | File | Scoring Dimensions |
|--------|------|--------------------|
| Engineering Manager | `templates/presets/engineering-manager.yaml` | Domain, Stack, Leadership, Company Stage |
| Software Developer | `templates/presets/software-developer.yaml` | Stack, Seniority, Company Stage, Growth |
| Generic | `templates/presets/generic.yaml` | Role, Industry, Company Stage, Location |

### Key Config Sections

```yaml
# Your profile
profile:
  title: "Engineering Manager"
  skills: ["Go", "TypeScript", "AWS"]
  seniority: "senior"
  location: "Latin America"
  remote_only: true
  min_salary_usd_month: 6000          # optional hard floor
  location_allow: ["latam", "latin america", "worldwide"]
  location_block: ["united states", "europe", "india"]

# Search keywords (multi-language)
keywords:
  en: ["Engineering Manager", "Technical Lead"]
  es: ["Gerente de Ingeniería"]
  exclude: ["frontend", "mobile", "qa"]

# Scoring — the scorer returns APPLY / EVALUATE / SKIP with a reason
scoring:
  criteria: ["Domain fit", "Tech stack fit", "Leadership fit", "Company stage fit"]
```

## LinkedIn Setup

LinkedIn is read through Claude in Chrome. Nothing is stored in your config.

1. Install and connect Claude in Chrome: [docs/claude-in-chrome-setup.md](docs/claude-in-chrome-setup.md)
2. In that Chrome profile, log in to LinkedIn.
3. Set `sources.linkedin.enabled: true` in `job-search.yaml` and run `/job-search`.

If LinkedIn shows a login or checkpoint page the skill stops and tells you; log in in Chrome and run it again. The skill is read-only and will not apply, message or edit anything.

> **Upgrading from 1.0:** the `cookie` field and Playwright are gone. Delete any `li_at` value from `job-search.yaml`, and consider signing out of old LinkedIn sessions to invalidate it.

## How It Works

1. **Discovery** — Fetches jobs from enabled sources using your keywords and watchlist
2. **Dedup** — Removes duplicates across sources and against previously found opportunities
3. **Verdict** — Checks location, salary and role first, then judges the rest on your criteria
4. **Track** — Inserts results into your tracking file with lifecycle sections

## Output

Results are written to `opportunities.md` (configurable). Scratch files go in `.job-search/`. Sections:

| Section | Purpose |
|---------|---------|
| ✅ APPLIED | Opportunities you've applied to |
| ⏳ PENDING | New opportunities to review |
| ❌ DISCARDED | Opportunities you've passed on |
| 💀 CLOSED | Positions that are no longer open |
| WATCHLIST | Companies being monitored via ATS |

Pending rows use `| Company | Role | Verdict | Salary | Date | Link | Notes |`. The WATCHLIST table header must be `| Company | Domain | Career Page | ATS | Slug | Last checked |`. The skill only writes to the PENDING and DISCARDED sections. You manually move entries between sections as you progress through your job search.

## License

MIT
