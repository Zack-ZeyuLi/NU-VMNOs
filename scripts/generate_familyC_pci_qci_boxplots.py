#!/usr/bin/env python3
"""
Family C (Family C) throughput boxplots conditioned on QCI 677-type AND PCI context.

Produces four figures saved to Paper/figures/:
  C_5G_PCI_QCI677_Same_DL.png  —  677-type DL, Same-PCI
  C_5G_PCI_QCI677_Diff_DL.png  —  677-type DL, Diff-PCI
  C_5G_PCI_QCI677_Same_UL.png  —  677-type UL, Same-PCI
  C_5G_PCI_QCI677_Diff_UL.png  —  677-type UL, Diff-PCI

Each figure is a single-panel boxplot following generate_pci_boxplots.py style.
"""

import os
import re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import OrderedDict

ROOT    = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
TM_DIR  = os.path.join(RAW, 'family_c')
OUT_DIR = os.path.join(ROOT, os.pardir, 'plots')
os.makedirs(OUT_DIR, exist_ok=True)

# ── Shared style (matches generate_pci_boxplots.py exactly) ──────
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
BOX_W     = 0.20
INTRA_GAP = 0.04
INTER_GAP = 0.38

# ── iperf helpers ─────────────────────────────────────────────────
_BITRATE_RE = re.compile(
    r'\[\s*\d+\]\s+[\d.]+-[\d.]+\s+sec\s+[\d.]+\s+[KMG]?Bytes\s+'
    r'([\d.]+)\s+([KMG]?)bits/sec')
_SUMMARY_RE = re.compile(r'0\.00-\d+\.\d+\s+sec.*(?:sender|receiver)')

def _mbps(val, pfx):
    return float(val) * {'': 1e-3, 'K': 1e-3, 'M': 1.0, 'G': 1e3}.get(pfx, 1.0)

def extract_tp(path):
    tps = []
    try:
        with open(path) as f:
            for ln in f:
                if _SUMMARY_RE.search(ln): continue
                m = _BITRATE_RE.search(ln)
                if m: tps.append(_mbps(m.group(1), m.group(2)))
    except Exception:
        pass
    return tps

def find_iperf(base, loc, rnd, sc_folder, provider, direction):
    sc_path = os.path.join(base, f'location_{loc}', f'round_{rnd}', sc_folder, provider)
    if not os.path.isdir(sc_path):
        return None
    for item in os.listdir(sc_path):
        full = os.path.join(sc_path, item)
        if direction in item and os.path.isdir(full):
            for f in os.listdir(full):
                if f.endswith('.out') and direction in f:
                    return os.path.join(full, f)
    return None

def get_samples(base, loc, rnd, sc_folder, provider, direction):
    fp = find_iperf(base, str(loc), rnd, sc_folder, provider, direction)
    return extract_tp(fp) if fp else []

# ── Carrier / scenario config ─────────────────────────────────────
TM_CARRIERS = OrderedDict([
    ('HC',  {'dl_boston': os.path.join(TM_DIR, 'iperf', 'boston', 'HC'),
             'ul_boston': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'HC'),
             'philly':    os.path.join(TM_DIR, 'iperf', 'philadelphia', 'HC'),
             'provider':  'main',      'color': '#E24A33', 'hatch': '/////'}),
    ('VC1', {'dl_boston': os.path.join(TM_DIR, 'iperf', 'boston', 'VC1'),
             'ul_boston': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC1'),
             'philly':    os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC1'),
             'provider':  'virtual_1', 'color': '#348ABD', 'hatch': '\\\\\\\\\\'}),
    ('VC2', {'dl_boston': os.path.join(TM_DIR, 'iperf', 'boston', 'VC2'),
             'ul_boston': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC2'),
             'philly':    os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC2'),
             'provider':  'virtual_2', 'color': '#FBC15E', 'hatch': 'xxxxx'}),
])

TM_SCENARIOS = OrderedDict([
    ('solo',    {'folders': OrderedDict([('HC','M'),  ('VC1','V1'), ('VC2','V2')]),
                 'label': 'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HC','M+V1'), ('VC1','M+V1')]),
                 'label': 'HC vs\nVC1'}),
    ('M+V2',    {'folders': OrderedDict([('HC','M+V2'), ('VC2','M+V2')]),
                 'label': 'HC vs\nVC2'}),
    ('V1+V2',   {'folders': OrderedDict([('VC1','V1+V2'), ('VC2','V1+V2')]),
                 'label': 'VC1 vs\nVC2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HC','M+V1+V2'), ('VC1','M+V1+V2'), ('VC2','M+V1+V2')]),
                 'label': 'HC vs VC1\nvs VC2'}),
])

_SC_MAP = {1: 'solo', 2: 'M+V1', 3: 'M+V2', 4: 'V1+V2', 5: 'M+V1+V2'}

# ── Parser: extracts QCI 677-type × PCI × direction × scenario ────
def _parse_rounds(s):
    return sorted({int(m.group(1)) for m in re.finditer(r'Round(\d+)', s)})

def parse_tm_qci677_pci(filepath):
    """
    Parse both Downlink and Uplink sections from valid_data_range.txt (5G only).
    Only keeps QCI 677-type entries (labels without '9').

    Returns:
        result[direction][pci_side][sc_key][city_key][loc_str] = [rounds]

    direction : 'downlink' | 'uplink'
    pci_side  : 'same' | 'diff'
    sc_key    : 'solo' | 'M+V1' | 'M+V2' | 'V1+V2' | 'M+V1+V2'
    city_key  : 'dl_boston'/'ul_boston' | 'philly'
    loc_str   : e.g. '1_1', '3', '1'
    """
    def _empty():
        return {sc: {} for sc in _SC_MAP.values()}

    result = {
        'downlink': {'same': _empty(), 'diff': _empty()},
        'uplink':   {'same': _empty(), 'diff': _empty()},
    }

    with open(filepath) as f:
        lines = f.readlines()

    in_5g = False
    direction = sc = city = qci = pci = None

    for raw in lines:
        s = raw.strip()
        if not s or s.startswith('##'):
            continue

        if s.startswith('5G only:'):
            in_5g = True
            continue
        if not in_5g:
            continue

        if s.startswith('Downlink:'):
            direction = 'downlink'
            sc = city = qci = pci = None
            continue
        if s.startswith('Uplink:'):
            direction = 'uplink'
            sc = city = qci = pci = None
            continue
        if direction is None:
            continue

        # ── Scenario ──────────────────────────────────────────
        m = re.match(r'Senario\s+(\d+):', s)
        if m:
            sc = _SC_MAP.get(int(m.group(1)))
            city = qci = pci = None
            continue
        if sc is None:
            continue

        # ── City ──────────────────────────────────────────────
        cm = re.match(r'(Boston|Philadelphia):', s, re.I)
        if cm:
            name = cm.group(1).strip().lower()
            if name == 'boston':
                city = 'dl_boston' if direction == 'downlink' else 'ul_boston'
            else:
                city = 'philly'
            qci = pci = None
            continue
        if city is None:
            continue

        # ── QCI label ─────────────────────────────────────────
        qm = re.match(r'QCI\s+(\d+)', s)
        if qm:
            digits = qm.group(1)
            # Only keep 677-type (no '9' in digits)
            if '9' in digits:
                qci = None   # skip 999-type
            else:
                qci = 'qci677'
            pci = None
            continue
        if qci is None:
            continue

        # ── PCI side ──────────────────────────────────────────
        if s.startswith('Same PCI:'):
            pci = 'same'
            continue
        if s.startswith('Diff PCI:'):
            pci = 'diff'
            continue
        if pci is None:
            continue

        # ── Location / round line ─────────────────────────────
        lm = re.match(r'(Location[\w_]*)\s*:\s*(.+)', s)
        if lm:
            raw_loc = lm.group(1).strip()
            if raw_loc.startswith('Location_'):
                loc = raw_loc[9:]
            elif raw_loc.startswith('Location'):
                loc = raw_loc[8:]
            else:
                loc = raw_loc
            rnds = _parse_rounds(lm.group(2))
            d = result[direction][pci][sc].setdefault(city, {})
            d[loc] = sorted(set(d.get(loc, []) + rnds))

    return result

# ── Data collection ───────────────────────────────────────────────
def collect_data(direction, scenarios, carriers, valid_ranges):
    """
    valid_ranges : {sc_key: {city_key: {loc_str: [rounds]}}}
    Returns      : {sc_key: {carrier: [tp_samples]}}
    """
    cities = ('dl_boston', 'philly') if direction == 'downlink' else ('ul_boston', 'philly')
    result = {sc: {c: [] for c in cfg['folders']}
              for sc, cfg in scenarios.items()}
    for sc, sc_cfg in scenarios.items():
        for city in cities:
            loc_rnds = valid_ranges.get(sc, {}).get(city, {})
            for loc in sorted(loc_rnds.keys(), key=str):
                for rnd in loc_rnds[loc]:
                    for carrier, folder in sc_cfg['folders'].items():
                        cfg = carriers[carrier]
                        result[sc][carrier].extend(
                            get_samples(cfg[city], loc, rnd, folder,
                                        cfg['provider'], direction))
    return result

# ── Boxplot drawing ───────────────────────────────────────────────
def draw_panel(ax, scenarios, carriers, carrier_data, ylabel, show_legend,
               panel_label=None):
    all_positions, all_data, all_colors, all_hatches = [], [], [], []
    group_centers = []
    x = 0.0

    for sc, sc_cfg in scenarios.items():
        carriers_in = [c for c in sc_cfg['folders'] if c in carriers]
        n = len(carriers_in)
        pos = [x + i * (BOX_W + INTRA_GAP) for i in range(n)]
        group_centers.append(((pos[0] + pos[-1]) / 2, sc_cfg['label']))

        for i, carrier in enumerate(carriers_in):
            vals = [v for v in carrier_data.get(sc, {}).get(carrier, []) if v is not None]
            all_positions.append(pos[i])
            all_data.append(vals if vals else [0])
            all_colors.append(carriers[carrier]['color'])
            all_hatches.append(carriers[carrier]['hatch'])

        x = pos[-1] + BOX_W + INTER_GAP

    x_max = x - INTER_GAP + BOX_W / 2

    bp = ax.boxplot(
        all_data, positions=all_positions, widths=BOX_W,
        patch_artist=True, notch=False, whis=(5, 95), showfliers=True,
        medianprops=dict(color='black', linewidth=1.0),
        whiskerprops=dict(linewidth=0.6, linestyle='--'),
        capprops=dict(linewidth=0.6),
        boxprops=dict(linewidth=0.6),
        flierprops=dict(marker='o', markersize=1.5, linewidth=0.4,
                        markerfacecolor='gray', markeredgecolor='gray', alpha=0.6),
    )
    for patch, col, hatch in zip(bp['boxes'], all_colors, all_hatches):
        patch.set_facecolor(col)
        patch.set_alpha(0.80)
        patch.set_hatch(hatch)
        patch.set_edgecolor('black')
        patch.set_linewidth(0.6)

    for pos, vals in zip(all_positions, all_data):
        if vals and vals != [0]:
            ax.plot(pos, np.mean(vals), marker='D', color='black',
                    markersize=2.5, zorder=5, markeredgewidth=0.4)

    ax.set_xticks([c for c, _ in group_centers])
    ax.set_xticklabels([l for _, l in group_centers], fontsize=8)
    ax.set_xlim(-0.25, x_max + 0.25)
    ax.set_ylim(bottom=0)
    ax.set_ylabel(ylabel)
    ax.grid(axis='y', alpha=0.3, linewidth=0.4)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    if panel_label:
        ax.text(0.03, 0.97, panel_label, transform=ax.transAxes,
                fontsize=9.5, va='top', fontstyle='italic')

    if show_legend:
        handles = [mpatches.Patch(facecolor=carriers[c]['color'], alpha=0.80,
                                  hatch=carriers[c]['hatch'], edgecolor='black',
                                  linewidth=0.6, label=c)
                   for c in carriers]
        ax.legend(handles=handles, ncol=len(carriers), loc='upper right',
                  framealpha=0.85, handletextpad=0.3, columnspacing=0.5,
                  handlelength=1.2, borderpad=0.4)

def make_single_figure(fname, scenarios, carriers, data, direction_label):
    """Save one single-panel boxplot figure."""
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(1, 1, figsize=(5.2, 2.4))

    ylabel = f'{direction_label} Throughput (Mbps)'
    draw_panel(ax, scenarios, carriers, data, ylabel, show_legend=True,
               panel_label=None)

    fig.tight_layout(pad=0.4)
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {path}')

# ── Main ─────────────────────────────────────────────────────────
print('Parsing Family C/valid_data_range.txt …')
qci_pci = parse_tm_qci677_pci(os.path.join(TM_DIR, 'valid_data_range.txt'))

for direction, dlabel in [('downlink', 'DL'), ('uplink', 'UL')]:
    print(f'\n── QCI 677-type {dlabel} ────────────────────────────────')
    same_ranges = qci_pci[direction]['same']
    diff_ranges  = qci_pci[direction]['diff']

    same_data = collect_data(direction, TM_SCENARIOS, TM_CARRIERS, same_ranges)
    diff_data  = collect_data(direction, TM_SCENARIOS, TM_CARRIERS, diff_ranges)

    # Print sample counts for verification
    for sc, sc_cfg in TM_SCENARIOS.items():
        label = sc_cfg['label']
        s_counts = {c: len(same_data[sc].get(c, [])) for c in sc_cfg['folders']}
        d_counts = {c: len(diff_data[sc].get(c, []))  for c in sc_cfg['folders']}
        print(f'  Same {label:>18s}: {s_counts}')
        print(f'  Diff {label:>18s}: {d_counts}')

    make_single_figure(f'C_5G_PCI_QCI677_Same_{dlabel}.png',
                       TM_SCENARIOS, TM_CARRIERS, same_data, dlabel)
    make_single_figure(f'C_5G_PCI_QCI677_Diff_{dlabel}.png',
                       TM_SCENARIOS, TM_CARRIERS, diff_data, dlabel)

print('\nDone.')
