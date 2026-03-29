# Job Search Skill for Claude Code

Automated job search across LinkedIn, ATS APIs, and web boards with configurable match scoring. Works for any profession — engineers, PMs, designers, data scientists, and more.

## Features

- Searches 7+ job board APIs (Greenhouse, Lever, RemoteOK, GetOnBoard, Himalayas, WorkingNomads, WeWorkRemotely)
- Optional LinkedIn search via Playwright (requires browser cookie)
- Configurable scoring dimensions — auto-proposed based on your profile
- Company watchlist for direct ATS monitoring
- Tracks opportunities with lifecycle management (Pending → Applied → Discarded → Closed)
- Multi-language support (English default, configurable)

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

# Search keywords (multi-language)
keywords:
  en: ["Engineering Manager", "Technical Lead"]
  es: ["Gerente de Ingeniería"]

# Scoring — auto-proposed, fully customizable
scoring:
  dimensions:
    - { name: "Domain fit", weight: 25 }
    - { name: "Tech stack fit", weight: 25 }
    - { name: "Leadership fit", weight: 25 }
    - { name: "Company stage fit", weight: 25 }
  thresholds:
    apply: 70
    evaluate: 50
```

## LinkedIn Setup (Optional)

LinkedIn search requires a browser cookie. To get it:

1. Open LinkedIn in your browser and log in
2. Open DevTools (`F12` or `Cmd+Option+I`)
3. Go to **Application** tab → **Cookies** → `linkedin.com`
4. Find the cookie named `li_at`
5. Copy the **Value** (starts with `AQEDA...`)
6. Paste it in your `job-search.yaml`:

```yaml
sources:
  linkedin:
    enabled: true
    cookie: "AQEDAQPk..."
```

> **Note:** This cookie expires periodically. If LinkedIn searches return 0 results, refresh the cookie using the steps above. The skill will warn you if the cookie is expired and continue with API sources only.

The skill will automatically install the Playwright MCP server if needed.

## Requirements

- [Claude Code](https://claude.com/claude-code) CLI
- Python 3.9+ (for the API fetcher script — uses standard library only, no pip installs)
- Playwright MCP (auto-installed if LinkedIn is enabled)

## How It Works

1. **Discovery** — Fetches jobs from enabled sources using your keywords and watchlist
2. **Dedup** — Removes duplicates across sources and against previously found opportunities
3. **Score** — Evaluates each new opportunity against your profile on your configured dimensions
4. **Track** — Inserts results into your tracking file with lifecycle sections

## Output

Results are written to `opportunities.md` (configurable) with these sections:

| Section | Purpose |
|---------|---------|
| ✅ APPLIED | Opportunities you've applied to |
| ⏳ PENDING | New opportunities to review |
| ❌ DISCARDED | Opportunities you've passed on |
| 💀 CLOSED | Positions that are no longer open |
| WATCHLIST | Companies being monitored via ATS |

The skill only writes to the PENDING and DISCARDED sections. You manually move entries between sections as you progress through your job search.

## License

MIT
