**CFBD Analyst**: ask Claude anything about college football, using data from CollegeFootballData.com and your own free API key.

**New in this version:** passing detail. Ask about air yards, yards after catch, depth of target, deep shots or targets by receiver, and Claude now pulls the play-by-play and charts every pass, using the catch spots in CFBD's play descriptions. CFBD only has those spots for recent games (for many teams, from late 2025 on), and Claude tells you which games are covered.

From 1.1.0: your API key lives in the **CFBD Data** desktop extension, stored in your computer's secure storage, where Claude never sees it.

**Install (Claude Desktop):**
1. Get a free key at https://collegefootballdata.com/key
2. Download **`cfbd-data.mcpb`** below, double-click it, click Install, and paste your key when asked.
3. Download **`cfbd-analyst.zip`** below (don't unzip it). In Claude, go to **Customize > Skills > + > Create skill > Upload a skill**.
4. Connect your `Documents/CFBD` folder to your chats, start a new chat, and say "Check my CFBD setup."

Full guide: https://github.com/dude1995/cfbd-analyst#setup-about-10-minutes-once
