#!/usr/bin/env python3
"""
Family A: RB allocation and MAC-layer throughput under a fully matched radio context.

Starting from the 5G-only *Same PCI* rounds listed in raw_data/family_a/valid_data_range.txt,
we additionally require that every operator participating in a round reports the
SAME NR-ARFCN and the SAME channel bandwidth as its rivals.  Only rounds passing
all three checks (PCI == ARFCN == BandWidth) are kept, so the comparison is made
within one physical cell, one carrier frequency and one bandwidth -- i.e. the
operators are genuinely served by the same scheduler on the same resource pool.

Radio samples come from the XCAL exports:
    HA_{BOS,ATL}_RBs.csv   VA1_{BOS,ATL}_RBs.csv   VA2_{BOS,ATL}_RBs.csv
and are aligned to each iperf run through the millisecond epoch embedded in the
test directory names.  Each XCAL log carries a constant whole-hour clock offset
(see CLOCK_OFFSET) that is removed before matching.

Produces 4 single-panel figures covering all five scenarios:
    A_Matched_DL_RB.png    A_Matched_DL_MAC.png
    A_Matched_UL_RB.png    A_Matched_UL_MAC.png
"""

import os, re, csv, bisect, collections
import gzip
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))

# ── Reuse the exact plotting style / parsing of the existing figures ──────────
# generate_pci_boxplots.py is a script; exec only the part above its main body
# so importing it does not regenerate the other 12 figures.
_src = open(os.path.join(ROOT, 'generate_pci_boxplots.py')).read()
_g = {'__file__': os.path.join(ROOT, 'generate_pci_boxplots.py')}
exec(_src[:_src.index('# ── Main ')], _g)

RC            = _g['RC']
draw_panel    = _g['draw_panel']
parse_pci     = _g['parse_pci_ranges']
VZ_SCENARIOS  = _g['VZ_SCENARIOS']
VZ_CARRIERS   = _g['VZ_CARRIERS']
VZ_DIR        = _g['VZ_DIR']
OUT_DIR       = _g['OUT_DIR']

# ── Per-log constant clock offset (seconds to SUBTRACT from the CSV epoch) ────
# Empirically fitted by maximising the fraction of radio samples that fall
# inside a known iperf window; every value came out an exact whole hour.
#   HA_BOS  +12 h  (that handset's XCAL clock was 13 h ahead of EST)
#   all others      -1 h  (systematic XCAL export offset)
CLOCK_OFFSET = {
    ('HA',  'boston'):  +12 * 3600,
    ('HA',  'atlanta'):  -1 * 3600,
    ('VA1', 'boston'):   -1 * 3600,
    ('VA1', 'atlanta'):  -1 * 3600,
    ('VA2', 'boston'):   -1 * 3600,
    ('VA2', 'atlanta'):  -1 * 3600,
}

CSV_FILE = {
    ('HA',  'boston'):  'HA_BOS_RBs.csv.gz',
    ('HA',  'atlanta'): 'HA_ATL_RBs.csv.gz',
    ('VA1', 'boston'):  'VA1_BOS_RBs.csv.gz',
    ('VA1', 'atlanta'): 'VA1_ATL_RBs.csv.gz',
    ('VA2', 'boston'):  'VA2_BOS_RBs.csv.gz',
    ('VA2', 'atlanta'): 'VA2_ATL_RBs.csv.gz',
}

C_TIME  = 'Unix TIME_STAMP'
C_PCI   = '5G KPI PCell RF Serving PCI'
C_ARFCN = '5G KPI PCell RF NR-ARFCN'
C_BW    = '5G KPI PCell RF BandWidth'
C_DLRB  = '5G KPI PCell Layer1 DL RB Num (Including 0)'
C_ULRB  = '5G KPI PCell Layer1 UL RB Num (Including 0)'
C_DLTP  = '5G KPI PCell Layer2 MAC DL Throughput [Mbps]'
C_ULTP  = '5G KPI PCell Layer2 MAC UL Throughput [Mbps]'

RUN_SECONDS = 61          # one iperf run lasts 60 s; allow 1 s of slack
TSRE = re.compile(r'^(\d{13})_(downlink|uplink)_s\d+$')


# ── Radio logs ───────────────────────────────────────────────────────────────
def load_log(carrier, city):
    """Return (times[], records[]) sorted by corrected epoch."""
    path = os.path.join(VZ_DIR, 'xcal', CSV_FILE[(carrier, city)])
    off = CLOCK_OFFSET[(carrier, city)]
    times, recs = [], []
    with gzip.open(path, 'rt', encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            t = (row.get(C_TIME) or '').strip()
            if not t.isdigit():
                continue
            def num(col):
                v = (row.get(col) or '').strip()
                try:
                    return float(v)
                except ValueError:
                    return None
            pci, arfcn, bw = num(C_PCI), num(C_ARFCN), num(C_BW)
            if pci is None or arfcn is None or bw is None:
                continue                      # no serving-cell info on this row
            times.append(int(t) - off)
            recs.append((int(pci), int(arfcn), int(bw),
                         num(C_DLRB), num(C_ULRB), num(C_DLTP), num(C_ULTP)))
    order = sorted(range(len(times)), key=times.__getitem__)
    return [times[i] for i in order], [recs[i] for i in order]


def slice_window(times, recs, t0, t1):
    lo = bisect.bisect_left(times, t0)
    hi = bisect.bisect_right(times, t1)
    return recs[lo:hi]


# ── iperf run windows ────────────────────────────────────────────────────────
def run_window(carrier, city, loc, rnd, sc_folder, direction):
    cfg = VZ_CARRIERS[carrier]
    base = cfg['boston_dir'] if city == 'boston' else cfg['atlanta_dir']
    d = os.path.join(base, f'location_{loc}', f'round_{rnd}',
                     sc_folder, cfg['provider'])
    if not os.path.isdir(d):
        return None
    for item in os.listdir(d):
        m = TSRE.match(item)
        if m and m.group(2) == direction:
            s = int(m.group(1)) / 1000.0
            return (s, s + RUN_SECONDS)
    return None


# ── Main collection ──────────────────────────────────────────────────────────
def collect(direction):
    """Returns (rb_data, mac_data, stats) keyed [scenario][carrier] -> [values]."""
    pci_ranges = parse_pci(os.path.join(VZ_DIR, 'valid_data_range.txt'), 'vz')
    same = pci_ranges['same'][direction]

    logs = {}
    for key in CSV_FILE:
        logs[key] = load_log(*key)

    rb  = {sc: {c: [] for c in cfg['folders']} for sc, cfg in VZ_SCENARIOS.items()}
    mac = {sc: {c: [] for c in cfg['folders']} for sc, cfg in VZ_SCENARIOS.items()}
    stats = collections.Counter()
    kept_rounds = collections.defaultdict(list)

    for sc, sc_cfg in VZ_SCENARIOS.items():
        carriers_in = list(sc_cfg['folders'])
        for city, locs in same.get(sc, {}).items():
            for loc, rounds in locs.items():
                for rnd in rounds:
                    stats['rounds_same_pci'] += 1

                    per_op = {}
                    ok = True
                    for carrier in carriers_in:
                        w = run_window(carrier, city, loc, rnd,
                                       sc_cfg['folders'][carrier], direction)
                        if w is None:
                            ok = False; break
                        t, r = logs[(carrier, city)]
                        s = slice_window(t, r, *w)
                        if not s:
                            ok = False; break
                        per_op[carrier] = s
                    if not ok:
                        stats['dropped_no_radio_samples'] += 1
                        continue

                    # modal (PCI, ARFCN, BW) for each operator in this round
                    modes = {}
                    for carrier, s in per_op.items():
                        cnt = collections.Counter((x[0], x[1], x[2]) for x in s)
                        modes[carrier] = cnt.most_common(1)[0][0]

                    triples = set(modes.values())
                    if len(triples) != 1:
                        # decide which of the three fields disagreed (for reporting)
                        if len({m[0] for m in modes.values()}) > 1:
                            stats['dropped_pci_mismatch'] += 1
                        elif len({m[1] for m in modes.values()}) > 1:
                            stats['dropped_arfcn_mismatch'] += 1
                        else:
                            stats['dropped_bw_mismatch'] += 1
                        continue

                    triple = triples.pop()
                    stats['rounds_kept'] += 1
                    kept_rounds[sc].append((city, loc, rnd, triple))

                    for carrier, s in per_op.items():
                        for pci, arfcn, bw, dlrb, ulrb, dltp, ultp in s:
                            if (pci, arfcn, bw) != triple:
                                continue        # drop handover excursions
                            if direction == 'downlink':
                                if dlrb is not None: rb[sc][carrier].append(dlrb)
                                if dltp is not None: mac[sc][carrier].append(dltp)
                            else:
                                if ulrb is not None: rb[sc][carrier].append(ulrb)
                                if ultp is not None: mac[sc][carrier].append(ultp)

    return rb, mac, stats, kept_rounds


def save_figure(fname, data, ylabel, legend_loc='upper right'):
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(1, 1, figsize=(5.2, 2.4))
    draw_panel(ax, VZ_SCENARIOS, VZ_CARRIERS, data, ylabel,
               show_legend=True, panel_label=None, legend_loc=legend_loc)
    fig.tight_layout(pad=0.4)
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f'  Saved: {path}')


if __name__ == '__main__':
    for direction, dl in (('downlink', 'DL'), ('uplink', 'UL')):
        print(f'\n── {dl}: matched PCI + NR-ARFCN + bandwidth ──────────────')
        rb, mac, stats, kept = collect(direction)

        print('  round accounting: %s' % dict(stats))
        for sc, sc_cfg in VZ_SCENARIOS.items():
            rows = kept[sc]
            n = {c: len(rb[sc][c]) for c in sc_cfg['folders']}
            cells = sorted({t for *_, t in rows})
            print('    %-18s rounds=%-3d samples=%s' %
                  (sc_cfg['label'].replace('\n', ' '), len(rows), n))
            for c in cells:
                print('        cell PCI=%d ARFCN=%d BW=%d MHz' % c)

        save_figure(f'A_Matched_{dl}_RB.png',  rb,
                    f'{dl} PCell RB Count')
        save_figure(f'A_Matched_{dl}_MAC.png', mac,
                    f'{dl} MAC Throughput (Mbps)')
    print('\nDone.')
