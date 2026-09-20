#!/usr/bin/env python3
"""
Family C DL: compute per-round win rates under QCI 677-type vs QCI 999-type conditions.

QCI 677-type  = rounds where HC has QCI 6, MVNOs have QCI 7
  file labels: "677" (S1/S5), "67" (S2/S3), "77" (S4)
QCI 999-type  = rounds where all operators have QCI 9
  file labels: "999" (S1/S5), "99"  (S2/S3/S4)

Win rule: an operator wins a round only if its mean iperf DL throughput exceeds
every rival by >10 %.  If no single operator clears that bar the round is a tie.
"""

import os, re
import numpy as np
from collections import defaultdict

ROOT     = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
TM_DIR   = os.path.join(RAW, 'family_c')
VDR_PATH = os.path.join(TM_DIR, 'valid_data_range.txt')

# ── base directories (DL) ─────────────────────────────────────────────────────
CITY_OP_DIR = {
    'Boston': {
        'HC':  os.path.join(TM_DIR, 'iperf', 'boston', 'HC'),
        'VC1': os.path.join(TM_DIR, 'iperf', 'boston', 'VC1'),
        'VC2': os.path.join(TM_DIR, 'iperf', 'boston', 'VC2'),
    },
    'Philadelphia': {
        'HC':  os.path.join(TM_DIR, 'iperf', 'philadelphia', 'HC'),
        'VC1': os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC1'),
        'VC2': os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC2'),
    },
}

# scenario folder each operator uses
SC_FOLDERS = {
    1: {'HC': 'M',       'VC1': 'V1',      'VC2': 'V2'},
    2: {'HC': 'M+V1',    'VC1': 'M+V1'},
    3: {'HC': 'M+V2',                       'VC2': 'M+V2'},
    4:                   {'VC1': 'V1+V2',   'VC2': 'V1+V2'},
    5: {'HC': 'M+V1+V2', 'VC1': 'M+V1+V2', 'VC2': 'M+V1+V2'},
}

# provider sub-folder
PROVIDER = {'HC': 'main', 'VC1': 'virtual_1', 'VC2': 'virtual_2'}

SC_LABEL = {1: 'Solo', 2: 'HC vs VC1', 3: 'HC vs VC2', 4: 'VC1 vs VC2', 5: 'HC vs VC1 vs VC2'}

# QCI groups
QCI_LABEL_TO_GROUP = {
    '677': '677', '67': '677', '77': '677',
    '999': '999', '99': '999',
}

# ── iperf parsing ─────────────────────────────────────────────────────────────
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

def find_iperf(city, op, scenario, loc_key, rnd, direction='downlink'):
    """Return path to iperf .out file, or None."""
    base   = CITY_OP_DIR[city][op]
    sc_fol = SC_FOLDERS[scenario][op]
    prov   = PROVIDER[op]
    # location folder: lower-case version of loc_key
    loc_fol = loc_key.lower()  # "Location_1_1" → "location_1_1"
    sc_path = os.path.join(base, loc_fol, f'round_{rnd}', sc_fol, prov)
    if not os.path.isdir(sc_path):
        return None
    dir_kw = direction  # 'downlink' or 'uplink'
    for item in sorted(os.listdir(sc_path)):
        full = os.path.join(sc_path, item)
        if dir_kw in item and os.path.isdir(full):
            for f in os.listdir(full):
                if f.endswith('.out') and dir_kw in f:
                    return os.path.join(full, f)
    return None

# ── parse valid_data_range.txt for 5G-only DL with QCI ───────────────────────
def parse_rounds(txt):
    return set(int(x) for x in re.findall(r'Round(\d+)', txt))

def parse_vdr_5g_qci(filepath):
    """
    Returns:
      rounds[scenario][qci_str][city][loc] = set(rounds)
    where qci_str is one of '677','999','67','99','77'
    """
    data = {s: {} for s in range(1, 6)}  # scenario → qci_str → city → loc → rounds

    in_dl_5g = False
    scenario  = None
    city      = None
    qci_str   = None

    with open(filepath) as f:
        lines = f.readlines()

    i = 0
    while i < len(lines):
        raw = lines[i].rstrip()
        s   = raw.strip()
        i  += 1

        if not s or s.startswith('##'):
            continue

        if s.lower().startswith('5g only'):
            in_dl_5g = False   # will be set True when we hit 'Downlink:'
            continue
        if s.lower() == 'downlink:':
            # Check if we're in 5G only section by looking at context
            # We set a flag when we enter 5G only
            in_dl_5g = True
            scenario = city = qci_str = None
            continue
        if s.lower() == 'uplink:':
            in_dl_5g = False
            continue

        if not in_dl_5g:
            continue

        m = re.match(r'Senario\s+(\d+)', s, re.I)
        if m:
            scenario = int(m.group(1)); city = qci_str = None; continue

        if s.rstrip(':').lower() == 'boston':
            city = 'Boston'; qci_str = None; continue
        if s.rstrip(':').lower() == 'philadelphia':
            city = 'Philadelphia'; qci_str = None; continue

        # QCI line: "QCI 677:", "QCI 99:", etc.
        m = re.match(r'QCI\s+(\d+)', s, re.I)
        if m:
            qci_str = m.group(1); continue

        # Skip PCI sub-headers
        if s.lower().startswith('same pci') or s.lower().startswith('diff pci'):
            continue

        # Location line
        m = re.match(r'(Location[\w]+)\s*:\s*(.+)', s, re.I)
        if m and scenario and city and qci_str:
            loc  = m.group(1)
            # Normalise Philadelphia naming
            loc  = re.sub(r'^Location(?!_)(\d)', r'Location_\1', loc)
            rnds = parse_rounds(m.group(2))
            if qci_str not in data[scenario]:
                data[scenario][qci_str] = {}
            if city not in data[scenario][qci_str]:
                data[scenario][qci_str][city] = {}
            existing = data[scenario][qci_str][city].get(loc, set())
            data[scenario][qci_str][city][loc] = existing | rnds

    return data

# ── main ──────────────────────────────────────────────────────────────────────

qci_data = parse_vdr_5g_qci(VDR_PATH)

# Check what QCI strings were found per scenario
print("=== QCI strings found per scenario (DL 5G only) ===")
for sc in range(1, 6):
    qcis = sorted(qci_data[sc].keys())
    print(f"  S{sc} {SC_LABEL[sc]}: {qcis}")
print()

def _determine_winner(vals, margin=0.10):
    """Return winner op name, or 'tie'.

    An operator wins only if its throughput exceeds every rival by >margin.
    """
    best = max(vals, key=vals.get)
    best_val = vals[best]
    for op, v in vals.items():
        if op == best:
            continue
        if best_val <= v * (1 + margin):
            return 'tie'
    return best

# Aggregate win counts
# wins[qci_group][scenario][op] = count
# ties[qci_group][scenario]     = count
wins   = {g: {s: defaultdict(int) for s in range(1, 6)} for g in ('677', '999')}
ties   = {g: {s: 0                for s in range(1, 6)} for g in ('677', '999')}
totals = {g: {s: 0                for s in range(1, 6)} for g in ('677', '999')}

no_data_rounds = []

for scenario in range(1, 6):
    ops = list(SC_FOLDERS[scenario].keys())
    for qci_str, qci_group in QCI_LABEL_TO_GROUP.items():
        if qci_str not in qci_data[scenario]:
            continue
        for city, loc_dict in qci_data[scenario][qci_str].items():
            for loc, rnd_set in loc_dict.items():
                for rnd in sorted(rnd_set):
                    means = {}
                    for op in ops:
                        fp = find_iperf(city, op, scenario, loc, rnd, 'downlink')
                        if fp:
                            tps = extract_tp(fp)
                            if tps:
                                means[op] = np.mean(tps)
                    if len(means) >= 2:
                        totals[qci_group][scenario] += 1
                        w = _determine_winner(means)
                        if w == 'tie':
                            ties[qci_group][scenario] += 1
                        else:
                            wins[qci_group][scenario][w] += 1
                    elif len(means) == 0:
                        no_data_rounds.append(
                            (scenario, qci_group, city, loc, rnd))

if no_data_rounds:
    print(f"WARNING: {len(no_data_rounds)} rounds had no iperf data:")
    for r in no_data_rounds:
        print(f"  S{r[0]} {SC_LABEL[r[0]]} QCI-{r[1]}  {r[2]} {r[3]} R{r[4]}")
    print()

# ── print per-scenario tables ─────────────────────────────────────────────────
print("=" * 65)
print("Family C DL Win Rates: QCI 677-type vs QCI 999-type")
print("(QCI 677-type: HC=6, MVNO(s)=7 ;  QCI 999-type: all=9)")
print("=" * 65)

for g in ('677', '999'):
    print(f"\n── QCI {g}-type ─────────────────────────────────────────────────────")
    header = f"{'Scenario':<18} {'Rounds':>6}  {'HC':>8}  {'VC1':>8}  {'VC2':>8}  {'Ties':>8}"
    print(header)
    print("-" * 65)
    for sc in range(1, 6):
        n = totals[g][sc]
        if n == 0:
            print(f"  S{sc} {SC_LABEL[sc]:<14} {'—':>6}")
            continue
        w  = wins[g][sc]
        t  = ties[g][sc]
        ops_in_sc = list(SC_FOLDERS[sc].keys())
        def pct(op): return f"{w[op]}/{n} ({100*w[op]/n:.1f}%)" if op in ops_in_sc else "---"
        tie_str = f"{t}/{n} ({100*t/n:.1f}%)"
        print(f"  S{sc} {SC_LABEL[sc]:<14} {n:>6}  {pct('HC'):>14}  {pct('VC1'):>14}  {pct('VC2'):>14}  {tie_str:>14}")

# ── overall win rates (across all scenarios) ──────────────────────────────────
print()
print("=" * 65)
print("Overall win rates per QCI group (all scenarios combined)")
print("=" * 65)
for g in ('677', '999'):
    total_rounds = sum(totals[g][sc] for sc in range(1, 6))
    pc_w   = sum(wins[g][sc]['HC']  for sc in range(1, 6))
    vc1_w  = sum(wins[g][sc]['VC1'] for sc in range(1, 6))
    vc2_w  = sum(wins[g][sc]['VC2'] for sc in range(1, 6))
    ties_w = sum(ties[g][sc]        for sc in range(1, 6))
    print(f"\nQCI {g}-type  (total {total_rounds} rounds):")
    def pct2(w): return f"{w}/{total_rounds} ({100*w/total_rounds:.1f}%)" if total_rounds else "—"
    print(f"  HC  : {pct2(pc_w)}")
    print(f"  VC1 : {pct2(vc1_w)}")
    print(f"  VC2 : {pct2(vc2_w)}")
    print(f"  Ties: {pct2(ties_w)}")
