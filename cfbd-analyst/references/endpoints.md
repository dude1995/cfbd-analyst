# CFBD endpoint map

Base URL: `https://api.collegefootballdata.com`. All endpoints are `GET`, and all need `Authorization: Bearer <key>`.

This is a quick-start map of commonly used endpoints, not a complete list. Parameters change over time. **The source of truth is the API reference at https://apinext.collegefootballdata.com** (legacy Swagger UI: https://api.collegefootballdata.com/swagger). If an endpoint or parameter isn't listed here, or a call returns 400 or 404, look it up there with web fetch before guessing again.

Common parameters: `year`, `week`, `seasonType` (`regular` | `postseason` | `both`), `team`, `conference` (an abbreviation such as `SEC`, `B1G`, `ACC`, `B12`), `classification` (`fbs` | `fcs` | ...).

| Area | Endpoint | Typical params | Notes |
|---|---|---|---|
| Games | `/games` | year (req), week, team, conference, seasonType | Scores, venue, Elo, excitement |
| | `/games/teams` | year + (week or team or conference) | Team box-score stats per game |
| | `/games/players` | year + (week or team or conference) | Player box scores per game |
| | `/games/media` | year | TV and network |
| | `/calendar` | year | Week start and end dates |
| | `/records` | year, team, conference | W-L splits |
| | `/scoreboard` | classification, conference | Live and recent games |
| Teams | `/teams`, `/teams/fbs` | year, conference | Team metadata, logos, colors |
| | `/roster` | team, year | |
| | `/talent` | year | 247 team talent composite |
| | `/teams/matchup` | team1, team2, minYear, maxYear | Head-to-head history |
| | `/conferences`, `/venues` | | |
| Coaches/players | `/coaches` | team, year, firstName, lastName | |
| | `/player/search` | searchTerm, team, year | |
| | `/player/usage`, `/player/returning` | year, team | |
| | `/player/portal` | year | Transfer portal |
| Rankings/lines | `/rankings` | year, week, seasonType | AP, Coaches, CFP |
| | `/lines` | year, week, team | Betting lines by provider |
| Recruiting | `/recruiting/players` | year, team, position | |
| | `/recruiting/teams`, `/recruiting/groups` | year, team | |
| Ratings | `/ratings/sp`, `/ratings/srs`, `/ratings/elo`, `/ratings/fpi` | year, team | SP+, SRS, Elo, FPI |
| Advanced (PPA/EPA) | `/ppa/teams`, `/ppa/games`, `/ppa/players/season`, `/ppa/players/games` | year, team | Predicted points added |
| | `/metrics/wp` | gameId | Win probability by play |
| | `/metrics/wp/pregame` | year, week | |
| Season stats | `/stats/season` | year, team, conference | Raw team totals |
| | `/stats/season/advanced` | year, team | Success rate, explosiveness, havoc, and similar |
| | `/stats/game/advanced` | year, week, team | |
| | `/stats/player/season` | year, team, category | |
| | `/stats/categories` | | |
| Play-by-play | `/plays` | year, week (req), seasonType, offense/defense/team | Expensive: one call per week. No air-yards/YAC fields; run `scripts/parse_passes.py` on the saved files (SKILL.md section 5) |
| | `/drives` | year, team, week | |
| | `/plays/types`, `/plays/stats` | | |
| Draft | `/draft/picks` | year, college | NFL draft picks |
| Account | `/info` | | Key's tier and remaining calls |

Some endpoints (for example live plays and weather) need a paid Patreon tier. A 403 on those is expected for free keys.

## Spending calls wisely (the free tier is about 1,000 calls a month, shared with the basketball API)

- Prefer one wide call over many narrow ones. For example, `/games year=2024` returns the whole season in one call, while looping `team=` costs one call per team.
- Season-level endpoints (`/stats/season/advanced`, `/ratings/sp`, `/ppa/teams`) cover all teams in a single call.
- `/plays` and per-game endpoints are the expensive ones. Estimate the number of calls first, and ask the user before going over about 25 calls in one go.
- Past seasons never change, so the helper caches them permanently.
