# Reusable team-calendar guide

This is the process to use whenever you are given another team's fixture list and want an automatically updating calendar.

## 1. Identify the source type

Use the most structured source available, in this order:

1. **ICS / webcal feed** — best option. Subscribe/filter the feed directly.
2. **Public JSON/API** — excellent. GitHub Actions can fetch it and generate ICS.
3. **Structured fixture webpage** — workable. Scrape the page with Python.
4. **PDF/image/social post** — poor for automation. Use it for a one-off calendar, then look for a better live source.

If you have an ICS URL, do not scrape the website unless necessary.

## 2. Decide what calendar(s) you want

Write down:

- exact team name used by the source
- all games / home only / away only
- title format, e.g. `🏒 Queens vs Solway`
- home venue/address
- reminders, e.g. 24 hours + 2 hours
- whether past fixtures should remain

## 3. Create the repository

Create a public GitHub repository such as `TEAM-calendar`.

Recommended structure:

```
.github/workflows/update-calendar.yml
config.json
generate_calendar.py
requirements.txt
tests/
docs/
README.md
```

## 4. Configure the source

For an **ICS source**, store its URL in config and have Python download it, filter `VEVENT` blocks, and write the output ICS.

For a **JSON/API source**, map the source's fields to:

- title/home/away teams
- start date/time
- venue
- source URL or description

For a **webpage source**, use stable HTML structure rather than brittle visual positions. Keep parsing conservative: if the script is unsure, skip the event instead of inventing data.

## 5. Home/away filtering

If fixture titles use `Home Team vs Away Team`, a safe home rule is:

`title starts with "Exact Team Name vs "`

Do not rely only on the venue unless the team can play home games at multiple rinks.

## 6. Protect against bad updates

Always add these safeguards:

- fail if download returns an error
- refuse to overwrite a valid calendar with zero events
- deduplicate by fixture + date/time
- keep stable UIDs so calendar apps update events instead of duplicating them
- run automated tests before generating/committing

## 7. Automate with GitHub Actions

A useful schedule is every 6 hours:

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "17 */6 * * *"
```

Use current action versions such as `actions/checkout@v5` and `actions/setup-python@v6`.

The workflow should:

1. check out the repo
2. set up Python
3. install requirements
4. run tests
5. fetch/filter/generate the calendar
6. commit only if `docs/*.ics` changed

## 8. Publish with GitHub Pages

Go to **Settings → Pages** and select:

- Source: Deploy from a branch
- Branch: `main`
- Folder: `/docs`

The subscription URL becomes:

`https://USERNAME.github.io/REPOSITORY/calendar-file.ics`

## 9. Test before subscribing

Check:

- Actions run is green
- generated file contains `BEGIN:VCALENDAR`
- expected fixtures appear
- away fixtures are absent if filtering home-only
- dates/times are correct
- title emoji renders correctly
- venue/reminders look right

Then subscribe on Apple Calendar/Google Calendar/Outlook.

## 10. Prove automatic updating works

Leave the scheduled workflow enabled and check Actions the next day. A run marked **schedule** rather than **workflow_dispatch/manual** proves GitHub is invoking it automatically.

When the source changes, the next run should commit a new `.ics`. Calendar apps then refresh the subscription on their own schedule.

## What to send me for another team

The fastest hand-off is:

- team name
- fixture-list URL, ICS/webcal URL, API URL, or uploaded fixture file
- whether you want all/home/away
- preferred event title style
- reminders
- home venue if you want it forced into home events

With those details, the same pattern can be adapted without rebuilding the whole approach from scratch.
