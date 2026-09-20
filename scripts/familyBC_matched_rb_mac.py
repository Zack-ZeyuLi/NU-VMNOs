#!/usr/bin/env python3
"""
Families B and C: RB allocation and MAC-layer throughput under a fully matched
radio context -- same PCI *and* same NR-ARFCN *and* same channel bandwidth.

Same method as familyA_matched_rb_mac.py, but these radio logs carry a
datetime TIME_STAMP instead of a Unix epoch:

    raw_data/family_b/xcal/{HB,VB1,VB2}_{BOS,ATL}_RBs.csv
    raw_data/family_c/xcal/{HC,VC1,VC2}_BOS_RBs.csv            (Boston, 1st visit)
    raw_data/family_c/xcal/{HC,VC1,VC2}_BOS_L2_L1_2nd_RBs.csv  (Boston, 2nd visit)
    raw_data/family_c/xcal/{HC,VC1,VC2}_BOS_UL_RBs.csv         (Boston, uplink)
    raw_data/family_c/xcal/{HC,VC1,VC2}_PHI_RBs.csv            (Philadelphia)

Family C is restricted to the QCI 677-type rounds only.

Produces 8 figures covering all five scenarios:
    B_Matched_{DL,UL}_{RB,MAC}.png
    C_Matched_QCI677_{DL,UL}_{RB,MAC}.png
"""

import os, re, csv, bisect, collections, datetime
import gzip
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW       = os.path.abspath(os.path.join(ROOT, os.pardir, 'raw_data'))

# ── Reuse the exact plotting style / parsers of the existing figures ─────────
def _load_prefix(fname, marker):
    src = open(os.path.join(ROOT, fname)).read()
    g = {'__file__': os.path.join(ROOT, fname)}
    exec(src[:src.index(marker)], g)
    return g

_g = _load_prefix('generate_pci_boxplots.py', '# ── Main ')
RC           = _g['RC']
draw_panel   = _g['draw_panel']
parse_pci    = _g['parse_pci_ranges']
AT_SCENARIOS = _g['AT_SCENARIOS'];  AT_CARRIERS = _g['AT_CARRIERS']
TM_SCENARIOS = _g['TM_SCENARIOS'];  TM_CARRIERS = _g['TM_CARRIERS']
AT_DIR       = _g['AT_DIR'];  TM_DIR = _g['TM_DIR'];  OUT_DIR = _g['OUT_DIR']

_gc = _load_prefix('generate_familyC_pci_qci_boxplots.py', 'qci_pci = ')
parse_tm_677 = _gc['parse_tm_qci677_pci']

RUN_SECONDS = 61
TSRE = re.compile(r'^(\d{13})_(downlink|uplink)_s\d+$')

H_PCI   = '5G KPI PCell RF Serving PCI'
H_ARFCN = '5G KPI PCell RF NR-ARFCN'
H_BW    = '5G KPI PCell RF BandWidth'
H_DLRB  = '5G KPI PCell Layer1 DL RB Num (Including 0)'
H_ULRB  = '5G KPI PCell Layer1 UL RB Num (Including 0)'
H_DLTP  = '5G KPI PCell Layer2 MAC DL Throughput [Mbps]'
H_ULTP  = '5G KPI PCell Layer2 MAC UL Throughput [Mbps]'

# ── Radio-log routing (one CSV per carrier x city) ──────────────────────────
# Family C accumulates the Boston 1st- and 2nd-visit logs into one dl_boston set,
# exactly as the original multi-sheet workbooks did.
LOG_FILES = {
    'B': {('HB','boston'):  ['HB_BOS_RBs.csv.gz'],  ('HB','atlanta'):  ['HB_ATL_RBs.csv.gz'],
          ('VB1','boston'): ['VB1_BOS_RBs.csv.gz'], ('VB1','atlanta'): ['VB1_ATL_RBs.csv.gz'],
          ('VB2','boston'): ['VB2_BOS_RBs.csv.gz'], ('VB2','atlanta'): ['VB2_ATL_RBs.csv.gz']},
    'C': {('HC','dl_boston'):  ['HC_BOS_RBs.csv.gz',  'HC_BOS_L2_L1_2nd_RBs.csv.gz'],
          ('HC','ul_boston'):  ['HC_BOS_UL_RBs.csv.gz'],  ('HC','philly'):  ['HC_PHI_RBs.csv.gz'],
          ('VC1','dl_boston'): ['VC1_BOS_RBs.csv.gz', 'VC1_BOS_L2_L1_2nd_RBs.csv.gz'],
          ('VC1','ul_boston'): ['VC1_BOS_UL_RBs.csv.gz'], ('VC1','philly'): ['VC1_PHI_RBs.csv.gz'],
          ('VC2','dl_boston'): ['VC2_BOS_RBs.csv.gz', 'VC2_BOS_L2_L1_2nd_RBs.csv.gz'],
          ('VC2','ul_boston'): ['VC2_BOS_UL_RBs.csv.gz'], ('VC2','philly'): ['VC2_PHI_RBs.csv.gz']},
}
XCAL_DIR = {'B': os.path.join(AT_DIR, 'xcal'), 'C': os.path.join(TM_DIR, 'xcal')}
H_TIME = 'TIME_STAMP'


def _dt(s):
    """Parse an XCAL 'YYYY-MM-DD HH:MM:SS[.fff]' stamp as a naive local time."""
    s = (s or '').strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def load_family_logs(family):
    """Returns {(carrier, city): (times[], recs[])} sorted by epoch."""
    acc = collections.defaultdict(list)
    for key, fnames in LOG_FILES[family].items():
        for fname in fnames:
            path = os.path.join(XCAL_DIR[family], fname)
            n = 0
            with gzip.open(path, 'rt', encoding='utf-8-sig', newline='') as fh:
                for row in csv.DictReader(fh):
                    t = _dt(row.get(H_TIME))
                    if t is None:
                        continue

                    def g(h):
                        v = (row.get(h) or '').strip()
                        try:
                            return float(v)
                        except ValueError:
                            return None

                    pci, arfcn, bw = g(H_PCI), g(H_ARFCN), g(H_BW)
                    if pci is None or arfcn is None or bw is None:
                        continue
                    acc[key].append((t.timestamp(),
                                     (int(pci), int(arfcn), int(bw),
                                      g(H_DLRB), g(H_ULRB), g(H_DLTP), g(H_ULTP))))
                    n += 1
            print('    %-28s -> %-4s %-10s  %d rows' % (fname, key[0], key[1], n))

    out = {}
    for key, rows in acc.items():
        rows.sort(key=lambda x: x[0])
        out[key] = ([r[0] for r in rows], [r[1] for r in rows])
    return out


# ── iperf run windows ───────────────────────────────────────────────────────
def op_base(carriers, carrier, city):
    cfg = carriers[carrier]
    if city in cfg:                       # Family C: dl_boston / ul_boston / philly
        return cfg[city]
    return cfg['boston_dir'] if city == 'boston' else cfg['atlanta_dir']


def run_window(carriers, carrier, city, loc, rnd, sc_folder, direction):
    cfg = carriers[carrier]
    d = os.path.join(op_base(carriers, carrier, city),
                     f'location_{loc}', f'round_{rnd}', sc_folder, cfg['provider'])
    if not os.path.isdir(d):
        return None
    for item in os.listdir(d):
        m = TSRE.match(item)
        if m and m.group(2) == direction:
            s = int(m.group(1)) / 1000.0
            return (s, s + RUN_SECONDS)
    return None


def fit_offset(times, windows):
    """Best whole-hour offset (seconds to subtract) maximising in-window samples."""
    if not times or not windows:
        return 0, 0.0
    starts = [a for a, _ in windows]
    best = (0, -1)
    for k in range(-26, 27):
        off = k * 3600
        hit = 0
        for t in times:
            x = t - off
            i = bisect.bisect_right(starts, x) - 1
            if i >= 0 and windows[i][0] <= x <= windows[i][1]:
                hit += 1
        if hit > best[1]:
            best = (off, hit)
    return best[0], 100.0 * best[1] / len(times)


# ── Collection ──────────────────────────────────────────────────────────────
def collect(direction, scenarios, carriers, ranges, logs, offsets):
    rb  = {sc: {c: [] for c in cfg['folders']} for sc, cfg in scenarios.items()}
    mac = {sc: {c: [] for c in cfg['folders']} for sc, cfg in scenarios.items()}
    stats = collections.Counter()
    kept = collections.defaultdict(list)

    for sc, sc_cfg in scenarios.items():
        for city, locs in ranges.get(sc, {}).items():
            for loc, rounds in locs.items():
                for rnd in rounds:
                    stats['rounds_same_pci'] += 1
                    per_op, ok = {}, True
                    for carrier in sc_cfg['folders']:
                        w = run_window(carriers, carrier, city, loc, rnd,
                                       sc_cfg['folders'][carrier], direction)
                        if w is None or (carrier, city) not in logs:
                            ok = False; break
                        t, r = logs[(carrier, city)]
                        off = offsets.get((carrier, city), 0)
                        lo = bisect.bisect_left(t, w[0] + off)
                        hi = bisect.bisect_right(t, w[1] + off)
                        if hi <= lo:
                            ok = False; break
                        per_op[carrier] = r[lo:hi]
                    if not ok:
                        stats['dropped_no_radio_samples'] += 1; continue

                    modes = {c: collections.Counter(
                                 (x[0], x[1], x[2]) for x in s).most_common(1)[0][0]
                             for c, s in per_op.items()}
                    if len(set(modes.values())) != 1:
                        if len({m[0] for m in modes.values()}) > 1:
                            stats['dropped_pci_mismatch'] += 1
                        elif len({m[1] for m in modes.values()}) > 1:
                            stats['dropped_arfcn_mismatch'] += 1
                        else:
                            stats['dropped_bw_mismatch'] += 1
                        continue

                    triple = next(iter(modes.values()))
                    stats['rounds_kept'] += 1
                    kept[sc].append((city, loc, rnd, triple))
                    for carrier, s in per_op.items():
                        for pci, arfcn, bw, dlrb, ulrb, dltp, ultp in s:
                            if (pci, arfcn, bw) != triple:
                                continue
                            v_rb, v_tp = (dlrb, dltp) if direction == 'downlink' else (ulrb, ultp)
                            if v_rb is not None: rb[sc][carrier].append(v_rb)
                            if v_tp is not None: mac[sc][carrier].append(v_tp)
    return rb, mac, stats, kept


def save_figure(fname, scenarios, carriers, data, ylabel, legend_loc='upper right',
                skip_empty=False):
    plt.rcParams.update(RC)
    fig, ax = plt.subplots(1, 1, figsize=(5.2, 2.4))
    draw_panel(ax, scenarios, carriers, data, ylabel,
               show_legend=True, panel_label=None, legend_loc=legend_loc,
               skip_empty=skip_empty)
    fig.tight_layout(pad=0.4)
    path = os.path.join(OUT_DIR, fname)
    fig.savefig(path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print('  Saved: %s' % path)


def run_family(fam, scenarios, carriers, ranges_for, prefix):
    print('\n' + '=' * 74)
    print('Family %s — loading radio logs' % fam)
    logs = load_family_logs(fam)

    # fit one whole-hour clock offset per (carrier, city)
    print('  clock offsets:')
    offsets = {}
    allwin = collections.defaultdict(list)
    for carrier in carriers:
        for (c, city) in logs:
            if c != carrier: continue
            for direction in ('downlink', 'uplink'):
                base = op_base(carriers, carrier, city)
                for dp, _, _ in os.walk(base):
                    m = TSRE.match(os.path.basename(dp))
                    if m and m.group(2) == direction:
                        s = int(m.group(1)) / 1000.0
                        allwin[(carrier, city)].append((s, s + RUN_SECONDS))
    for key, wins in allwin.items():
        wins.sort()
        off, pct = fit_offset(logs[key][0], wins)
        offsets[key] = off
        print('    %-4s %-10s offset=%+3d h  in-window %.1f%%' % (key[0], key[1], off // 3600, pct))

    for direction, dl in (('downlink', 'DL'), ('uplink', 'UL')):
        print('\n── Family %s %s: matched PCI + NR-ARFCN + bandwidth ──' % (fam, dl))
        rb, mac, stats, kept = collect(direction, scenarios, carriers,
                                       ranges_for(direction), logs, offsets)
        print('  round accounting: %s' % dict(stats))
        for sc, sc_cfg in scenarios.items():
            print('    %-18s rounds=%-3d samples=%s' % (
                sc_cfg['label'].replace('\n', ' '), len(kept[sc]),
                {c: len(rb[sc][c]) for c in sc_cfg['folders']}))
        # Family C downlink: two scenarios retain no matched round, so leave
        # those slots blank rather than drawing a degenerate box at zero.
        skip_empty = (fam == 'C' and direction == 'downlink')
        save_figure(f'{prefix}_{dl}_RB.png',  scenarios, carriers, rb,
                    f'{dl} PCell RB Count', skip_empty=skip_empty)
        save_figure(f'{prefix}_{dl}_MAC.png', scenarios, carriers, mac,
                    f'{dl} MAC Throughput (Mbps)', skip_empty=skip_empty)


if __name__ == '__main__':
    at_pci = parse_pci(os.path.join(AT_DIR, 'valid_data_range.txt'), 'at')
    run_family('B', AT_SCENARIOS, AT_CARRIERS,
               lambda d: at_pci['same'][d], 'B_Matched')

    tm_677 = parse_tm_677(os.path.join(TM_DIR, 'valid_data_range.txt'))
    run_family('C', TM_SCENARIOS, TM_CARRIERS,
               lambda d: tm_677[d]['same'], 'C_Matched_QCI677')
    print('\nDone.')
