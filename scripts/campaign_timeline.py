#!/usr/bin/env python3
"""
Build the measurement-campaign timeline table from the VALID rounds only.

Valid rounds are taken from each family's `valid_data_range.txt`
("All valid data" section).  Timestamps come from the millisecond epoch
embedded in every iperf test directory name:

    .../location_<loc>/round_<r>/<scenario>/<provider>/<ts>_<direction>_s<n>/

Output: one row per (Family, City, Location) with the calendar dates and the
local-time-of-day range over which that location's valid rounds were measured.
"""

import os, re, datetime, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))

VZ_DIR = os.path.join(RAW, 'family_a')
AT_DIR = os.path.join(RAW, 'family_b')
TM_DIR = os.path.join(RAW, 'family_c')

# scenario index -> folder name per operator role
SC_FOLDERS = {
    1: {'main': 'M',        'virtual_1': 'V1',       'virtual_2': 'V2'},
    2: {'main': 'M+V1',     'virtual_1': 'M+V1'},
    3: {'main': 'M+V2',                              'virtual_2': 'M+V2'},
    4: {                    'virtual_1': 'V1+V2',    'virtual_2': 'V1+V2'},
    5: {'main': 'M+V1+V2',  'virtual_1': 'M+V1+V2',  'virtual_2': 'M+V1+V2'},
}

FAMILIES = {
    'A': {
        'label': 'A (Family A)',
        'cities': {
            'Boston':  {'main': os.path.join(VZ_DIR, 'iperf', 'boston', 'HA'),
                        'virtual_1': os.path.join(VZ_DIR, 'iperf', 'boston', 'VA1'),
                        'virtual_2': os.path.join(VZ_DIR, 'iperf', 'boston', 'VA2')},
            'Atlanta': {'main': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'HA'),
                        'virtual_1': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'VA1'),
                        'virtual_2': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'VA2')},
        },
        'file': os.path.join(VZ_DIR, 'valid_data_range.txt'),
    },
    'B': {
        'label': 'B (Family B)',
        'cities': {
            'Boston':  {'main': os.path.join(AT_DIR, 'iperf', 'boston', 'HB'),
                        'virtual_1': os.path.join(AT_DIR, 'iperf', 'boston', 'VB1'),
                        'virtual_2': os.path.join(AT_DIR, 'iperf', 'boston', 'VB2')},
            'Atlanta': {'main': os.path.join(AT_DIR, 'iperf', 'atlanta', 'HB'),
                        'virtual_1': os.path.join(AT_DIR, 'iperf', 'atlanta', 'VB1'),
                        'virtual_2': os.path.join(AT_DIR, 'iperf', 'atlanta', 'VB2')},
        },
        'file': os.path.join(AT_DIR, 'valid_data_range.txt'),
    },
    'C': {
        # Family C keeps separate Boston trees for DL and UL
        'label': 'C (Family C)',
        'cities': {
            'Boston': {
                'downlink': {'main': os.path.join(TM_DIR, 'iperf', 'boston', 'HC'),
                             'virtual_1': os.path.join(TM_DIR, 'iperf', 'boston', 'VC1'),
                             'virtual_2': os.path.join(TM_DIR, 'iperf', 'boston', 'VC2')},
                'uplink':   {'main': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'HC'),
                             'virtual_1': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC1'),
                             'virtual_2': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC2')},
            },
            'Philadelphia': {
                'downlink': {'main': os.path.join(TM_DIR, 'iperf', 'philadelphia', 'HC'),
                             'virtual_1': os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC1'),
                             'virtual_2': os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC2')},
            },
        },
        'file': os.path.join(TM_DIR, 'valid_data_range.txt'),
    },
}
FAMILIES['C']['cities']['Philadelphia']['uplink'] = \
    FAMILIES['C']['cities']['Philadelphia']['downlink']


def parse_all_valid(path):
    """Parse the 'All valid data' section only.

    Returns [(direction, scenario_idx, city, loc_key, round_idx), ...]
    """
    out = []
    section = direction = sc = city = None
    for raw in open(path):
        line = raw.rstrip('\n')
        s = line.strip()
        if not s or s.startswith('##'):
            continue
        if s.lower().startswith('all valid data'):
            section = 'all'; continue
        if s.lower().startswith('5g only'):
            section = '5g'; continue
        if section != 'all':
            continue
        if re.match(r'^(Downlink|Uplink):', s, re.I):
            direction = s.split(':')[0].strip().lower(); continue
        m = re.match(r'^Sen[ae]rio\s*(\d+)\s*:', s, re.I)
        if m:
            sc = int(m.group(1)); continue
        m = re.match(r'^(Boston|Atlanta|Philadelphia)\s*:$', s, re.I)
        if m:
            city = m.group(1).capitalize(); continue
        m = re.match(r'^Location[_ ]?([0-9_]+)\s*:\s*(.*)$', s, re.I)
        if m and direction and sc and city:
            loc = m.group(1).strip('_')
            rounds = [int(x) for x in re.findall(r'Round\s*(\d+)', m.group(2))]
            for r in rounds:
                out.append((direction, sc, city, loc, r))
    return out


TS_RE = re.compile(r'^(\d{13})_(downlink|uplink)_s\d+$')


def timestamps_for(base, loc, rnd, sc_folder, provider, direction):
    """All epoch-second timestamps under one (loc, round, scenario, provider)."""
    d = os.path.join(base, f'location_{loc}', f'round_{rnd}', sc_folder, provider)
    if not os.path.isdir(d):
        return []
    ts = []
    for item in os.listdir(d):
        m = TS_RE.match(item)
        if m and m.group(2) == direction:
            ts.append(int(m.group(1)) / 1000.0)
    return ts


def collect():
    """Returns per-(fam, city, loc, direction) timestamps and round sets."""
    rows = collections.defaultdict(list)          # key -> [epoch]
    rounds_seen = collections.defaultdict(set)    # key -> {round}
    missing = collections.Counter()

    for fam, cfg in FAMILIES.items():
        for direction, sc, city, loc, rnd in parse_all_valid(cfg['file']):
            citycfg = cfg['cities'].get(city)
            if citycfg is None:
                missing[(fam, city, 'no-city-cfg')] += 1
                continue
            # Family C nests one more level by direction
            opdirs = citycfg[direction] if direction in citycfg else citycfg
            key = (fam, city, loc, direction)
            got = False
            for provider, sc_folder in SC_FOLDERS[sc].items():
                base = opdirs.get(provider)
                if not base:
                    continue
                ts = timestamps_for(base, loc, rnd, sc_folder, provider, direction)
                if ts:
                    rows[key].extend(ts)
                    got = True
            if got:
                rounds_seen[key].add(rnd)
            else:
                missing[(fam, city, loc, direction)] += 1
    return rows, rounds_seen, missing


def merge_directions(rows, rounds_seen):
    """Merge DL and UL into one row when they were measured on the same day(s);
    keep them separate otherwise (Family C Boston)."""
    bysite = collections.defaultdict(dict)
    for (fam, city, loc, d), ts in rows.items():
        bysite[(fam, city, loc)][d] = ts
    out = []
    for site, perdir in bysite.items():
        fam, city, loc = site
        daysets = {d: {datetime.datetime.fromtimestamp(t).date() for t in ts}
                   for d, ts in perdir.items()}
        same_day = len(daysets) < 2 or len(set.union(*daysets.values())) == \
            max(len(s) for s in daysets.values())
        if same_day:
            ts = [t for v in perdir.values() for t in v]
            nr = len(set.union(*[rounds_seen[(fam, city, loc, d)]
                                 for d in perdir]))
            if len(perdir) == 1:                       # site has one direction only
                only = next(iter(perdir))
                label = 'DL only' if only == 'downlink' else 'UL only'
            else:
                label = 'DL+UL'
            out.append((fam, city, loc, label, ts, nr))
        else:
            for d, ts in perdir.items():
                out.append((fam, city, loc,
                            'DL' if d == 'downlink' else 'UL', ts,
                            len(rounds_seen[(fam, city, loc, d)])))
    return out


def fmt_dates(dts):
    """Compact date list: merge into ranges when consecutive."""
    days = sorted({d.date() for d in dts})
    if not days:
        return '—'
    groups, start, prev = [], days[0], days[0]
    for d in days[1:]:
        if (d - prev).days == 1:
            prev = d; continue
        groups.append((start, prev)); start = prev = d
    groups.append((start, prev))
    parts = []
    for a, b in groups:
        parts.append(a.strftime('%Y-%m-%d') if a == b
                     else f"{a.strftime('%Y-%m-%d')}–{b.strftime('%m-%d')}")
    return ', '.join(parts)


FAM_ANON = {'A': 'A', 'B': 'B', 'C': 'C'}   # never print real carrier names


def emit_latex_dl(rows, rounds_seen):
    """Single-column table, downlink rounds only, no direction column."""
    recs = []
    for (fam, city, loc, direction), ts in rows.items():
        if direction != 'downlink' or not ts:
            continue
        dts = sorted(datetime.datetime.fromtimestamp(t) for t in ts)
        recs.append((fam, city, loc.replace('_', '.'),
                     len(rounds_seen[(fam, city, loc, direction)]),
                     fmt_dates(dts),
                     '%s--%s' % (dts[0].strftime('%H:%M'),
                                 dts[-1].strftime('%H:%M'))))
    recs.sort(key=lambda r: (r[0], r[1], [int(x) for x in re.findall(r'\d+', r[2])]))

    print(r'\begin{table}[t]')
    print(r'  \setlength{\abovecaptionskip}{1pt}')
    print(r'  \setlength{\belowcaptionskip}{0pt}')
    print(r'  \centering')
    print(r'  \caption{Measurement campaign timeline. Dates and local times '
          r'(U.S.\ Eastern) are those of the downlink runs at each site; '
          r'\emph{Rds} is the number of valid rounds retained after filtering.}')
    print(r'  \label{tab:campaign_timeline}')
    print(r'  \footnotesize')
    print(r'  \setlength{\tabcolsep}{4pt}')
    print(r'  \renewcommand{\arraystretch}{0.95}')
    print(r'  \begin{tabular}{@{}ll l r l l@{}}')
    print(r'    \toprule')
    print(r'    \textbf{Fam.} & \textbf{City} & \textbf{Site} & \textbf{Rds} '
          r'& \textbf{Date} & \textbf{Local time} \\')
    print(r'    \midrule')
    prev_fam = prev_city = None
    for fam, city, loc, nr, dates, tr in recs:
        if prev_fam is not None and fam != prev_fam:
            print(r'    \midrule')
        famcell = fam if fam != prev_fam else ''
        citycell = city if (city != prev_city or fam != prev_fam) else ''
        print('    %s & %s & %s & %d & %s & %s \\\\'
              % (famcell, citycell, loc, nr, dates, tr))
        prev_fam, prev_city = fam, city
    print(r'    \bottomrule')
    print(r'  \end{tabular}')
    print(r'\end{table}')


def emit_latex(merged, sortkey):
    """Two side-by-side panels inside one full-width table*."""
    recs = []
    for fam, city, loc, d, ts, nr in sorted(merged, key=sortkey):
        dts = sorted(datetime.datetime.fromtimestamp(t) for t in ts)
        recs.append((FAM_ANON[fam], city, loc.replace('_', '.'), d, nr,
                     fmt_dates(dts),
                     '%s--%s' % (dts[0].strftime('%H:%M'),
                                 dts[-1].strftime('%H:%M'))))

    split = next(i for i, r in enumerate(recs) if r[0] == 'C')
    left, right = recs[:split], recs[split:]

    def block(rs):
        out, prev = [], None
        for i, (fam, city, loc, d, nr, dates, tr) in enumerate(rs):
            if prev is not None and fam != prev:
                out.append(r'    \midrule')
            famcell = fam if fam != prev else ''
            out.append('    %s & %s & %s & %s & %d & %s & %s \\\\' %
                       (famcell, city, loc, d, nr, dates, tr))
            prev = fam
        return '\n'.join(out)

    def cells(rs, i):
        """One panel's 7 cells for row i (blank-padded)."""
        if i >= len(rs):
            return [''] * 7
        fam, city, loc, d, nr, dates, tr = rs[i]
        famcell = fam if (i == 0 or rs[i - 1][0] != fam) else ''
        citycell = city if (i == 0 or rs[i - 1][1] != city
                            or rs[i - 1][0] != fam) else ''
        return [famcell, citycell, loc, d, str(nr), dates, tr]

    hdr = [r'\textbf{Fam.}', r'\textbf{City}', r'\textbf{Site}',
           r'\textbf{Dir.}', r'\textbf{Rds}', r'\textbf{Date(s)}',
           r'\textbf{Local time}']
    colspec = 'll l l r l l'

    print(r'\begin{table*}[t]')
    print(r'  \setlength{\abovecaptionskip}{1pt}')
    print(r'  \setlength{\belowcaptionskip}{0pt}')
    print(r'  \centering')
    print(r'  \caption{Measurement campaign timeline over all valid rounds. '
          r'\emph{Rds} is the number of valid rounds retained after filtering; '
          r'all times are U.S.\ Eastern local. '
          r'In Families~A and~B, and at the Family~C Philadelphia sites, '
          r'downlink and uplink alternate within the same round (\emph{DL+UL}). '
          r'The Family~C Boston downlink and uplink measurements were collected '
          r'as separate campaigns and are therefore listed as distinct rows.}')
    print(r'  \label{tab:campaign_timeline}')
    print(r'  \footnotesize')
    print(r'  \setlength{\tabcolsep}{4pt}')
    print(r'  \renewcommand{\arraystretch}{0.95}')
    print(r'  \begin{tabular}{@{}%s@{\hspace{8pt}}|@{\hspace{8pt}}%s@{}}'
          % (colspec, colspec))
    print(r'    \toprule')
    print('    ' + ' & '.join(hdr + hdr) + r' \\')
    print(r'    \midrule')
    for i in range(max(len(left), len(right))):
        # rule under the left panel only, where its family changes
        if 0 < i < len(left) and left[i][0] != left[i - 1][0]:
            print(r'    \cmidrule(r){1-7}')
        row = cells(left, i) + cells(right, i)
        print('    ' + ' & '.join(row) + r' \\')
    print(r'    \bottomrule')
    print(r'  \end{tabular}')
    print(r'\end{table*}')


def main():
    import sys
    rows, rounds_seen, missing = collect()
    merged = merge_directions(rows, rounds_seen)

    def sortkey(r):
        fam, city, loc, d = r[0], r[1], r[2], r[3]
        return (fam, city, [int(x) for x in re.findall(r'\d+', loc)], d)

    if '--latex' in sys.argv:
        emit_latex(merged, sortkey)
        return

    print('| Family | City | Location | Dir | Rounds | Dates | Local-time range |')
    print('| ------ | ---- | -------- | --- | -----: | ----- | ---------------- |')
    for fam, city, loc, d, ts, nr in sorted(merged, key=sortkey):
        dts = sorted(datetime.datetime.fromtimestamp(t) for t in ts)
        print('| %s | %s | %s | %s | %d | %s | %s–%s |' % (
            FAMILIES[fam]['label'], city, loc.replace('_', '.'), d, nr,
            fmt_dates(dts), dts[0].strftime('%H:%M'), dts[-1].strftime('%H:%M')))

    # ── per-family summary ────────────────────────────────────────
    print('\n\n### Per-family summary\n')
    print('| Family | Cities | Sites | Test runs | Date span | Days | Local-time range | Weekend share |')
    print('| ------ | ------ | ----: | --------: | --------- | ---: | ---------------- | ------------: |')
    for fam in ('A', 'B', 'C'):
        keys = [k for k in rows if k[0] == fam]
        dts = sorted(datetime.datetime.fromtimestamp(t)
                     for k in keys for t in rows[k])
        sites = {(k[1], k[2]) for k in keys}
        cities = sorted({k[1] for k in keys})
        wk = sum(1 for d in dts if d.weekday() >= 5) / len(dts) * 100
        ndays = len({d.date() for d in dts})
        print('| %s | %s | %d | %d | %s → %s | %d | %s–%s | %.0f%% |' % (
            FAMILIES[fam]['label'], ', '.join(cities), len(sites), len(dts),
            dts[0].strftime('%Y-%m-%d'), dts[-1].strftime('%Y-%m-%d'), ndays,
            min(dts, key=lambda d: (d.hour, d.minute)).strftime('%H:%M'),
            max(dts, key=lambda d: (d.hour, d.minute)).strftime('%H:%M'), wk))

    # ── hour-of-day histogram over all valid tests ────────────────
    allh = collections.Counter(
        datetime.datetime.fromtimestamp(t).hour for k in rows for t in rows[k])
    total = sum(allh.values())
    print('\n\n### Hour-of-day distribution (all valid tests, n=%d)\n' % total)
    print('| Hour | Tests | Share |')
    print('| ---- | ----: | ----: |')
    for h in sorted(allh):
        print('| %02d:00 | %d | %.1f%% |' % (h, allh[h], 100 * allh[h] / total))

    if missing:
        print('\n\n### Valid rounds with no matching test directory\n')
        for k, v in sorted(missing.items(), key=lambda x: -x[1]):
            print('  %s: %d' % (k, v))


if __name__ == '__main__':
    main()
