#!/usr/bin/env python3
"""
Per-city throughput boxplots (5 scenarios) for all 3 operator families.

Data used:
  Family A (VZ): all-valid data  — cities: Boston, Atlanta
  Family B (AT): all-valid data  — cities: Boston, Atlanta
  Family C (TM): 5G-only QCI677  — cities: Boston, Philadelphia

Produces 12 single-panel figures:
  {A|B}_City_{Boston|Atlanta}_{DL|UL}.png
  C_City_{Boston|Philadelphia}_{DL|UL}.png

Output: Paper/figures/
"""

import os, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import OrderedDict

ROOT    = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
VZ_DIR  = os.path.join(RAW, 'family_a')
AT_DIR  = os.path.join(RAW, 'family_b')
TM_DIR  = os.path.join(RAW, 'family_c')
OUT_DIR = os.path.join(ROOT, os.pardir, 'plots')
os.makedirs(OUT_DIR, exist_ok=True)

# ── Shared style ──────────────────────────────────────────────────
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
    sc_path = os.path.join(base, f'location_{loc}', f'round_{rnd}',
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

def get_samples(base, loc, rnd, sc_folder, provider, direction):
    fp = find_iperf(base, str(loc), rnd, sc_folder, provider, direction)
    return extract_tp(fp) if fp else []

# ── valid_data_range.txt parser ───────────────────────────────────
_SC_MAP = {1: 'solo', 2: 'M+V1', 3: 'M+V2', 4: 'V1+V2', 5: 'M+V1+V2'}
_LOW_QCI  = {'67', '77', '677'}

def _parse_rounds(s):
    return sorted({int(m.group(1)) for m in re.finditer(r'Round(\d+)', s)})

def _loc_int(label):
    m = re.search(r'(\d+)', label.replace('Location', ''))
    return int(m.group(1)) if m else label

def _loc_str(label):
    s = label.strip()
    if s.startswith('Location_'): return s[9:]
    if s.startswith('Location'):  return s[8:]
    return s

def parse_ranges(filepath, family='vz'):
    """
    Parse all_valid and qci677 sections.
    Returns:
      {
        'all_valid': {'downlink': {sc: {city: {loc: [rounds]}}}, 'uplink': ...},
        'qci677':    {'downlink': {sc: {city: {loc: [rounds]}}}, 'uplink': ...},
      }
    city keys:
      vz/at: 'boston', 'atlanta'
      tm:    'dl_boston'/'ul_boston', 'philly'
    """
    loc_fn = _loc_str if family == 'tm' else _loc_int

    def city_key(name, direction):
        c = name.strip().lower()
        if family == 'tm':
            if c == 'boston':
                return 'dl_boston' if direction == 'downlink' else 'ul_boston'
            if c == 'philadelphia':
                return 'philly'
        return c

    def _empty():
        return {sc: {} for sc in _SC_MAP.values()}

    res = {
        'all_valid': {'downlink': _empty(), 'uplink': _empty()},
    }
    stg677 = {}   # (direction, sc, city, pci) → {loc: [rounds]}

    sec = direction = sc = city = pci = qci_cat = None

    with open(filepath) as f:
        lines = f.readlines()

    for raw in lines:
        s = raw.strip()
        if not s or s.startswith('##'):
            continue
        indent = len(raw) - len(raw.lstrip())

        if s.startswith('All valid data:'):
            sec = 'all_valid'; continue
        if s.startswith('5G only:'):
            sec = '5g_only'; continue
        if sec is None:
            continue

        if indent == 0:
            if s.startswith('Downlink:'):
                direction = 'downlink'; sc = city = pci = qci_cat = None; continue
            if s.startswith('Uplink:'):
                direction = 'uplink'; sc = city = pci = qci_cat = None; continue
        if direction is None:
            continue

        m = re.match(r'Senario\s+(\d+):', s)
        if m:
            sc = _SC_MAP.get(int(m.group(1)))
            city = pci = qci_cat = None; continue
        if sc is None:
            continue

        cm = re.match(r'(Boston|Atlanta|Philadelphia):', s, re.I)
        if cm:
            city = city_key(cm.group(1), direction)
            pci = qci_cat = None; continue
        if city is None:
            continue

        if sec == '5g_only':
            qm = re.match(r'QCI\s*(\d+)', s)
            if qm:
                qci_cat = 'low' if qm.group(1) in _LOW_QCI else 'other'
                pci = None; continue
            if s.startswith('Same PCI:'):
                pci = 'same'; continue
            if s.startswith('Diff PCI:'):
                pci = 'diff'; continue

        lm = re.match(r'(Location\w*)\s*:\s*(.+)', s)
        if lm:
            loc   = loc_fn(lm.group(1))
            rnds  = _parse_rounds(lm.group(2))
            if sec == 'all_valid':
                res['all_valid'][direction][sc].setdefault(city, {})[loc] = rnds
            elif sec == '5g_only' and pci is not None and qci_cat == 'low':
                k = (direction, sc, city, pci)
                d = stg677.setdefault(k, {})
                d[loc] = sorted(set(d.get(loc, []) + rnds))

    # Flush qci677 (merge same+diff PCI)
    if stg677:
        res['qci677'] = {'downlink': _empty(), 'uplink': _empty()}
        for (drct, sc2, c, _p), lr in stg677.items():
            for loc, rnds in lr.items():
                t = res['qci677'][drct][sc2].setdefault(c, {})
                t[loc] = sorted(set(t.get(loc, []) + rnds))

    return res

# ── Carrier / scenario configs ────────────────────────────────────
VZ_CARRIERS = OrderedDict([
    ('HA',  {'boston': os.path.join(VZ_DIR, 'iperf', 'boston', 'HA'),
             'atlanta': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'HA'),
             'provider': 'main',      'color': '#E24A33', 'hatch': '/////'}),
    ('VA1', {'boston': os.path.join(VZ_DIR, 'iperf', 'boston', 'VA1'),
             'atlanta': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'VA1'),
             'provider': 'virtual_1', 'color': '#348ABD', 'hatch': '\\\\\\\\\\'}),
    ('VA2', {'boston': os.path.join(VZ_DIR, 'iperf', 'boston', 'VA2'),
             'atlanta': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'VA2'),
             'provider': 'virtual_2', 'color': '#FBC15E', 'hatch': 'xxxxx'}),
])
VZ_SCENARIOS = OrderedDict([
    ('solo',    {'folders': OrderedDict([('HA','M'),('VA1','V1'),('VA2','V2')]),       'label': 'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HA','M+V1'),('VA1','M+V1')]),               'label': 'HA vs\nVA1'}),
    ('M+V2',    {'folders': OrderedDict([('HA','M+V2'),('VA2','M+V2')]),               'label': 'HA vs\nVA2'}),
    ('V1+V2',   {'folders': OrderedDict([('VA1','V1+V2'),('VA2','V1+V2')]),            'label': 'VA1 vs\nVA2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HA','M+V1+V2'),('VA1','M+V1+V2'),('VA2','M+V1+V2')]), 'label': 'HA vs VA1\nvs VA2'}),
])

AT_CARRIERS = OrderedDict([
    ('HB',  {'boston': os.path.join(AT_DIR, 'iperf', 'boston', 'HB'),
             'atlanta': os.path.join(AT_DIR, 'iperf', 'atlanta', 'HB'),
             'provider': 'main',      'color': '#E24A33', 'hatch': '/////'}),
    ('VB1', {'boston': os.path.join(AT_DIR, 'iperf', 'boston', 'VB1'),
             'atlanta': os.path.join(AT_DIR, 'iperf', 'atlanta', 'VB1'),
             'provider': 'virtual_1', 'color': '#348ABD', 'hatch': '\\\\\\\\\\'}),
    ('VB2', {'boston': os.path.join(AT_DIR, 'iperf', 'boston', 'VB2'),
             'atlanta': os.path.join(AT_DIR, 'iperf', 'atlanta', 'VB2'),
             'provider': 'virtual_2', 'color': '#FBC15E', 'hatch': 'xxxxx'}),
])
AT_SCENARIOS = OrderedDict([
    ('solo',    {'folders': OrderedDict([('HB','M'),('VB1','V1'),('VB2','V2')]),       'label': 'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HB','M+V1'),('VB1','M+V1')]),               'label': 'HB vs\nVB1'}),
    ('M+V2',    {'folders': OrderedDict([('HB','M+V2'),('VB2','M+V2')]),               'label': 'HB vs\nVB2'}),
    ('V1+V2',   {'folders': OrderedDict([('VB1','V1+V2'),('VB2','V1+V2')]),            'label': 'VB1 vs\nVB2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HB','M+V1+V2'),('VB1','M+V1+V2'),('VB2','M+V1+V2')]), 'label': 'HB vs VB1\nvs VB2'}),
])

TM_CARRIERS = OrderedDict([
    ('HC',  {'dl_boston': os.path.join(TM_DIR, 'iperf', 'boston', 'HC'),
             'ul_boston': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'HC'),
             'philly':    os.path.join(TM_DIR, 'iperf', 'philadelphia', 'HC'),
             'provider': 'main',      'color': '#E24A33', 'hatch': '/////'}),
    ('VC1', {'dl_boston': os.path.join(TM_DIR, 'iperf', 'boston', 'VC1'),
             'ul_boston': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC1'),
             'philly':    os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC1'),
             'provider': 'virtual_1', 'color': '#348ABD', 'hatch': '\\\\\\\\\\'}),
    ('VC2', {'dl_boston': os.path.join(TM_DIR, 'iperf', 'boston', 'VC2'),
             'ul_boston': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC2'),
             'philly':    os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC2'),
             'provider': 'virtual_2', 'color': '#FBC15E', 'hatch': 'xxxxx'}),
])
TM_SCENARIOS = OrderedDict([
    ('solo',    {'folders': OrderedDict([('HC','M'),('VC1','V1'),('VC2','V2')]),       'label': 'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HC','M+V1'),('VC1','M+V1')]),               'label': 'HC vs\nVC1'}),
    ('M+V2',    {'folders': OrderedDict([('HC','M+V2'),('VC2','M+V2')]),               'label': 'HC vs\nVC2'}),
    ('V1+V2',   {'folders': OrderedDict([('VC1','V1+V2'),('VC2','V1+V2')]),            'label': 'VC1 vs\nVC2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HC','M+V1+V2'),('VC1','M+V1+V2'),('VC2','M+V1+V2')]), 'label': 'HC vs VC1\nvs VC2'}),
])

# ── Data collection ───────────────────────────────────────────────
def collect_vz_at(scenarios, carriers, valid_dir, city_key, direction):
    """Collect raw samples for one city (VZ or AT family)."""
    result = {sc: {c: [] for c in cfg['folders']}
              for sc, cfg in scenarios.items()}
    for sc, sc_cfg in scenarios.items():
        city_data = valid_dir.get(sc, {}).get(city_key, {})
        for loc in sorted(city_data.keys()):
            for rnd in city_data[loc]:
                for carrier, folder in sc_cfg['folders'].items():
                    cfg = carriers[carrier]
                    base = cfg[city_key]
                    result[sc][carrier].extend(
                        get_samples(base, loc, rnd, folder, cfg['provider'], direction))
    return result

def collect_tm(scenarios, carriers, valid_dir, city_key, direction):
    """Collect raw samples for one city (TM family)."""
    result = {sc: {c: [] for c in cfg['folders']}
              for sc, cfg in scenarios.items()}
    for sc, sc_cfg in scenarios.items():
        city_data = valid_dir.get(sc, {}).get(city_key, {})
        for loc in sorted(city_data.keys(), key=str):
            for rnd in city_data[loc]:
                for carrier, folder in sc_cfg['folders'].items():
                    cfg = carriers[carrier]
                    result[sc][carrier].extend(
                        get_samples(cfg[city_key], loc, rnd, folder,
                                    cfg['provider'], direction))
    return result

# ── Boxplot drawing ───────────────────────────────────────────────
def draw_panel(ax, scenarios, carriers, carrier_data, ylabel,
               legend_loc='upper right'):
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
        patch.set_facecolor(col); patch.set_alpha(0.80)
        patch.set_hatch(hatch);   patch.set_edgecolor('black')
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

    handles = [mpatches.Patch(facecolor=carriers[c]['color'], alpha=0.80,
                               hatch=carriers[c]['hatch'], edgecolor='black',
                               linewidth=0.6, label=c)
               for c in carriers]
    ax.legend(handles=handles, ncol=len(carriers), loc=legend_loc,
              framealpha=0.85, handletextpad=0.3, columnspacing=0.5,
              handlelength=1.2, borderpad=0.4)

def save_figure(fname, scenarios, carriers, data, direction_label,
                legend_loc='upper right'):
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(1, 1, figsize=(5.2, 2.4))
    draw_panel(ax, scenarios, carriers, data,
               f'{direction_label} Throughput (Mbps)', legend_loc=legend_loc)
    fig.tight_layout(pad=0.4)
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {path}')

# ── Main ─────────────────────────────────────────────────────────
print('Parsing valid_data_range.txt files…')
vz_ranges = parse_ranges(os.path.join(VZ_DIR, 'valid_data_range.txt'), 'vz')
at_ranges = parse_ranges(os.path.join(AT_DIR, 'valid_data_range.txt'), 'at')
tm_ranges = parse_ranges(os.path.join(TM_DIR, 'valid_data_range.txt'), 'tm')

TASKS = [
    # (family_label, scenarios, carriers, ranges_key, cities_by_direction, collect_fn, name_map)
    ('A', VZ_SCENARIOS, VZ_CARRIERS, vz_ranges['all_valid'],
     {'downlink': ['boston', 'atlanta'], 'uplink': ['boston', 'atlanta']},
     collect_vz_at,
     {'boston': 'Boston', 'atlanta': 'Atlanta'}),

    ('B', AT_SCENARIOS, AT_CARRIERS, at_ranges['all_valid'],
     {'downlink': ['boston', 'atlanta'], 'uplink': ['boston', 'atlanta']},
     collect_vz_at,
     {'boston': 'Boston', 'atlanta': 'Atlanta'}),

    ('C', TM_SCENARIOS, TM_CARRIERS, tm_ranges.get('qci677', {}),
     {'downlink': ['dl_boston', 'philly'], 'uplink': ['ul_boston', 'philly']},
     collect_tm,
     {'dl_boston': 'Boston', 'ul_boston': 'Boston', 'philly': 'Philadelphia'}),
]

for fam, scenarios, carriers, ranges, cities_by_dir, collect_fn, city_names in TASKS:
    print(f'\n── Family {fam} ──────────────────────────────────────')
    for direction, dlabel in [('downlink', 'DL'), ('uplink', 'UL')]:
        valid_dir = ranges.get(direction, {}) if isinstance(ranges, dict) and 'downlink' not in ranges else ranges[direction] if 'downlink' in ranges else {}
        for city_key in cities_by_dir[direction]:
            city_name = city_names[city_key]
            print(f'  {dlabel} — {city_name}…')
            data = collect_fn(scenarios, carriers, valid_dir, city_key, direction)

            # Print sample counts
            for sc, sc_cfg in scenarios.items():
                counts = {c: len(data[sc].get(c, [])) for c in sc_cfg['folders']}
                print(f'    {sc_cfg["label"]:>20s}: {counts}')

            fname = f'{fam}_City_{city_name}_{dlabel}.png'
            # A/Atlanta/DL: an upper-right legend hides the last scenario's boxes
            legend_loc = ('lower right'
                          if fname == 'A_City_Atlanta_DL.png' else 'upper right')
            save_figure(fname, scenarios, carriers, data, dlabel,
                        legend_loc=legend_loc)

print('\nDone.')
