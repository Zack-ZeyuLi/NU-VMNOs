#!/usr/bin/env python3
"""
City comparison figures with both cities merged into a single panel.

Replaces the previous pair of stacked per-city subfigures. Each panel keeps the
five competition scenarios and the three operators, and adds the city as a
second grouping level, so one legend serves the whole figure.

Two size variants are produced:
  *_half.png  — intended to sit at 0.49\\linewidth (two panels per figure row)
  *_full.png  — intended to sit at \\linewidth (one panel per figure)
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))
src = open(os.path.join(ROOT, 'generate_city_boxplots.py')).read()
g = {'__file__': os.path.join(ROOT, 'generate_city_boxplots.py')}
exec(src[:src.index('TASKS = [')], g)

OUT_DIR = g['OUT_DIR']
collect_vz_at, collect_tm = g['collect_vz_at'], g['collect_tm']
parse_ranges = g['parse_ranges']
VZ_DIR, AT_DIR, TM_DIR = g['VZ_DIR'], g['AT_DIR'], g['TM_DIR']

FAMILIES = [
    ('A', g['VZ_SCENARIOS'], g['VZ_CARRIERS'],
     parse_ranges(os.path.join(VZ_DIR, 'valid_data_range.txt'), 'vz')['all_valid'],
     {'downlink': [('boston', 'Boston'), ('atlanta', 'Atlanta')],
      'uplink':   [('boston', 'Boston'), ('atlanta', 'Atlanta')]}, collect_vz_at),
    ('B', g['AT_SCENARIOS'], g['AT_CARRIERS'],
     parse_ranges(os.path.join(AT_DIR, 'valid_data_range.txt'), 'at')['all_valid'],
     {'downlink': [('boston', 'Boston'), ('atlanta', 'Atlanta')],
      'uplink':   [('boston', 'Boston'), ('atlanta', 'Atlanta')]}, collect_vz_at),
    ('C', g['TM_SCENARIOS'], g['TM_CARRIERS'],
     parse_ranges(os.path.join(TM_DIR, 'valid_data_range.txt'), 'tm').get('qci677', {}),
     {'downlink': [('dl_boston', 'Boston'), ('philly', 'Philadelphia')],
      'uplink':   [('ul_boston', 'Boston'), ('philly', 'Philadelphia')]}, collect_tm),
]

# ── size variants ────────────────────────────────────────────────────────────
# 'half' is rendered small so that, once LaTeX scales it to 0.49\linewidth,
# the glyphs land at roughly the same physical size as the full-width figures.
VARIANTS = {
    'half': dict(figsize=(2.9, 1.26), font=6.5, tick=5.5, lab=6.5, leg=6.0,
                 boxw=0.16, intra=0.02, city=0.16, inter=0.34, lw=0.4, ms=1.0),
    'full': dict(figsize=(5.2, 2.16), font=8.0, tick=10.0, lab=9.0, leg=8.0,
                 boxw=0.20, intra=0.03, city=0.32, inter=0.46, lw=0.6, ms=1.5),
}


def draw(ax, scenarios, carriers, per_city, cities, ylabel, v):
    pos, data, cols, hats = [], [], [], []
    group_centres, city_ticks = [], []
    x = 0.0
    for sc, cfg in scenarios.items():
        ops = [c for c in cfg['folders'] if c in carriers]
        sc_start = x
        for ci, (ckey, _) in enumerate(cities):
            block_start = x
            for op in ops:
                vals = [t for t in per_city[ckey][sc].get(op, []) if t is not None]
                pos.append(x)
                data.append(vals if vals else [0])
                cols.append(carriers[op]['color'])
                hats.append(carriers[op]['hatch'])
                x += v['boxw'] + v['intra']
            city_ticks.append(((block_start + x - v['boxw'] - v['intra']) / 2, ci))
            if ci == 0:
                x += v['city']
        group_centres.append(((sc_start + x - v['boxw'] - v['intra']) / 2,
                              cfg['label']))
        x += v['inter']

    bp = ax.boxplot(data, positions=pos, widths=v['boxw'], patch_artist=True,
                    whis=(5, 95), showfliers=True,
                    medianprops=dict(color='black', linewidth=v['lw'] * 1.6),
                    whiskerprops=dict(linewidth=v['lw'], linestyle='--'),
                    capprops=dict(linewidth=v['lw']),
                    boxprops=dict(linewidth=v['lw']),
                    flierprops=dict(marker='o', markersize=v['ms'], linewidth=0.3,
                                    markerfacecolor='gray', markeredgecolor='gray',
                                    alpha=0.5))
    for p, c, h in zip(bp['boxes'], cols, hats):
        p.set_facecolor(c); p.set_alpha(0.80)
        p.set_hatch(h);     p.set_edgecolor('black'); p.set_linewidth(v['lw'])

    # city label under each block, scenario label below that
    ax.set_xticks([c for c, _ in city_ticks])
    ax.set_xticklabels([cities[i][1][:3] for _, i in city_ticks],
                       fontsize=v['tick'] + 0.5)
    ax.tick_params(axis='x', length=0, pad=1)
    for cx, lab in group_centres:
        ax.text(cx, -0.13, lab, transform=
                ax.get_xaxis_transform(), ha='center', va='top',
                fontsize=v['tick'], fontweight='bold')

    ax.set_xlim(-0.25, x - v['inter'] + v['boxw'])
    ax.set_ylim(bottom=0)
    ax.set_ylabel(ylabel, fontsize=v['lab'], fontweight='bold')
    ax.tick_params(axis='y', labelsize=v['tick'])
    ax.grid(axis='y', alpha=0.3, linewidth=0.4)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)


def build(fam, scenarios, carriers, ranges, cities_by_dir, collect, variant):
    v = VARIANTS[variant]
    plt.rcParams.update(g['RC'])
    for direction, dl in (('downlink', 'DL'), ('uplink', 'UL')):
        cities = cities_by_dir[direction]
        per_city = {ck: collect(scenarios, carriers,
                                ranges.get(direction, {}), ck, direction)
                    for ck, _ in cities}
        fig, ax = plt.subplots(1, 1, figsize=v['figsize'])
        draw(ax, scenarios, carriers, per_city, cities,
             f'{dl} Throughput (Mbps)', v)
        handles = [mpatches.Patch(facecolor=carriers[c]['color'], alpha=0.80,
                                  hatch=carriers[c]['hatch'], edgecolor='black',
                                  linewidth=v['lw'], label=c) for c in carriers]
        ax.legend(handles=handles, ncol=len(carriers), loc='upper right',
                  fontsize=v['leg'], framealpha=0.85, handletextpad=0.25,
                  columnspacing=0.4, handlelength=1.1, borderpad=0.3)
        fig.tight_layout(pad=0.3)
        path = os.path.join(OUT_DIR, f'{fam}_CityMerged_{dl}_{variant}.png')
        fig.savefig(path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        print('  Saved:', os.path.basename(path))


if __name__ == '__main__':
    for variant in ('half', 'full'):
        print(f'\n── {variant} ──')
        for fam, sc, ca, rg, cb, col in FAMILIES:
            build(fam, sc, ca, rg, cb, col, variant)
    print('\nDone.')
