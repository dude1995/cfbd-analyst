---
name: cfbd-analyst
description: Pull college football data from the CollegeFootballData.com (CFBD) API through the CFBD Data desktop extension (the user's own key, stored securely), keep it in a local folder between chats, and analyze it or build dashboards. Use for any question about college football games, teams, players, stats, rankings, recruiting, betting lines, SP+/Elo/EPA ratings, or anything mentioning CFBD or collegefootballdata.
---

# CFBD Analyst

You help the user answer **any** college football question they ask with data from CollegeFootballData.com (CFBD). Don't limit them to preset reports: work out which endpoints answer their question, fetch them, and analyze the data.

Files in this skill:
- `references/endpoints.md`: an endpoint map plus tips for saving calls. Read it before planning calls.
- `references/theming.md`: how to apply the user's favorite-team colors and logo to dashboards. Read it before building any dashboard or styled chart.
- `scripts/parse_passes.py`: turns saved `/plays` files into one row per pass with air yards, yards after catch (YAC), receiver and depth. See section 5.
- `scripts/cfbd.py`: the fallback client, only for when the extension can't be used (see section 6).

## 1. How data access works

The user installs the **CFBD Data** Claude Desktop extension and enters their API key in its settings. Claude Desktop keeps the key in the operating system's secure storage and hands it only to the extension. **You never see the key, and you never need it.** Never ask the user to paste their key into the chat when the extension is available.

The extension provides these tools (they may appear with a prefix such as `CFBD_Data__`):
- `cfbd_get(path, params, csv?, refresh?, max_age_hours?, preview_records?)` fetches an endpoint and saves the result in the user's CFBD data folder (default `Documents/CFBD`). It returns the saved file's path, the record count, the field names, and a short preview. Repeat requests come from the cache and cost no API call. Past seasons are cached permanently.
- `cfbd_read(file, fields?, offset?, limit?)` reads saved records (up to 500 per call).
- `cfbd_status(check_key?)` checks the key, lists saved data, and shows this month's call count.
- `cfbd_team(action, name?)` saves, shows, or clears the user's favorite team (`profile.json`).

Requests run from the user's computer, so Claude's sandbox network settings don't matter for them.

## 2. First use in a chat (quick)

1. Look for the `cfbd_*` tools. **If they're missing**, tell the user to install the extension: download `cfbd-data.mcpb` from https://github.com/dude1995/cfbd-analyst/releases/latest, double-click it, click Install, and paste their key when Claude Desktop asks. Then start a new chat. Only if they can't use Claude Desktop, go to section 6.
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

## 5. Passing detail: air yards, YAC, targets and depth

CFBD has no air-yards or YAC fields, but many play descriptions say where the ball was caught ("caught at A&M49"). `scripts/parse_passes.py` reads those descriptions. Use it for questions about air yards, yards after catch, depth of target (aDOT), deep shots, completion rate by depth, throws by direction, or targets and catches by receiver.

1. **Fetch the plays.** Get the team's schedule with `/games` (year, team, `seasonType: both`) to list the weeks played, then call `/plays` once per game week with `year`, `week`, `seasonType` and `offense: <team>`. That's one call per game (about 13 per season), so count the calls and follow the 25-call rule in section 3.
2. **Run the parser** where the saved files are reachable: on the user's computer through a shell on the connected data folder if you have one, or in your own workspace after copying the `plays__*.json` files there. Never re-type play data by hand.
   `python3 scripts/parse_passes.py --team "Texas A&M" --out <data folder>/derived/<team>_passes_<years>.csv <data folder>/raw`
   Spell `--team` exactly as CFBD does. Passing a folder reads every saved `plays__*.json` in it and keeps only plays where that team is on offense, so other teams' saved files don't get mixed in.
3. **Read the summary it prints, and tell the user what it means:**
   - **Coverage.** Only some games have catch spots. CFBD's older, short descriptions ("Marcel Reed pass complete to KC Concepcion for 15 yds") give the passer, receiver, result and yards but no spot. In those games `air_yards` and `yac` are blank. The summary names the first charted game; for example, Texas A&M's start in 2025 Week 11. Compare seasons on air yards and YAC only over charted games, and say so. Attempts, completions, yards, TDs, interceptions, EPA and targets work in every game.
   - **Check.** "Completions where parsed yards differ from CFBD yards" should be 0. If it isn't, look at those rows before you trust the totals.
4. **Analyze the CSV in code.** Leave out rows with `counted = no` (plays wiped out by a penalty). Sacks are already excluded. Useful cuts: depth bands (at or behind the line, 1–9, 10–19, 20+ air yards) with completion %, yards per attempt and YAC per catch; aDOT (mean air yards per attempt); YAC share of passing yards; and per receiver targets, catches, aDOT, YAC per catch and EPA per target.
5. **Caveats to mention:** spots are charted by the official scorer, so single plays are close to a yard, not exact; season totals are solid. In uncharted games many incompletions name no target, so catch rates per receiver look high there. Names are shortened to "F.Last", and the same player can still show up two ways (accents, garbled characters in CFBD's text, or "II"/"III"); merge obvious duplicates before you rank receivers.

## 6. Fallback: no desktop extension (Claude on the web only)

Use this only when the user can't install the extension. Tell them plainly that in this mode the key is visible to Claude in the chat, and that the extension is the way to avoid that.
- The user must allow `api.collegefootballdata.com` under Settings > Capabilities > Additional allowed domains, then start a new chat. If the script prints `NETWORK_BLOCKED`, that setting is missing.
- Run `python3 scripts/cfbd.py --data-dir <dir> check | get /path name=value ... [--csv] | cache | calls | team set "<name>"` with the key supplied in the environment variable `CFBD_API_KEY`. Never echo the key, and never write it into outputs.
- Without a connected folder, data only lasts for this chat. Say so once.
