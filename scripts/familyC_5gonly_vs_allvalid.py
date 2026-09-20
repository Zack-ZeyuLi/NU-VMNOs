#!/usr/bin/env python3
"""
Family C: find rounds that appear in '5G only' but NOT in 'All valid data'.
(Checks for data-entry inconsistencies in raw_data/family_c/valid_data_range.txt)
Also prints the reverse (All valid but not 5G only) as mismatch reference.
"""
import os, re

ROOT     = os.path.dirname(os.path.abspath(__file__))
RAW      = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
VDR_PATH = os.path.join(RAW, 'family_c', 'valid_data_range.txt')

def parse_rounds(txt):
    return set(int(x) for x in re.findall(r'Round(\d+)', txt))

def parse_vdr(filepath):
    """
    Returns:
      all_valid[direction][scenario][city][loc] = set(rounds)
      fiveg[direction][scenario][city][loc]     = set(rounds)  (union across all QCI/PCI)
    """
    def make():
        return {d: {s: {'Boston': {}, 'Philadelphia': {}} for s in range(1, 6)}
                for d in ('downlink', 'uplink')}

    all_valid = make()
    fiveg     = make()

    section   = None   # 'all' | '5g'
    direction = None
    scenario  = None
    city      = None

    with open(filepath) as f:
        for raw in f:
            line    = raw.rstrip()
            stripped = line.strip()
            if not stripped or stripped.startswith('##'):
                continue

            # ── section headers ──────────────────────────────────────────────
            if stripped.lower().startswith('all valid data'):
                section = 'all';  continue
            if stripped.lower().startswith('5g only'):
                section = '5g';   continue

            # ── direction ────────────────────────────────────────────────────
            if stripped.lower() == 'downlink:':
                direction = 'downlink'; continue
            if stripped.lower() == 'uplink:':
                direction = 'uplink';   continue

            # ── scenario ─────────────────────────────────────────────────────
            m = re.match(r'Senario\s+(\d+)', stripped, re.I)
            if m:
                scenario = int(m.group(1)); city = None; continue

            # ── city ─────────────────────────────────────────────────────────
            if stripped.rstrip(':').lower() == 'boston':
                city = 'Boston';       continue
            if stripped.rstrip(':').lower() == 'philadelphia':
                city = 'Philadelphia'; continue

            # ── skip QCI / PCI sub-headers (5G only section) ─────────────────
            if re.match(r'QCI\s+\d+', stripped, re.I):
                continue
            if stripped.lower().startswith('same pci'):
                continue
            if stripped.lower().startswith('diff pci'):
                continue

            # ── location line ─────────────────────────────────────────────────
            m = re.match(r'(Location[\w]+)\s*:\s*(.+)', stripped, re.I)
            if m and section and direction and scenario and city:
                loc  = m.group(1)
                # Normalize: "Location1" → "Location_1" (Philadelphia uses no underscore
                # in All valid but uses underscore in 5G only section)
                loc = re.sub(r'^Location(?!_)(\d)', r'Location_\1', loc)
                rnds = parse_rounds(m.group(2))
                target = all_valid if section == 'all' else fiveg
                existing = target[direction][scenario][city].get(loc, set())
                target[direction][scenario][city][loc] = existing | rnds

    return all_valid, fiveg

# ── run ───────────────────────────────────────────────────────────────────────

all_valid, fiveg = parse_vdr(VDR_PATH)

SC_LABEL = {1: 'Solo', 2: 'HC vs VC1', 3: 'HC vs VC2', 4: 'VC1 vs VC2', 5: 'HC vs VC1 vs VC2'}

print('=' * 65)
print('Family C: Rounds in 5G Only but NOT in All Valid  (errors/typos)')
print('=' * 65)

errors = []
for direction in ('downlink', 'uplink'):
    for scenario in range(1, 6):
        for city in ('Boston', 'Philadelphia'):
            av_locs = all_valid[direction][scenario][city]
            fg_locs = fiveg[direction][scenario][city]
            all_loc_keys = set(av_locs.keys()) | set(fg_locs.keys())
            for loc in sorted(all_loc_keys):
                av    = av_locs.get(loc, set())
                fg    = fg_locs.get(loc, set())
                extra = sorted(fg - av)
                if extra:
                    errors.append((direction, scenario, city, loc, extra))

if errors:
    cur = (None, None, None)
    for direction, scenario, city, loc, extra in errors:
        key = (direction, scenario, city)
        if key != cur:
            print(f'\n[{direction.upper()}  S{scenario} {SC_LABEL[scenario]}  {city}]')
            cur = key
        print(f'  {loc}: Rounds {extra}  → in 5G-only but missing from All valid')
else:
    print('\n  None found — no inconsistencies detected.\n')

print()
print('=' * 65)
print('Family C: Rounds in All Valid but NOT in 5G Only  (RAT mismatch)')
print('=' * 65)

mismatch_total = 0
for direction in ('downlink', 'uplink'):
    cur = (None, None, None)
    sc_totals = {}  # (scenario, city) -> count
    for scenario in range(1, 6):
        for city in ('Boston', 'Philadelphia'):
            av_locs = all_valid[direction][scenario][city]
            fg_locs = fiveg[direction][scenario][city]
            all_loc_keys = set(av_locs.keys()) | set(fg_locs.keys())
            for loc in sorted(all_loc_keys):
                av      = av_locs.get(loc, set())
                fg      = fg_locs.get(loc, set())
                missing = sorted(av - fg)
                if missing:
                    key = (direction, scenario, city)
                    if key != cur:
                        print(f'\n[{direction.upper()}  S{scenario} {SC_LABEL[scenario]}  {city}]')
                        cur = key
                    print(f'  {loc}: Rounds {missing}')
                    mismatch_total += len(missing)

print(f'\nTotal RAT-mismatch rounds (All valid − 5G only): {mismatch_total}')

# ── summary counts ────────────────────────────────────────────────────────────
print()
print('=' * 65)
print('Round counts by direction')
print('=' * 65)
for direction in ('downlink', 'uplink'):
    av_total = 0
    fg_total = 0
    for scenario in range(1, 6):
        for city in ('Boston', 'Philadelphia'):
            for loc, rnds in all_valid[direction][scenario][city].items():
                av_total += len(rnds)
            for loc, rnds in fiveg[direction][scenario][city].items():
                fg_total += len(rnds)
    mm = av_total - fg_total
    print(f'  {direction:10s}: All valid={av_total:4d}  5G only={fg_total:4d}  '
          f'mismatch={mm:4d}  ({100*mm/av_total:.1f}%)')
