# CFBD Analyst: a Claude skill for college football data

Ask Claude anything about college football, like "Which Big 12 defenses improved most in EPA per play from 2023 to 2024?" or "Build me a dashboard of SEC teams' success rate by week." Claude pulls the numbers from [CollegeFootballData.com](https://collegefootballdata.com) (CFBD), analyzes them, and builds charts or dashboards.

- **You use your own free CFBD API key.** You enter it once, and it's stored in your computer's secure storage, where Claude can't read it.
- **No preset reports.** Ask whatever you want, and Claude works out which data to pull.
- **Your data stays with you.** Everything Claude downloads is saved in a folder on your computer. Later chats reuse it instead of using up API calls.

---

## Setup (about 10 minutes, once)

You need the **Claude Desktop** app (Mac or Windows). Setup has two pieces: the **CFBD Data extension**, which holds your key and fetches the data, and the **CFBD Analyst skill**, which teaches Claude how to use it.

### 1. Get your free CFBD API key
Go to **https://collegefootballdata.com/key**, enter your email, and pick a primary use. The key arrives by email. The free tier gives you about **1,000 API calls a month**, and a `.edu` email gets more.

### 2. Install the CFBD Data extension (this is where your key lives)
1. Download **[`cfbd-data.mcpb`](https://github.com/dude1995/cfbd-analyst/releases/latest/download/cfbd-data.mcpb)**.
2. Double-click it, or in Claude Desktop go to **Settings > Extensions > Advanced settings > Install Extension…** and pick the file. Then click **Install**.
3. When Claude Desktop asks, paste your **CFBD API key**. Optionally choose a data folder (the default is `Documents/CFBD`).

Your key is stored in your computer's secure storage (Keychain on Mac, Credential Manager on Windows). **Claude never sees it, and you never type it into a chat.** The extension adds it to each request to CollegeFootballData.com on your computer. To change it later, go to **Settings > Extensions > CFBD Data**.

> **Team or Enterprise plan?** Your organization may need to allow desktop extensions. Ask your admin.

### 3. Install the skill
1. Download **[`cfbd-analyst.zip`](https://github.com/dude1995/cfbd-analyst/releases/latest/download/cfbd-analyst.zip)**. Don't unzip it.
2. In Claude, go to **Customize > Skills**, click **+**, choose **Create skill**, then **Upload a skill**, and pick the ZIP.
3. Make sure the skill is toggled **on**.

### 4. Connect your data folder (recommended)
In Claude Desktop, connect your CFBD data folder (`Documents/CFBD` unless you changed it) to your chats. Claude can then work with the full saved data. Without it, Claude can still read the data through the extension, just in smaller pieces.

### 5. First chat
Start a **new** chat and try:
> Check my CFBD setup.

Claude confirms your key works (without seeing it) and shows how many API calls you have left. Then ask away:

- "Who had the best offense in the SEC in 2024 by EPA per play?"
- "Compare Texas and Oklahoma recruiting rankings over the last 5 years."
- "Show a dashboard of my team's week-by-week success rate this season."
- "How did teams with top-10 preseason AP rankings finish, 2015 to 2024?"
- "Break down my QB's passing by air yards and yards after catch, and show his targets by receiver."

### 6. Make it yours (optional)
Tell Claude your team:
> My team is Texas A&M.

From then on, "my team" and "we" mean that team. Your dashboards get a header in your team's colors with its logo, and your team is highlighted in every comparison chart. Claude tweaks the colors where it needs to so text and charts stay readable. To change teams, say "switch my team to Baylor". To turn it off, say "forget my team".

The logo is the image CFBD links to for that school, shown on your own dashboards. Claude doesn't redraw logos, and if an image can't load, the header shows a monogram such as **TAMU** instead. Team names and logos belong to the schools, so keep that in mind before you publish dashboards widely.

---

## What ends up in your folder

```
CFBD/
├── profile.json       ← your favorite team, colors, and logo link (optional)
├── raw/               ← every API response, as JSON (+ CSV when requested)
├── derived/           ← tables Claude built for your questions (e.g. one row per pass with air yards and YAC)
└── _calls.log         ← how many API calls you've used
```

Past seasons are downloaded once and kept. Current-season data refreshes after 12 hours, or whenever you ask for the latest.

## Troubleshooting

| What you see | What to do |
|---|---|
| Claude says the CFBD tools aren't available | Make sure the CFBD Data extension is installed and enabled under Settings > Extensions, then start a new chat. |
| `NOT SET` or `401` / key rejected | Re-enter the key in Settings > Extensions > CFBD Data. Copy it fresh from the CFBD email, or request a new one. |
| `403` on one endpoint | Some endpoints (such as live plays and weather) need a paid CFBD Patreon tier. |
| Quota warnings | Ask Claude to "check my CFBD usage", or wait until next month. |
| Claude doesn't use the skill | Make sure it's toggled on, or say "use the CFBD analyst skill". |

## Privacy and safety
- Your API key lives only in your computer's secure storage. The extension sends it only to `api.collegefootballdata.com`, and never includes it in anything it returns to Claude or saves to disk. If an error message from the API happens to contain the key, it's replaced with `[key hidden]`.
- Data you download stays in your own data folder.
- The extension's source is in [`extension/src/index.js`](extension/src/index.js). The released `.mcpb` is built from it by GitHub Actions.
- Dashboards and shared charts never include your key.

**Claude on the web only (no desktop app)?** The skill has a fallback mode where you paste the key into a chat and allow `api.collegefootballdata.com` under Settings > Capabilities > Additional allowed domains. In that mode Claude can see the key, so the desktop extension is the recommended setup.

## Credits
Data comes from [CollegeFootballData.com](https://collegefootballdata.com). If you post charts publicly, please credit "Data: CollegeFootballData.com." This project isn't affiliated with CFBD or Anthropic.

## Claude Code users
Copy the `cfbd-analyst/` folder into `~/.claude/skills/`. To keep the key out of chats, add the extension's server as an MCP server with `CFBD_API_KEY` set in its environment.

## For maintainers
Edit the skill in `cfbd-analyst/` or the extension in `extension/src/`. Bump `VERSION` (for example to `1.2.0`), update `.github/release-notes.md`, and push to `main`. The GitHub Action checks both pieces, builds `cfbd-analyst.zip` and `cfbd-data.mcpb`, and publishes them as release `v1.2.0`. Pushing without bumping `VERSION` refreshes the files on the current release. The download links above always point to the newest release.
