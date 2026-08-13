    #!/usr/bin/env python3
import json, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
TEAM = CFG["team_name"]
SHORT = CFG.get("short_name", TEAM)
SITE = CFG["site_url"].rstrip("/")


def clean_html(value):
    if not value:
        return ""
    return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)


def fetch_json(url):
    r = requests.get(url, timeout=30, headers={"User-Agent":"Mozilla/5.0 SteelQueensCalendar/1.0"})
    r.raise_for_status()
    return r.json()


def parse_iso_date(s):
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def candidates_from_rest():
    endpoints = [
        f"{SITE}/wp-json/sportspress/v2/events?per_page=100&orderby=date&order=asc",
        f"{SITE}/wp-json/wp/v2/sp_event?per_page=100&orderby=date&order=asc",
    ]
    events = []
    for url in endpoints:
        try:
            data = fetch_json(url)
            if not isinstance(data, list):
                continue
            for item in data:
                title_obj = item.get("title", "")
                title = clean_html(title_obj.get("rendered", "") if isinstance(title_obj, dict) else title_obj)
                if TEAM.lower() not in title.lower():
                    continue
                dt = parse_iso_date(item.get("date") or item.get("date_gmt"))
                if not dt:
                    continue
                link = item.get("link") or ""
                content = item.get("content", {})
                desc = clean_html(content.get("rendered", "") if isinstance(content, dict) else content)
                events.append({"title": title, "start": dt, "url": link, "description": desc})
            if events:
                return events, url
        except Exception:
            pass
    return [], None


def candidates_from_homepage():
    # Fallback only: captures public next-game cards if REST is disabled.
    r = requests.get(SITE + "/", timeout=30, headers={"User-Agent":"Mozilla/5.0 SteelQueensCalendar/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text("\n", strip=True)
    events = []
    # conservative pattern: team-vs-opponent followed soon by dd/mm/yyyy and optional hh:mm
    pat = re.compile(rf"({re.escape(TEAM)}\s+vs\s+[^\n]+).*?(\d{{2}}/\d{{2}}/\d{{4}})(?:.*?(\d{{1,2}}:\d{{2}}))?", re.I | re.S)
    for m in pat.finditer(text):
        title = m.group(1).strip()
        date_s = m.group(2)
        time_s = m.group(3) or "19:30"
        try:
            dt = datetime.strptime(date_s + " " + time_s, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        events.append({"title": title, "start": dt, "url": SITE, "description": ""})
    return events, SITE + "/"


def is_home(title):
    # Team listed first = home for standard "A vs B" fixture naming.
    norm = re.sub(r"\s+", " ", title).strip().lower()
    return norm.startswith(TEAM.lower() + " vs ")


def opponent(title):
    parts = re.split(r"\s+vs\s+", title, maxsplit=1, flags=re.I)
    if len(parts) == 2:
        return parts[1] if is_home(title) else parts[0]
    return title


def esc(s):
    return str(s).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fmt(dt):
    # Keep UTC in generated ICS; calendar apps display local time.
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def event_lines(ev):
    start = ev["start"]
    end = start + timedelta(minutes=int(CFG.get("default_duration_minutes", 180)))
    home = is_home(ev["title"])
    opp = opponent(ev["title"])
    nice = f"🏒 {SHORT} vs {opp}" if home else f"🏒 {SHORT} @ {opp}"
    uid_base = re.sub(r"[^a-z0-9]+", "-", (ev["title"] + start.isoformat()).lower()).strip("-")
    desc = ev.get("description", "").strip()
    if ev.get("url"):
        desc = (desc + "\n" if desc else "") + "Fixture source: " + ev["url"]
    location = CFG.get("home_venue", "") if home else ""
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid_base}@steel-queens-calendar",
        f"DTSTAMP:{fmt(datetime.now(timezone.utc))}",
        f"DTSTART:{fmt(start)}",
        f"DTEND:{fmt(end)}",
        f"SUMMARY:{esc(nice)}",
        f"LOCATION:{esc(location)}",
        f"DESCRIPTION:{esc(desc)}",
        "STATUS:CONFIRMED",
    ]
    for mins in CFG.get("reminders_minutes", []):
        lines += [
            "BEGIN:VALARM", "ACTION:DISPLAY",
            f"DESCRIPTION:{esc(nice)} reminder",
            f"TRIGGER:-PT{int(mins)}M" if int(mins) < 1440 else f"TRIGGER:-P{int(mins)//1440}D",
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines


def calendar(events, name):
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "PRODID:-//Steel Queens Calendar//EN",
        f"X-WR-CALNAME:{esc(name)}",
        f"X-WR-TIMEZONE:{esc(CFG.get('timezone','Europe/London'))}",
    ]
    for ev in sorted(events, key=lambda x: x["start"]):
        lines.extend(event_lines(ev))
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    events, source = candidates_from_rest()
    if not events:
        events, source = candidates_from_homepage()
    # Deduplicate by title + start.
    # Deduplicate by title + start.
dedup = {}
for e in events:
    dedup[(e["title"].lower(), e["start"].isoformat())] = e

events = list(dedup.values())

# Keep today's fixtures and all future fixtures.
today = datetime.now(timezone.utc).date()
events = [e for e in events if e["start"].date() >= today]

if not events:
    print(
        "No current or future Steel Queens fixtures found. "
        "Refusing to overwrite existing calendars.",
        file=sys.stderr,
    )
    return 2

home = [e for e in events if is_home(e["title"])]
    Path(CFG["feeds"]["all"]).write_text(calendar(events, "Caledonia Steel Queens – All Games"), encoding="utf-8")
    Path(CFG["feeds"]["home"]).write_text(calendar(home, "Caledonia Steel Queens – Home Games"), encoding="utf-8")
    print(f"Source: {source}")
    print(f"Found {len(events)} Steel Queens fixtures; {len(home)} home fixtures.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
