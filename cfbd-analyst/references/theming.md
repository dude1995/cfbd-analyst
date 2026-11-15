# Personalized team theming

The user's favorite team is saved in `<data-dir>/profile.json` by `cfbd.py team set "<name>"`. The colors come from CFBD's own team data (`color`, `alternateColor`). The script then adjusts them so text and chart marks stay readable.

## Fields to use

| profile.json field | Use it for |
|---|---|
| `theme.primary` | Header band or banner background, and the brand accent |
| `theme.onPrimary` | Text and icons placed **on** the primary color (already contrast-checked) |
| `theme.secondary` | Thin accent rules, borders, the second series. Never body text |
| `theme.light.highlight` / `theme.dark.highlight` | The user's team's bars, lines, and points in charts (readable at 3:1 or better) |
| `theme.light.accent` / `theme.dark.accent` | A second highlighted series (for example "conference average") |
| `theme.light.others` / `theme.dark.others` | Every other team: muted gray, so the user's team stands out |
| `logo_urls.light_bg` / `logo_urls.dark_bg` | The logo image, if CFBD provides one |
| `abbreviation` | The monogram fallback text |

Rules:
- Keep page backgrounds and body text neutral (`theme.light.bg` and `theme.light.text`). Put team color in the header, accents, and the highlighted series. Don't paint whole pages in team colors.
- In comparison charts, color **only** the user's team (and, if needed, one comparison series). Everyone else gets `others`.
- When a chart shows another team's own data (for example a rival's page), it's fine to use that team's colors from `/teams/fbs`. The user's team still keeps its highlight.

## Logo rules
- Only ever use a logo **URL from CFBD's `logos` field**, shown as an `<img>`. Don't redraw, trace, or recreate a team logo in SVG, CSS, canvas, or ASCII. Don't invent a "close enough" emblem either.
- Hotlink the URL. Don't download the image into the data folder or the artifact.
- Always include the monogram fallback. Some viewers block outside images, and some teams have no logo in CFBD.
- Team names and logos belong to the schools. Personal dashboards are fine. If the user plans to share widely or commercially, mention that once in a sentence.

## Header snippet (self-contained HTML)

```html
<style>
  :root{
    --team: {{theme.primary}}; --on-team: {{theme.onPrimary}};
    --team-2: {{theme.secondary}}; --hl: {{theme.light.highlight}};
    --others: {{theme.light.others}}; --bg:#ffffff; --text:#111827;
  }
  @media (prefers-color-scheme: dark){
    :root{ --hl: {{theme.dark.highlight}}; --others: {{theme.dark.others}}; --bg:#111827; --text:#f3f4f6; }
  }
  body{background:var(--bg);color:var(--text);font-family:system-ui,sans-serif;margin:0}
  .team-head{display:flex;align-items:center;gap:14px;padding:14px 20px;
             background:var(--team);color:var(--on-team);border-bottom:4px solid var(--team-2)}
  .team-head img,.team-head .mono{width:48px;height:48px;flex:none}
  .team-head .mono{display:none;border-radius:50%;align-items:center;justify-content:center;
             font-weight:800;font-size:15px;background:var(--on-team);color:var(--team)}
</style>
<header class="team-head">
  <img src="{{logo_urls.light_bg}}" alt=""
       onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
  <span class="mono" aria-hidden="true">{{abbreviation}}</span>
  <div><div style="font-size:20px;font-weight:700">{{team}} {{mascot}}</div>
       <div style="opacity:.85;font-size:13px">{{conference}} · Data: CollegeFootballData.com</div></div>
</header>
```

Escape team names and abbreviations for HTML (for example `TA&M` becomes `TA&amp;M`). If `logo_urls.light_bg` is null, leave out the `<img>` and set the monogram to `display:flex`.

## No profile saved
Use a neutral theme: primary `#334155`, on-primary `#ffffff`, highlight `#2563eb`, others `#94a3b8`. Don't ask about a favorite team again in the same chat if the user has already declined.
