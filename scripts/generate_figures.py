#!/usr/bin/env python3
"""
generate_figures.py
Tasks 1, 2, 3:
  Task 1: Box plots per operator family (Family A / Family B 4 plots; Family C 8 plots)
  Task 2: Overview cross-family throughput box plot
  Task 3: Win-count statistics tables written to statistic.md
"""
import os, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import OrderedDict

# ── Paths ────────────────────────────────────────────────────────
ROOT      = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
OUT_DIR   = os.path.join(ROOT, os.pardir, 'plots')
STAT_PATH = os.path.join(ROOT, os.pardir, 'statistic.md')
os.makedirs(OUT_DIR, exist_ok=True)

VZ_DIR   = os.path.join(RAW, 'family_a')
AT_DIR   = os.path.join(RAW, 'family_b')
TM_DIR   = os.path.join(RAW, 'family_c')

# ── Shared rcParams ──────────────────────────────────────────────
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

# ── iperf3 parsing ───────────────────────────────────────────────
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

def round_avg(base_dir, loc_str, rnd, sc_folder, provider, direction):
    fp = find_iperf_file(base_dir, loc_str, rnd, sc_folder, provider, direction)
    if not fp:
        return None
    tps = extract_tp(fp)
    return float(np.mean(tps)) if tps else None

def round_samples(base_dir, loc_str, rnd, sc_folder, provider, direction):
    """Return all 0.5s iperf samples (Mbps) for one round, not just the mean."""
    fp = find_iperf_file(base_dir, loc_str, rnd, sc_folder, provider, direction)
    if not fp:
        return []
    return extract_tp(fp)

# ── Parse valid-range dicts from valid_data_range.txt (single source of truth) ─
import re as _re

_SC_MAP_PARSE = {1: 'solo', 2: 'M+V1', 3: 'M+V2', 4: 'V1+V2', 5: 'M+V1+V2'}
_LOW_QCI  = {'67', '77', '677'}
_HIGH_QCI = {'99', '999'}

def _parse_rounds_txt(s):
    return sorted({int(m.group(1)) for m in _re.finditer(r'Round(\d+)', s)})

def _loc_key_int(label):
    m = _re.search(r'(\d+)', label.replace('Location', ''))
    return int(m.group(1)) if m else label

def _loc_key_str(label):
    s = label.strip()
    if s.startswith('Location_'): return s[9:]
    if s.startswith('Location'):  return s[8:]
    return s

def parse_valid_data_range(filepath, family='vz'):
    """Parse valid_data_range.txt for the given operator family.

    family 'vz'/'at': int location keys; cities 'boston'/'atlanta'
    family 'tm'     : str location keys; cities 'dl_boston'/'ul_boston'/'philly'

    Returns dict with keys:
      'all_valid', '5g_only'  — always present
      'qci677',   'qci999'   — present for Family C only
    Each value: {'downlink': {sc: {city: {loc: [rounds]}}}, 'uplink': {...}}
    """
    loc_fn = _loc_key_str if family == 'tm' else _loc_key_int

    def _city(name, direction):
        c = name.strip().lower()
        if family == 'tm':
            if c == 'boston':
                return 'dl_boston' if direction == 'downlink' else 'ul_boston'
            if c == 'philadelphia':
                return 'philly'
        return c  # 'boston' or 'atlanta'

    def _empty():
        return {sc: {} for sc in _SC_MAP_PARSE.values()}

    with open(filepath) as f:
        lines = f.readlines()

    res = {
        'all_valid': {'downlink': _empty(), 'uplink': _empty()},
        '5g_only':   {'downlink': _empty(), 'uplink': _empty()},
    }
    stg5g  = {}   # (direction, sc, city, pci) → {loc: [rounds]}
    stg677 = {}
    stg999 = {}

    sec = direction = sc = city = pci = qci_cat = None

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

        m = _re.match(r'Senario\s+(\d+):', s)
        if m:
            sc = _SC_MAP_PARSE.get(int(m.group(1)))
            city = pci = qci_cat = None; continue
        if sc is None:
            continue

        cm = _re.match(r'(Boston|Atlanta|Philadelphia):', s, _re.I)
        if cm:
            city = _city(cm.group(1), direction)
            pci = qci_cat = None; continue
        if city is None:
            continue

        if sec == '5g_only':
            qm = _re.match(r'QCI\s*(\d+)', s)
            if qm:
                q = qm.group(1)
                qci_cat = ('low'  if q in _LOW_QCI  else
                           'high' if q in _HIGH_QCI else None)
                pci = None; continue
            if s.startswith('Same PCI:'):
                pci = 'same'; continue
            if s.startswith('Diff PCI:'):
                pci = 'diff'; continue

        lm = _re.match(r'(Location\w*)\s*:\s*(.+)', s)
        if lm:
            loc    = loc_fn(lm.group(1))
            rounds = _parse_rounds_txt(lm.group(2))
            if sec == 'all_valid':
                res['all_valid'][direction][sc].setdefault(city, {})[loc] = rounds
            elif sec == '5g_only' and pci is not None:
                k = (direction, sc, city, pci)
                for _stg in ([stg5g] +
                             ([stg677] if qci_cat == 'low'  else
                              [stg999] if qci_cat == 'high' else [])):
                    d = _stg.setdefault(k, {})
                    d[loc] = sorted(set(d.get(loc, []) + rounds))

    def _flush(stg, key):
        if not stg:
            return
        if key not in res:
            res[key] = {'downlink': _empty(), 'uplink': _empty()}
        for (d, sc2, c, _p), lr in stg.items():
            for loc, rnds in lr.items():
                t = res[key][d][sc2].setdefault(c, {})
                t[loc] = sorted(set(t.get(loc, []) + rnds))

    _flush(stg5g,  '5g_only')
    _flush(stg677, 'qci677')
    _flush(stg999, 'qci999')
    return res

# ── Load ranges from the three valid_data_range.txt files ────────
VZ_TXT = os.path.join(VZ_DIR, 'valid_data_range.txt')
AT_TXT = os.path.join(AT_DIR, 'valid_data_range.txt')
TM_TXT = os.path.join(TM_DIR, 'valid_data_range.txt')

_vz_ranges = parse_valid_data_range(VZ_TXT, family='vz')
_at_ranges = parse_valid_data_range(AT_TXT, family='at')
_tm_ranges = parse_valid_data_range(TM_TXT, family='tm')

# ════════════════════════════════════════════════════════════════
#  FAMILY A
# ════════════════════════════════════════════════════════════════
VZ_CARRIERS = OrderedDict([
    ('HA',  {'boston_dir': os.path.join(VZ_DIR, 'iperf', 'boston', 'HA'),
             'atlanta_dir': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'HA'),
             'provider': 'main',      'color': '#E24A33', 'hatch': '/////'}),
    ('VA1', {'boston_dir': os.path.join(VZ_DIR, 'iperf', 'boston', 'VA1'),
             'atlanta_dir': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'VA1'),
             'provider': 'virtual_1', 'color': '#348ABD', 'hatch': '\\\\\\\\\\'}),
    ('VA2', {'boston_dir': os.path.join(VZ_DIR, 'iperf', 'boston', 'VA2'),
             'atlanta_dir': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'VA2'),
             'provider': 'virtual_2', 'color': '#FBC15E', 'hatch': 'xxxxx'}),
])

VZ_SCENARIOS = OrderedDict([
    ('solo',    {'folders': OrderedDict([('HA','M'),('VA1','V1'),('VA2','V2')]),
                 'label': 'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HA','M+V1'),('VA1','M+V1')]),
                 'label': 'HA vs\nVA1'}),
    ('M+V2',    {'folders': OrderedDict([('HA','M+V2'),('VA2','M+V2')]),
                 'label': 'HA vs\nVA2'}),
    ('V1+V2',   {'folders': OrderedDict([('VA1','V1+V2'),('VA2','V1+V2')]),
                 'label': 'VA1 vs\nVA2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HA','M+V1+V2'),('VA1','M+V1+V2'),('VA2','M+V1+V2')]),
                 'label': 'HA vs VA1\nvs VA2'}),
])

VZ_ALL_VALID = _vz_ranges['all_valid']
VZ_5G        = _vz_ranges['5g_only']

def vz_collect(direction, sc_key, valid, use_samples=False):
    ranges = valid[direction].get(sc_key, {})
    folders = VZ_SCENARIOS[sc_key]['folders']
    round_keys = []
    for city in ['boston', 'atlanta']:
        for loc in sorted(ranges.get(city, {}).keys()):
            for rnd in ranges[city][loc]:
                round_keys.append((city, loc, rnd))
    result = {c: [] for c in folders}
    for city, loc, rnd in round_keys:
        for carrier, folder in folders.items():
            cfg = VZ_CARRIERS[carrier]
            base = cfg['boston_dir'] if city == 'boston' else cfg['atlanta_dir']
            if use_samples:
                result[carrier].extend(round_samples(base, loc, rnd, folder, cfg['provider'], direction))
            else:
                result[carrier].append(round_avg(base, loc, rnd, folder, cfg['provider'], direction))
    return result

# ════════════════════════════════════════════════════════════════
#  Family B FAMILY
# ════════════════════════════════════════════════════════════════
AT_CARRIERS = OrderedDict([
    ('HB',  {'boston_dir': os.path.join(AT_DIR, 'iperf', 'boston', 'HB'),
             'atlanta_dir': os.path.join(AT_DIR, 'iperf', 'atlanta', 'HB'),
             'provider': 'main',      'color': '#E24A33', 'hatch': '/////'}),
    ('VB1', {'boston_dir': os.path.join(AT_DIR, 'iperf', 'boston', 'VB1'),
             'atlanta_dir': os.path.join(AT_DIR, 'iperf', 'atlanta', 'VB1'),
             'provider': 'virtual_1', 'color': '#348ABD', 'hatch': '\\\\\\\\\\'}),
    ('VB2', {'boston_dir': os.path.join(AT_DIR, 'iperf', 'boston', 'VB2'),
             'atlanta_dir': os.path.join(AT_DIR, 'iperf', 'atlanta', 'VB2'),
             'provider': 'virtual_2', 'color': '#FBC15E', 'hatch': 'xxxxx'}),
])

AT_SCENARIOS = OrderedDict([
    ('solo',    {'folders': OrderedDict([('HB','M'),('VB1','V1'),('VB2','V2')]),
                 'label': 'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HB','M+V1'),('VB1','M+V1')]),
                 'label': 'HB vs\nVB1'}),
    ('M+V2',    {'folders': OrderedDict([('HB','M+V2'),('VB2','M+V2')]),
                 'label': 'HB vs\nVB2'}),
    ('V1+V2',   {'folders': OrderedDict([('VB1','V1+V2'),('VB2','V1+V2')]),
                 'label': 'VB1 vs\nVB2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HB','M+V1+V2'),('VB1','M+V1+V2'),('VB2','M+V1+V2')]),
                 'label': 'HB vs VB1\nvs VB2'}),
])

AT_ALL_VALID = _at_ranges['all_valid']
AT_5G        = _at_ranges['5g_only']

def at_collect(direction, sc_key, valid, use_samples=False):
    ranges = valid[direction].get(sc_key, {})
    folders = AT_SCENARIOS[sc_key]['folders']
    round_keys = []
    for city in ['boston', 'atlanta']:
        for loc in sorted(ranges.get(city, {}).keys()):
            for rnd in ranges[city][loc]:
                round_keys.append((city, loc, rnd))
    result = {c: [] for c in folders}
    for city, loc, rnd in round_keys:
        for carrier, folder in folders.items():
            cfg = AT_CARRIERS[carrier]
            base = cfg['boston_dir'] if city == 'boston' else cfg['atlanta_dir']
            if use_samples:
                result[carrier].extend(round_samples(base, loc, rnd, folder, cfg['provider'], direction))
            else:
                result[carrier].append(round_avg(base, loc, rnd, folder, cfg['provider'], direction))
    return result

# ════════════════════════════════════════════════════════════════
#  FAMILY C
# ════════════════════════════════════════════════════════════════
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
    ('solo',    {'folders': OrderedDict([('HC','M'),('VC1','V1'),('VC2','V2')]),
                 'label': 'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HC','M+V1'),('VC1','M+V1')]),
                 'label': 'HC vs\nVC1'}),
    ('M+V2',    {'folders': OrderedDict([('HC','M+V2'),('VC2','M+V2')]),
                 'label': 'HC vs\nVC2'}),
    ('V1+V2',   {'folders': OrderedDict([('VC1','V1+V2'),('VC2','V1+V2')]),
                 'label': 'VC1 vs\nVC2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HC','M+V1+V2'),('VC1','M+V1+V2'),('VC2','M+V1+V2')]),
                 'label': 'HC vs VC1\nvs VC2'}),
])

TM_ALL_VALID_DL = _tm_ranges['all_valid']['downlink']
TM_ALL_VALID_UL = _tm_ranges['all_valid']['uplink']
TM_5G_DL        = _tm_ranges['5g_only']['downlink']
TM_5G_UL        = _tm_ranges['5g_only']['uplink']
TM_QCI677_DL    = _tm_ranges.get('qci677', {}).get('downlink', {})
TM_QCI999_DL    = _tm_ranges.get('qci999', {}).get('downlink', {})
TM_QCI677_UL    = _tm_ranges.get('qci677', {}).get('uplink', {})
TM_QCI999_UL    = _tm_ranges.get('qci999', {}).get('uplink', {})

CITIES_TM_DL = ('dl_boston', 'philly')
CITIES_TM_UL = ('ul_boston', 'philly')

def tm_collect(direction, sc_key, valid_map, use_samples=False):
    """valid_map[sc_key] = {city_key: {loc_str: [rounds]}}"""
    city_ranges = valid_map.get(sc_key, {})
    folders = TM_SCENARIOS[sc_key]['folders']
    cities = CITIES_TM_DL if direction == 'downlink' else CITIES_TM_UL
    round_keys = []
    for city in cities:
        locs = city_ranges.get(city, {})
        for loc in sorted(locs.keys(), key=str):
            for rnd in locs[loc]:
                round_keys.append((city, loc, rnd))
    result = {c: [] for c in folders}
    for city, loc, rnd in round_keys:
        for carrier, folder in folders.items():
            cfg = TM_CARRIERS[carrier]
            base = cfg[city]
            if use_samples:
                result[carrier].extend(round_samples(base, str(loc), rnd, folder, cfg['provider'], direction))
            else:
                result[carrier].append(round_avg(base, str(loc), rnd, folder, cfg['provider'], direction))
    return result

# ════════════════════════════════════════════════════════════════
#  BOX PLOT DRAWING
# ════════════════════════════════════════════════════════════════
BOX_W        = 0.20   # width of each box
INTRA_GAP    = 0.04   # gap between boxes within one scenario
INTER_GAP    = 0.38   # gap between scenario groups

def _compute_positions(scenarios, carrier_data):
    """Return positions list and group_centers list."""
    positions = []
    group_centers = []
    x = 0.0
    for sc_key, sc_cfg in scenarios.items():
        carriers_in = [c for c in sc_cfg['folders'] if c in carrier_data]
        n = len(carriers_in)
        sc_positions = [x + i * (BOX_W + INTRA_GAP) for i in range(n)]
        center = (sc_positions[0] + sc_positions[-1]) / 2.0
        positions.extend(sc_positions)
        group_centers.append((center, sc_cfg['label']))
        x = sc_positions[-1] + BOX_W + INTER_GAP
    return positions, group_centers, x - INTER_GAP + BOX_W / 2

def draw_boxplot(ax, scenarios, carriers_cfg, carrier_data,
                 ylabel, show_legend=True):
    """
    carrier_data: {sc_key: {carrier_name: [per_round_avg_or_None]}}
    """
    all_positions = []
    all_data = []
    all_colors = []
    all_hatches = []
    carrier_order_per_sc = {}

    x = 0.0
    group_centers = []
    for sc_key, sc_cfg in scenarios.items():
        carriers_in = [c for c in sc_cfg['folders'] if c in carriers_cfg]
        n = len(carriers_in)
        sc_positions = [x + i * (BOX_W + INTRA_GAP) for i in range(n)]
        center = (sc_positions[0] + sc_positions[-1]) / 2.0
        group_centers.append((center, sc_cfg['label']))

        for i, carrier in enumerate(carriers_in):
            vals = [v for v in carrier_data.get(sc_key, {}).get(carrier, []) if v is not None]
            all_positions.append(sc_positions[i])
            all_data.append(vals if vals else [0])
            all_colors.append(carriers_cfg[carrier]['color'])
            all_hatches.append(carriers_cfg[carrier]['hatch'])

        carrier_order_per_sc[sc_key] = carriers_in
        x = sc_positions[-1] + BOX_W + INTER_GAP

    x_max = x - INTER_GAP + BOX_W / 2

    bp = ax.boxplot(
        all_data,
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

    # Add mean marker
    for pos, data in zip(all_positions, all_data):
        if data and data != [0]:
            ax.plot(pos, np.mean(data), marker='D', color='black',
                    markersize=2.5, zorder=5, markeredgewidth=0.4)

    ax.set_xticks([c for c, _ in group_centers])
    ax.set_xticklabels([l for _, l in group_centers], fontsize=8)
    ax.set_xlim(-0.25, x_max + 0.25)
    ax.set_ylim(bottom=0)
    ax.set_ylabel(ylabel)
    ax.grid(axis='y', alpha=0.3, linewidth=0.4)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    if show_legend:
        handles = []
        for carrier, cfg in carriers_cfg.items():
            patch = mpatches.Patch(
                facecolor=cfg['color'], alpha=0.80,
                hatch=cfg['hatch'], edgecolor='black',
                linewidth=0.6, label=carrier)
            handles.append(patch)
        ax.legend(handles=handles, ncol=len(carriers_cfg),
                  loc='upper right', framealpha=0.85,
                  handletextpad=0.3, columnspacing=0.5,
                  handlelength=1.2, fontsize=9,
                  borderpad=0.4)

    return bp

def save_boxplot(fname, scenarios, carriers_cfg, carrier_data, direction_label):
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(figsize=(5.2, 2.4))
    draw_boxplot(ax, scenarios, carriers_cfg, carrier_data,
                 ylabel=f'{direction_label} Throughput (Mbps)',
                 show_legend=True)
    fig.tight_layout(pad=0.4)
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {path}')

# ════════════════════════════════════════════════════════════════
#  TASK 1 HELPERS: collect data for all scenarios into dict
# ════════════════════════════════════════════════════════════════
def collect_vz(direction, valid, use_samples=False):
    data = {}
    for sc_key in VZ_SCENARIOS:
        data[sc_key] = vz_collect(direction, sc_key, valid, use_samples=use_samples)
    return data

def collect_at(direction, valid, use_samples=False):
    data = {}
    for sc_key in AT_SCENARIOS:
        data[sc_key] = at_collect(direction, sc_key, valid, use_samples=use_samples)
    return data

def collect_tm(direction, valid_map, use_samples=False):
    data = {}
    for sc_key in TM_SCENARIOS:
        data[sc_key] = tm_collect(direction, sc_key, valid_map, use_samples=use_samples)
    return data

# ════════════════════════════════════════════════════════════════
#  TASK 1: Generate per-family box plots
# ════════════════════════════════════════════════════════════════
def task1():
    print('\n=== Task 1: Per-family box plots ===')

    # Family A
    for valid, tag in [(VZ_ALL_VALID, 'All_Valid_Data'), (VZ_5G, '5G_Only')]:
        for direction, dlabel in [('downlink', 'DL'), ('uplink', 'UL')]:
            data = collect_vz(direction, valid, use_samples=True)
            save_boxplot(f'FamilyA_{tag}_{dlabel}.png',
                         VZ_SCENARIOS, VZ_CARRIERS, data, dlabel)

    # Family B
    for valid, tag in [(AT_ALL_VALID, 'All_Valid_Data'), (AT_5G, '5G_Only')]:
        for direction, dlabel in [('downlink', 'DL'), ('uplink', 'UL')]:
            data = collect_at(direction, valid, use_samples=True)
            save_boxplot(f'FamilyB_{tag}_{dlabel}.png',
                         AT_SCENARIOS, AT_CARRIERS, data, dlabel)

    # Family C — 8 plots
    for valid_dl, valid_ul, tag in [
        (TM_ALL_VALID_DL, TM_ALL_VALID_UL, 'All_Valid_Data'),
        (TM_5G_DL, TM_5G_UL, '5G_Only'),
        (TM_QCI677_DL, TM_QCI677_UL, '5G_Only_QCI677'),
        (TM_QCI999_DL, TM_QCI999_UL, '5G_Only_QCI999'),
    ]:
        for valid_map, direction, dlabel in [
            (valid_dl, 'downlink', 'DL'), (valid_ul, 'uplink', 'UL')
        ]:
            data = collect_tm(direction, valid_map, use_samples=True)
            save_boxplot(f'FamilyC_{tag}_{dlabel}.png',
                         TM_SCENARIOS, TM_CARRIERS, data, dlabel)

# ════════════════════════════════════════════════════════════════
#  TASK 2: Cross-family overview box plot
# ════════════════════════════════════════════════════════════════
FAMILY_COLORS = {
    'Family A': '#2b8cbf',
    'Family B': '#31a354',
    'Family C': '#de2d26',
}
# Internal key → display name mapping (keeps pool collection decoupled from labels)
_FAM_INTERNAL = {
    'Family A': 'family_a',
    'Family B': 'family_b',
    'Family C': 'family_c',
}

ROLE_HATCHES = {
    'main': '/////',
    'virtual_1': '\\\\\\\\\\',
    'virtual_2': 'xxxxx',
}

def _collect_all_valid_pool(display_name, direction):
    """Return {carrier_name: [all iperf samples]} across all scenarios for given direction."""
    family = _FAM_INTERNAL.get(display_name, display_name)
    pool = {}
    if family == 'family_a':
        for sc_key in VZ_SCENARIOS:
            d = vz_collect(direction, sc_key, VZ_ALL_VALID, use_samples=True)
            for c, vals in d.items():
                pool.setdefault(c, []).extend(vals)
    elif family == 'family_b':
        for sc_key in AT_SCENARIOS:
            d = at_collect(direction, sc_key, AT_ALL_VALID, use_samples=True)
            for c, vals in d.items():
                pool.setdefault(c, []).extend(vals)
    elif family == 'family_c':
        valid_map = TM_ALL_VALID_DL if direction == 'downlink' else TM_ALL_VALID_UL
        for sc_key in TM_SCENARIOS:
            d = tm_collect(direction, sc_key, valid_map, use_samples=True)
            for c, vals in d.items():
                pool.setdefault(c, []).extend(vals)
    return pool

def _draw_overview(ax, families, direction):
    """Draw one overview box plot panel onto ax."""
    BOX_W2 = 0.22
    INTRA2 = 0.05
    INTER2 = 0.45

    positions    = []
    box_data     = []
    box_colors   = []
    box_hatches  = []
    group_centers = []
    xtick_labels  = []

    x = 0.0
    for fam_name, carrier_list, carriers_cfg in families:
        pool = _collect_all_valid_pool(fam_name, direction)
        n = len(carrier_list)
        sc_positions = [x + i * (BOX_W2 + INTRA2) for i in range(n)]
        group_centers.append((sc_positions[0] + sc_positions[-1]) / 2.0)

        for i, carrier in enumerate(carrier_list):
            vals = pool.get(carrier, [])
            positions.append(sc_positions[i])
            box_data.append(vals if vals else [0])
            box_colors.append(FAMILY_COLORS[fam_name])
            box_hatches.append(ROLE_HATCHES[carriers_cfg[carrier]['provider']])
            xtick_labels.append(carrier)

        x = sc_positions[-1] + BOX_W2 + INTER2

    bp = ax.boxplot(
        box_data,
        positions=positions,
        widths=BOX_W2,
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

    for patch, color, hatch in zip(bp['boxes'], box_colors, box_hatches):
        patch.set_facecolor(color)
        patch.set_alpha(0.80)
        patch.set_hatch(hatch)
        patch.set_edgecolor('black')
        patch.set_linewidth(0.6)

    for pos, data in zip(positions, box_data):
        if data and data != [0]:
            ax.plot(pos, np.mean(data), marker='D', color='black',
                    markersize=2.5, zorder=5, markeredgewidth=0.4)

    dlabel = 'DL' if direction == 'downlink' else 'UL'
    ax.set_xticks(positions)
    ax.set_xticklabels(xtick_labels, fontsize=8)
    ax.set_xlim(-0.3, x - INTER2 + BOX_W2 + 0.2)
    ax.set_ylim(bottom=0)
    ax.set_ylabel(f'{dlabel} Throughput (Mbps)')
    ax.grid(axis='y', alpha=0.3, linewidth=0.4)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    for i, (fam_name, _, _) in enumerate(families):
        ax.annotate(fam_name, xy=(group_centers[i], 0),
                    xycoords=('data', 'axes fraction'),
                    xytext=(group_centers[i], -0.22),
                    textcoords=('data', 'axes fraction'),
                    ha='center', va='top', fontsize=9, fontstyle='italic')

    legend_handles = []
    for fam_name, _, _ in families:
        legend_handles.append(
            mpatches.Patch(facecolor=FAMILY_COLORS[fam_name], alpha=0.8,
                           edgecolor='black', linewidth=0.5, label=fam_name))
    for role_label, hatch in [('Main (P)', '/////'), ('MVNO-1 (V1)', '\\\\\\\\\\'), ('MVNO-2 (V2)', 'xxxxx')]:
        legend_handles.append(
            mpatches.Patch(facecolor='white', alpha=0.8,
                           hatch=hatch, edgecolor='black', linewidth=0.5, label=role_label))
    ax.legend(handles=legend_handles, ncol=3, loc='upper right',
              framealpha=0.85, handletextpad=0.3, columnspacing=0.5,
              handlelength=1.2, fontsize=8.5, borderpad=0.4)

def task2():
    print('\n=== Task 2: Cross-family overview box plots ===')
    plt.rcParams.update(RC)

    families = [
        ('Family A', ['HA', 'VA1', 'VA2'], VZ_CARRIERS),
        ('Family B', ['HB', 'VB1', 'VB2'], AT_CARRIERS),
        ('Family C', ['HC', 'VC1', 'VC2'], TM_CARRIERS),
    ]

    for direction, dlabel in [('downlink', 'DL'), ('uplink', 'UL')]:
        fig, ax = plt.subplots(figsize=(5.2, 2.4))
        _draw_overview(ax, families, direction)
        fig.tight_layout(pad=0.4)
        path = os.path.join(OUT_DIR, f'Overview_CrossFamily_{dlabel}.png')
        fig.savefig(path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print(f'  Saved: {path}')

# ════════════════════════════════════════════════════════════════
#  TASK 3: Win statistics → statistic.md
# ════════════════════════════════════════════════════════════════
def _determine_winner(vals, margin=0.10):
    """Return the winner operator name, or 'tie'.

    An operator wins only if its throughput is strictly more than (1+margin)×
    the throughput of every other operator in vals.  If no single operator
    clears that bar, the round is a tie.
    """
    best = max(vals, key=vals.get)
    best_val = vals[best]
    for op, v in vals.items():
        if op == best:
            continue
        if best_val <= v * (1 + margin):
            return 'tie'
    return best

def compute_wins(scenarios, carrier_data):
    """Per-round win counting (10 % margin rule).

    A round is counted only when ≥2 operators have non-None data.
    An operator wins if its throughput exceeds every rival by >10 %;
    otherwise the round is a tie.

    Returns {sc_key: {'wins': {carrier: int}, 'ties': int, 'total': int}}
    """
    result = {}
    for sc_key, sc_cfg in scenarios.items():
        carriers_in = list(sc_cfg['folders'].keys())
        sc_data = carrier_data.get(sc_key, {})

        n_rounds = max((len(sc_data.get(c, [])) for c in carriers_in), default=0)
        wins  = {c: 0 for c in carriers_in}
        ties  = 0
        total = 0

        for i in range(n_rounds):
            vals = {c: sc_data[c][i]
                    for c in carriers_in
                    if i < len(sc_data.get(c, [])) and sc_data[c][i] is not None}
            if len(vals) >= 2:
                total += 1
                w = _determine_winner(vals)
                if w == 'tie':
                    ties += 1
                else:
                    wins[w] += 1

        result[sc_key] = {'wins': wins, 'ties': ties, 'total': total}
    return result

def _wins_table(title, scenarios, carrier_names, carrier_data, scenario_labels):
    lines = [f'\n### {title}\n']
    header = ' | '.join(f'{c} wins' for c in carrier_names)
    lines.append(f'| Scenario | Total Rounds | {header} | Ties |')
    lines.append(f'|:---:| :---: | {" | ".join([":---:"] * len(carrier_names))} | :---: |')
    stats = compute_wins(scenarios, carrier_data)
    for sc_key, sc_cfg in scenarios.items():
        sc_label = scenario_labels.get(sc_key, sc_cfg['label'])
        s = stats[sc_key]
        wins_str = ' | '.join(
            str(s['wins'].get(c, '-')) if c in s['wins'] else '-'
            for c in carrier_names)
        lines.append(f'| {sc_label} | {s["total"]} | {wins_str} | {s["ties"]} |')
    return '\n'.join(lines)

VZ_SC_LABELS = {'solo': 'Solo', 'M+V1': 'HA vs\nVA1', 'M+V2': 'HA vs\nVA2',
                'V1+V2': 'VA1 vs\nVA2', 'M+V1+V2': 'HA vs VA1\nvs VA2'}
AT_SC_LABELS = {'solo': 'Solo', 'M+V1': 'HB vs\nVB1', 'M+V2': 'HB vs\nVB2',
                'V1+V2': 'VB1 vs\nVB2', 'M+V1+V2': 'HB vs VB1\nvs VB2'}
TM_SC_LABELS = {'solo': 'Solo', 'M+V1': 'HC vs\nVC1', 'M+V2': 'HC vs\nVC2',
                'V1+V2': 'VC1 vs\nVC2', 'M+V1+V2': 'HC vs VC1\nvs VC2'}

def task3():
    print('\n=== Task 3: Statistics tables ===')
    sections = ['# Throughput Win Statistics\n',
                '_Win = operator whose per-round average throughput exceeds every '
                'rival by >10 %. If no operator clears that bar the round is a Tie. '
                'Only rounds where ≥2 operators have data are counted._\n']

    # ── Family A ──────────────────────────────────────────────────
    sections.append('\n## Family A Family (HA / VA1 / VA2)\n')
    for valid, tag in [(VZ_ALL_VALID, 'All Valid Data'), (VZ_5G, '5G Only')]:
        for direction, dlabel in [('downlink', 'DL'), ('uplink', 'UL')]:
            data = collect_vz(direction, valid)   # use_samples=False → per-round avg
            sections.append(_wins_table(
                f'{tag} — {dlabel}', VZ_SCENARIOS,
                ['HA', 'VA1', 'VA2'], data, VZ_SC_LABELS))

    # ── Family B ─────────────────────────────────────────────────────
    sections.append('\n\n## Family B (HB / VB1 / VB2)\n')
    for valid, tag in [(AT_ALL_VALID, 'All Valid Data'), (AT_5G, '5G Only')]:
        for direction, dlabel in [('downlink', 'DL'), ('uplink', 'UL')]:
            data = collect_at(direction, valid)
            sections.append(_wins_table(
                f'{tag} — {dlabel}', AT_SCENARIOS,
                ['HB', 'VB1', 'VB2'], data, AT_SC_LABELS))

    # ── Family C ─────────────────────────────────────────────────
    sections.append('\n\n## Family C Family (HC / VC1 / VC2)\n')
    combos = [
        (TM_ALL_VALID_DL, TM_ALL_VALID_UL, 'All Valid Data'),
        (TM_5G_DL, TM_5G_UL, '5G Only'),
        (TM_QCI677_DL, TM_QCI677_UL, '5G Only QCI677'),
        (TM_QCI999_DL, TM_QCI999_UL, '5G Only QCI999'),
    ]
    for valid_dl, valid_ul, tag in combos:
        for valid_map, direction, dlabel in [
            (valid_dl, 'downlink', 'DL'), (valid_ul, 'uplink', 'UL')
        ]:
            data = collect_tm(direction, valid_map)
            sections.append(_wins_table(
                f'{tag} — {dlabel}', TM_SCENARIOS,
                ['HC', 'VC1', 'VC2'], data, TM_SC_LABELS))

    with open(STAT_PATH, 'w') as f:
        f.write('\n'.join(sections) + '\n')
    print(f'  Written: {STAT_PATH}')

# ════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    task1()
    task2()
    task3()
    print('\nDone.')
