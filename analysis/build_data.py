"""Rebuild data.js and hourly.js from the silkier-muses/raes archive.

Usage:
    python analysis/build_data.py /path/to/raes-checkout [output-dir]

Reads results.csv and source_data.zip (hourly_activity.csv.gz) from the raes
checkout, reproduces the repository's per-incident statistics to machine
precision, adds the site-wide, chance-model and placebo computations shown
on the page, and writes data.js and hourly.js into output-dir (default: the
repository root). Needs numpy and pandas.
"""
import json, math, sys, zipfile, io
from pathlib import Path
import numpy as np, pandas as pd

RAES = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else Path(__file__).resolve().parent.parent
H = pd.Timedelta(hours=1); DAY = pd.Timedelta(days=1)
ANCHORS = {'Sasovo': pd.Timestamp('2026-10-08T00:00'), 'Kaluga': pd.Timestamp('2026-10-09T03:00'), 'Vladimir': pd.Timestamp('2026-10-11T01:00')}
EXCL = {pd.Timestamp('2026-10-07T19:00'), pd.Timestamp('2026-10-07T20:00')}   # documented Reddit outage
OFFS = [0, 27, 73]                                                             # hours between the three anchors
END = pd.Timestamp('2026-10-11T18:00')                                         # later hours are undercounted in the snapshot

with zipfile.ZipFile(RAES / 'source_data.zip') as z:
    hourly = pd.read_csv(io.BytesIO(z.read('hourly_activity.csv.gz')), compression='gzip')
hourly['t'] = pd.to_datetime(hourly['timestamp_utc'])
piv = hourly.pivot(index='t', columns='subreddit', values='posts_plus_comments')
res = pd.read_csv(RAES / 'results.csv')
el = res[res.eligible].subreddit.tolist()
P = piv[el]; idx = P.index; N = len(el)
L = np.log1p(P)
orig = res.set_index('subreddit').loc[el]

def refs(lags):
    """Adjusted log activity Z and arithmetic expected count E against same-hour lags."""
    Lx = pd.DataFrame(np.nan, index=idx, columns=el); Ex = Lx.copy()
    for t in idx:
        hs = [t - k * DAY for k in lags]
        if all(h in idx for h in hs):
            Lx.loc[t] = np.mean([L.loc[h].values for h in hs], axis=0)
            Ex.loc[t] = np.mean([P.loc[h].values for h in hs], axis=0)
    return L - Lx, Ex

Z3, E3 = refs((7, 14, 21)); Z2, E2 = refs((7, 14))
full = P.notna().all(axis=1); good_hours = set(idx[full])

def stat(anchor, Z, E, w=12):
    """The repository's per-incident r and % change for every subreddit (vectorised)."""
    tt = [anchor + i * H for i in range(-w, w)]; tt = [x for x in tt if x not in EXCL]
    if not all(x in good_hours for x in tt): return None
    z = Z.loc[tt]; e = E.loc[tt]; O = P.loc[tt]
    if e.isna().all().all(): return None
    post = np.array([t >= anchor for t in tt]); x = post.astype(float); xc = x - x.mean()
    zv = z.values; yc = zv - zv.mean(axis=0, keepdims=True)
    cov = (yc * xc[:, None]).mean(axis=0); vx = (xc * xc).mean(); vy = (yc * yc).mean(axis=0)
    with np.errstate(all='ignore'):
        r = cov / np.sqrt(vx * vy)
        op = O[post].sum().values; ob = O[~post].sum().values; ep = e[post].sum().values; eb = e[~post].sum().values
        pct = 100 * ((op / ep) / (ob / eb) - 1)
    good = np.isfinite(r) & np.isfinite(pct) & (eb >= 20) & (ep >= 20) & (ob > 0) & (~np.isnan(zv).any(axis=0))
    return pd.DataFrame({'r': r, 'pct': pct, 'good': good, 'op': op, 'ob': ob, 'ep': ep, 'eb': eb}, index=el)

out = {}
# site-wide hourly totals and expectation
tot = P.sum(axis=1)[full]; expt = E3.sum(axis=1)[full]
out['hourly'] = [dict(t=t.isoformat(timespec='minutes'), obs=int(tot[t]), exp=round(float(expt[t]), 1))
                 for t in tot.index if not np.isnan(expt[t]) and pd.Timestamp('2026-10-03') <= t <= END]
out['daily'] = [dict(date=str(d), total=int(v)) for d, v in tot.groupby(tot.index.date).sum().items()
                if '2026-09-12' <= str(d) <= '2026-10-11']
# reproduce the repository's nominal statistics and build the chance model
real = {n: stat(a, Z3, E3) for n, a in ANCHORS.items()}
for n, k in zip(ANCHORS, ['sasovo', 'kaluga', 'vladimir']):
    assert np.nanmax(np.abs(real[n].r - orig[k + '_r'])) < 1e-9 and np.nanmax(np.abs(real[n].pct - orig[k + '_pct'])) < 1e-8, 'reproduction failed'
p = [float(((s.r < 0) & (s.pct < 0))[s.good].mean()) for s in real.values()]; pm = float(np.mean(p))
out['binomial'] = dict(n=N, p_each={n: round(v, 4) for n, v in zip(ANCHORS, p)},
    observed={int(k): int(v) for k, v in orig.decreases.value_counts().sort_index().items()},
    expected_indep={k: round(N * math.comb(3, k) * pm ** k * (1 - pm) ** (3 - k), 1) for k in range(4)},
    expected_product3=round(N * p[0] * p[1] * p[2], 1),
    site_ratio={n: dict(pre=round(float(s.ob.sum() / s.eb.sum()), 4), post=round(float(s.op.sum() / s.ep.sum()), 4)) for n, s in real.items()},
    median_pct={n: round(float(s.pct[s.good].median()), 2) for n, s in real.items()})
# placebo: the decrease rule at every feasible anchor hour (three-week baseline)
rows = []
for a in idx:
    if a < pd.Timestamp('2026-10-03T12:00') or a > pd.Timestamp('2026-10-11T06:00'): continue
    s = stat(a, Z3, E3)
    if s is None: continue
    g = s[s.good]
    if len(g) < 900: continue
    rows.append(dict(t=a.isoformat(timespec='minutes'), frac_dec=round(float(((g.r < 0) & (g.pct < 0)).mean()), 4),
                     median_pct=round(float(g.pct.median()), 2), site=round(float((g.op.sum() / g.ep.sum()) / (g.ob.sum() / g.eb.sum())), 4)))
out['placebo_single'] = rows
# placebo: the three-window layout shifted earlier (two-week baseline so placements fit before Oct 7)
def triplets(Z, E, kmax):
    b = ANCHORS['Sasovo']; res_ = []
    for k in range(0, kmax + 1):
        aa = [b - k * H + o * H for o in OFFS]; ss = [stat(a, Z, E) for a in aa]
        if any(s is None for s in ss): continue
        ok = np.ones(N, bool); d = np.zeros(N, int)
        for s in ss: ok &= s.good.values; d += ((s.r < 0) & (s.pct < 0)).values
        if ok.sum() < 900: continue
        res_.append(dict(shift_h=k, all3=int((ok & (d == 3)).sum()), clean=bool(aa[2] + 12 * H <= pd.Timestamp('2026-10-07T12:00'))))
    return res_
t2 = triplets(Z2, E2, 400); t3 = triplets(Z3, E3, 200)
out['placebo_triplets'] = dict(counts=[r['all3'] for r in t2 if r['clean']], real_2lag=[r for r in t2 if r['shift_h'] == 0][0]['all3'],
                               real_3lag=int((orig.decreases == 3).sum()), clean3=[r['all3'] for r in t3 if r['clean']])
# per-subreddit summary (the repository's own values)
out['funnel'] = [dict(s=s, b=round(float(r.baseline_day), 2), r=None if np.isnan(r.pooled_r) else round(float(r.pooled_r), 3), d=int(r.decreases),
                      p=[round(float(r.sasovo_pct), 3), round(float(r.kaluga_pct), 3), round(float(r.vladimir_pct), 3)]) for s, r in orig.iterrows()]
big = orig[orig.baseline_day >= 3000].sort_values('pooled_r')
cols = ['baseline_day', 'pooled_r', 'sasovo_pct', 'kaluga_pct', 'vladimir_pct', 'decreases']
out['top_neg'] = big[cols].head(12).round(3).reset_index().to_dict('records')
out['top_pos'] = big[cols].tail(12).round(3).reset_index().to_dict('records')
(OUT / 'data.js').write_text('window.RAES=' + json.dumps(out, separators=(',', ':')) + ';\n')
# hourly observed (whole month) and expected (from Oct 3) for every eligible subreddit
obs_rng = idx[(idx >= pd.Timestamp('2026-09-12')) & (idx <= pd.Timestamp('2026-10-11T23:00'))]
exp_rng = idx[(idx >= pd.Timestamp('2026-10-03')) & (idx <= pd.Timestamp('2026-10-11T23:00'))]
hd = {'t0': '2026-09-12T00:00', 'n_obs': len(obs_rng), 'exp_start_index': int(list(obs_rng).index(exp_rng[0])), 'subs': {}}
for s in el:
    hd['subs'][s] = [P.loc[obs_rng, s].fillna(0).astype(int).tolist(), [round(float(x), 1) for x in E3.loc[exp_rng, s].tolist()]]
(OUT / 'hourly.js').write_text('window.RAES_HOURLY=' + json.dumps(hd, separators=(',', ':')) + ';\n')
print('wrote', OUT / 'data.js', OUT / 'hourly.js', '| eligible', N, '| fell 3x', out['placebo_triplets']['real_3lag'], '| chance', out['binomial']['expected_product3'])
