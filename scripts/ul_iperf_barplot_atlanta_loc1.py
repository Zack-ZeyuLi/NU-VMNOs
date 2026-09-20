#!/usr/bin/env python3
"""
Family A (HA / VA1 / VA2) — Atlanta Location 1, All Valid Data, UL
iperf3 throughput boxplot (all 0.5 s samples), 5 scenarios.
Style identical to generate_figures.py.

Valid rounds (from valid_data_range.txt):
  All five scenarios → Atlanta Location1 → Round 1 only
"""

import os, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ─── Paths ────────────────────────────────────────────────────────────────────
ROOT     = os.path.dirname(os.path.abspath(__file__))
RAW      = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
AT_BASE  = os.path.join(RAW, 'family_a', 'iperf', 'atlanta')
PA_DIR   = os.path.join(AT_BASE, 'HA')
VA1_DIR  = os.path.join(AT_BASE, 'VA1')
VA2_DIR  = os.path.join(AT_BASE, 'VA2')
OUT_PATH = os.path.join(ROOT, os.pardir, 'plots',
                         'A_UL_iperf_Atlanta_loc1.png')

LOC  = '1'    # location_1
RND  = 1      # only Round 1 is valid for all scenarios at this location

# ─── Shared style (mirrors generate_figures.py exactly) ──────────────────────
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

CARRIERS = {
    'HA':  {'dir': PA_DIR,  'provider': 'main',      'color': '#E24A33', 'hatch': '/////'},
    'VA1': {'dir': VA1_DIR, 'provider': 'virtual_1', 'color': '#348ABD', 'hatch': '\\\\\\\\\\'},
    'VA2': {'dir': VA2_DIR, 'provider': 'virtual_2', 'color': '#FBC15E', 'hatch': 'xxxxx'},
}

# scenario key → (label, {carrier: sc_folder})
SCENARIOS = [
    ('solo',    'Solo',       {'HA': 'M',       'VA1': 'V1',    'VA2': 'V2'}),
    ('M+V1',    'HA vs\nVA1',  {'HA': 'M+V1',    'VA1': 'M+V1'}),
    ('M+V2',    'HA vs\nVA2',  {'HA': 'M+V2',    'VA2': 'M+V2'}),
    ('V1+V2',   'VA1 vs\nVA2', {'VA1': 'V1+V2',  'VA2': 'V1+V2'}),
    ('M+V1+V2', 'HA vs VA1\nvs VA2', {'HA': 'M+V1+V2', 'VA1': 'M+V1+V2', 'VA2': 'M+V1+V2'}),
]

# ─── iperf helpers (identical logic to generate_figures.py) ──────────────────
_BITRATE_RE = re.compile(
    r'\[\s*\d+\]\s+[\d.]+-[\d.]+\s+sec\s+[\d.]+\s+[KMG]?Bytes\s+'
    r'([\d.]+)\s+([KMG]?)bits/sec')
_SUMMARY_RE = re.compile(r'0\.00-\d+\.\d+\s+sec.*(?:sender|receiver)')


def _parse_mbps(val, prefix):
    return float(val) * {'': 1e-3, 'K': 1e-3, 'M': 1.0, 'G': 1000.0}.get(prefix, 1.0)


def extract_tp(filepath):
    tps = []
    try:
        with open(filepath) as f:
            for line in f:
                if _SUMMARY_RE.search(line):
                    continue
                m = _BITRATE_RE.search(line)
                if m:
                    tps.append(_parse_mbps(m.group(1), m.group(2)))
    except Exception:
        pass
    return tps


def find_iperf_file(base_dir, loc_str, rnd, sc_folder, provider, direction):
    sc_path = os.path.join(base_dir, f'location_{loc_str}', f'round_{rnd}',
                           sc_folder, provider)
    if not os.path.isdir(sc_path):
        return None
    for item in os.listdir(sc_path):
        full = os.path.join(sc_path, item)
        if direction in item and os.path.isdir(full):
            for f in os.listdir(full):
                if f.endswith('.out') and direction in f:
                    return os.path.join(full, f)
    return None


# ─── Collect samples ──────────────────────────────────────────────────────────
# data[sc_key][carrier] = [Mbps, ...]
data = {}
for sc_key, sc_label, folders in SCENARIOS:
    data[sc_key] = {}
    for carrier, sc_folder in folders.items():
        cfg  = CARRIERS[carrier]
        fp   = find_iperf_file(cfg['dir'], LOC, RND, sc_folder,
                               cfg['provider'], 'uplink')
        samp = extract_tp(fp) if fp else []
        data[sc_key][carrier] = samp
        print(f'  {sc_label:12s} {carrier}: {len(samp)} samples'
              + (f'  mean={np.mean(samp):.1f} Mbps' if samp else '  NO DATA'))

# ─── Plot ─────────────────────────────────────────────────────────────────────
plt.rcParams.update(RC)
fig, ax = plt.subplots(figsize=(5.2, 2.4))

all_positions, all_box_data, all_colors, all_hatches = [], [], [], []
group_centers = []
x = 0.0

for sc_key, sc_label, folders in SCENARIOS:
    carriers_in = [c for c in ('HA', 'VA1', 'VA2') if c in folders]
    n = len(carriers_in)
    sc_positions = [x + i * (BOX_W + INTRA_GAP) for i in range(n)]
    center = (sc_positions[0] + sc_positions[-1]) / 2.0
    group_centers.append((center, sc_label))

    for i, carrier in enumerate(carriers_in):
        samp = data[sc_key].get(carrier, [])
        all_positions.append(sc_positions[i])
        all_box_data.append(samp if samp else [0])
        all_colors.append(CARRIERS[carrier]['color'])
        all_hatches.append(CARRIERS[carrier]['hatch'])

    x = sc_positions[-1] + BOX_W + INTER_GAP

x_max = x - INTER_GAP + BOX_W / 2

bp = ax.boxplot(
    all_box_data,
    positions=all_positions,
    widths=BOX_W,
    patch_artist=True,
    notch=False,
    whis=(5, 95),
    showfliers=True,
    medianprops=dict(color='black', linewidth=1.0),
    whiskerprops=dict(linewidth=0.6, linestyle='--'),
    capprops=dict(linewidth=0.6),
    boxprops=dict(linewidth=0.6),
    flierprops=dict(marker='o', markersize=1.5, linewidth=0.4,
                    markerfacecolor='gray', markeredgecolor='gray', alpha=0.6),
)

for patch, color, hatch in zip(bp['boxes'], all_colors, all_hatches):
    patch.set_facecolor(color)
    patch.set_alpha(0.80)
    patch.set_hatch(hatch)
    patch.set_edgecolor('black')
    patch.set_linewidth(0.6)

# Mean marker (diamond)
for pos, samp in zip(all_positions, all_box_data):
    if samp and samp != [0]:
        ax.plot(pos, np.mean(samp), marker='D', color='black',
                markersize=2.5, zorder=5, markeredgewidth=0.4)

ax.set_xticks([c for c, _ in group_centers])
ax.set_xticklabels([l for _, l in group_centers], fontsize=8)
ax.set_xlim(-0.25, x_max + 0.25)
ax.set_ylim(bottom=0)
ax.set_ylabel('UL Throughput (Mbps)')
ax.grid(axis='y', alpha=0.3, linewidth=0.4)
ax.spines['top'].set_visible(False)
ax.spines['right'].set_visible(False)

# Legend
handles = [
    mpatches.Patch(facecolor=CARRIERS[c]['color'], alpha=0.80,
                   hatch=CARRIERS[c]['hatch'], edgecolor='black',
                   linewidth=0.6, label=c)
    for c in ('HA', 'VA1', 'VA2')
]
ax.legend(handles=handles, ncol=3, loc='upper right', framealpha=0.85,
          handletextpad=0.3, columnspacing=0.5, handlelength=1.2,
          borderpad=0.4)

fig.tight_layout(pad=0.4)
os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
fig.savefig(OUT_PATH, dpi=300, bbox_inches='tight')
plt.close(fig)
print(f'\nSaved → {OUT_PATH}')
