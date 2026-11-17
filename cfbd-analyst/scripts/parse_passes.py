#!/usr/bin/env python3
"""Turn CFBD play-by-play into one row per pass, with air yards and yards after catch.

CFBD's /plays endpoint has no air-yards or YAC fields, but its play descriptions
often say where a pass was caught:

  detailed: "#10 M.Reed pass complete short left to #7 I.Horton caught at A&M49,
             for 10 yards to the CIT46"
            -> catch (or target) spot is known, so air yards and YAC are computed.
  basic:    "Marcel Reed pass complete to KC Concepcion for 15 yds to the TA&M 40"
            -> passer, receiver, result and yards only; air_yards and yac are blank.

Which format a game uses depends on CFBD's source for that game, so coverage
varies by season and even by week. The summary printed at the end says how many
passes have air yards.

Definitions
  air_yards = line of scrimmage (yards to goal) - catch/target spot (yards to goal)
              (negative for throws behind the line, such as screens)
  yac       = yards gained - air_yards            (completions only)
  For incompletions air_yards is the depth of the target ("thrown to" spot);
  for interceptions it is where the ball was intercepted.

Field spots look like "A&M49" or "CIT46". The script works out which side of the
field each prefix belongs to, game by game, from plays whose end spot and yardage
are both known, so it works for any team without a list of abbreviations.

Usage
  python3 parse_passes.py --team "Texas A&M" --out passes.csv  <plays .json files or folders>
  python3 parse_passes.py --team "Texas A&M" --out passes.csv  ~/Documents/CFBD/raw

  Inputs are the JSON files cfbd_get saves for /plays, for example
  raw/plays__offense-TexasAM_seasonType-regular_week-3_year-2026__6b4291db.json.
  Season, week and season type are read from the file name. Pass a folder to read
  every plays__*.json in it. Only plays where --team is the offense are kept.

Output columns
  season, season_type, week, game_id, opponent, play_id, quarter, clock, down,
  distance, yards_to_goal, format, passer, receiver, result, depth_tag, direction,
  air_yards, yac, yards, touchdown, first_down, counted, epa, cfbd_yards,
  description

  counted = "no" for plays wiped out by a penalty (NO PLAY); leave those out of
  totals. Sacks are not passes here. Names are shortened to "F.Last" so both
  formats match ("KC Concepcion" -> "K.Concepcion").
"""
import argparse, csv, glob, json, os, re, sys, unicodedata
from collections import defaultdict

SUFFIX = {'Jr.', 'Sr.', 'II', 'III', 'IV', 'V', 'Jr', 'Sr'}
SPOT = r"([A-Za-z&'\.]*?)\s?(\d{1,2})\b"


def fold(s):
    """Drop accents so 'Öhrström' and 'Ohrstrom' match across the two formats."""
    return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii')


def short_name(full):
    """'KC Concepcion' -> 'K.Concepcion'; 'Reed, Marcel' -> 'M.Reed'; 'M.Reed' stays."""
    full = fold(full or '').strip().strip(',').strip()
    if not full:
        return ''
    if ',' in full:
        last, first = [p.strip() for p in full.split(',', 1)]
        full = first + ' ' + last
    if re.match(r"^[A-Z]\.[^ ]", full):
        return full
    parts = full.split()
    if len(parts) == 1:
        return full
    suffix = ''
    if parts[-1] in SUFFIX:
        suffix, parts = ' ' + parts[-1], parts[:-1]
    return parts[0][0] + '.' + ' '.join(parts[1:]) + suffix


def file_meta(path):
    name = os.path.basename(path)
    y = re.search(r'year-(\d{4})', name)
    w = re.search(r'week-(\d+)', name)
    st = re.search(r'seasonType-(\w+?)_', name)
    return (int(y.group(1)) if y else None, int(w.group(1)) if w else None,
            st.group(1) if st else 'regular')


def learn_sides(plays, team):
    """For each game, map a spot prefix to 'own' or 'opp' (relative to the offense).

    Uses the end spot ("to the CIT46") of plays with a known yardage: the end is
    yards_to_goal - yards_gained from the goal the offense is attacking.
    """
    votes = defaultdict(lambda: defaultdict(int))
    for r in plays:
        t = r.get('playText') or ''
        m = re.search(r'to the ' + SPOT + r'(?!\d)', t)
        if not m or not m.group(1) or r.get('yardsToGoal') is None or r.get('yardsGained') is None:
            continue
        if 'NO PLAY' in t or 'PENALTY' in t:
            continue
        end = r['yardsToGoal'] - r['yardsGained']
        n = int(m.group(2))
        if n == 50:
            continue
        key = (r['gameId'], m.group(1).upper())
        if end == n:
            votes[key]['opp'] += 1
        elif end == 100 - n:
            votes[key]['own'] += 1
    return {k: max(v, key=v.get) for k, v in votes.items()}


def spot_to_ytg(prefix, n, game_id, ytg_now, sides):
    """Convert a spot to yards-to-goal for the offense."""
    n = int(n)
    if n == 50 or not prefix:
        return 50 if n == 50 else None
    side = sides.get((game_id, prefix.upper()))
    if side == 'opp':
        return n
    if side == 'own':
        return 100 - n
    # Unknown prefix: pick the reading closest to the line of scrimmage.
    a, b = n, 100 - n
    return a if abs(ytg_now - a) <= abs(ytg_now - b) else b


def parse_detailed(t):
    m = re.search(r'#\d+ (.+?) pass (complete|incomplete|intercepted)', t)
    if not m:
        return None
    outcome = m.group(2)
    dm = re.search(r'pass (?:complete|incomplete) (short|deep)? ?(left|middle|right)?', t)
    rm = re.search(r"pass (?:complete|incomplete)[a-z ]* to #\d+ (.+?)(?:,| caught| thrown| for |$)", t)
    if outcome == 'complete':
        sm = re.search(r'caught at ' + SPOT, t)
        gm = re.search(r'for (\d+) yards? (gain|loss)', t)
        if gm:
            gained = int(gm.group(1)) * (-1 if gm.group(2) == 'loss' else 1)
        elif re.search(r'for (\d+) yards?', t):
            gained = int(re.search(r'for (\d+) yards?', t).group(1))
        elif 'no gain' in t:
            gained = 0
        else:
            gained = None
    elif outcome == 'incomplete':
        sm = re.search(r'thrown to ' + SPOT, t)
        gained = 0
    else:
        sm = re.search(r'intercepted by .+? at ' + SPOT, t)
        gained = 0
    return dict(fmt='detailed', passer=fold(m.group(1).strip()), outcome=outcome,
                depth=(dm.group(1) or '') if dm else '', side=(dm.group(2) or '') if dm else '',
                receiver=fold(rm.group(1).strip()) if rm else '', spot=sm.groups() if sm else None, gained=gained)


def parse_basic(t):
    m = re.match(r"^(?P<rec>.+?) (?P<y>\d+) Yd pass from (?P<qb>[^(]+?)(?: \(|$)", t)
    if m:
        return dict(fmt='basic', passer=short_name(m.group('qb')), outcome='complete',
                    receiver=short_name(m.group('rec')), gained=int(m.group('y')))
    m = re.match(r"^(.+?) pass intercepted", t)
    if m:
        return dict(fmt='basic', passer=short_name(m.group(1)), outcome='intercepted', receiver='', gained=0)
    core = re.split(r',? PENALTY', t)[0]
    m = re.match(r"^(?P<qb>.+?) pass (?P<o>complete|incomplete)(?: to (?P<rec>.+?))?(?: for (?P<rest>.*))?$", core)
    if not m:
        return None
    o, rest = m.group('o'), m.group('rest') or ''
    rec = re.split(r' (?:return|for)\b', m.group('rec') or '')[0]
    gained = 0
    if o == 'complete':
        gm = re.match(r'(\d+) yds?', rest) or re.match(r'a loss of (\d+) yards?', rest)
        if gm:
            gained = int(gm.group(1)) * (-1 if rest.startswith('a loss') else 1)
        elif not rest.startswith('no gain'):
            gained = None
    return dict(fmt='basic', passer=short_name(m.group('qb')), outcome=o, receiver=short_name(rec), gained=gained)


def collect_files(paths):
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += glob.glob(os.path.join(p, 'plays__*.json'))
        else:
            files += glob.glob(p)
    return sorted(f for f in set(files) if not f.endswith('.meta.json'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--team', required=True, help='Offense to keep, exactly as CFBD spells it, e.g. "Texas A&M"')
    ap.add_argument('--out', required=True, help='Output CSV path')
    ap.add_argument('inputs', nargs='+', help='plays__*.json files saved by cfbd_get, or folders holding them')
    a = ap.parse_args()

    files = collect_files(a.inputs)
    if not files:
        sys.exit('No plays__*.json files found in: ' + ', '.join(a.inputs))

    rows, seen = [], set()
    for f in files:
        season, week, stype = file_meta(f)
        data = json.load(open(f, encoding='utf-8'))
        plays = [r for r in data if r.get('offense') == a.team]
        sides = learn_sides(plays, a.team)
        for r in plays:
            if r['id'] in seen or r.get('playType') == 'Sack':
                continue
            t = (r.get('playText') or '').strip()
            rec = parse_detailed(t) or parse_basic(t)
            if not rec:
                continue
            seen.add(r['id'])
            ytg = r.get('yardsToGoal')
            air = None
            if rec.get('spot') and ytg is not None:
                to = spot_to_ytg(rec['spot'][0], rec['spot'][1], r['gameId'], ytg, sides)
                air = (ytg - to) if to is not None else None
            gained = rec['gained'] if rec['gained'] is not None else r.get('yardsGained')
            complete = rec['outcome'] == 'complete'
            nullified = 'NO PLAY' in t
            clock = r.get('clock') or {}
            rows.append({
                'season': season, 'season_type': stype, 'week': week, 'game_id': r['gameId'],
                'opponent': r.get('defense'), 'play_id': r['id'], 'quarter': r.get('period'),
                'clock': f"{clock.get('minutes', 0)}:{clock.get('seconds', 0):02d}" if clock else '',
                'down': r.get('down'), 'distance': r.get('distance'), 'yards_to_goal': ytg,
                'format': rec['fmt'], 'passer': rec['passer'], 'receiver': rec['receiver'],
                'result': {'complete': 'complete', 'incomplete': 'incomplete', 'intercepted': 'interception'}[rec['outcome']],
                'depth_tag': rec.get('depth', ''), 'direction': rec.get('side', ''),
                'air_yards': air, 'yac': (gained - air) if (complete and air is not None and gained is not None) else None,
                'yards': gained if complete else 0,
                'touchdown': 'yes' if complete and not nullified and (('TOUCHDOWN' in t and 'nullified' not in t) or 'Yd pass from' in t or r.get('playType') == 'Passing Touchdown') else 'no',
                'first_down': 'yes' if complete and not nullified and re.search(r'1ST (DOWN|down)', t) else 'no',
                'counted': 'no' if nullified else 'yes',
                'epa': None if r.get('ppa') is None else round(r['ppa'], 3),
                'cfbd_yards': r.get('yardsGained'), 'description': t,
            })

    if not rows:
        sys.exit(f'No passes found for offense "{a.team}". Check the spelling against /teams/fbs.')
    rows.sort(key=lambda x: (x['season'] or 0, x['season_type'] == 'postseason', x['week'] or 0, x['quarter'] or 0, int(x['play_id'])))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # Summary, so Claude can tell the user what the data does and doesn't cover.
    counted = [x for x in rows if x['counted'] == 'yes']
    with_air = [x for x in counted if x['air_yards'] is not None]
    comp = [x for x in with_air if x['result'] == 'complete']
    mismatch = [x for x in comp if x['cfbd_yards'] is not None and x['yards'] != x['cfbd_yards'] and 'PENALTY' not in x['description']]
    by_game = defaultdict(lambda: [0, 0])
    for x in counted:
        by_game[(x['season'], x['season_type'], x['week'], x['opponent'])][0] += 1
        by_game[(x['season'], x['season_type'], x['week'], x['opponent'])][1] += x['air_yards'] is not None
    print(f'{len(rows)} passes written to {a.out} ({len(counted)} counted, {len(rows) - len(counted)} wiped out by penalties)')
    print(f'Air yards available on {len(with_air)} of {len(counted)} counted passes')
    order = lambda k: (k[0] or 0, k[1] == 'postseason', k[2] or 0)
    charted = sorted((k for k, v in by_game.items() if v[1] >= 0.8 * v[0]), key=order)
    uncharted = sorted((k for k, v in by_game.items() if v[1] < 0.8 * v[0]), key=order)
    print(f'Games with catch spots: {len(charted)}; games without: {len(uncharted)}')
    if uncharted and charted:
        print('  First charted game: %s %s week %s vs %s' % charted[0])
        print('  Last game without:  %s %s week %s vs %s' % uncharted[-1])
    print(f'Completions where parsed yards differ from CFBD yards (no penalty on the play): {len(mismatch)}')


if __name__ == '__main__':
    main()
