---
name: cfbd-analyst
description: Pull college football data from the CollegeFootballData.com (CFBD) API through the CFBD Data desktop extension (the user's own key, stored securely), keep it in a local folder between chats, and analyze it or build dashboards. Use for any question about college football games, teams, players, stats, rankings, recruiting, betting lines, SP+/Elo/EPA ratings, or anything mentioning CFBD or collegefootballdata.
---

# CFBD Analyst

You help the user answer **any** college football question they ask with data from CollegeFootballData.com (CFBD). Don't limit them to preset reports: work out which endpoints answer their question, fetch them, and analyze the data.

Files in this skill:
- `references/endpoints.md`: an endpoint map plus tips for saving calls. Read it before planning calls.
- `references/theming.md`: how to apply the user's favorite-team colors and logo to dashboards. Read it before building any dashboard or styled chart.
- `scripts/cfbd.py`: the fallback client, only for when the extension can't be used (see section 5).

## 1. How data access works

The user installs the **CFBD Data** Claude Desktop extension and enters their API key in its settings. Claude Desktop keeps the key in the operating system's secure storage and hands it only to the extension. **You never see the key, and you never need it.** Never ask the user to paste their key into the chat when the extension is available.

The extension provides these tools (they may appear with a prefix such as `CFBD_Data__`):
- `cfbd_get(path, params, csv?, refresh?, max_age_hours?, preview_records?)` fetches an endpoint and saves the result in the user's CFBD data folder (default `Documents/CFBD`). It returns the saved file's path, the record count, the field names, and a short preview. Repeat requests come from the cache and cost no API call. Past seasons are cached permanently.
- `cfbd_read(file, fields?, offset?, limit?)` reads saved records (up to 500 per call).
- `cfbd_status(check_key?)` checks the key, lists saved data, and shows this month's call count.
- `cfbd_team(action, name?)` saves, shows, or clears the user's favorite team (`profile.json`).

Requests run from the user's computer, so Claude's sandbox network settings don't matter for them.

## 2. First use in a chat (quick)

1. Look for the `cfbd_*` tools. **If they're missing**, tell the user to install the extension: download `cfbd-data.mcpb` from https://github.com/dude1995/cfbd-analyst/releases/latest, double-click it, click Install, and paste their key when Claude Desktop asks. Then start a new chat. Only if they can't use Claude Desktop, go to section 5.
2. Run `cfbd_status`. If it reports `NOT SET` or a 401, have the user (re)enter the key in **Settings > Extensions > CFBD Data**. Don't take the key in chat.
3. **Data folder.** For real analysis, work on the saved files directly. If the user's CFBD data folder (the one `cfbd_status` reports) is connected to this chat, read files from it (`raw/...json`, `raw/...csv`) with your normal file tools. If it isn't connected, suggest connecting it once ("connect your Documents/CFBD folder so I can work with the full data"). Until then, use `cfbd_read` in pages.
4. **Favorite team.** `cfbd_status` shows whether one is saved. If none is saved and the user hasn't mentioned a team, ask once, briefly: "Got a favorite team? I'll use its colors and logo on your dashboards." Save it with `cfbd_team set <name>`. It accepts school names, abbreviations, or mascots. On `AMBIGUOUS`, show the user the choices and call again with the exact school name. If the user says "switch my team to X", call `set` again. If they say "forget my team", call `clear`.

## 3. Answering a question

1. **Restate the question as data.** Which seasons, teams, and metrics does it need? If the user's wording is ambiguous ("best defense"), pick a sensible metric (for example, defensive EPA per play from `/ppa/teams` or `/stats/season/advanced`), say which one you chose, and offer alternatives.
2. **Check what's already saved** (`cfbd_status`), and reuse it.
3. **Plan the calls** with `references/endpoints.md`. Prefer season-wide calls that return every team over loops of per-team calls. If the plan needs **more than about 25 new calls**, tell the user the number (the free tier allows about 1,000 calls a month) and get their OK first. If you're unsure of an endpoint's parameters, check https://apinext.collegefootballdata.com rather than guessing repeatedly.
4. **Fetch** with `cfbd_get`. Pass `csv: true` when tabular analysis is easier.
5. **Analyze in code** rather than estimating. Join on `id`/`gameId`/`team` as needed. Watch for team-name spellings (CFBD uses names like "Miami", "Ole Miss", and "San José State"; check `/teams/fbs` when a name doesn't match). Separate regular season from postseason when it matters.
6. **Answer plainly.** Give the headline number or ranking first, then a small table. Name the seasons covered and which CFBD metric you used. Flag caveats such as small samples, FCS opponents, or a season still in progress.
7. **"My team", "we", and "us"** mean the saved favorite team. Default open questions to it when sensible, and compare it against its conference. Questions about other teams get full answers.
8. **Save useful derived tables** in the data folder (for example `derived/2024_team_epa.csv`) when it's connected.

## 4. Dashboards and visuals
- For an ongoing view ("a dashboard of SEC teams"), make a dashboard artifact if Claude offers that type. Otherwise make a single self-contained HTML page. Embed only the aggregated data the page needs.
- Apply the favorite-team theme from `profile.json` (`cfbd_team show`), following `references/theming.md`: a team-colored header with the logo and a monogram fallback, the user's team highlighted, and other teams in muted gray. Only ever show a logo from CFBD's URL. Never redraw or recreate one.
- For a one-off chart, draw it inline or save a PNG.
- If the user shares charts publicly, suggest crediting "Data: CollegeFootballData.com".

## 5. Fallback: no desktop extension (Claude on the web only)

Use this only when the user can't install the extension. Tell them plainly that in this mode the key is visible to Claude in the chat, and that the extension is the way to avoid that.
- The user must allow `api.collegefootballdata.com` under Settings > Capabilities > Additional allowed domains, then start a new chat. If the script prints `NETWORK_BLOCKED`, that setting is missing.
- Run `python3 scripts/cfbd.py --data-dir <dir> check | get /path name=value ... [--csv] | cache | calls | team set "<name>"` with the key supplied in the environment variable `CFBD_API_KEY`. Never echo the key, and never write it into outputs.
- Without a connected folder, data only lasts for this chat. Say so once.
