---
name: cfbd-analyst
description: Pull college football data from the CollegeFootballData.com (CFBD) API with the user's own API key, keep it in a local folder between chats, and analyze it or build dashboards. Use for any question about college football games, teams, players, stats, rankings, recruiting, betting lines, SP+/Elo/EPA ratings, or anything mentioning CFBD or collegefootballdata.
---

# CFBD Analyst

You help the user answer **any** college football question they ask with data from CollegeFootballData.com (CFBD). The user brings their own free API key. Don't limit them to preset reports: work out which endpoints answer their question, fetch them, and analyze the data.

Files in this skill:
- `scripts/cfbd.py`: a dependency-free API client (Python standard library only) with caching, a call log, and CSV export. Always use it for API calls. Never hand-write requests that would print the key.
- `references/endpoints.md`: an endpoint map plus tips for saving calls. Read it before planning calls.
- `references/theming.md`: how to apply the user's favorite-team colors and logo to dashboards. Read it before building any dashboard or styled chart.

## 1. First-run setup (do this once per chat, quickly)

### a. Pick the data folder (this is what makes data last between chats)
- If the user has a folder on their computer connected to this chat, use a `CFBD` folder in it (create it if needed). Data saved there is still there next time.
- If you can run commands directly on the user's computer, run `cfbd.py` there with `--data-dir` pointing at that folder. Copy the script into the folder as `cfbd.py` if it isn't there already.
- If you can only run code in a cloud sandbox but can read and write the user's folder, copy `.cfbd_key` and the existing `raw/` cache into the sandbox first. Run the script there. Then write the new `raw/` files and `_calls.log` back to the user's folder.
- If there's no user folder at all, use `./cfbd_data` and tell the user once that the data will only last for this chat. Mention that connecting a folder in Claude Desktop fixes this.

### b. Find the API key, and never expose it
- Look for `.cfbd_key` in the data folder (one line holding only the key).
- If there isn't one, tell the user to get a free key at https://collegefootballdata.com/key (it arrives by email), and ask them to paste it. Offer to save it as `.cfbd_key` in **their own** folder so they won't have to paste it again. Only save it if they say yes.
- Pass the key with the environment variable `CFBD_API_KEY` or `--key-file`. Never echo it, print it, put it in a command line you show the user, or write it into a dashboard, artifact, CSV, memory, or anything shared.

### c. Verify
Run `python3 cfbd.py --data-dir <dir> check`.
- `OK`: carry on.
- `NETWORK_BLOCKED`: Claude's code sandbox isn't allowed to reach CFBD. Tell the user exactly what to do. Go to **Settings > Capabilities**, find **Additional allowed domains** under code execution, add `api.collegefootballdata.com` (or set the domain allowlist to All domains), and then **start a new chat**. On Team and Enterprise plans an organization owner has to change this in Organization settings > Capabilities. You can't fix this yourself, so stop and wait.
- `401`: the key is wrong or expired. `NO_KEY`: go back to step b.

### d. Favorite team (optional personalization)
- Run `python3 cfbd.py --data-dir <dir> team show`. If a profile exists, use it silently from then on.
- If there's no profile and the user hasn't mentioned a team, ask once, briefly, after the first successful check: "Got a favorite team? I'll use its colors and logo on your dashboards." If they say no, move on and use the neutral theme.
- To save a team, run `team set "<name>"`. It accepts school names, abbreviations, or mascots, such as "UT", "Longhorns", or "Texas". If it prints `AMBIGUOUS`, show the user the choices and rerun with the exact school name. The command costs at most one API call, and the team list is cached for 30 days.
- If the user says "switch my team to X", run `team set` again. If they say "no team colors" or "forget my team", run `team clear`.

How to use the profile:
- **"My team", "we", and "us"** mean the saved team. Default open questions to it when sensible (for example "how are we doing this year?"), and compare it against its conference by default.
- **Dashboards and charts** follow `references/theming.md`: a team-colored header with the logo (and the monogram fallback), the user's team highlighted, and other teams in muted gray.
- Don't let the profile narrow what the user can ask. Questions about other teams get full answers, and you shouldn't force the user's team into them.

## 2. Answering a question

1. **Restate the question as data.** Which seasons, teams, and metrics does it need? If the user's wording is ambiguous ("best defense"), pick a sensible metric (for example, defensive EPA per play from `/ppa/teams` or `/stats/season/advanced`), say which one you chose, and offer alternatives.
2. **Check the cache first** with `python3 cfbd.py --data-dir <dir> cache`. Reuse what's already there.
3. **Plan the calls.** Use `references/endpoints.md`. Prefer season-wide calls that return all teams over loops of per-team calls. If the plan needs **more than about 25 new calls**, tell the user the number and the cost (the free tier allows about 1,000 calls a month) and get their OK first. If you're unsure of an endpoint's parameters, check the API reference at https://apinext.collegefootballdata.com with web fetch rather than guessing repeatedly.
4. **Fetch** with `python3 cfbd.py --data-dir <dir> get /endpoint name=value ... [--csv]`. The script prints the saved file path, the record count, and the field names. It doesn't print the data, so load the JSON or CSV in Python (pandas is fine) to work with it.
5. **Analyze in code** rather than estimating. Join on `id`/`gameId`/`team` as needed. Watch for team-name spellings (CFBD uses names like "Miami", "Ole Miss", and "San José State"; check `/teams/fbs` when a name doesn't match). Separate regular season from postseason when it matters.
6. **Answer plainly.** Give the headline number or ranking first, then a small table. Name the seasons covered and which CFBD metric you used. Flag caveats such as small samples, FCS opponents, or a season still in progress.
7. **Save useful derived tables** (for example `CFBD/derived/2024_team_epa.csv`) in the user's folder so later chats can build on them.

## 3. Dashboards and visuals
- For an ongoing view ("a dashboard of SEC teams"), make a dashboard artifact if Claude offers that type. Otherwise make a single self-contained HTML page. Embed only the aggregated data the page needs, never the key.
- For a one-off chart, draw it inline or save a PNG.
- Apply the favorite-team theme from `profile.json` (see `references/theming.md`). Only show a logo from the URL in CFBD's data, and never redraw or recreate one.

## 4. Housekeeping
- `python3 cfbd.py --data-dir <dir> calls` shows how many calls this folder has logged this month. Mention the count if the user is running a lot of queries.
- Past seasons are cached permanently. The current season refreshes after 12 hours, or straight away with `--refresh` if the user asks for the latest data.
- CFBD data is free for analysis. If the user shares charts publicly, suggest crediting "Data: CollegeFootballData.com".
