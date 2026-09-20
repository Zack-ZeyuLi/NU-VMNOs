#!/usr/bin/env python3
"""
Generate two stacked-bar MAC-layer breakdown charts for Family C:
  1. C_MAC_DL_stacked_loc3.png  — DL Boston Location_3 (all 5G-only rounds)
  2. C_MAC_UL_stacked_overall.png — UL all Boston locations (all 5G-only rounds)

Bar structure: 5G NR (solid fill) + LTE (hatched, only VC1/VC1 has LTE column)
Data: MAC CSV sliced by iperf start/end timestamps; average per scenario.
"""

import os, re
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT   = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
TM_DIR = os.path.join(RAW, 'family_c')

# ── Colours & style ───────────────────────────────────────────────────────────
C_PC  = '#E24A33'   # red-orange
C_VC1 = '#348ABD'   # blue
C_VC2 = '#FBC15E'   # gold

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

SC_LABELS = {1: 'Solo', 2: 'HC\nvs VC1', 3: 'HC\nvs VC2', 4: 'VC1\nvs VC2', 5: 'HC vs\nVC1 vs VC2'}

# ── Directory config ──────────────────────────────────────────────────────────
DL_BASES = {
    'HC':  os.path.join(TM_DIR, 'iperf', 'boston', 'HC'),
    'VC1': os.path.join(TM_DIR, 'iperf', 'boston', 'VC1'),
    'VC2': os.path.join(TM_DIR, 'iperf', 'boston', 'VC2'),
}
UL_BASES = {
    'HC':  os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'HC'),
    'VC1': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC1'),
    'VC2': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC2'),
}
PROVIDER = {'HC': 'main', 'VC1': 'virtual_1', 'VC2': 'virtual_2'}
SC_FOLDERS = {
    1: {'HC': 'M',       'VC1': 'V1',      'VC2': 'V2'},
    2: {'HC': 'M+V1',    'VC1': 'M+V1'},
    3: {'HC': 'M+V2',                       'VC2': 'M+V2'},
    4:                   {'VC1': 'V1+V2',   'VC2': 'V1+V2'},
    5: {'HC': 'M+V1+V2', 'VC1': 'M+V1+V2', 'VC2': 'M+V1+V2'},
}

# MAC CSV columns: (5G col, LTE col or None)
DL_MAC_COLS = {
    'HC':  ('HC 5G MAC DL Throughput [Mbps]',    None),
    'VC1': ('VC1 5G MAC DL Throughput [Mbps]',        'VC1 LTE MAC DL Throughput [Mbps]'),
    'VC2': ('VC2 5G DL Throughput [Mbps]',           None),
}
UL_MAC_COLS = {
    'HC':  ('HC 5G MAC UL Throughput [Mbps]',    None),
    'VC1': ('VC1 5G MAC UL Throughput [Mbps]',        'VC1 LTE MAC UL Throughput [Mbps]'),
    'VC2': ('VC2 5G MAC UL Throughput [Mbps]',       None),
}

# ── Load MAC CSVs ─────────────────────────────────────────────────────────────
print('Loading MAC CSVs ...')
DL_MAC = pd.read_csv(os.path.join(TM_DIR, 'xcal', 'DL_BOS_MAC_TP.csv.gz'))
UL_MAC = pd.read_csv(os.path.join(TM_DIR, 'xcal', 'UL_BOS_MAC_TP.csv.gz'))
DL_MAC['Unix TIME_STAMP'] = pd.to_numeric(DL_MAC['Unix TIME_STAMP'], errors='coerce')
UL_MAC['Unix TIME_STAMP'] = pd.to_numeric(UL_MAC['Unix TIME_STAMP'], errors='coerce')
print(f'  DL MAC: {len(DL_MAC)} rows  ts=[{DL_MAC["Unix TIME_STAMP"].min():.0f}, {DL_MAC["Unix TIME_STAMP"].max():.0f}]')
print(f'  UL MAC: {len(UL_MAC)} rows  ts=[{UL_MAC["Unix TIME_STAMP"].min():.0f}, {UL_MAC["Unix TIME_STAMP"].max():.0f}]')

# ── iperf timestamp extraction ────────────────────────────────────────────────
_TS_START = re.compile(r'Start time:\s*(\d+)')
_TS_END   = re.compile(r'End time:\s*(\d+)')

def get_iperf_window_ms(fp):
    """Return (start_ms, end_ms) from iperf .out file, or None."""
    try:
        with open(fp) as f:
            txt = f.read()
        ms = _TS_START.search(txt)
        me = _TS_END.search(txt)
        if ms and me:
            return int(ms.group(1)), int(me.group(1))
    except Exception:
        pass
    return None

def find_iperf_file(base, loc_key, rnd, sc_folder, provider, direction):
    loc_fol = loc_key.lower()
    path = os.path.join(base, loc_fol, f'round_{rnd}', sc_folder, provider)
    if not os.path.isdir(path):
        return None
    for item in sorted(os.listdir(path)):
        full = os.path.join(path, item)
        if direction in item and os.path.isdir(full):
            for f in os.listdir(full):
                if f.endswith('.out') and direction in f:
                    return os.path.join(full, f)
    return None

# ── MAC query ─────────────────────────────────────────────────────────────────
def mac_avg_in_window(mac_df, start_ms, end_ms, col_5g, col_lte, ts_offset_s=0):
    """Average 5G and LTE MAC throughput (Mbps) in [start_ms, end_ms] (ms → seconds).
    ts_offset_s: subtract this many seconds from the iperf window before querying
    (use -3600 for UL where MAC CSV timestamps lag iperf by 1 hour)."""
    t0 = start_ms / 1000.0 + ts_offset_s
    t1 = end_ms   / 1000.0 + ts_offset_s
    win = mac_df[(mac_df['Unix TIME_STAMP'] >= t0) & (mac_df['Unix TIME_STAMP'] <= t1)]
    if win.empty:
        return None, None
    avg_5g = win[col_5g].mean() if col_5g else 0.0
    avg_lte = win[col_lte].mean() if col_lte and col_lte in win.columns else 0.0
    return float(avg_5g) if not np.isnan(avg_5g) else 0.0, \
           float(avg_lte) if not np.isnan(avg_lte) else 0.0

# ── Parse valid_data_range.txt for 5G-only rounds (union across QCI+PCI) ──────
def parse_rounds(txt):
    return set(int(x) for x in re.findall(r'Round(\d+)', txt))

def parse_5g_rounds(filepath):
    """
    Returns fiveg[direction][scenario][city][loc] = set(rounds)
    (union across all QCI and PCI sub-conditions)
    """
    def make():
        return {d: {s: {'Boston': {}, 'Philadelphia': {}} for s in range(1,6)}
                for d in ('downlink', 'uplink')}
    fiveg = make()

    section = None; direction = None; scenario = None; city = None

    with open(filepath) as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith('##'):
                continue
            if s.lower().startswith('all valid data'):
                section = 'all'; continue
            if s.lower().startswith('5g only'):
                section = '5g'; continue
            if s.lower() == 'downlink:':
                direction = 'downlink'; continue
            if s.lower() == 'uplink:':
                direction = 'uplink'; continue
            if not (section == '5g' and direction):
                continue
            m = re.match(r'Senario\s+(\d+)', s, re.I)
            if m:
                scenario = int(m.group(1)); city = None; continue
            if s.rstrip(':').lower() == 'boston':
                city = 'Boston'; continue
            if s.rstrip(':').lower() == 'philadelphia':
                city = 'Philadelphia'; continue
            if re.match(r'QCI\s+\d+', s, re.I):
                continue
            if s.lower().startswith('same pci') or s.lower().startswith('diff pci'):
                continue
            m = re.match(r'(Location[\w]+)\s*:\s*(.+)', s, re.I)
            if m and scenario and city:
                loc = re.sub(r'^Location(?!_)(\d)', r'Location_\1', m.group(1))
                rnds = parse_rounds(m.group(2))
                existing = fiveg[direction][scenario][city].get(loc, set())
                fiveg[direction][scenario][city][loc] = existing | rnds
    return fiveg

VDR = os.path.join(TM_DIR, 'valid_data_range.txt')
fiveg = parse_5g_rounds(VDR)

# ── Collect MAC data per scenario ─────────────────────────────────────────────

def collect_mac(direction, city, loc_filter=None):
    """
    For each scenario, average MAC 5G+LTE over all 5G-only rounds in city.
    loc_filter: set of loc strings to include, or None for all.
    Returns:
      sc_data[scenario][op] = {'nr': Mbps, 'lte': Mbps}
    """
    bases    = DL_BASES    if direction == 'downlink' else UL_BASES
    mac_df   = DL_MAC      if direction == 'downlink' else UL_MAC
    mac_cols = DL_MAC_COLS if direction == 'downlink' else UL_MAC_COLS
    # UL MAC CSV timestamps lag iperf timestamps by exactly 1 hour
    ts_offset_s = 0 if direction == 'downlink' else -3600

    sc_data = {sc: {} for sc in range(1, 6)}

    for sc in range(1, 6):
        ops = list(SC_FOLDERS[sc].keys())
        accum = {op: {'nr': [], 'lte': []} for op in ops}

        locs_rounds = fiveg[direction][sc][city]
        if not locs_rounds:
            continue

        for loc, rnd_set in locs_rounds.items():
            if loc_filter and loc not in loc_filter:
                continue
            for rnd in sorted(rnd_set):
                # For S1 Solo: each op has its own time window
                # For S2-S5: all ops run together; use first available window
                if sc == 1:
                    for op in ops:
                        fp = find_iperf_file(bases[op], loc, rnd,
                                             SC_FOLDERS[sc][op], PROVIDER[op],
                                             direction)
                        win = get_iperf_window_ms(fp) if fp else None
                        if not win:
                            continue
                        c5g, clte = mac_cols[op]
                        nr, lte = mac_avg_in_window(mac_df, win[0], win[1], c5g, clte, ts_offset_s)
                        if nr is not None:
                            accum[op]['nr'].append(nr)
                            accum[op]['lte'].append(lte)
                else:
                    # Get one time window (from first op in scenario)
                    win = None
                    for op in ops:
                        fp = find_iperf_file(bases[op], loc, rnd,
                                             SC_FOLDERS[sc][op], PROVIDER[op],
                                             direction)
                        win = get_iperf_window_ms(fp) if fp else None
                        if win:
                            break
                    if not win:
                        continue
                    for op in ops:
                        c5g, clte = mac_cols[op]
                        nr, lte = mac_avg_in_window(mac_df, win[0], win[1], c5g, clte, ts_offset_s)
                        if nr is not None:
                            accum[op]['nr'].append(nr)
                            accum[op]['lte'].append(lte)

        for op in ops:
            if accum[op]['nr']:
                sc_data[sc][op] = {
                    'nr':  np.mean(accum[op]['nr']),
                    'lte': np.mean(accum[op]['lte']),
                }
    return sc_data

print('Collecting DL MAC data for Boston Location_3 ...')
dl_loc3 = collect_mac('downlink', 'Boston', loc_filter={'Location_3'})

print('Collecting UL MAC data for Boston (all locations) ...')
ul_all  = collect_mac('uplink',   'Boston', loc_filter=None)

# ── Plotting ──────────────────────────────────────────────────────────────────

OP_COLOR = {'HC': C_PC,    'VC1': C_VC1,          'VC2': C_VC2}
OP_HATCH = {'HC': '/////', 'VC1': '\\\\\\\\\\',   'VC2': 'xxxxx'}
OP_ORDER = ['HC', 'VC1', 'VC2']

BAR_W      = 0.20   # matches BOX_W in box-plot figures
INTRA_GAP  = 0.04   # gap between bars within a group (matches box-plot INTRA_GAP)
INTER_GAP  = 0.38   # gap between groups (matches box-plot INTER_GAP)


def draw_mac_stacked(sc_data, ylabel, out_path):
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(figsize=(5.2, 2.4))

    x_ticks, x_labels = [], []
    seen_ops = set()
    x = 0.0

    for sc in range(1, 6):
        data = sc_data.get(sc, {})
        ops  = [op for op in OP_ORDER if op in SC_FOLDERS[sc] and op in data]
        if not ops:
            # advance by one empty group slot to preserve alignment
            x += BAR_W + INTER_GAP
            continue

        n = len(ops)
        pos = [x + i * (BAR_W + INTRA_GAP) for i in range(n)]
        group_center = (pos[0] + pos[-1]) / 2

        for i, op in enumerate(ops):
            nr  = data[op]['nr']
            lte = data[op]['lte']
            col   = OP_COLOR[op]
            hatch = OP_HATCH[op]
            bx    = pos[i]
            # 5G NR: solid fill
            ax.bar(bx, nr,  BAR_W, color=col, linewidth=0.4, edgecolor='white')
            # LTE: same color + per-operator hatch, alpha 0.65
            if lte and lte > 0.1:
                ax.bar(bx, lte, BAR_W, bottom=nr,
                       color=col, hatch=hatch, linewidth=0.4,
                       edgecolor='white', alpha=0.65)
            seen_ops.add(op)

        x_ticks.append(group_center)
        x_labels.append(SC_LABELS[sc])
        x = pos[-1] + BAR_W + INTER_GAP

    x_max = x - INTER_GAP + BAR_W / 2

    # ── Legend ────────────────────────────────────────────────────────────────
    legend_elems = []
    for op in OP_ORDER:
        if op in seen_ops:
            legend_elems.append(
                mpatches.Patch(facecolor=OP_COLOR[op], edgecolor='grey',
                               linewidth=0.4, label=op))
    legend_elems.append(
        mpatches.Patch(facecolor='grey', edgecolor='grey', linewidth=0.4, label='5G NR'))
    legend_elems.append(
        mpatches.Patch(facecolor='grey', hatch='xxxxx', edgecolor='grey',
                       alpha=0.65, linewidth=0.4, label='LTE'))

    ax.legend(handles=legend_elems, loc='upper right',
              ncol=5, handlelength=1.0, handleheight=0.9,
              borderpad=0.4, labelspacing=0.3, columnspacing=0.8,
              framealpha=0.85, edgecolor='#cccccc')

    ax.set_xticks(x_ticks)
    ax.set_xticklabels(x_labels)
    ax.set_ylabel(ylabel)
    ax.set_xlim(-0.25, x_max + 0.25)
    ax.set_ylim(0, None)
    ax.yaxis.grid(True, linestyle='--', linewidth=0.4, alpha=0.6)
    ax.set_axisbelow(True)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    fig.tight_layout(pad=0.4)
    fig.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {out_path}')


# ── Print summary tables ──────────────────────────────────────────────────────

def print_table(sc_data, title):
    print(f'\n=== {title} ===')
    print(f"{'Scenario':<16} {'Op':<5} {'5G NR (Mbps)':>14} {'LTE (Mbps)':>12} {'Total':>10}")
    print('-' * 62)
    for sc in range(1, 6):
        data = sc_data.get(sc, {})
        for op in ['HC', 'VC1', 'VC2']:
            if op not in data:
                continue
            nr  = data[op]['nr']
            lte = data[op]['lte']
            print(f"  S{sc} {SC_LABELS[sc].replace(chr(10), ' '):<13} {op:<5} "
                  f"{nr:>14.2f} {lte:>12.2f} {nr+lte:>10.2f}")

print_table(dl_loc3, 'DL Boston Location_3 — MAC averages per scenario (5G-only rounds)')
print_table(ul_all,  'UL Boston All Locations — MAC averages per scenario (5G-only rounds)')

# ── Draw and save ─────────────────────────────────────────────────────────────
OUT_DIR = os.path.join(ROOT, os.pardir, 'plots')
os.makedirs(OUT_DIR, exist_ok=True)

print('\nDrawing charts ...')
draw_mac_stacked(
    dl_loc3,
    'MAC DL Throughput (Mbps)',
    os.path.join(OUT_DIR, 'C_MAC_DL_stacked_loc3.png'),
)
draw_mac_stacked(
    ul_all,
    'MAC UL Throughput (Mbps)',
    os.path.join(OUT_DIR, 'C_MAC_UL_stacked_overall.png'),
)
print('Done.')
