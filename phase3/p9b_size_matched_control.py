"""
p9b_size_matched_control.py
Destination:  C:\\Users\\user\\gmppt\\phase3\\p9b_size_matched_control.py
Run from:     C:\\Users\\user\\gmppt>  python phase3\\p9b_size_matched_control.py

WHY THIS RUN EXISTS
-------------------
P9 found that holding out whole_substring degrades mean loss by 2.84x while
holding out sub_substring degrades it by 1.25x. Holding out whole_substring
also leaves the smallest training set (8,852 rows against 9,562 and 13,646).

Two explanations are consistent with that: the geometry was absent, or the
training set was smaller. P9 did not hold training volume equal, so it cannot
distinguish them. This run does.

No re-simulation. No opening of the held-out test set.

DESIGN — three arms, one evaluation set
---------------------------------------
For each geometry G, scored on the SAME validation rows with geometry == G:

    full     train on all TRAIN rows (16,030), all geometries
    matched  train on a random subsample of TRAIN of size n_G, all geometries
    unseen   train on the n_G TRAIN rows with geometry != G

where n_G is the row count P9 used for that holdout, so `matched` and `unseen`
differ only in whether geometry G is present.

DECOMPOSITION, DECLARED BEFORE THE RUN
--------------------------------------
    volume effect   = matched - full
    geometry effect = unseen  - matched

D1  Training volume is the explanation for geometry G if the volume effect
    accounts for at least 60% of the total gap (unseen - full).

D2  Geometry absence is the explanation if the geometry effect accounts for at
    least 60% of the total gap.

D3  Where neither reaches 60%, the cause is reported as mixed. No single-cause
    claim is made.

D4  The `matched` arm is repeated over N_REPEATS independent subsample draws.
    The subsample draw is the stochastic element here, and it is a real
    variance source -- unlike the model seed, which per defect D8 does nothing
    under these estimator settings. The spread across draws is reported, and a
    geometry effect smaller than that spread is not claimed as an effect.

D5  The verdict is reported per geometry. Uniform is included for completeness
    but its losses sit near zero, so its percentages are reported without a
    causal claim.
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gmppt import dataset as ds
from gmppt import model as mdl

OUT_CSV = ROOT / "results" / "phase3" / "p9b_size_matched_control.csv"

N_REPEATS = 5
SUBSAMPLE_SEED = 20260901
ATTRIB_THRESHOLD = 0.60

FEATS = list(ds.FEATURE_NAMES)
RULE = "=" * 78


def head(t):
    print("\n" + RULE)
    print(t)
    print(RULE)


head("Load")
df, curves = ds.load(tag="full")
df = df.reset_index(drop=True)
if "row_id" not in df.columns:
    df["row_id"] = np.arange(len(df))

split = ds.module_split(val_fraction=ds.VAL_FRACTION_OF_TRAIN)
train_mods, val_mods = set(split.train), set(split.val)
df["_split"] = np.where(
    df["module"].isin(train_mods), "train",
    np.where(df["module"].isin(val_mods), "val", "test"),
)
TR = df[df["_split"] == "train"].copy()
VA = df[df["_split"] == "val"].copy()
GEOMS = sorted(df["geometry"].unique())
print(f"  train rows {len(TR)}   val rows {len(VA)}   test untouched")


def mean_loss(model, frame):
    X = frame[FEATS].to_numpy(dtype=float)
    k_pred = np.asarray(model.predict_k(X), dtype=float)
    rows = frame["row_id"].to_numpy()
    p_gmpp = frame["p_gmpp"].to_numpy(dtype=float)
    p_at = np.asarray(ds.power_at_k(curves, rows, k_pred), dtype=float)
    watts = np.maximum(p_gmpp - p_at, 0.0)
    pct = 100.0 * watts / p_gmpp
    return float(pct.mean()), float(np.percentile(pct, 99)), float(watts.max())


head("Full control (all TRAIN rows, all geometries)")
t0 = time.time()
full_model = mdl.train(TR, verbose=False)
print(f"  trained on {len(TR)} rows in {time.time() - t0:.1f} s")

records = []
rng = np.random.default_rng(SUBSAMPLE_SEED)

for g in GEOMS:
    head(f"Geometry: {g}")
    ev = VA[VA["geometry"] == g]
    tr_unseen = TR[TR["geometry"] != g]
    n_g = len(tr_unseen)
    print(f"  eval rows {len(ev)}   matched training size n_G = {n_g}")

    if len(ev) < 100:
        print("  SKIPPED — fewer than 100 evaluation rows.")
        continue

    full_mean, full_p99, full_w = mean_loss(full_model, ev)

    matched = []
    for r in range(N_REPEATS):
        seed = int(rng.integers(0, 2**31 - 1))
        sub = TR.sample(n=n_g, random_state=seed)
        m = mdl.train(sub, verbose=False)
        matched.append(mean_loss(m, ev)[0])
        print(f"    matched draw {r + 1}/{N_REPEATS}  seed {seed}  mean {matched[-1]:.4f} %")
    matched = np.array(matched)

    unseen_model = mdl.train(tr_unseen, verbose=False)
    unseen_mean, unseen_p99, unseen_w = mean_loss(unseen_model, ev)

    m_mean, m_spread = float(matched.mean()), float(matched.max() - matched.min())
    volume = m_mean - full_mean
    geometry = unseen_mean - m_mean
    total = unseen_mean - full_mean

    print(f"\n  {'arm':<12}{'mean %':>10}")
    print(f"  {'full':<12}{full_mean:>10.4f}")
    print(f"  {'matched':<12}{m_mean:>10.4f}   (spread across draws {m_spread:.4f} pt)")
    print(f"  {'unseen':<12}{unseen_mean:>10.4f}")

    print(f"\n  volume effect   (matched - full)   : {volume:+.4f} pt")
    print(f"  geometry effect (unseen  - matched): {geometry:+.4f} pt")
    print(f"  total gap       (unseen  - full)   : {total:+.4f} pt")

    if abs(total) < 1e-9:
        verdict, share_v, share_g = "no gap", 0.0, 0.0
    else:
        share_v, share_g = volume / total, geometry / total
        print(f"    volume share   : {100 * share_v:6.1f} %")
        print(f"    geometry share : {100 * share_g:6.1f} %")
        if abs(geometry) < m_spread:
            verdict = "geometry effect below subsample spread — not claimed"
        elif share_g >= ATTRIB_THRESHOLD:
            verdict = "GEOMETRY ABSENCE (D2)"
        elif share_v >= ATTRIB_THRESHOLD:
            verdict = "TRAINING VOLUME (D1)"
        else:
            verdict = "MIXED (D3)"
    print(f"\n  VERDICT: {verdict}")

    records.append({
        "geometry": g, "eval_rows": len(ev), "n_matched": n_g,
        "full_mean_pct": full_mean, "matched_mean_pct": m_mean,
        "matched_spread_pt": m_spread, "unseen_mean_pct": unseen_mean,
        "volume_effect_pt": volume, "geometry_effect_pt": geometry,
        "total_gap_pt": total, "volume_share": share_v,
        "geometry_share": share_g, "verdict": verdict,
    })

head("Summary")
if records:
    out = pd.DataFrame(records)
    print(out[["geometry", "full_mean_pct", "matched_mean_pct", "unseen_mean_pct",
               "volume_effect_pt", "geometry_effect_pt", "verdict"]]
          .to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"\n  written: {OUT_CSV.relative_to(ROOT)}")
print("\n  Held-out test set was not opened by this run.")