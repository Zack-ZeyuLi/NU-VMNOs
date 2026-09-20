#!/usr/bin/env python3
"""
Same-PCI vs Diff-PCI throughput boxplots for all 3 operator families.
Produces 12 figures (A/B/C × DL/UL × Same/Diff), each as a single-panel PNG.
Naming: {Family}_5G_PCI_{Same|Diff}_{DL|UL}.png

Data source : valid_data_range.txt  (single source of truth)
Output      : Paper/figures/
"""

import os, re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import OrderedDict

# ── Paths ─────────────────────────────────────────────────────────
ROOT    = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
VZ_DIR  = os.path.join(RAW, 'family_a')
AT_DIR  = os.path.join(RAW, 'family_b')
TM_DIR  = os.path.join(RAW, 'family_c')
OUT_DIR = os.path.join(ROOT, os.pardir, 'plots')
os.makedirs(OUT_DIR, exist_ok=True)

# ── Shared style (identical to generate_figures.py) ───────────────
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

# ── PCI ranges parser ─────────────────────────────────────────────
_SC_MAP = {1:'solo', 2:'M+V1', 3:'M+V2', 4:'V1+V2', 5:'M+V1+V2'}

def _parse_rounds(s):
    return sorted({int(m.group(1)) for m in re.finditer(r'Round(\d+)', s)})

def _loc_key_str(label):
    s = label.strip()
    if s.startswith('Location_'): return s[9:]
    if s.startswith('Location'):  return s[8:]
    return s

def _loc_key_int(label):
    m = re.search(r'(\d+)', label.replace('Location',''))
    return int(m.group(1)) if m else label

def parse_pci_ranges(filepath, family='vz'):
    """
    Parse 5G-only section, keeping Same PCI and Diff PCI separate.
    Returns:
      {'same': {'downlink': {sc:{city:{loc:[rounds]}}}, 'uplink': ...},
       'diff': {'downlink': {sc:{city:{loc:[rounds]}}}, 'uplink': ...}}
    """
    loc_fn = _loc_key_str if family == 'tm' else _loc_key_int

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
        'same': {'downlink': _empty(), 'uplink': _empty()},
        'diff': {'downlink': _empty(), 'uplink': _empty()},
    }

    with open(filepath) as f:
        lines = f.readlines()

    in_5g = direction = sc = city = pci = None

    for raw in lines:
        s = raw.strip()
        if not s or s.startswith('##'): continue

        if s.startswith('All valid data:'): in_5g = False; continue
        if s.startswith('5G only:'):        in_5g = True;  continue
        if not in_5g: continue

        indent = len(raw) - len(raw.lstrip())

        if indent == 0:
            if s.startswith('Downlink:'):
                direction = 'downlink'; sc = city = pci = None; continue
            if s.startswith('Uplink:'):
                direction = 'uplink'; sc = city = pci = None; continue
        if direction is None: continue

        m = re.match(r'Senario\s+(\d+):', s)
        if m:
            sc = _SC_MAP.get(int(m.group(1))); city = pci = None; continue
        if sc is None: continue

        cm = re.match(r'(Boston|Atlanta|Philadelphia):', s, re.I)
        if cm:
            city = city_key(cm.group(1), direction); pci = None; continue
        if city is None: continue

        # QCI line (Family C only) – reset pci so next Same/Diff PCI wins
        if re.match(r'QCI\s*\d+', s): pci = None; continue

        if s.startswith('Same PCI:'): pci = 'same'; continue
        if s.startswith('Diff PCI:'): pci = 'diff'; continue
        if pci is None: continue

        lm = re.match(r'(Location[\w_]*)\s*:\s*(.+)', s)
        if lm:
            try:
                loc = loc_fn(lm.group(1))
            except Exception:
                continue
            rnds = _parse_rounds(lm.group(2))
            d = res[pci][direction][sc].setdefault(city, {})
            d[loc] = sorted(set(d.get(loc, []) + rnds))

    return res

# ── Carrier / scenario configs ────────────────────────────────────
VZ_CARRIERS = OrderedDict([
    ('HA',  {'boston_dir': os.path.join(VZ_DIR, 'iperf', 'boston', 'HA'),
             'atlanta_dir': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'HA'),
             'provider':'main',      'color':'#E24A33', 'hatch':'/////'}),
    ('VA1', {'boston_dir': os.path.join(VZ_DIR, 'iperf', 'boston', 'VA1'),
             'atlanta_dir': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'VA1'),
             'provider':'virtual_1', 'color':'#348ABD', 'hatch':'\\\\\\\\\\'}),
    ('VA2', {'boston_dir': os.path.join(VZ_DIR, 'iperf', 'boston', 'VA2'),
             'atlanta_dir': os.path.join(VZ_DIR, 'iperf', 'atlanta', 'VA2'),
             'provider':'virtual_2', 'color':'#FBC15E', 'hatch':'xxxxx'}),
])
VZ_SCENARIOS = OrderedDict([
    ('solo',    {'folders': OrderedDict([('HA','M'),('VA1','V1'),('VA2','V2')]),       'label':'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HA','M+V1'),('VA1','M+V1')]),               'label':'HA vs\nVA1'}),
    ('M+V2',    {'folders': OrderedDict([('HA','M+V2'),('VA2','M+V2')]),               'label':'HA vs\nVA2'}),
    ('V1+V2',   {'folders': OrderedDict([('VA1','V1+V2'),('VA2','V1+V2')]),            'label':'VA1 vs\nVA2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HA','M+V1+V2'),('VA1','M+V1+V2'),('VA2','M+V1+V2')]), 'label':'HA vs VA1\nvs VA2'}),
])

AT_CARRIERS = OrderedDict([
    ('HB',  {'boston_dir': os.path.join(AT_DIR, 'iperf', 'boston', 'HB'),
             'atlanta_dir': os.path.join(AT_DIR, 'iperf', 'atlanta', 'HB'),
             'provider':'main',      'color':'#E24A33', 'hatch':'/////'}),
    ('VB1', {'boston_dir': os.path.join(AT_DIR, 'iperf', 'boston', 'VB1'),
             'atlanta_dir': os.path.join(AT_DIR, 'iperf', 'atlanta', 'VB1'),
             'provider':'virtual_1', 'color':'#348ABD', 'hatch':'\\\\\\\\\\'}),
    ('VB2', {'boston_dir': os.path.join(AT_DIR, 'iperf', 'boston', 'VB2'),
             'atlanta_dir': os.path.join(AT_DIR, 'iperf', 'atlanta', 'VB2'),
             'provider':'virtual_2', 'color':'#FBC15E', 'hatch':'xxxxx'}),
])
AT_SCENARIOS = OrderedDict([
    ('solo',    {'folders': OrderedDict([('HB','M'),('VB1','V1'),('VB2','V2')]),       'label':'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HB','M+V1'),('VB1','M+V1')]),               'label':'HB vs\nVB1'}),
    ('M+V2',    {'folders': OrderedDict([('HB','M+V2'),('VB2','M+V2')]),               'label':'HB vs\nVB2'}),
    ('V1+V2',   {'folders': OrderedDict([('VB1','V1+V2'),('VB2','V1+V2')]),            'label':'VB1 vs\nVB2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HB','M+V1+V2'),('VB1','M+V1+V2'),('VB2','M+V1+V2')]), 'label':'HB vs VB1\nvs VB2'}),
])

TM_CARRIERS = OrderedDict([
    ('HC',  {'dl_boston': os.path.join(TM_DIR, 'iperf', 'boston', 'HC'),
             'ul_boston': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'HC'),
             'philly':    os.path.join(TM_DIR, 'iperf', 'philadelphia', 'HC'),
             'provider':'main',      'color':'#E24A33', 'hatch':'/////'}),
    ('VC1', {'dl_boston': os.path.join(TM_DIR, 'iperf', 'boston', 'VC1'),
             'ul_boston': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC1'),
             'philly':    os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC1'),
             'provider':'virtual_1', 'color':'#348ABD', 'hatch':'\\\\\\\\\\'}),
    ('VC2', {'dl_boston': os.path.join(TM_DIR, 'iperf', 'boston', 'VC2'),
             'ul_boston': os.path.join(TM_DIR, 'iperf', 'boston_uplink', 'VC2'),
             'philly':    os.path.join(TM_DIR, 'iperf', 'philadelphia', 'VC2'),
             'provider':'virtual_2', 'color':'#FBC15E', 'hatch':'xxxxx'}),
])
TM_SCENARIOS = OrderedDict([
    ('solo',    {'folders': OrderedDict([('HC','M'),('VC1','V1'),('VC2','V2')]),       'label':'Solo'}),
    ('M+V1',    {'folders': OrderedDict([('HC','M+V1'),('VC1','M+V1')]),               'label':'HC vs\nVC1'}),
    ('M+V2',    {'folders': OrderedDict([('HC','M+V2'),('VC2','M+V2')]),               'label':'HC vs\nVC2'}),
    ('V1+V2',   {'folders': OrderedDict([('VC1','V1+V2'),('VC2','V1+V2')]),            'label':'VC1 vs\nVC2'}),
    ('M+V1+V2', {'folders': OrderedDict([('HC','M+V1+V2'),('VC1','M+V1+V2'),('VC2','M+V1+V2')]), 'label':'HC vs VC1\nvs VC2'}),
])

# ── Data collection ───────────────────────────────────────────────
def collect_vz_at(scenarios, carriers, pci_ranges, direction):
    """Collect all iperf samples for VZ or AT family."""
    result = {sc: {c: [] for c in cfg['folders']}
              for sc, cfg in scenarios.items()}
    for sc, sc_cfg in scenarios.items():
        ranges = pci_ranges[direction].get(sc, {})
        for city in ('boston', 'atlanta'):
            for loc in sorted(ranges.get(city, {}).keys()):
                for rnd in ranges[city][loc]:
                    for carrier, folder in sc_cfg['folders'].items():
                        cfg = carriers[carrier]
                        base = cfg['boston_dir'] if city == 'boston' else cfg['atlanta_dir']
                        result[sc][carrier].extend(
                            get_samples(base, loc, rnd, folder, cfg['provider'], direction))
    return result

def collect_tm(scenarios, carriers, pci_ranges, direction):
    """Collect all iperf samples for Family C family."""
    cities = ('dl_boston', 'philly') if direction == 'downlink' else ('ul_boston', 'philly')
    result = {sc: {c: [] for c in cfg['folders']}
              for sc, cfg in scenarios.items()}
    for sc, sc_cfg in scenarios.items():
        ranges = pci_ranges[direction].get(sc, {})
        for city in cities:
            for loc in sorted(ranges.get(city, {}).keys(), key=str):
                for rnd in ranges[city][loc]:
                    for carrier, folder in sc_cfg['folders'].items():
                        cfg = carriers[carrier]
                        result[sc][carrier].extend(
                            get_samples(cfg[city], loc, rnd, folder, cfg['provider'], direction))
    return result

# ── Boxplot drawing ───────────────────────────────────────────────
def draw_panel(ax, scenarios, carriers, carrier_data, ylabel, show_legend,
               panel_label=None, legend_loc='upper right', skip_empty=False):
    # skip_empty: draw nothing for a carrier with no samples instead of a
    # degenerate box at 0, which would read as "measured zero" rather than
    # "no data". The scenario keeps its x-axis label either way.
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
            if not vals and skip_empty:
                continue
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

    if panel_label:
        ax.text(0.03, 0.97, panel_label, transform=ax.transAxes,
                fontsize=9.5, va='top', fontstyle='italic')

    if show_legend:
        handles = [mpatches.Patch(facecolor=carriers[c]['color'], alpha=0.80,
                                  hatch=carriers[c]['hatch'], edgecolor='black',
                                  linewidth=0.6, label=c)
                   for c in carriers]
        ax.legend(handles=handles, ncol=len(carriers), loc=legend_loc,
                  framealpha=0.85, handletextpad=0.3, columnspacing=0.5,
                  handlelength=1.2, borderpad=0.4)

# ── Figure generator ──────────────────────────────────────────────
def make_single_figure(fname, scenarios, carriers, data, direction_label,
                       legend_loc='upper right'):
    """Save one single-panel boxplot figure (Same PCI or Diff PCI)."""
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(1, 1, figsize=(5.2, 2.4))

    ylabel = f'{direction_label} Throughput (Mbps)'
    draw_panel(ax, scenarios, carriers, data, ylabel, show_legend=True,
               panel_label=None, legend_loc=legend_loc)

    fig.tight_layout(pad=0.4)
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {path}')

# ── Main ─────────────────────────────────────────────────────────
print('Parsing valid_data_range.txt files…')
vz_pci = parse_pci_ranges(os.path.join(VZ_DIR, 'valid_data_range.txt'), 'vz')
at_pci = parse_pci_ranges(os.path.join(AT_DIR, 'valid_data_range.txt'), 'at')
tm_pci = parse_pci_ranges(os.path.join(TM_DIR, 'valid_data_range.txt'), 'tm')

for direction, dlabel in [('downlink', 'DL'), ('uplink', 'UL')]:
    print(f'\n── {dlabel} ─────────────────────────────────')

    # Family A — Family A
    print('  Family A (Family A)…')
    same_d = collect_vz_at(VZ_SCENARIOS, VZ_CARRIERS, vz_pci['same'], direction)
    diff_d = collect_vz_at(VZ_SCENARIOS, VZ_CARRIERS, vz_pci['diff'], direction)
    make_single_figure(f'A_5G_PCI_Same_{dlabel}.png', VZ_SCENARIOS, VZ_CARRIERS, same_d, dlabel)
    # Diff-PCI DL: tall boxes at the right end collide with an upper-right legend
    make_single_figure(f'A_5G_PCI_Diff_{dlabel}.png', VZ_SCENARIOS, VZ_CARRIERS, diff_d, dlabel,
                       legend_loc='lower right' if dlabel == 'DL' else 'upper right')

    # Family B — Family B
    print('  Family B (Family B)…')
    same_d = collect_vz_at(AT_SCENARIOS, AT_CARRIERS, at_pci['same'], direction)
    diff_d = collect_vz_at(AT_SCENARIOS, AT_CARRIERS, at_pci['diff'], direction)
    make_single_figure(f'B_5G_PCI_Same_{dlabel}.png', AT_SCENARIOS, AT_CARRIERS, same_d, dlabel)
    make_single_figure(f'B_5G_PCI_Diff_{dlabel}.png', AT_SCENARIOS, AT_CARRIERS, diff_d, dlabel)

    # Family C — Family C
    print('  Family C (Family C)…')
    same_d = collect_tm(TM_SCENARIOS, TM_CARRIERS, tm_pci['same'], direction)
    diff_d = collect_tm(TM_SCENARIOS, TM_CARRIERS, tm_pci['diff'], direction)
    make_single_figure(f'C_5G_PCI_Same_{dlabel}.png', TM_SCENARIOS, TM_CARRIERS, same_d, dlabel)
    make_single_figure(f'C_5G_PCI_Diff_{dlabel}.png', TM_SCENARIOS, TM_CARRIERS, diff_d, dlabel)

print('\nDone.')
