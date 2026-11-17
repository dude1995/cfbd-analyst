// CFBD Data - local MCP server packaged as a Claude Desktop extension (.mcpb).
//
// The user's CollegeFootballData.com API key is entered once in Claude Desktop's
// extension settings, which keep it in the operating system's secure storage
// (Keychain / Credential Manager) and pass it to this process as CFBD_API_KEY.
// This server adds it to requests to api.collegefootballdata.com and never
// returns it, logs it, or writes it to disk. Claude only sees tool results.
//
// Responses are cached under the user's data folder so later chats reuse them.

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";
import crypto from "node:crypto";

const VERSION = "1.2.0";
const API_HOST = "https://api.collegefootballdata.com";
// Test hook: only a localhost http URL may replace the real host, so the key can
// never be pointed at another internet host.
const BASE_URL = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/.test(process.env.CFBD_BASE_URL || "")
  ? process.env.CFBD_BASE_URL
  : API_HOST;

const API_KEY = (process.env.CFBD_API_KEY || "").trim().replace(/^bearer\s+/i, "");

function resolveDataDir() {
  let d = (process.env.CFBD_DATA_DIR || "").trim();
  if (!d || d.includes("${")) d = path.join(os.homedir(), "Documents", "CFBD");
  if (d.startsWith("~")) d = path.join(os.homedir(), d.slice(1));
  d = path.resolve(d);
  fs.mkdirSync(path.join(d, "raw"), { recursive: true });
  return d;
}
const DATA_DIR = resolveDataDir();
const RAW = path.join(DATA_DIR, "raw");

// ------------------------------------------------------------------ helpers
const text = (s) => ({ content: [{ type: "text", text: s }] });
const fail = (s) => ({ content: [{ type: "text", text: s }], isError: true });
const scrub = (s) => (API_KEY ? String(s).split(API_KEY).join("[key hidden]") : String(s));

function cacheName(p, params) {
  const slug = p.replace(/^\/+/, "").replace(/[^A-Za-z0-9]+/g, "_") || "root";
  const keys = Object.keys(params).sort();
  let readable = keys.map((k) => `${k}-${params[k]}`).join("_");
  readable = readable.replace(/\s+/g, "").replace(/[^A-Za-z0-9\-_]+/g, "").slice(0, 80);
  const h = crypto.createHash("sha1")
    .update(JSON.stringify([p, keys.map((k) => [k, String(params[k])])])).digest("hex").slice(0, 8);
  return readable ? `${slug}__${readable}__${h}` : `${slug}__${h}`;
}

function currentSeason() {
  const now = new Date();
  return now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1;
}

function isFinal(params) {
  const ys = Object.entries(params)
    .filter(([k]) => ["year", "season", "startyear", "endyear"].includes(k.toLowerCase()))
    .map(([, v]) => parseInt(v, 10));
  return ys.length > 0 && ys.every((y) => Number.isFinite(y) && y < currentSeason());
}

function logCall(p, params, status, remaining) {
  fs.appendFileSync(path.join(DATA_DIR, "_calls.log"),
    JSON.stringify({ at: new Date().toISOString().slice(0, 19), path: p, params, status, remaining }) + "\n");
}

async function apiGet(p, params) {
  if (!API_KEY) {
    return { error: "NO_KEY: No CFBD API key is set. In Claude Desktop open Settings > Extensions > CFBD Data > Configure and paste your key (free at https://collegefootballdata.com/key)." };
  }
  const url = new URL(BASE_URL + p);
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, String(v));
  let res;
  try {
    res = await fetch(url, {
      headers: { Authorization: `Bearer ${API_KEY}`, Accept: "application/json", "User-Agent": `cfbd-data-extension/${VERSION}` },
      signal: AbortSignal.timeout(60000),
    });
  } catch (e) {
    return { error: scrub(`NETWORK_ERROR: could not reach ${API_HOST} from this computer (${e.cause?.code || e.message}).`) };
  }
  const remaining = res.headers.get("x-calllimit-remaining");
  const body = await res.text();
  logCall(p, params, res.status, remaining);
  if (!res.ok) {
    const hints = {
      400: "Bad parameters for this endpoint. Check the API reference at https://apinext.collegefootballdata.com.",
      401: "Key rejected. Re-enter it in Settings > Extensions > CFBD Data (request a new one at collegefootballdata.com/key if needed).",
      403: "This key can't use this endpoint (some need a paid CFBD Patreon tier) or the monthly quota is used up.",
      404: "Unknown endpoint path. Check spelling against the API reference.",
      429: "Monthly call quota or rate limit reached.",
    };
    return { error: scrub(`HTTP ${res.status}: ${hints[res.status] || "Unexpected error."} Server said: ${body.slice(0, 300)}`) };
  }
  try {
    return { data: JSON.parse(body), remaining };
  } catch {
    return { error: "The API returned something that isn't JSON." };
  }
}

function flatten(rec, prefix = "", out = {}) {
  if (rec && typeof rec === "object" && !Array.isArray(rec)) {
    for (const [k, v] of Object.entries(rec)) {
      if (v && typeof v === "object" && !Array.isArray(v)) flatten(v, `${prefix}${k}.`, out);
      else out[`${prefix}${k}`] = Array.isArray(v) ? JSON.stringify(v) : v;
    }
  } else out[prefix.replace(/\.$/, "") || "value"] = rec;
  return out;
}

function writeCsv(data, file) {
  const rows = (Array.isArray(data) ? data : [data]).map((r) => flatten(r));
  const cols = [];
  for (const r of rows) for (const c of Object.keys(r)) if (!cols.includes(c)) cols.push(c);
  const esc = (v) => {
    if (v === null || v === undefined) return "";
    const s = String(v);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  fs.writeFileSync(file, [cols.join(","), ...rows.map((r) => cols.map((c) => esc(r[c])).join(","))].join("\n"));
  return { rows: rows.length, cols: cols.length };
}

function summarize(data) {
  if (Array.isArray(data)) {
    const fields = data.length && typeof data[0] === "object" ? Object.keys(data[0]).slice(0, 30) : [];
    return `records: ${data.length}${fields.length ? `\nfields: ${fields.join(", ")}` : ""}`;
  }
  if (data && typeof data === "object") return `object fields: ${Object.keys(data).slice(0, 30).join(", ")}`;
  return `value: ${String(data).slice(0, 80)}`;
}

function preview(data, n) {
  if (!n) return "";
  const sample = Array.isArray(data) ? data.slice(0, n) : data;
  let s = JSON.stringify(sample);
  if (s.length > 4000) s = s.slice(0, 4000) + " …(truncated)";
  return `\npreview (${Array.isArray(data) ? Math.min(n, data.length) + " records" : "object"}): ${s}`;
}

function relDisplay(f) {
  return path.relative(DATA_DIR, f).split(path.sep).join("/");
}

// ------------------------------------------------------------------ team theme
const hex = (c) => {
  c = String(c || "").trim().replace(/^#/, "");
  if (c.length === 3) c = c.split("").map((x) => x + x).join("");
  return /^[0-9a-fA-F]{6}$/.test(c) ? "#" + c.toLowerCase() : null;
};
const rgb = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const toHex = (a) => "#" + a.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, "0")).join("");
const lum = (h) => {
  const [r, g, b] = rgb(h).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };
const mix = (h, t, k) => { const a = rgb(h), b = rgb(t); return toHex(a.map((v, i) => v + (b[i] - v) * k)); };
const readableOn = (h, bg, min = 3) => {
  if (contrast(h, bg) >= min) return h;
  const t = lum(bg) > 0.5 ? "#000000" : "#ffffff";
  for (let i = 1; i <= 20; i++) { const c = mix(h, t, i / 20); if (contrast(c, bg) >= min) return c; }
  return t;
};
const dist = (a, b) => Math.hypot(...rgb(a).map((v, i) => v - rgb(b)[i]));

function buildTheme(primary, secondary) {
  primary = primary || "#4b5563";
  secondary = secondary && dist(secondary, primary) > 60 ? secondary : null;
  const onPrimary = contrast("#ffffff", primary) >= contrast("#000000", primary) ? "#ffffff" : "#000000";
  const t = {
    primary, secondary: secondary || "#9ca3af", onPrimary,
    light: { bg: "#ffffff", text: "#111827", highlight: readableOn(primary, "#ffffff"),
      accent: secondary ? readableOn(secondary, "#ffffff") : "#6b7280", others: "#94a3b8" },
    dark: { bg: "#111827", text: "#f3f4f6", highlight: readableOn(primary, "#111827"),
      accent: secondary ? readableOn(secondary, "#111827") : "#9ca3af", others: "#64748b" },
    notes: [],
  };
  if (t.light.highlight !== primary) t.notes.push("primary adjusted for contrast on white backgrounds");
  if (!secondary) t.notes.push("alternate colour missing or too close to primary; neutral used");
  return t;
}

const norm = (s) => String(s || "").toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]/g, "");

async function loadTeams() {
  const f = path.join(RAW, "teams__all.json");
  if (fs.existsSync(f) && Date.now() - fs.statSync(f).mtimeMs < 30 * 86400e3) {
    return { teams: JSON.parse(fs.readFileSync(f, "utf8")) };
  }
  const r = await apiGet("/teams", {});
  if (r.error) return r;
  fs.writeFileSync(f, JSON.stringify(r.data));
  return { teams: r.data };
}

function levenshtein(a, b) {
  const m = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
  for (let j = 1; j <= b.length; j++) m[0][j] = j;
  for (let i = 1; i <= a.length; i++)
    for (let j = 1; j <= b.length; j++)
      m[i][j] = Math.min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
  return m[a.length][b.length];
}

function matchTeam(teams, query) {
  const q = norm(query);
  const names = (t) => [t.school, t.abbreviation, t.mascot, `${t.school} ${t.mascot}`, ...(t.alternateNames || t.alt_names || [])].filter(Boolean);
  let exact = teams.filter((t) => names(t).some((n) => norm(n) === q));
  if (exact.length) {
    const rank = (t) => ({ fbs: 0, fcs: 1 }[String(t.classification || "").toLowerCase()] ?? 2);
    exact.sort((a, b) => rank(a) - rank(b));
    return exact.filter((t) => rank(t) === rank(exact[0]));
  }
  const scored = [];
  for (const t of teams) {
    let best = Infinity;
    for (const n of names(t)) { const nn = norm(n); best = Math.min(best, levenshtein(q, nn) / Math.max(q.length, nn.length, 1)); }
    if (best <= 0.25) scored.push([best, t]);
  }
  scored.sort((a, b) => a[0] - b[0]);
  if (scored.length > 1 && scored[0][0] < scored[1][0]) return [scored[0][1]];
  return scored.slice(0, 6).map((s) => s[1]);
}

// ------------------------------------------------------------------ server
const server = new McpServer({ name: "cfbd-data", version: VERSION });

const paramValue = z.union([z.string(), z.number(), z.boolean()]);

server.registerTool("cfbd_get", {
  title: "Get CollegeFootballData.com data",
  description:
    "Fetch data from the CollegeFootballData.com API using the API key stored in Claude Desktop (you never see or need the key). " +
    "Results are saved as JSON (and optionally CSV) in the user's CFBD data folder and reused on repeat requests, so repeated calls cost nothing. " +
    "Past seasons are cached permanently; current-season data refreshes after max_age_hours. " +
    "Returns the saved file path, record count, field names, remaining monthly calls and an optional short preview, not the full data: " +
    "read the saved file (via the user's connected CFBD folder) or use cfbd_read to work with it.",
  inputSchema: {
    path: z.string().regex(/^\/[A-Za-z0-9_\/\-]*$/, "an endpoint path such as /games or /stats/season/advanced")
      .describe("Endpoint path, e.g. /games, /teams/fbs, /stats/season/advanced, /ppa/teams, /rankings"),
    params: z.record(z.string(), paramValue).optional().describe("Query parameters, e.g. {\"year\": 2024, \"team\": \"Texas\"}"),
    refresh: z.boolean().optional().describe("Ignore the cache and refetch (uses an API call)"),
    max_age_hours: z.number().optional().describe("Refetch cached current-season data older than this (default 12)"),
    csv: z.boolean().optional().describe("Also save a flattened CSV next to the JSON"),
    preview_records: z.number().int().min(0).max(10).optional().describe("Include up to this many records in the reply (default 2)"),
  },
}, async ({ path: p, params = {}, refresh = false, max_age_hours = 12, csv = false, preview_records = 2 }) => {
  if (p.includes("..")) return fail("Invalid path.");
  const name = cacheName(p, params);
  const jf = path.join(RAW, name + ".json");
  const mf = path.join(RAW, name + ".meta.json");
  let data, status, remaining = null;
  if (!refresh && fs.existsSync(jf)) {
    const ageH = (Date.now() - fs.statSync(jf).mtimeMs) / 3600e3;
    if (isFinal(params) || ageH < max_age_hours) {
      data = JSON.parse(fs.readFileSync(jf, "utf8"));
      status = `CACHED (no API call, ${ageH.toFixed(1)}h old)`;
    }
  }
  if (data === undefined) {
    const r = await apiGet(p, params);
    if (r.error) return fail(r.error);
    data = r.data; remaining = r.remaining;
    fs.writeFileSync(jf, JSON.stringify(data));
    fs.writeFileSync(mf, JSON.stringify({ path: p, params, fetched_at: new Date().toISOString().slice(0, 19), calls_remaining: remaining }, null, 1));
    status = "FETCHED (1 API call)";
  }
  let out = `${status}\nfile: ${relDisplay(jf)}  (in data folder ${DATA_DIR})\n${summarize(data)}`;
  if (remaining !== null) out += `\ncalls_remaining_this_month: ${remaining}`;
  if (csv) {
    const cf = jf.replace(/\.json$/, ".csv");
    const { rows, cols } = writeCsv(data, cf);
    out += `\ncsv: ${relDisplay(cf)} (${rows} rows, ${cols} cols)`;
  }
  out += preview(data, preview_records);
  return text(out);
});

server.registerTool("cfbd_read", {
  title: "Read saved CFBD data",
  description:
    "Read records from a file previously saved by cfbd_get (path relative to the data folder, e.g. raw/games__team-Texas_year-2024__ab12cd34.json). " +
    "Use when the CFBD folder isn't connected to the chat. Optionally pick fields (dot paths allowed) and page with offset/limit (max 500 rows per call).",
  inputSchema: {
    file: z.string().describe("File path relative to the data folder, as returned by cfbd_get"),
    fields: z.array(z.string()).optional().describe("Only return these fields, e.g. [\"homeTeam\",\"homePoints\",\"venue.name\"]"),
    offset: z.number().int().min(0).optional(),
    limit: z.number().int().min(1).max(500).optional(),
  },
}, async ({ file, fields, offset = 0, limit = 200 }) => {
  const f = path.resolve(DATA_DIR, file);
  if (!f.startsWith(DATA_DIR + path.sep) || !f.endsWith(".json") || path.basename(f).startsWith(".")) return fail("Only .json files inside the CFBD data folder can be read.");
  if (!fs.existsSync(f)) return fail(`No such file: ${file}. Use cfbd_status to list saved data.`);
  let data = JSON.parse(fs.readFileSync(f, "utf8"));
  const rows = Array.isArray(data) ? data : [data];
  const pick = (r) => {
    if (!fields?.length) return r;
    const flat = flatten(r);
    return Object.fromEntries(fields.map((k) => [k, k in flat ? flat[k] : r[k]]));
  };
  const page = rows.slice(offset, offset + limit).map(pick);
  return text(JSON.stringify({ total: rows.length, offset, returned: page.length, records: page }));
});

server.registerTool("cfbd_status", {
  title: "CFBD status, saved data and usage",
  description:
    "Check that the stored API key works (one API call to /info unless check_key is false), and list what's already saved in the data folder and how many API calls were logged this month. " +
    "Never reveals the key.",
  inputSchema: { check_key: z.boolean().optional().describe("Verify the key with a live call (default true)") },
}, async ({ check_key = true }) => {
  const lines = [`extension version ${VERSION}`, `data folder: ${DATA_DIR}`, `API key: ${API_KEY ? "set (hidden)" : "NOT SET - add it in Settings > Extensions > CFBD Data"}`];
  if (check_key && API_KEY) {
    const r = await apiGet("/info", {});
    lines.push(r.error ? `key check: ${r.error}` : `key check: OK ${JSON.stringify(r.data)}${r.remaining ? ` (calls remaining: ${r.remaining})` : ""}`);
  }
  const month = new Date().toISOString().slice(0, 7);
  const log = path.join(DATA_DIR, "_calls.log");
  const calls = fs.existsSync(log) ? fs.readFileSync(log, "utf8").split("\n").filter((l) => l.includes(`"at":"${month}`)).length : 0;
  lines.push(`API calls logged this month: ${calls} (free tier is about 1,000/month)`);
  const metas = fs.readdirSync(RAW).filter((f) => f.endsWith(".meta.json")).sort();
  lines.push(`saved responses: ${metas.length}`);
  for (const m of metas.slice(-60)) {
    try {
      const j = JSON.parse(fs.readFileSync(path.join(RAW, m), "utf8"));
      lines.push(`  ${j.path} ${JSON.stringify(j.params)}  fetched ${j.fetched_at} -> raw/${m.replace(/\.meta\.json$/, ".json")}`);
    } catch { /* ignore */ }
  }
  const pf = path.join(DATA_DIR, "profile.json");
  lines.push(fs.existsSync(pf) ? `favorite team: ${JSON.parse(fs.readFileSync(pf, "utf8")).team}` : "favorite team: none saved");
  return text(lines.join("\n"));
});

server.registerTool("cfbd_team", {
  title: "Favorite team personalization",
  description:
    "Save, show or clear the user's favorite team. 'set' matches school names, abbreviations or mascots (e.g. 'UT', 'Longhorns'), " +
    "saves profile.json in the data folder with CFBD's colours, a contrast-checked theme for dashboards, and CFBD's logo URLs. " +
    "If several teams match, it lists them so you can ask the user. Costs at most one API call (team list cached 30 days).",
  inputSchema: {
    action: z.enum(["set", "show", "clear"]),
    name: z.string().optional().describe("Team to save when action is 'set'"),
  },
}, async ({ action, name }) => {
  const pf = path.join(DATA_DIR, "profile.json");
  if (action === "show") return text(fs.existsSync(pf) ? fs.readFileSync(pf, "utf8") : "NO_PROFILE: no favorite team saved yet.");
  if (action === "clear") { if (fs.existsSync(pf)) fs.unlinkSync(pf); return text("Profile cleared; dashboards will use the neutral theme."); }
  if (!name) return fail("Give a team name.");
  const r = await loadTeams();
  if (r.error) return fail(r.error);
  const hits = matchTeam(r.teams, name);
  if (!hits.length) return fail(`NO_MATCH: no team matches '${name}'. Try the school name as CFBD spells it.`);
  if (hits.length > 1) {
    return text("AMBIGUOUS: ask the user which one, then call again with the exact school name:\n" +
      hits.map((t) => `  ${t.school} ${t.mascot || ""} (${t.conference || "?"}, ${t.classification || "?"})`).join("\n"));
  }
  const t = hits[0];
  const primary = hex(t.color), secondary = hex(t.alternateColor || t.alt_color);
  const logos = (t.logos || []).filter((u) => typeof u === "string" && u.startsWith("http")).map((u) => u.replace(/^http:\/\//, "https://"));
  const profile = {
    team: t.school, mascot: t.mascot, abbreviation: t.abbreviation || String(t.school || "").slice(0, 4).toUpperCase(),
    conference: t.conference, classification: t.classification, teamId: t.id,
    colors_from_cfbd: { color: primary, alternateColor: secondary },
    theme: buildTheme(primary, secondary),
    logo_urls: { light_bg: logos[0] || null, dark_bg: logos[1] || logos[0] || null },
    saved_at: new Date().toISOString().slice(0, 19),
  };
  fs.writeFileSync(pf, JSON.stringify(profile, null, 1));
  return text(`SAVED favorite team: ${profile.team} ${profile.mascot || ""} (${profile.conference})\n` + JSON.stringify(profile, null, 1));
});

await server.connect(new StdioServerTransport());
