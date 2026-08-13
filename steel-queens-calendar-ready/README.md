# Caledonia Steel Queens calendar

Creates two automatically updated iCalendar feeds for the **Caledonia Steel Queens**:

- `docs/steel-queens-all.ics` — all fixtures
- `docs/steel-queens-home.ics` — home fixtures only

The workflow checks the Steel Queens website every 6 hours. It first tries SportsPress/WordPress REST endpoints, then falls back to the public homepage. It refuses to overwrite the calendar when no fixtures are found.

## Important current-season note

As of August 2026, the public Steel Queens website/search results still surface 2025–26 fixture data rather than a complete 2026–27 senior schedule. The automation is ready now, but it can only publish what the club has made available on its website. Once their new fixtures appear in the same site data, the scheduled run should pick them up automatically.

## Setup

1. Create a **public** GitHub repository called `steel-queens-calendar`.
2. Upload everything inside this folder to the repository root, including `.github` and `.gitignore`.
3. Go to **Actions → Update Steel Queens calendars → Run workflow**.
4. If the run is green, open `docs/` and inspect the generated `.ics` files.
5. Enable **Settings → Pages → Deploy from a branch → main → /docs**.
6. Your Pages site will be `https://YOUR-USERNAME.github.io/steel-queens-calendar/`.
7. Subscribe to either:
   - `https://YOUR-USERNAME.github.io/steel-queens-calendar/steel-queens-all.ics`
   - `https://YOUR-USERNAME.github.io/steel-queens-calendar/steel-queens-home.ics`

See `TEAM-CALENDAR-GUIDE.md` for a reusable step-by-step process for other teams.
