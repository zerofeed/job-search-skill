#!/usr/bin/env python3
"""
fetch_opportunities.py — Fetch job opportunities from multiple sources.

Usage:
    python3 fetch_opportunities.py \\
        --keywords "engineering manager,technical lead,head of engineering" \\
        --watchlist-file PATH \\
        --output PATH

The orchestrator (SKILL.md) reads job-search.yaml and passes keywords as a
comma-separated list. The watchlist is still read from the existing markdown
output file (the WATCHLIST table), keeping the same format as the original.

Output: JSON array of {title, company, location, url, posted_date, source[, salary]}
Sidecar: <output-stem>_meta.json with stats and discovered slugs.
"""

import argparse
import json
import re
import sys
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
TIMEOUT = 10

# Filters configured once in main() from CLI flags. Kept at module level so every
# fetcher applies the same title and location rules without extra parameters.
EXCLUDE_KEYWORDS: list[str] = []
LOCATION_ALLOW: list[str] = []
LOCATION_BLOCK: list[str] = []
SEARCH_QUERIES: list[str] = []


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class WatchlistEntry(NamedTuple):
    empresa: str
    ats: str
    slug: str


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch_json(url: str) -> object:
    """Fetch URL and return parsed JSON. Raises on HTTP/network errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_xml(url: str) -> str:
    """Fetch URL and return raw text. Raises on HTTP/network errors."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8")


# ---------------------------------------------------------------------------
# Keyword parsing
# ---------------------------------------------------------------------------

def parse_keywords(keywords_arg: str) -> list[str]:
    """
    Parse a comma-separated keywords string into a list of lowercase strings.
    Strips whitespace, removes empty entries.
    """
    return [kw.strip().lower() for kw in keywords_arg.split(",") if kw.strip()]


# ---------------------------------------------------------------------------
# Title filter
# ---------------------------------------------------------------------------

def matches_keywords(title: str, keywords: list[str]) -> bool:
    t = title.lower()
    if any(ex in t for ex in EXCLUDE_KEYWORDS):
        return False
    return any(kw in t for kw in keywords)


def location_ok(location: str) -> bool:
    """
    Decide whether a job location is plausible for the candidate.

    No filter is applied when LOCATION_ALLOW and LOCATION_BLOCK are both empty.
    Otherwise: an allowed term wins, then a blocked term rejects, and anything
    else is kept only if it is remote or has no location at all.
    """
    if not LOCATION_ALLOW and not LOCATION_BLOCK:
        return True
    loc = f" {location.lower()} "
    if any(term in loc for term in LOCATION_ALLOW):
        return True
    if any(term in loc for term in LOCATION_BLOCK):
        return False
    return "remote" in loc or not location.strip()


# ---------------------------------------------------------------------------
# Watchlist parser
# ---------------------------------------------------------------------------

def parse_watchlist(path: str) -> list[WatchlistEntry]:
    """
    Parse the WATCHLIST markdown table from the output file.

    Expected header:
        | Company | Domain | Career Page | ATS | Slug | Last checked |

    Skips rows where ats == 'none' or slug is '—' or empty.
    Returns list of WatchlistEntry(empresa, ats, slug).
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"[warn] watchlist file not found: {path}", file=sys.stderr)
        return []

    header_pattern = re.compile(
        r"\|\s*Company\s*\|\s*Domain\s*\|\s*Career Page\s*\|\s*ATS\s*\|\s*Slug\s*\|\s*Last checked\s*\|"
        r"|"
        r"\|\s*Empresa\s*\|\s*Dominio\s*\|\s*Career Page\s*\|\s*ATS\s*\|\s*Slug\s*\|\s*Ultima revision\s*\|"
    )

    lines = content.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if header_pattern.search(line):
            header_idx = i
            break

    if header_idx is None:
        return []

    entries: list[WatchlistEntry] = []
    # Skip header row (header_idx) and separator row (header_idx + 1)
    for line in lines[header_idx + 2:]:
        line = line.strip()
        if not line.startswith("|"):
            break  # end of table
        parts = [p.strip() for p in line.split("|")]
        # parts[0] is empty (before first |), parts[-1] is empty (after last |)
        # Columns: Company=1, Domain=2, Career Page=3, ATS=4, Slug=5
        if len(parts) < 7:
            continue
        empresa = parts[1]
        ats = parts[4].lower()
        slug = parts[5]

        if ats == "none":
            continue
        if not slug or slug == "—":
            continue

        entries.append(WatchlistEntry(empresa=empresa, ats=ats, slug=slug))

    return entries


# ---------------------------------------------------------------------------
# Greenhouse fetcher
# ---------------------------------------------------------------------------

def fetch_greenhouse(
    entries: list[WatchlistEntry],
    keywords: list[str],
) -> tuple[dict, list[dict]]:
    """Fetch job listings from Greenhouse ATS for all watchlist entries."""
    slugs = [e for e in entries if e.ats == "greenhouse"]
    stats = {
        "slugs_attempted": len(slugs),
        "slugs_ok": 0,
        "slugs_failed": [],
        "jobs_found": 0,
    }
    opportunities: list[dict] = []

    for entry in slugs:
        slug = entry.slug
        url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        try:
            data = fetch_json(url)
            jobs = data.get("jobs", [])
            stats["slugs_ok"] += 1
            company = entry.empresa or slug.capitalize()
            for job in jobs:
                title = job.get("title", "")
                if not matches_keywords(title, keywords):
                    continue
                loc = ""
                loc_obj = job.get("location")
                if isinstance(loc_obj, dict):
                    loc = loc_obj.get("name", "")
                updated_at = job.get("updated_at", "")
                posted_date = updated_at.split("T")[0] if updated_at else ""
                opportunities.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": job.get("absolute_url", ""),
                    "posted_date": posted_date,
                    "source": "greenhouse",
                })
        except Exception as exc:
            print(f"[warn] greenhouse/{slug}: {exc}", file=sys.stderr)
            stats["slugs_failed"].append(slug)

    stats["jobs_found"] = len(opportunities)
    return stats, opportunities


# ---------------------------------------------------------------------------
# Ashby fetcher (public posting API)
# ---------------------------------------------------------------------------

def fetch_ashby(
    entries: list[WatchlistEntry], keywords: list[str]
) -> tuple[dict, list[dict]]:
    slugs = [e for e in entries if e.ats == "ashby"]
    stats: dict = {"slugs_attempted": len(slugs), "slugs_ok": 0, "slugs_failed": [], "jobs_found": 0}
    opportunities: list[dict] = []

    for entry in slugs:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{entry.slug}"
        try:
            data = fetch_json(url)
            stats["slugs_ok"] += 1
            for job in data.get("jobs", []):
                title = job.get("title", "")
                if not matches_keywords(title, keywords):
                    continue
                published = job.get("publishedAt") or ""
                opportunities.append({
                    "title": title,
                    "company": entry.empresa,
                    "location": job.get("location", "") or "",
                    "url": job.get("jobUrl", ""),
                    "posted_date": published.split("T")[0] if published else "",
                    "source": "ashby",
                })
        except Exception as exc:
            print(f"[warn] ashby slug={entry.slug}: {exc}", file=sys.stderr)
            stats["slugs_failed"].append(entry.slug)

    stats["jobs_found"] = len(opportunities)
    return stats, opportunities


# ---------------------------------------------------------------------------
# Lever fetcher
# ---------------------------------------------------------------------------

def fetch_lever(
    entries: list[WatchlistEntry],
    keywords: list[str],
) -> tuple[dict, list[dict]]:
    """Fetch job listings from Lever ATS for all watchlist entries."""
    slugs = [e for e in entries if e.ats == "lever"]
    stats = {
        "slugs_attempted": len(slugs),
        "slugs_ok": 0,
        "slugs_failed": [],
        "jobs_found": 0,
    }
    opportunities: list[dict] = []

    for entry in slugs:
        slug = entry.slug
        url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
        try:
            data = fetch_json(url)
            stats["slugs_ok"] += 1
            company = entry.empresa or slug.capitalize()
            for posting in data:
                title = posting.get("text", "")
                if not matches_keywords(title, keywords):
                    continue
                categories = posting.get("categories", {})
                loc = (
                    categories.get("location", "")
                    if isinstance(categories, dict)
                    else ""
                )
                created_at_ms = posting.get("createdAt", 0)
                try:
                    posted_date = datetime.fromtimestamp(
                        created_at_ms / 1000, tz=timezone.utc
                    ).strftime("%Y-%m-%d")
                except Exception:
                    posted_date = ""
                opportunities.append({
                    "title": title,
                    "company": company,
                    "location": loc,
                    "url": posting.get("hostedUrl", ""),
                    "posted_date": posted_date,
                    "source": "lever",
                })
        except Exception as exc:
            print(f"[warn] lever/{slug}: {exc}", file=sys.stderr)
            stats["slugs_failed"].append(slug)

    stats["jobs_found"] = len(opportunities)
    return stats, opportunities


# ---------------------------------------------------------------------------
# GetOnBoard fetcher
# ---------------------------------------------------------------------------

REMOTE_TERMS = {"remote", "worldwide", "anywhere", "global", "latam", "latin america",
                "south america", "americas"}


def fetch_getonboard(keywords: list[str]) -> tuple[dict, list[dict]]:
    """
    Search GetOnBoard (LATAM-focused) with the configured search queries.

    The old /api/v0/jobs listing endpoint now answers 401, so this uses the
    public /api/v0/search/jobs endpoint instead.
    """
    stats = {"queries": 0, "jobs_found": 0}
    opportunities: list[dict] = []
    seen: set[str] = set()

    for query in SEARCH_QUERIES:
        url = (
            "https://www.getonbrd.com/api/v0/search/jobs"
            f"?query={urllib.parse.quote(query)}&per_page=30"
        )
        try:
            data = fetch_json(url)
            stats["queries"] += 1
        except Exception as exc:
            print(f"[warn] getonboard query={query!r}: {exc}", file=sys.stderr)
            continue
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            title = attrs.get("title", "")
            link = item.get("links", {}).get("public_url", "")
            if not link or link in seen or not matches_keywords(title, keywords):
                continue
            if not attrs.get("remote"):
                continue
            countries = [str(c).lower() for c in (attrs.get("countries") or [])]
            if countries and not any(c in REMOTE_TERMS for c in countries):
                continue
            seen.add(link)
            low, high = attrs.get("min_salary"), attrs.get("max_salary")
            published = attrs.get("published_at")
            posted_date = ""
            if isinstance(published, (int, float)):
                posted_date = datetime.fromtimestamp(published, tz=timezone.utc).strftime("%Y-%m-%d")
            opportunities.append({
                "title": title,
                "company": item.get("id", "").rsplit("-", 1)[0],
                "location": f"Remote ({attrs.get('remote_modality') or 'remote'})",
                "url": link,
                "posted_date": posted_date,
                "source": "getonboard",
                "salary": f"{low}-{high}" if low and high else "",
            })

    stats["jobs_found"] = len(opportunities)
    return stats, opportunities


# ---------------------------------------------------------------------------
# RemoteOK fetcher
# ---------------------------------------------------------------------------

def fetch_remoteok(keywords: list[str]) -> tuple[dict, list[dict]]:
    """Fetch jobs from RemoteOK using management-oriented tags."""
    tags = ["lead", "engineering-manager", "manager"]
    stats = {"tags_fetched": 0, "jobs_found": 0}
    opportunities: list[dict] = []

    for tag in tags:
        url = f"https://remoteok.com/api?tag={tag}"
        try:
            data = fetch_json(url)
            stats["tags_fetched"] += 1
            # Index 0 is metadata, jobs start at index 1
            for job in data[1:]:
                title = job.get("position", "")
                if not matches_keywords(title, keywords):
                    continue
                date_raw = job.get("date", "")
                posted_date = date_raw.split("T")[0] if date_raw else ""
                opportunities.append({
                    "title": title,
                    "company": job.get("company", ""),
                    "location": job.get("location", ""),
                    "url": job.get("url", ""),
                    "posted_date": posted_date,
                    "source": "remoteok",
                })
        except Exception as exc:
            print(f"[warn] remoteok tag={tag}: {exc}", file=sys.stderr)

    stats["jobs_found"] = len(opportunities)
    return stats, opportunities


# ---------------------------------------------------------------------------
# Himalayas fetcher
# ---------------------------------------------------------------------------

def fetch_himalayas(keywords: list[str]) -> tuple[dict, list[dict]]:
    """
    Search Himalayas with the configured search queries.

    Jobs carry explicit country restrictions; those are kept only when they are
    empty, global, or match a term from LOCATION_ALLOW.
    """
    stats = {"queries": 0, "jobs_found": 0}
    opportunities: list[dict] = []
    seen: set[str] = set()
    open_terms = {"worldwide", "anywhere", "latam", "latin america", "south america", "americas"}

    for query in SEARCH_QUERIES:
        url = f"https://himalayas.app/jobs/api/search?q={urllib.parse.quote_plus(query)}&limit=50"
        try:
            data = fetch_json(url)
            stats["queries"] += 1
        except Exception as exc:
            print(f"[warn] himalayas query={query!r}: {exc}", file=sys.stderr)
            continue
        for job in data.get("jobs", []):
            title = job.get("title", "")
            link = job.get("applicationLink") or job.get("guid", "")
            if not link or link in seen or not matches_keywords(title, keywords):
                continue
            restrictions = [str(r).lower() for r in (job.get("locationRestrictions") or [])]
            if LOCATION_ALLOW and restrictions:
                allowed = LOCATION_ALLOW + sorted(open_terms)
                if not any(any(term in r for term in allowed) for r in restrictions):
                    continue
            seen.add(link)
            low, high, currency = job.get("minSalary"), job.get("maxSalary"), job.get("currency") or ""
            pub = job.get("pubDate")
            posted_date = (
                datetime.fromtimestamp(int(pub), tz=timezone.utc).strftime("%Y-%m-%d") if pub else ""
            )
            where = ", ".join(restrictions) if restrictions else "worldwide"
            opportunities.append({
                "title": title,
                "company": job.get("companyName", ""),
                "location": f"Remote ({where})",
                "url": link,
                "posted_date": posted_date,
                "source": "himalayas",
                "salary": (
                    f"{low}-{high} {currency} /{job.get('salaryPeriod', '')}".strip()
                    if low and high else ""
                ),
            })

    stats["jobs_found"] = len(opportunities)
    return stats, opportunities


# ---------------------------------------------------------------------------
# Working Nomads fetcher
# ---------------------------------------------------------------------------

def fetch_workingnomads(keywords: list[str]) -> tuple[dict, list[dict]]:
    """Fetch all jobs from Working Nomads single endpoint."""
    stats = {"fetched": False, "jobs_found": 0}
    opportunities: list[dict] = []

    url = "https://www.workingnomads.com/api/exposed_jobs/"
    try:
        data = fetch_json(url)
        stats["fetched"] = True
        for job in data:
            title = job.get("title", "")
            if not matches_keywords(title, keywords):
                continue
            pub = job.get("pub_date", "")
            posted_date = pub.split("T")[0] if pub else ""
            opportunities.append({
                "title": title,
                "company": job.get("company_name", ""),
                "location": job.get("location", ""),
                "url": job.get("url", ""),
                "posted_date": posted_date,
                "source": "workingnomads",
            })
    except Exception as exc:
        print(f"[warn] workingnomads: {exc}", file=sys.stderr)

    stats["jobs_found"] = len(opportunities)
    return stats, opportunities


# ---------------------------------------------------------------------------
# We Work Remotely fetcher (RSS)
# ---------------------------------------------------------------------------

def fetch_weworkremotely(keywords: list[str]) -> tuple[dict, list[dict]]:
    """Fetch jobs from We Work Remotely via RSS feed."""
    stats = {"fetched": False, "jobs_found": 0}
    opportunities: list[dict] = []

    url = "https://weworkremotely.com/remote-jobs.rss"
    try:
        xml_data = fetch_xml(url)
        stats["fetched"] = True
        root = ET.fromstring(xml_data)

        for item in root.findall(".//item"):
            title_el = item.find("title")
            raw_title = (
                title_el.text.strip()
                if title_el is not None and title_el.text
                else ""
            )
            if not matches_keywords(raw_title, keywords):
                continue

            link_el = item.find("link")
            link = (
                link_el.text.strip()
                if link_el is not None and link_el.text
                else ""
            )

            region_el = item.find("region")
            region = (
                region_el.text.strip()
                if region_el is not None and region_el.text
                else ""
            )

            # RSS title format is "Company: Role" — split on first colon
            company = ""
            title = raw_title
            if ":" in raw_title:
                company = raw_title.split(":")[0].strip()
                title = ":".join(raw_title.split(":")[1:]).strip()

            posted_date = ""
            pub_el = item.find("pubDate")
            if pub_el is not None and pub_el.text:
                try:
                    dt = parsedate_to_datetime(pub_el.text)
                    posted_date = dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

            opportunities.append({
                "title": title,
                "company": company,
                "location": region,
                "url": link,
                "posted_date": posted_date,
                "source": "weworkremotely",
            })
    except Exception as exc:
        print(f"[warn] weworkremotely: {exc}", file=sys.stderr)

    stats["jobs_found"] = len(opportunities)
    return stats, opportunities


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _normalize_url(url: str) -> str:
    """Lowercase URL and strip trailing slash for comparison."""
    return url.lower().rstrip("/")


def deduplicate(opportunities: list[dict]) -> list[dict]:
    """Remove duplicate opportunities by URL (case-insensitive, trailing-slash agnostic)."""
    seen_urls: set[str] = set()
    result: list[dict] = []
    for opp in opportunities:
        url = opp.get("url", "")
        if not url:
            result.append(opp)
            continue
        normalized = _normalize_url(url)
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        result.append(opp)
    return result


# ---------------------------------------------------------------------------
# Slug discovery — detect new Greenhouse / Lever slugs from opportunity URLs
# ---------------------------------------------------------------------------

GREENHOUSE_PATTERN = re.compile(r"boards\.greenhouse\.io/([a-zA-Z0-9_-]+)/")
LEVER_PATTERN = re.compile(r"jobs\.lever\.co/([a-zA-Z0-9_-]+)/")


def discover_new_slugs(
    opportunities: list[dict],
    existing_slugs: set[str],
) -> list[dict]:
    """
    Scan opportunity URLs for Greenhouse / Lever patterns.
    Returns list of newly discovered slugs not already in the watchlist.
    Each entry: {slug, ats, company}
    """
    discovered: dict[str, dict] = {}

    for opp in opportunities:
        url = opp.get("url", "")
        company = opp.get("company", "")

        gh_match = GREENHOUSE_PATTERN.search(url)
        if gh_match:
            slug = gh_match.group(1).lower()
            if slug not in existing_slugs and slug not in discovered:
                discovered[slug] = {"slug": slug, "ats": "greenhouse", "company": company}
            continue

        lv_match = LEVER_PATTERN.search(url)
        if lv_match:
            slug = lv_match.group(1).lower()
            if slug not in existing_slugs and slug not in discovered:
                discovered[slug] = {"slug": slug, "ats": "lever", "company": company}

    return list(discovered.values())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch job opportunities from multiple sources and write JSON output."
    )
    parser.add_argument(
        "--keywords",
        required=True,
        help=(
            "Comma-separated list of job title keywords to match, e.g. "
            '"engineering manager,technical lead,head of engineering". '
            "Case-insensitive substring match against job titles."
        ),
    )
    parser.add_argument(
        "--watchlist-file",
        required=True,
        help=(
            "Path to the markdown output file that contains a WATCHLIST table "
            "with Company, Domain, Career Page, ATS, Slug, and Last checked columns."
        ),
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to write the JSON output array of discovered opportunities.",
    )
    parser.add_argument(
        "--exclude",
        default="",
        help="Comma-separated title terms to drop even if a keyword matches (e.g. 'frontend,mobile,qa').",
    )
    parser.add_argument(
        "--location-allow",
        default="",
        help="Comma-separated location terms that are acceptable (e.g. 'latam,latin america,brazil').",
    )
    parser.add_argument(
        "--location-block",
        default="",
        help="Comma-separated location terms to reject (e.g. 'united states,europe,india'). "
             "Remote or empty locations that match neither list are kept.",
    )
    parser.add_argument(
        "--search-queries",
        default="",
        help="Comma-separated queries for the search-based boards (GetOnBoard, Himalayas). "
             "Defaults to the first 8 keywords.",
    )
    args = parser.parse_args()

    keywords = parse_keywords(args.keywords)
    if not keywords:
        print("[error] --keywords produced an empty list. Provide at least one keyword.", file=sys.stderr)
        sys.exit(1)

    global EXCLUDE_KEYWORDS, LOCATION_ALLOW, LOCATION_BLOCK, SEARCH_QUERIES
    EXCLUDE_KEYWORDS = parse_keywords(args.exclude)
    LOCATION_ALLOW = parse_keywords(args.location_allow)
    LOCATION_BLOCK = parse_keywords(args.location_block)
    SEARCH_QUERIES = parse_keywords(args.search_queries) or keywords[:8]

    entries = parse_watchlist(args.watchlist_file)

    all_opportunities: list[dict] = []

    # Greenhouse (watchlist-driven)
    gh_stats, gh_opps = fetch_greenhouse(entries, keywords)
    all_opportunities.extend(gh_opps)

    # Lever (watchlist-driven)
    lv_stats, lv_opps = fetch_lever(entries, keywords)
    all_opportunities.extend(lv_opps)

    # Ashby (watchlist-driven)
    ash_stats, ash_opps = fetch_ashby(entries, keywords)
    all_opportunities.extend(ash_opps)

    # GetOnBoard (paginated public API)
    gob_stats, gob_opps = fetch_getonboard(keywords)
    all_opportunities.extend(gob_opps)

    # RemoteOK (tag-based public API)
    rok_stats, rok_opps = fetch_remoteok(keywords)
    all_opportunities.extend(rok_opps)

    # Himalayas (paginated public API)
    him_stats, him_opps = fetch_himalayas(keywords)
    all_opportunities.extend(him_opps)

    # Working Nomads (single endpoint)
    wn_stats, wn_opps = fetch_workingnomads(keywords)
    all_opportunities.extend(wn_opps)

    # We Work Remotely (RSS/XML)
    wwr_stats, wwr_opps = fetch_weworkremotely(keywords)
    all_opportunities.extend(wwr_opps)

    # Deduplicate by URL
    all_opportunities = deduplicate(all_opportunities)

    # Drop locations the candidate cannot work from
    total_before_location = len(all_opportunities)
    all_opportunities = [o for o in all_opportunities if location_ok(o.get("location", ""))]

    # Discover new ATS slugs from opportunity URLs
    existing_slugs = {e.slug.lower() for e in entries}
    new_slugs = discover_new_slugs(all_opportunities, existing_slugs)

    timestamp = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Write opportunities as JSON array
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_opportunities, f, indent=2, ensure_ascii=False)

    # Write metadata sidecar: stats + discovered slugs
    meta_path = args.output.rsplit(".", 1)[0] + "_meta.json"
    meta = {
        "timestamp": timestamp,
        "keywords_used": keywords,
        "total_opportunities": len(all_opportunities),
        "dropped_by_location": total_before_location - len(all_opportunities),
        "sources": {
            "greenhouse": gh_stats,
            "lever": lv_stats,
            "ashby": ash_stats,
            "getonboard": gob_stats,
            "remoteok": rok_stats,
            "himalayas": him_stats,
            "workingnomads": wn_stats,
            "weworkremotely": wwr_stats,
        },
        "discovered_slugs": new_slugs,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"Done. {len(all_opportunities)} opportunities written to {args.output}")
    if new_slugs:
        slug_summary = ", ".join(
            f"{s['slug']} ({s['ats']})" for s in new_slugs
        )
        print(f"Discovered {len(new_slugs)} new slug(s): {slug_summary}")

    sys.exit(0)


if __name__ == "__main__":
    main()
