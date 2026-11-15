#!/usr/bin/env python3
"""
cfbd.py - tiny, dependency-free client for the CollegeFootballData.com (CFBD) API.

Each user supplies THEIR OWN API key (free at https://collegefootballdata.com/key).
The key is never printed, logged, or written into output files.

Usage
-----
  python cfbd.py check                                   # verify key + network, show quota
  python cfbd.py get /games year=2024 team=Texas         # fetch (or reuse cache)
  python cfbd.py get /stats/season year=2024 --csv       # also write a flattened CSV
  python cfbd.py get /games year=2025 --refresh          # ignore cache
  python cfbd.py cache                                   # list what's already saved
  python cfbd.py calls                                   # show recent API call log
  python cfbd.py team set "Texas A&M"                    # save favourite team + theme
  python cfbd.py team show | team clear                  # view / remove personalization

Key lookup order (first match wins)
-----------------------------------
  1. --key-file PATH
  2. environment variable CFBD_API_KEY
  3. a file named .cfbd_key in the data directory, or in its parent

Data directory
--------------
  --data-dir PATH, else env CFBD_DATA_DIR, else ./cfbd_data
  Point this at a folder on the user's computer so data survives between chats.

Caching
-------
  Responses are saved as JSON under <data-dir>/raw/. A repeat request with the
  same path + params is served from disk and costs no API call. Seasons before
  the current year are treated as final and never refetched unless --refresh.
  Anything touching the current season (or with no year) is refetched after
  --max-age-hours (default 12).
"""
import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = os.environ.get("CFBD_BASE_URL", "https://api.collegefootballdata.com").rstrip("/")
UA = "cfbd-analyst-skill/1.0"


# ---------------------------------------------------------------- helpers
def data_dir(args):
    d = args.data_dir or os.environ.get("CFBD_DATA_DIR") or "./cfbd_data"
    d = os.path.abspath(os.path.expanduser(d))
    os.makedirs(os.path.join(d, "raw"), exist_ok=True)
    return d


def find_key(args, ddir):
    if args.key_file:
        p = os.path.expanduser(args.key_file)
        if os.path.isfile(p):
            return _read_key(p), f"key file {p}"
        sys.exit(f"ERROR: key file not found: {p}")
    if os.environ.get("CFBD_API_KEY"):
        return os.environ["CFBD_API_KEY"].strip(), "env CFBD_API_KEY"
    for p in (os.path.join(ddir, ".cfbd_key"), os.path.join(os.path.dirname(ddir), ".cfbd_key")):
        if os.path.isfile(p):
            return _read_key(p), f"key file {p}"
    sys.exit(
        "NO_KEY: No CFBD API key found.\n"
        "  Get a free key at https://collegefootballdata.com/key, then either:\n"
        "  - save it (just the key, one line) in a file named .cfbd_key in the data folder, or\n"
        "  - set CFBD_API_KEY in the environment for this run."
    )


def _read_key(p):
    k = open(p, encoding="utf-8").read().strip()
    if k.lower().startswith("bearer "):
        k = k[7:].strip()
    if not k:
        sys.exit(f"ERROR: key file {p} is empty")
    return k


def parse_params(pairs):
    params = {}
    for p in pairs:
        if "=" not in p:
            sys.exit(f"ERROR: parameter '{p}' must look like name=value")
        k, v = p.split("=", 1)
        params[k.strip()] = v.strip()
    return params


def cache_name(path, params):
    slug = re.sub(r"[^A-Za-z0-9]+", "_", path.strip("/")) or "root"
    readable = "_".join(f"{k}-{params[k]}" for k in sorted(params))
    readable = re.sub(r"[^A-Za-z0-9\-_]+", "", readable.replace(" ", ""))[:80]
    h = hashlib.sha1(json.dumps([path, sorted(params.items())]).encode()).hexdigest()[:8]
    return f"{slug}__{readable}__{h}" if readable else f"{slug}__{h}"


def is_final(params):
    """True if every year in the request is before the current season."""
    now = dt.date.today()
    current_season = now.year if now.month >= 8 else now.year - 1
    years = [v for k, v in params.items() if k.lower() in ("year", "season", "startyear", "endyear")]
    if not years:
        return False
    try:
        return all(int(y) < current_season for y in years)
    except ValueError:
        return False


def log_call(ddir, path, params, status, remaining):
    with open(os.path.join(ddir, "_calls.log"), "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "at": dt.datetime.now().isoformat(timespec="seconds"),
            "path": path, "params": params, "status": status, "remaining": remaining,
        }) + "\n")


def http_get(path, params, key):
    url = BASE_URL + "/" + path.lstrip("/")
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {key}", "Accept": "application/json", "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            body = r.read()
            remaining = r.headers.get("X-CallLimit-Remaining")
            return r.status, body, remaining
    except urllib.error.HTTPError as e:
        remaining = e.headers.get("X-CallLimit-Remaining") if e.headers else None
        return e.code, e.read(), remaining
    except urllib.error.URLError as e:
        msg = str(e.reason)
        if "403" in msg or "Tunnel" in msg or "Forbidden" in msg:
            sys.exit(
                "NETWORK_BLOCKED: Claude's sandbox is not allowed to reach api.collegefootballdata.com.\n"
                "  Fix: Claude Settings > Capabilities > (Code execution) Additional allowed domains:\n"
                "       add  api.collegefootballdata.com  then start a NEW chat.\n"
                "  Team/Enterprise plans: an org owner must add it in Organization settings > Capabilities."
            )
        sys.exit(f"NETWORK_ERROR: {msg}")


def explain_status(status, body):
    text = body[:300].decode("utf-8", "replace") if body else ""
    hints = {
        400: "Bad parameters - check required params for this endpoint in references/endpoints.md or the API reference.",
        401: "Key rejected - check the key is current (re-request at collegefootballdata.com/key).",
        403: "Key lacks access to this endpoint (some endpoints need a paid Patreon tier) or quota used up.",
        404: "Unknown endpoint path - check spelling against the API reference.",
        429: "Monthly call quota or rate limit reached.",
    }
    return f"HTTP {status}: {hints.get(status, 'Unexpected error.')}\n  Server said: {text}"


def flatten(rec, prefix=""):
    out = {}
    if isinstance(rec, dict):
        for k, v in rec.items():
            key = f"{prefix}{k}"
            if isinstance(v, dict):
                out.update(flatten(v, key + "."))
            elif isinstance(v, list):
                out[key] = json.dumps(v)
            else:
                out[key] = v
    else:
        out[prefix.rstrip(".") or "value"] = rec
    return out


def write_csv(data, path):
    rows = data if isinstance(data, list) else [data]
    flat = [flatten(r) for r in rows]
    cols = []
    for r in flat:
        for c in r:
            if c not in cols:
                cols.append(c)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(flat)
    return len(flat), len(cols)


def summarize(data):
    if isinstance(data, list):
        n = len(data)
        keys = list(data[0].keys())[:25] if n and isinstance(data[0], dict) else []
        return f"records={n}" + (f" fields={keys}" if keys else "")
    if isinstance(data, dict):
        return f"object fields={list(data.keys())[:25]}"
    return f"value={str(data)[:80]}"


# ---------------------------------------------------------------- commands
def cmd_get(args):
    ddir = data_dir(args)
    params = parse_params(args.params)
    name = cache_name(args.path, params)
    jpath = os.path.join(ddir, "raw", name + ".json")
    mpath = os.path.join(ddir, "raw", name + ".meta.json")

    if os.path.isfile(jpath) and not args.refresh:
        age_h = (dt.datetime.now().timestamp() - os.path.getmtime(jpath)) / 3600
        if is_final(params) or age_h < args.max_age_hours:
            data = json.load(open(jpath, encoding="utf-8"))
            print(f"CACHED (no API call, {age_h:.1f}h old): {jpath}")
            print(summarize(data))
            if args.csv:
                cpath = jpath[:-5] + ".csv"
                n, c = write_csv(data, cpath)
                print(f"CSV: {cpath} ({n} rows, {c} cols)")
            return

    key, src = find_key(args, ddir)
    status, body, remaining = http_get(args.path, params, key)
    log_call(ddir, args.path, params, status, remaining)
    if status != 200:
        sys.exit(explain_status(status, body))
    data = json.loads(body.decode("utf-8"))
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(data, f)
    with open(mpath, "w", encoding="utf-8") as f:
        json.dump({"path": args.path, "params": params, "base_url": BASE_URL,
                   "fetched_at": dt.datetime.now().isoformat(timespec="seconds"),
                   "calls_remaining": remaining}, f, indent=1)
    print(f"FETCHED (1 API call): {jpath}")
    print(summarize(data))
    if remaining is not None:
        print(f"calls_remaining_this_month={remaining}")
    if args.csv:
        cpath = jpath[:-5] + ".csv"
        n, c = write_csv(data, cpath)
        print(f"CSV: {cpath} ({n} rows, {c} cols)")


def cmd_check(args):
    ddir = data_dir(args)
    key, src = find_key(args, ddir)
    print(f"key source: {src} (key itself not shown)")
    print(f"data dir:   {ddir}")
    status, body, remaining = http_get("/info", {}, key)
    log_call(ddir, "/info", {}, status, remaining)
    if status != 200:
        sys.exit(explain_status(status, body))
    try:
        info = json.loads(body.decode("utf-8"))
    except Exception:
        info = body[:200].decode("utf-8", "replace")
    print("OK: key accepted and API reachable.")
    print(f"account info: {info}")
    if remaining is not None:
        print(f"calls_remaining_this_month={remaining}")


# ---------------------------------------------------------------- team personalization
def _hex(c):
    c = (c or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return "#" + c.lower() if re.fullmatch(r"[0-9a-fA-F]{6}", c) else None


def _rgb(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(v))):02x}" for v in rgb)


def _lum(h):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _mix(h, target, t):
    a, b = _rgb(h), _rgb(target)
    return _to_hex(tuple(a[i] + (b[i] - a[i]) * t for i in range(3)))


def readable_on(h, bg, min_ratio=3.0):
    """Shift colour h toward black or white until it reaches min_ratio contrast on bg."""
    if contrast(h, bg) >= min_ratio:
        return h
    target = "#000000" if _lum(bg) > 0.5 else "#ffffff"
    for i in range(1, 21):
        c = _mix(h, target, i / 20)
        if contrast(c, bg) >= min_ratio:
            return c
    return target


def _dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(_rgb(a), _rgb(b))) ** 0.5


def build_theme(primary, secondary):
    primary = primary or "#4b5563"
    secondary = secondary if secondary and _dist(secondary, primary) > 60 else None
    on_primary = "#ffffff" if contrast("#ffffff", primary) >= contrast("#000000", primary) else "#000000"
    neutral = "#9ca3af"
    t = {
        "primary": primary,
        "secondary": secondary or neutral,
        "onPrimary": on_primary,
        "light": {"bg": "#ffffff", "text": "#111827",
                  "highlight": readable_on(primary, "#ffffff"),
                  "accent": readable_on(secondary, "#ffffff") if secondary else "#6b7280",
                  "others": "#94a3b8"},
        "dark": {"bg": "#111827", "text": "#f3f4f6",
                 "highlight": readable_on(primary, "#111827"),
                 "accent": readable_on(secondary, "#111827") if secondary else "#9ca3af",
                 "others": "#64748b"},
        "notes": [],
    }
    if t["light"]["highlight"] != primary:
        t["notes"].append("primary adjusted for contrast on white backgrounds")
    if not secondary:
        t["notes"].append("alternate colour missing or too close to primary; neutral used")
    return t


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("&", "and"))


def load_teams(args, ddir):
    """All teams (FBS+FCS+lower) from /teams, cached for 30 days. One API call at most."""
    jpath = os.path.join(ddir, "raw", "teams__all.json")
    if os.path.isfile(jpath) and (dt.datetime.now().timestamp() - os.path.getmtime(jpath)) < 30 * 86400:
        return json.load(open(jpath, encoding="utf-8"))
    key, _ = find_key(args, ddir)
    status, body, remaining = http_get("/teams", {}, key)
    log_call(ddir, "/teams", {}, status, remaining)
    if status != 200:
        sys.exit(explain_status(status, body))
    data = json.loads(body.decode("utf-8"))
    json.dump(data, open(jpath, "w", encoding="utf-8"))
    return data


def match_team(teams, query):
    q = _norm(query)
    def names(t):
        alts = t.get("alternateNames") or t.get("alt_names") or []
        mascot = t.get("mascot") or ""
        school = t.get("school") or ""
        return [school, t.get("abbreviation") or "", mascot, f"{school} {mascot}"] + list(alts)
    exact = [t for t in teams if q in {_norm(n) for n in names(t) if n}]
    if exact:
        # prefer FBS, then FCS, when names collide (e.g. "Miami")
        rank = {"fbs": 0, "fcs": 1}
        exact.sort(key=lambda t: rank.get((t.get("classification") or "").lower(), 2))
        top = [t for t in exact if t.get("classification") == exact[0].get("classification")]
        return top
    import difflib
    pool = {_norm(n): t for t in teams for n in names(t) if n}
    close = difflib.get_close_matches(q, list(pool), n=6, cutoff=0.75)
    seen, out = set(), []
    for c in close:
        t = pool[c]
        if t.get("school") not in seen:
            seen.add(t.get("school")); out.append(t)
    return out


def cmd_team(args):
    ddir = data_dir(args)
    ppath = os.path.join(ddir, "profile.json")
    if args.action == "show":
        if not os.path.isfile(ppath):
            print("NO_PROFILE: no favourite team saved yet.")
            return
        print(open(ppath, encoding="utf-8").read())
        return
    if args.action == "clear":
        if os.path.isfile(ppath):
            os.remove(ppath)
        print("Profile cleared; dashboards will use the neutral theme.")
        return
    if not args.name:
        sys.exit("ERROR: give a team name, e.g.  team set \"Texas A&M\"")
    teams = load_teams(args, ddir)
    hits = match_team(teams, " ".join(args.name))
    if not hits:
        sys.exit(f"NO_MATCH: no team matches '{' '.join(args.name)}'. Try the school name as CFBD spells it.")
    if len(hits) > 1:
        print("AMBIGUOUS: several teams match - ask the user which one, then rerun with the exact school name:")
        for t in hits:
            print(f"  {t.get('school')} {t.get('mascot') or ''} ({t.get('conference') or '?'}, {t.get('classification') or '?'})")
        sys.exit(2)
    t = hits[0]
    primary = _hex(t.get("color"))
    secondary = _hex(t.get("alternateColor") or t.get("alt_color"))
    logos = [re.sub(r"^http://", "https://", u) for u in (t.get("logos") or [])
             if isinstance(u, str) and u.startswith("http")]
    profile = {
        "team": t.get("school"),
        "mascot": t.get("mascot"),
        "abbreviation": t.get("abbreviation") or (t.get("school") or "")[:4].upper(),
        "conference": t.get("conference"),
        "classification": t.get("classification"),
        "teamId": t.get("id"),
        "colors_from_cfbd": {"color": primary, "alternateColor": secondary},
        "theme": build_theme(primary, secondary),
        "logo_urls": {"light_bg": logos[0] if logos else None,
                      "dark_bg": logos[1] if len(logos) > 1 else (logos[0] if logos else None)},
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
    }
    json.dump(profile, open(ppath, "w", encoding="utf-8"), indent=1)
    print(f"SAVED favourite team: {profile['team']} {profile['mascot'] or ''} ({profile['conference']})")
    print(f"profile: {ppath}")
    th = profile["theme"]
    print(f"primary={th['primary']} secondary={th['secondary']} onPrimary={th['onPrimary']} "
          f"chart highlight light/dark={th['light']['highlight']}/{th['dark']['highlight']}")
    print(f"logo urls: {'yes' if logos else 'none in CFBD data - use monogram'}")
    for n in th["notes"]:
        print(f"note: {n}")


def cmd_cache(args):
    ddir = data_dir(args)
    metas = sorted(f for f in os.listdir(os.path.join(ddir, "raw")) if f.endswith(".meta.json"))
    if not metas:
        print(f"No cached data yet in {ddir}")
        return
    print(f"{len(metas)} cached responses in {ddir}/raw:")
    for m in metas:
        meta = json.load(open(os.path.join(ddir, "raw", m), encoding="utf-8"))
        print(f"  {meta['path']} {meta['params']}  fetched {meta['fetched_at']}  -> {m[:-10]}.json")


def cmd_calls(args):
    ddir = data_dir(args)
    p = os.path.join(ddir, "_calls.log")
    if not os.path.isfile(p):
        print("No API calls logged yet.")
        return
    lines = open(p, encoding="utf-8").read().splitlines()
    month = dt.date.today().strftime("%Y-%m")
    this_month = [l for l in lines if f'"at": "{month}' in l]
    print(f"API calls logged this month: {len(this_month)} (free tier is about 1,000/month)")
    for l in lines[-args.n:]:
        print("  " + l)


def main():
    ap = argparse.ArgumentParser(description="CollegeFootballData.com API helper (bring your own key)")
    ap.add_argument("--data-dir")
    ap.add_argument("--key-file")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("get", help="GET an endpoint, using the local cache when possible")
    g.add_argument("path", help="endpoint path, e.g. /games")
    g.add_argument("params", nargs="*", help="name=value query parameters")
    g.add_argument("--refresh", action="store_true", help="ignore cache and refetch")
    g.add_argument("--max-age-hours", type=float, default=12.0)
    g.add_argument("--csv", action="store_true", help="also write a flattened CSV next to the JSON")
    g.set_defaults(fn=cmd_get)

    sub.add_parser("check", help="verify key + network").set_defaults(fn=cmd_check)
    sub.add_parser("cache", help="list cached responses").set_defaults(fn=cmd_cache)
    c = sub.add_parser("calls", help="show the API call log")
    c.add_argument("-n", type=int, default=15)
    c.set_defaults(fn=cmd_calls)
    tm = sub.add_parser("team", help="favourite-team personalization: set NAME | show | clear")
    tm.add_argument("action", choices=["set", "show", "clear"])
    tm.add_argument("name", nargs="*")
    tm.set_defaults(fn=cmd_team)

    # allow --data-dir / --key-file after the subcommand too
    argv = sys.argv[1:]
    hoisted, rest, i = [], [], 0
    while i < len(argv):
        if argv[i] in ("--data-dir", "--key-file") and i + 1 < len(argv):
            hoisted += argv[i:i + 2]; i += 2
        else:
            rest.append(argv[i]); i += 1
    args = ap.parse_args(hoisted + rest)
    args.fn(args)


if __name__ == "__main__":
    main()
