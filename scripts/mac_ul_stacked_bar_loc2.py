#!/usr/bin/env python3
"""
Family A (HA / VA1 / VA2) — Boston Location 2, Rounds 1–4, UL
MAC-layer throughput stacked bar chart: 5G vs LTE, 5 scenarios.

Source of truth for valid rounds: raw_data/family_a/valid_data_range.txt
  → 5G-only, UL, Boston Location2: R1-R4 for all 5 scenarios (Same PCI)

Directory layout
----------------
Scenario 1 (Solo)    HA : HA/location_2/round_N/M/main/<ts>_uplink_s1/
                    VA1 : VA1/location_2/round_N/V1/virtual_1/<ts>_uplink_s2/
                    VA2 : VA2/location_2/round_N/V2/virtual_2/<ts>_uplink_s3/
Scenario 2 (HA/VA1)  HA : HA/.../M+V1/main/<ts>_uplink_s4/
                    VA1 : VA1/.../M+V1/virtual_1/<ts>_uplink_s4/
Scenario 3 (HA/VA2)  HA : HA/.../M+V2/main/<ts>_uplink_s5/
                    VA2 : VA2/.../M+V2/virtual_2/<ts>_uplink_s5/
Scenario 4 (V1/V2)  VA1 : VA1/.../V1+V2/virtual_1/<ts>_uplink_s6/
                    VA2 : VA2/.../V1+V2/virtual_2/<ts>_uplink_s6/
Scenario 5 (Simul)   HA : HA/.../M+V1+V2/main/<ts>_uplink_s7/
                    VA1 : VA1/.../M+V1+V2/virtual_1/<ts>_uplink_s7/
                    VA2 : VA2/.../M+V1+V2/virtual_2/<ts>_uplink_s7/
"""

import os, glob, csv, math
import gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT      = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
VZ_DIR    = os.path.join(RAW, 'family_a')
PA_CSV    = os.path.join(VZ_DIR, 'xcal', 'HA_BOS_MAC_Throughput.csv.gz')
VA1_CSV   = os.path.join(VZ_DIR, 'xcal', 'VA1_BOS_MAC_Throughput.csv.gz')
VA2_CSV   = os.path.join(VZ_DIR, 'xcal', 'VA2_BOS_MAC_Throughput.csv.gz')
OUT_PATH  = os.path.join(ROOT, os.pardir, 'plots',
                         'A_MAC_UL_stacked_loc2.png')

ROUNDS    = [1, 2, 3, 4]     # 5G-only valid rounds for Location2 UL

# ─── Helpers ──────────────────────────────────────────────────────────────────

def find_uplink_log(directory):
    """Return the uplink .out file inside `directory`, or None."""
    pattern = os.path.join(directory, '*_uplink_s*', '*.out')
    hits = glob.glob(pattern)
    if hits:
        return hits[0]
    return None


def get_timestamps(log_path):
    """Return (start_ms, end_ms) from an iperf .out file."""
    start_ms = end_ms = None
    if log_path is None or not os.path.exists(log_path):
        return None, None
    with open(log_path, 'r', errors='replace') as f:
        first = f.readline()
        if first.startswith('Start time:'):
            try:
                start_ms = int(first.split(':', 1)[1].strip())
            except ValueError:
                pass
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 512))
        tail = f.read()
    for line in reversed(tail.split('\n')):
        if 'End time:' in line:
            try:
                end_ms = int(line.split('End time:')[1].strip().split()[0])
                break
            except (ValueError, IndexError):
                pass
    return start_ms, end_ms


def mac_mean(csv_path, start_ms, end_ms):
    """
    Return (mean_5g_mbps, mean_lte_mbps) for the window [start_ms, end_ms].
    Only non-zero readings are averaged (following the project convention).
    """
    if start_ms is None or end_ms is None:
        return 0.0, 0.0
    t0 = math.floor(start_ms / 1000.0)
    t1 = math.ceil(end_ms   / 1000.0)
    vals5g, valslte = [], []
    COL5G = '5G KPI Total Info Layer2 MAC UL Throughput [Mbps]'
    COLLTE = 'LTE KPI MAC UL Throughput [Mbps]'
    with gzip.open(csv_path, 'rt', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            ts_str = row.get('Unix TIME_STAMP', '').strip()
            if not ts_str:
                continue
            try:
                ts = int(ts_str)
            except ValueError:
                continue
            if not (t0 <= ts <= t1):
                continue
            v5 = row.get(COL5G, '').strip()
            if v5:
                try:
                    fv = float(v5)
                    if fv > 0:
                        vals5g.append(fv)
                except ValueError:
                    pass
            vl = row.get(COLLTE, '').strip()
            if vl:
                try:
                    fv = float(vl)
                    if fv > 0:
                        valslte.append(fv)
                except ValueError:
                    pass
    return (float(np.mean(vals5g)) if vals5g else 0.0,
            float(np.mean(valslte)) if valslte else 0.0)


# ─── Collect per-scenario data ─────────────────────────────────────────────────
# Each entry: (scenario_label, {op_label: (5g, lte)})

print('=== Collecting MAC UL data for Boston Location2 ===\n')

M_LOC   = os.path.join(VZ_DIR, 'iperf', 'boston', 'HA',  'location_2')
V1_LOC  = os.path.join(VZ_DIR, 'iperf', 'boston', 'VA1', 'location_2')
V2_LOC  = os.path.join(VZ_DIR, 'iperf', 'boston', 'VA2', 'location_2')

scenarios = []


def scenario_mean(round_dirs_fn, csv_path, rounds):
    """
    round_dirs_fn(r) → path to the round folder containing the uplink log folder.
    Averages (mean_5g, mean_lte) across all supplied rounds.
    """
    r5g, rlte = [], []
    for r in rounds:
        rdir = round_dirs_fn(r)
        log  = find_uplink_log(rdir)
        if log is None:
            print(f'    [WARN] no log: {rdir}')
            continue
        t0, t1 = get_timestamps(log)
        if t0 is None or t1 is None:
            print(f'    [WARN] bad ts: {log}')
            continue
        m5g, mlte = mac_mean(csv_path, t0, t1)
        r5g.append(m5g)
        rlte.append(mlte)
        print(f'    R{r}: 5G={m5g:.2f}  LTE={mlte:.2f}  [{os.path.basename(log)}]')
    return (float(np.mean(r5g)) if r5g else 0.0,
            float(np.mean(rlte)) if rlte else 0.0)


# Scenario 1: Solo
print('\n--- Scenario 1: Solo ---')
print('  HA:')
pa = scenario_mean(lambda r: os.path.join(M_LOC,  f'round_{r}', 'M',   'main'),      PA_CSV,  ROUNDS)
print('  VA1:')
va1 = scenario_mean(lambda r: os.path.join(V1_LOC, f'round_{r}', 'V1',  'virtual_1'), VA1_CSV, ROUNDS)
print('  VA2:')
va2 = scenario_mean(lambda r: os.path.join(V2_LOC, f'round_{r}', 'V2',  'virtual_2'), VA2_CSV, ROUNDS)
scenarios.append(('Solo', {'HA': pa, 'VA1': va1, 'VA2': va2}))

# Scenario 2: HA vs VA1
print('\n--- Scenario 2: HA vs VA1 ---')
print('  HA:')
pa  = scenario_mean(lambda r: os.path.join(M_LOC,  f'round_{r}', 'M+V1', 'main'),      PA_CSV,  ROUNDS)
print('  VA1:')
va1 = scenario_mean(lambda r: os.path.join(V1_LOC, f'round_{r}', 'M+V1', 'virtual_1'), VA1_CSV, ROUNDS)
scenarios.append(('HA vs\nVA1', {'HA': pa, 'VA1': va1}))

# Scenario 3: HA vs VA2
print('\n--- Scenario 3: HA vs VA2 ---')
print('  HA:')
pa  = scenario_mean(lambda r: os.path.join(M_LOC,  f'round_{r}', 'M+V2', 'main'),      PA_CSV,  ROUNDS)
print('  VA2:')
va2 = scenario_mean(lambda r: os.path.join(V2_LOC, f'round_{r}', 'M+V2', 'virtual_2'), VA2_CSV, ROUNDS)
scenarios.append(('HA vs\nVA2', {'HA': pa, 'VA2': va2}))

# Scenario 4: VA1 vs VA2
print('\n--- Scenario 4: VA1 vs VA2 ---')
print('  VA1:')
va1 = scenario_mean(lambda r: os.path.join(V1_LOC, f'round_{r}', 'V1+V2', 'virtual_1'), VA1_CSV, ROUNDS)
print('  VA2:')
va2 = scenario_mean(lambda r: os.path.join(V2_LOC, f'round_{r}', 'V1+V2', 'virtual_2'), VA2_CSV, ROUNDS)
scenarios.append(('VA1 vs\nVA2', {'VA1': va1, 'VA2': va2}))

# Scenario 5: Simultaneous
print('\n--- Scenario 5: Simultaneous ---')
print('  HA:')
pa  = scenario_mean(lambda r: os.path.join(M_LOC,  f'round_{r}', 'M+V1+V2', 'main'),      PA_CSV,  ROUNDS)
print('  VA1:')
va1 = scenario_mean(lambda r: os.path.join(V1_LOC, f'round_{r}', 'M+V1+V2', 'virtual_1'), VA1_CSV, ROUNDS)
print('  VA2:')
va2 = scenario_mean(lambda r: os.path.join(V2_LOC, f'round_{r}', 'M+V1+V2', 'virtual_2'), VA2_CSV, ROUNDS)
scenarios.append(('HA vs\nVA1 vs VA2', {'HA': pa, 'VA1': va1, 'VA2': va2}))

# ─── Plotting — paper style ───────────────────────────────────────────────────
from matplotlib.patches import Patch

RC = {
    'font.family':           'sans-serif',
    'font.sans-serif':       ['Verdana', 'Arial', 'DejaVu Sans'],
    'font.size':             8,
    'font.weight':           'bold',
    'axes.labelsize':        9,
    'axes.labelweight':      'bold',
    'xtick.labelsize':       8,
    'ytick.labelsize':       8,
    'legend.fontsize':       10.5,
    'legend.title_fontsize': 10.5,
    'axes.linewidth':        0.8,
    'xtick.major.width':     0.6,
    'ytick.major.width':     0.6,
    'hatch.linewidth':       0.5,
    'lines.linewidth':       1.5,
    'lines.markeredgewidth': 1.0,
}
plt.rcParams.update(RC)

# Operator colors / hatches match generate_figures.py exactly
OP_COLOR = {'HA': '#E24A33', 'VA1': '#348ABD', 'VA2': '#FBC15E'}
OP_HATCH = {'HA': '/////',   'VA1': '\\\\\\\\\\', 'VA2': 'xxxxx'}
OP_ORDER  = ['HA', 'VA1', 'VA2']
OP_LABEL  = {'HA': 'HA',     'VA1': 'VA1',         'VA2': 'VA2'}

BAR_W      = 0.20   # matches BOX_W in box-plot figures
INTRA_GAP  = 0.04   # gap between bars within a group (matches box-plot INTRA_GAP)
INTER_GAP  = 0.38   # gap between groups (matches box-plot INTER_GAP)

fig, ax = plt.subplots(figsize=(5.2, 2.4))

x_ticks, x_labels = [], []
seen_ops = set()

x = 0.0
for sc_label, op_data in scenarios:
    ops_present = [op for op in OP_ORDER if op in op_data]
    n = len(ops_present)
    pos = [x + i * (BAR_W + INTRA_GAP) for i in range(n)]
    group_center = (pos[0] + pos[-1]) / 2

    for i, op in enumerate(ops_present):
        v5g, vlte = op_data[op]
        bx    = pos[i]
        col   = OP_COLOR[op]
        hatch = OP_HATCH[op]
        # 5G: solid fill; LTE: same color + hatch overlay
        ax.bar(bx, v5g,  BAR_W, color=col, linewidth=0.4, edgecolor='white')
        ax.bar(bx, vlte, BAR_W, bottom=v5g,
               color=col, hatch=hatch, linewidth=0.4,
               edgecolor='white', alpha=0.65)
        seen_ops.add(op)

    x_ticks.append(group_center)
    x_labels.append(sc_label)
    x = pos[-1] + BAR_W + INTER_GAP

x_max = x - INTER_GAP + BAR_W / 2

# ── Legend ────────────────────────────────────────────────────────────────────
# Row 1: operator identity (solid color patch)
# Row 2: pattern key — 5G solid, LTE hatched
legend_elems = []
for op in OP_ORDER:
    if op in seen_ops:
        legend_elems.append(
            Patch(facecolor=OP_COLOR[op], edgecolor='grey',
                  linewidth=0.4, label=OP_LABEL[op]))
# Separator entries for 5G / LTE pattern
legend_elems.append(
    Patch(facecolor='grey', edgecolor='grey', linewidth=0.4, label='5G'))
legend_elems.append(
    Patch(facecolor='grey', hatch='xxxxx', edgecolor='grey',
          alpha=0.65, linewidth=0.4, label='LTE'))

ax.legend(handles=legend_elems, loc='upper right',
          ncol=5, handlelength=1.0, handleheight=0.9,
          borderpad=0.4, labelspacing=0.3, columnspacing=0.8,
          framealpha=0.85, edgecolor='#cccccc')

ax.set_xticks(x_ticks)
ax.set_xticklabels(x_labels)
ax.set_ylabel('MAC UL Throughput (Mbps)')
ax.set_xlim(-0.25, x_max + 0.25)
ax.set_ylim(0, None)
ax.yaxis.grid(True, linestyle='--', linewidth=0.4, alpha=0.6)
ax.set_axisbelow(True)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

fig.tight_layout(pad=0.4)
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
fig.savefig(OUT_PATH, dpi=300, bbox_inches='tight')
print(f'\nSaved → {OUT_PATH}')
