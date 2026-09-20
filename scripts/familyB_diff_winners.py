#!/usr/bin/env python3
"""
Family B: compute (All valid − 5G only) diff and determine the winner
(highest mean iperf throughput) of each missing round.
"""

import os, re
import numpy as np

ROOT     = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
FAM_B_DIR = os.path.join(RAW, 'family_b')

CITY_DIRS = {
    'Boston': {
        'HB':  os.path.join(FAM_B_DIR, 'iperf', 'boston', 'HB'),
        'VB1': os.path.join(FAM_B_DIR, 'iperf', 'boston', 'VB1'),
        'VB2': os.path.join(FAM_B_DIR, 'iperf', 'boston', 'VB2'),
    },
    'Atlanta': {
        'HB':  os.path.join(FAM_B_DIR, 'iperf', 'atlanta', 'HB'),
        'VB1': os.path.join(FAM_B_DIR, 'iperf', 'atlanta', 'VB1'),
        'VB2': os.path.join(FAM_B_DIR, 'iperf', 'atlanta', 'VB2'),
    },
}

PROVIDER = {'HB': 'main', 'VB1': 'virtual_1', 'VB2': 'virtual_2'}

SCENARIO_FOLDERS = {
    1: {'HB': 'M',       'VB1': 'V1',      'VB2': 'V2'},
    2: {'HB': 'M+V1',    'VB1': 'M+V1'},
    3: {'HB': 'M+V2',                       'VB2': 'M+V2'},
    4:                   {'VB1': 'V1+V2',   'VB2': 'V1+V2'},
    5: {'HB': 'M+V1+V2', 'VB1': 'M+V1+V2', 'VB2': 'M+V1+V2'},
}

_BITRATE_RE = re.compile(
    r'\[\s*\d+\]\s+[\d.]+-[\d.]+\s+sec\s+[\d.]+\s+[KMG]?Bytes\s+'
    r'([\d.]+)\s+([KMG]?)bits/sec')
_SUMMARY_RE = re.compile(r'0\.00-\d+\.\d+\s+sec.*(?:sender|receiver)')

def parse_mbps(val, prefix):
    return float(val) * {'': 1e-3, 'K': 1e-3, 'M': 1.0, 'G': 1000.0}.get(prefix, 1.0)

def extract_tp(fp):
    tps = []
    try:
        with open(fp) as f:
            for line in f:
                if _SUMMARY_RE.search(line):
                    continue
                m = _BITRATE_RE.search(line)
                if m:
                    tps.append(parse_mbps(m.group(1), m.group(2)))
    except Exception:
        pass
    return tps

def find_iperf(base_dir, loc, rnd, sc_folder, provider, direction):
    sc_path = os.path.join(base_dir, f'location_{loc}', f'round_{rnd}', sc_folder, provider)
    if not os.path.isdir(sc_path):
        return None
    for item in os.listdir(sc_path):
        full = os.path.join(sc_path, item)
        if direction in item and os.path.isdir(full):
            for f in os.listdir(full):
                if f.endswith('.out') and direction in f:
                    return os.path.join(full, f)
    return None

# ── parse valid_data_range.txt ────────────────────────────────────────────────

def parse_rounds(txt):
    """Return list[int] of round numbers from 'Round1, Round2, ...' text."""
    return [int(x) for x in re.findall(r'Round(\d+)', txt)]

def parse_vdr(filepath):
    """
    Returns:
      all_valid[direction][scenario][city][loc] = set(rounds)
      fiveg[direction][scenario][city][loc]     = set(rounds)   (same+diff union)
    """
    def make():
        return {d: {s: {'Boston': {}, 'Atlanta': {}} for s in range(1,6)}
                for d in ('downlink', 'uplink')}

    all_valid = make()
    fiveg     = make()

    section   = None   # 'all' | '5g'
    direction = None   # 'downlink' | 'uplink'
    scenario  = None   # 1‒5
    city      = None   # 'Boston' | 'Atlanta'
    # pci ignored for all_valid; for 5g we union same+diff

    with open(filepath) as f:
        for raw in f:
            line = raw.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith('##'):
                continue

            # ── section headers ──
            if stripped.lower().startswith('all valid data'):
                section = 'all'; continue
            if stripped.lower().startswith('5g only'):
                section = '5g'; continue

            # ── direction ──
            if stripped.lower() == 'downlink:':
                direction = 'downlink'; continue
            if stripped.lower() == 'uplink:':
                direction = 'uplink'; continue

            # ── scenario ──
            m = re.match(r'Senario\s+(\d+)', stripped, re.I)
            if m:
                scenario = int(m.group(1)); city = None; continue

            # ── city ──
            if stripped.rstrip(':').lower() == 'boston':
                city = 'Boston'; continue
            if stripped.rstrip(':').lower() == 'atlanta':
                city = 'Atlanta'; continue

            # ── pci lines (5g only, we just ignore the label) ──
            if stripped.lower().startswith('same pci'):
                continue
            if stripped.lower().startswith('diff pci'):
                continue

            # ── location line ──
            m = re.match(r'Location(\d+)\s*:\s*(.+)', stripped, re.I)
            if m and section and direction and scenario and city:
                loc  = int(m.group(1))
                rnds = set(parse_rounds(m.group(2)))
                target = all_valid if section == 'all' else fiveg
                existing = target[direction][scenario][city].get(loc, set())
                target[direction][scenario][city][loc] = existing | rnds

    return all_valid, fiveg

VDR_PATH = os.path.join(FAM_B_DIR, 'valid_data_range.txt')
all_valid, fiveg = parse_vdr(VDR_PATH)

# ── compute diff ──────────────────────────────────────────────────────────────

diffs = []  # list of (direction, scenario, city, loc, sorted_missing_rounds)

for direction in ('downlink', 'uplink'):
    for scenario in range(1, 6):
        for city in ('Boston', 'Atlanta'):
            all_locs  = all_valid[direction][scenario][city]
            five_locs = fiveg[direction][scenario][city]
            all_loc_keys = set(all_locs.keys()) | set(five_locs.keys())
            for loc in sorted(all_loc_keys):
                av = all_locs.get(loc, set())
                fg = five_locs.get(loc, set())
                missing = sorted(av - fg)
                extra   = sorted(fg - av)
                if extra:
                    print(f'  [WARN] {direction} S{scenario} {city} Loc{loc}: '
                          f'rounds {extra} in 5G only but not in All valid — check file')
                if missing:
                    diffs.append((direction, scenario, city, loc, missing))

# ── for each missing round, find winner ───────────────────────────────────────

SC_LABEL = {1:'Solo', 2:'HB vs VB1', 3:'HB vs VB2', 4:'VB1 vs VB2', 5:'HB vs VB1 vs VB2'}

results = []

for direction, scenario, city, loc, missing_rounds in diffs:
    op_folders = SCENARIO_FOLDERS[scenario]
    dir_key = 'downlink' if direction == 'downlink' else 'uplink'

    for rnd in missing_rounds:
        means = {}
        for op, sc_folder in op_folders.items():
            base = CITY_DIRS[city][op]
            provider = PROVIDER[op]
            fp = find_iperf(base, loc, rnd, sc_folder, provider, dir_key)
            if fp:
                tps = extract_tp(fp)
                if tps:
                    means[op] = np.mean(tps)

        if len(means) >= 1:
            winner = max(means, key=means.get)
            mean_str = ', '.join(f'{op}={means[op]:.1f}' for op in sorted(means))
        else:
            winner = 'NO DATA'
            mean_str = ''

        results.append({
            'dir': direction, 'sc': scenario, 'sc_label': SC_LABEL[scenario],
            'city': city, 'loc': loc, 'rnd': rnd,
            'winner': winner, 'means': mean_str,
        })

# ── print results ─────────────────────────────────────────────────────────────

print('\n=== Family B: Rounds in All Valid but NOT in 5G Only, with winners ===\n')

cur = (None, None, None)
for r in results:
    key = (r['dir'], r['sc'], r['city'])
    if key != cur:
        print(f"\n[{r['dir'].upper()}  S{r['sc']} {r['sc_label']}  {r['city']}]")
        cur = key
    flag = ' ← NO DATA' if r['winner'] == 'NO DATA' else ''
    print(f"  Loc{r['loc']} R{r['rnd']:1d}  winner={r['winner']:4s}  ({r['means']}){flag}")

# ── summary counts ────────────────────────────────────────────────────────────

from collections import Counter
win_counts = Counter(r['winner'] for r in results if r['winner'] != 'NO DATA')
total = sum(win_counts.values())
print(f'\n=== Win summary over {total} missing rounds ===')
for op, cnt in sorted(win_counts.items(), key=lambda x: -x[1]):
    print(f'  {op}: {cnt}  ({100*cnt/total:.1f}%)')
no_data = sum(1 for r in results if r['winner'] == 'NO DATA')
if no_data:
    print(f'  NO DATA: {no_data}')
