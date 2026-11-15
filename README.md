# CFBD Analyst: a Claude skill for college football data

Ask Claude anything about college football, like "Which Big 12 defenses improved most in EPA per play from 2023 to 2024?" or "Build me a dashboard of SEC teams' success rate by week." Claude pulls the numbers from [CollegeFootballData.com](https://collegefootballdata.com) (CFBD), analyzes them, and builds charts or dashboards.

- **You use your own free CFBD API key.** It stays on your computer and is never part of this skill.
- **No preset reports.** Ask whatever you want, and Claude works out which data to pull.
- **Your data stays with you.** Everything Claude downloads is saved in a folder on your computer. Later chats reuse it instead of using up API calls.

---

## Setup (about 10 minutes, once)

### 1. Get your free CFBD API key
Go to **https://collegefootballdata.com/key**, enter your email, and pick a primary use. The key arrives by email. The free tier gives you about **1,000 API calls a month**, and a `.edu` email gets more.

### 2. Let Claude reach the CFBD website
Claude runs code in a secure sandbox that blocks most websites by default. You need to allow this one:

1. In Claude, open **Settings > Capabilities**.
2. Make sure **Code execution and file creation** is on, and **Allow network egress** is on.
3. Under **Additional allowed domains**, add: `api.collegefootballdata.com`
   (Or set the domain allowlist to **All domains**. Adding just this one domain is the more cautious choice.)
4. Start a **new** chat afterward. Settings don't apply to chats that are already open.

> **Team or Enterprise plan?** Only your organization owner can change this, in Organization settings > Capabilities. Ask them to add `api.collegefootballdata.com`.

### 3. Install the skill
1. Download **[`cfbd-analyst.zip`](https://github.com/dude1995/cfbd-analyst/releases/latest/download/cfbd-analyst.zip)** (latest release). Don't unzip it.
2. In Claude, go to **Customize > Skills**, click **+**, choose **Create skill**, then **Upload a skill**, and pick the ZIP.
3. Make sure the skill is toggled **on**.

Custom skills work on Free, Pro, Max, Team, and Enterprise plans.

### 4. Give Claude a folder to keep your data in (recommended)
Use **Claude Desktop** and connect a folder on your computer to the chat, for example `Documents/CFBD`. This is what lets your data and API key carry over from one chat to the next. Without a folder, Claude still works, but it starts from scratch each chat and uses more of your API calls.

### 5. First chat
Try:
> Set up CFBD. Here's my API key: ••••••••

Claude checks the key, offers to save it as `.cfbd_key` in your folder (on your computer only), and runs a test call. Then ask away:

- "Who had the best offense in the SEC in 2024 by EPA per play?"
- "Compare Texas and Oklahoma recruiting rankings over the last 5 years."
- "Show a dashboard of my team's week-by-week success rate this season."
- "How did teams with top-10 preseason AP rankings finish, 2015 to 2024?"

### 6. Make it yours (optional)
Tell Claude your team:
> My team is Texas A&M.

From then on, "my team" and "we" mean that team. Your dashboards get a header in your team's colors with its logo, and your team is highlighted in every comparison chart. Claude tweaks the colors where it needs to so text and charts stay readable. To change teams, say "switch my team to Baylor". To turn it off, say "forget my team".

The logo is the image CFBD links to for that school, shown on your own dashboards. Claude doesn't redraw logos, and if an image can't load, the header shows a monogram such as **TAMU** instead. Team names and logos belong to the schools, so keep that in mind before you publish dashboards widely.

---

## What ends up in your folder

```
CFBD/
├── .cfbd_key          ← your key (only if you told Claude to save it). Don't share this file.
├── cfbd.py            ← the helper script (copied in automatically when needed)
├── profile.json       ← your favorite team, colors, and logo link (optional)
├── raw/               ← every API response, as JSON (+ CSV when requested)
├── derived/           ← tables Claude built for your questions
└── _calls.log         ← how many API calls you've used
```

Past seasons are downloaded once and kept. Current-season data refreshes after 12 hours, or whenever you ask for the latest.

## Troubleshooting

| What Claude says | What to do |
|---|---|
| `NETWORK_BLOCKED` | Do step 2 again, check the domain is spelled exactly `api.collegefootballdata.com`, and start a **new** chat. |
| `401` / key rejected | Re-copy the key from the CFBD email, or request a new one. |
| `403` on one endpoint | Some endpoints (such as live plays and weather) need a paid CFBD Patreon tier. |
| Quota warnings | Check your usage (Claude can run the `calls` command), or wait until next month. |
| Claude doesn't use the skill | Make sure it's toggled on, or say "use the CFBD analyst skill". |

## Privacy and safety
- This skill contains **no API keys** and sends your key only to `api.collegefootballdata.com`.
- The helper script (`scripts/cfbd.py`) uses only Python's standard library, so you can read every line of it.
- Dashboards and shared charts never include your key.

## Credits
Data comes from [CollegeFootballData.com](https://collegefootballdata.com). If you post charts publicly, please credit "Data: CollegeFootballData.com." This project isn't affiliated with CFBD or Anthropic.

## Claude Code users
Copy the `cfbd-analyst/` folder into `~/.claude/skills/`. Your machine's network isn't sandboxed, so you can skip step 2.

## For maintainers
Edit files in `cfbd-analyst/`, bump the number in `VERSION` (for example to `1.1.0`), update `.github/release-notes.md`, and push to `main`. The GitHub Action checks the skill, builds `cfbd-analyst.zip` with the skill folder at the top level, and publishes it as release `v1.1.0`. Pushing without bumping `VERSION` refreshes the ZIP on the current release. Users always get the newest version from the download link above.
