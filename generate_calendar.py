#!/usr/bin/env python3

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

    return BeautifulSoup(
        value,
        "html.parser",
    ).get_text(" ", strip=True)


def fetch_json(url):
    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 SteelQueensCalendar/1.0"
        },
    )

    response.raise_for_status()
    return response.json()


def parse_iso_date(value):
    if not value:
        return None

    value = value.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(value)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt

    except ValueError:
        return None


def candidates_from_rest():
    endpoints = [
        (
            f"{SITE}/wp-json/sportspress/v2/events"
            "?per_page=100&orderby=date&order=asc"
        ),
        (
            f"{SITE}/wp-json/wp/v2/sp_event"
            "?per_page=100&orderby=date&order=asc"
        ),
    ]

    events = []

    for url in endpoints:
        try:
            data = fetch_json(url)

            if not isinstance(data, list):
                continue

            for item in data:
                title_obj = item.get("title", "")

                if isinstance(title_obj, dict):
                    title = clean_html(
                        title_obj.get("rendered", "")
                    )
                else:
                    title = clean_html(title_obj)

                if TEAM.lower() not in title.lower():
                    continue

                dt = parse_iso_date(
                    item.get("date")
                    or item.get("date_gmt")
                )

                if not dt:
                    continue

                link = item.get("link") or ""

                content = item.get("content", {})

                if isinstance(content, dict):
                    desc = clean_html(
                        content.get("rendered", "")
                    )
                else:
                    desc = clean_html(content)

                events.append(
                    {
                        "title": title,
                        "start": dt,
                        "url": link,
                        "description": desc,
                    }
                )

            if events:
                return events, url

        except Exception:
            pass

    return [], None


def candidates_from_homepage():
    """
    Fallback if the WordPress REST/SportsPress API
    is unavailable.

    Captures public fixture information from the
    Steel Queens website.
    """

    response = requests.get(
        SITE + "/",
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 SteelQueensCalendar/1.0"
        },
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    text = soup.get_text(
        "\n",
        strip=True,
    )

    events = []

    pattern = re.compile(
        rf"({re.escape(TEAM)}\s+vs\s+[^\n]+)"
        rf".*?"
        rf"(\d{{2}}/\d{{2}}/\d{{4}})"
        rf"(?:.*?(\d{{1,2}}:\d{{2}}))?",
        re.I | re.S,
    )

    for match in pattern.finditer(text):
        title = match.group(1).strip()
        date_string = match.group(2)

        # Default to 19:30 if no time is published.
        time_string = match.group(3) or "19:30"

        try:
            dt = datetime.strptime(
                date_string + " " + time_string,
                "%d/%m/%Y %H:%M",
            ).replace(tzinfo=timezone.utc)

        except ValueError:
            continue

        events.append(
            {
                "title": title,
                "start": dt,
                "url": SITE,
                "description": "",
            }
        )

    return events, SITE + "/"


def is_home(title):
    """
    The Steel Queens website normally formats fixtures:

        Caledonia Steel Queens vs Opponent

    for home games.
    """

    normalised = re.sub(
        r"\s+",
        " ",
        title,
    ).strip().lower()

    return normalised.startswith(
        TEAM.lower() + " vs "
    )


def opponent(title):
    parts = re.split(
        r"\s+vs\s+",
        title,
        maxsplit=1,
        flags=re.I,
    )

    if len(parts) == 2:
        if is_home(title):
            return parts[1]

        return parts[0]

    return title


def esc(value):
    """
    Escape text for use inside an ICS file.
    """

    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fmt(dt):
    """
    Store times in UTC.

    Calendar apps will display the corresponding
    local time automatically.
    """

    return (
        dt.astimezone(timezone.utc)
        .strftime("%Y%m%dT%H%M%SZ")
    )


def event_lines(event):
    start = event["start"]

    duration = int(
        CFG.get(
            "default_duration_minutes",
            180,
        )
    )

    end = start + timedelta(
        minutes=duration
    )

    home = is_home(
        event["title"]
    )

    opp = opponent(
        event["title"]
    )

    if home:
        nice_title = (
            f"🏒 {SHORT} vs {opp}"
        )
    else:
        nice_title = (
            f"🏒 {SHORT} @ {opp}"
        )

    uid_base = re.sub(
        r"[^a-z0-9]+",
        "-",
        (
            event["title"]
            + start.isoformat()
        ).lower(),
    ).strip("-")

    description = (
        event.get(
            "description",
            "",
        ).strip()
    )

    if event.get("url"):
        if description:
            description += "\n"

        description += (
            "Fixture source: "
            + event["url"]
        )

    if home:
        location = CFG.get(
            "home_venue",
            "",
        )
    else:
        location = ""

    lines = [
        "BEGIN:VEVENT",
        (
            f"UID:{uid_base}"
            "@steel-queens-calendar"
        ),
        (
            "DTSTAMP:"
            + fmt(
                datetime.now(
                    timezone.utc
                )
            )
        ),
        f"DTSTART:{fmt(start)}",
        f"DTEND:{fmt(end)}",
        f"SUMMARY:{esc(nice_title)}",
        f"LOCATION:{esc(location)}",
        (
            "DESCRIPTION:"
            + esc(description)
        ),
        "STATUS:CONFIRMED",
    ]

    for minutes in CFG.get(
        "reminders_minutes",
        [],
    ):
        minutes = int(minutes)

        if minutes < 1440:
            trigger = (
                f"TRIGGER:-PT{minutes}M"
            )
        else:
            days = minutes // 1440
            trigger = (
                f"TRIGGER:-P{days}D"
            )

        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            (
                "DESCRIPTION:"
                + esc(
                    f"{nice_title} reminder"
                )
            ),
            trigger,
            "END:VALARM",
        ]

    lines.append(
        "END:VEVENT"
    )

    return lines


def calendar(events, name):
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        (
            "PRODID:"
            "-//Steel Queens Calendar//EN"
        ),
        (
            "X-WR-CALNAME:"
            + esc(name)
        ),
        (
            "X-WR-TIMEZONE:"
            + esc(
                CFG.get(
                    "timezone",
                    "Europe/London",
                )
            )
        ),
    ]

    for event in sorted(
        events,
        key=lambda item: item["start"],
    ):
        lines.extend(
            event_lines(event)
        )

    lines.append(
        "END:VCALENDAR"
    )

    return (
        "\r\n".join(lines)
        + "\r\n"
    )


def main():
    # First try the structured WordPress /
    # SportsPress fixture data.
    events, source = candidates_from_rest()

    # Fall back to the public website if necessary.
    if not events:
        events, source = candidates_from_homepage()

    # -------------------------------------------------
    # DEDUPLICATE FIXTURES
    # -------------------------------------------------

    deduplicated = {}

    for event in events:
        key = (
            event["title"].lower(),
            event["start"].isoformat(),
        )

        deduplicated[key] = event

    events = list(
        deduplicated.values()
    )

    # -------------------------------------------------
    # REMOVE HISTORICAL FIXTURES
    # -------------------------------------------------
    #
    # Keep:
    #   - games taking place today
    #   - every future game
    #
    # Remove:
    #   - yesterday and anything earlier
    #
    # Keeping today's game means it will remain visible
    # for the whole match day rather than disappearing
    # immediately after face-off.
    # -------------------------------------------------

    today = datetime.now(
        timezone.utc
    ).date()

    events = [
        event
        for event in events
        if event["start"].date() >= today
    ]

    # Safety feature:
    #
    # If the source suddenly contains no current/future
    # fixtures, don't overwrite the existing calendars
    # with empty files.
    if not events:
    print(
        "No current or future Steel Queens fixtures found. "
        "Publishing empty calendars until new fixtures are added."
    )

    # -------------------------------------------------
    # HOME-ONLY CALENDAR
    # -------------------------------------------------

    home_events = [
        event
        for event in events
        if is_home(event["title"])
    ]

    # -------------------------------------------------
    # WRITE ALL-GAMES CALENDAR
    # -------------------------------------------------

    Path(
        CFG["feeds"]["all"]
    ).write_text(
        calendar(
            events,
            "Caledonia Steel Queens – All Games",
        ),
        encoding="utf-8",
    )

    # -------------------------------------------------
    # WRITE HOME-GAMES CALENDAR
    # -------------------------------------------------

    Path(
        CFG["feeds"]["home"]
    ).write_text(
        calendar(
            home_events,
            "Caledonia Steel Queens – Home Games",
        ),
        encoding="utf-8",
    )

    # -------------------------------------------------
    # LOG RESULTS IN GITHUB ACTIONS
    # -------------------------------------------------

    print(
        f"Source: {source}"
    )

    print(
        f"Found {len(events)} current/future "
        f"Steel Queens fixtures; "
        f"{len(home_events)} home fixtures."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
