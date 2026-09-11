"""
p9_geometry_holdout.py
Destination:  C:\\Users\\user\\gmppt\\phase3\\p9_geometry_holdout.py
Run from:     C:\\Users\\user\\gmppt>  python phase3\\p9_geometry_holdout.py

WHY THIS RUN EXISTS
-------------------
The module-design split is a correct leakage guard and a weak generalisation
test: c-Si module designs resemble one another (population coefficient s.d.
0.0152), so a held-out module is not very different from a training module.
The axis that matters for deployment is shading condition, and it has never
been tested. This run tests it.

No re-simulation. No opening of the held-out test set. Validation modules only.

DESIGN
------
For each geometry G:
    unseen  = train on TRAIN-split rows with geometry != G,
              score on VAL-split rows with geometry == G
    seen    = train on TRAIN-split rows, ALL geometries (one control model),
              score on VAL-split rows with geometry == G

The evaluation set is identical in both arms. Only the training composition
differs, so the comparison holds every other condition equal.

CRITERIA, DECLARED BEFORE THE RUN
---------------------------------
C1  Condition generalisation is demonstrated for geometry G if the unseen-arm
    mean power loss is within 2.0x the seen-arm mean power loss on the SAME
    evaluation rows, and the upper bound of the bootstrap 95% interval on that
    ratio also falls at or below 2.0.

C2  Where the seen-arm mean loss is below 0.02%, the ratio is numerically
    unstable and is NOT evaluated. The absolute difference is reported instead,
    and generalisation is called if that difference is below 0.10 pt.

C3  A verdict is reported per geometry. There is no pooled verdict: pooling
    would let the two easy geometries mask a failure on the third.

C4  Variance is estimated by resampling the EVALUATION ROWS, not the model
    seed. Per defect D8, the estimator is deterministic under these settings,
    so a seed-based guard would measure nothing and pass silently.

C5  Region coverage of each training set is reported alongside every result.
    A degraded unseen-arm score has two possible causes -- the geometry was
    unseen, or a region became rare in training -- and they must be
    distinguishable before the number is interpreted.

Failure is a reportable outcome, not a problem with the run. If the seed
depends on having seen the geometry, that is a deployment constraint: the
training mix must cover the geometries the field presents, and the
fast-re-seeding work inherits it.
"""

import sys
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gmppt import dataset as ds
from gmppt import model as mdl

FEATURES = ROOT / "results" / "phase3" / "full_features.parquet"
CURVES = ROOT / "results" / "phase3" / "full_curves.npy"
OUT_CSV = ROOT / "results" / "phase3" / "p9_geometry_holdout.csv"

RATIO_LIMIT = 2.0
FLAT_FLOOR_PCT = 0.02
FLAT_ABS_LIMIT = 0.10
N_BOOT = 2000
BOOT_SEED = 20260901

FEATS = list(ds.FEATURE_NAMES)
RULE = "=" * 78
SUB = "-" * 78


def head(t):
    print("\n" + RULE)
    print(t)
    print(RULE)


# ----------------------------------------------------------------------
# load
# ----------------------------------------------------------------------
head("Load")

try:
    df, curves = ds.load(tag="full")
    print("  loaded via gmppt.dataset.load(tag='full')")
except Exception:
    df = pd.read_parquet(FEATURES)
    curves = np.load(CURVES)
    print("  loaded directly from parquet + npy")

df = df.reset_index(drop=True)
if "row_id" not in df.columns:
    df["row_id"] = np.arange(len(df))

print(f"  rows   : {len(df)}")
print(f"  curves : {curves.shape}")
assert curves.shape[0] == len(df), "curve array and feature table disagree on row count"

split = ds.module_split(val_fraction=ds.VAL_FRACTION_OF_TRAIN)
train_mods = set(split.train)
val_mods = set(split.val)
print(f"  modules: train {len(train_mods)}  val {len(val_mods)}  test {len(split.test)} (test untouched)")

df["_split"] = np.where(
    df["module"].isin(train_mods), "train",
    np.where(df["module"].isin(val_mods), "val", "test"),
)
print("\n  rows by split x geometry")
print(pd.crosstab(df["_split"], df["geometry"]).to_string())

TR = df[df["_split"] == "train"].copy()
VA = df[df["_split"] == "val"].copy()
GEOMS = sorted(df["geometry"].unique())


# ----------------------------------------------------------------------
# scoring helpers
# ----------------------------------------------------------------------
def score(model, frame):
    """Return per-row percentage loss and watt loss on `frame`."""
    X = frame[FEATS].to_numpy(dtype=float)
    k_pred = np.asarray(model.predict_k(X), dtype=float)
    rows = frame["row_id"].to_numpy()
    p_gmpp = frame["p_gmpp"].to_numpy(dtype=float)

    p_at = np.asarray(ds.power_at_k(curves, rows, k_pred), dtype=float)
    watts = np.maximum(p_gmpp - p_at, 0.0)
    pct = 100.0 * watts / p_gmpp

    # parity check against the library's own loss function, to catch a unit
    # mismatch rather than assume one.
    try:
        lib = np.asarray(ds.power_loss_for_k(curves, rows, k_pred, p_gmpp), dtype=float)
        parity = float(np.abs(np.mean(lib) - np.mean(pct)))
    except Exception:
        parity = float("nan")

    region_pred = np.clip((k_pred * mdl.N_SUB).astype(int), 0, mdl.N_SUB - 1)
    region_acc = 100.0 * float(np.mean(region_pred == frame["region"].to_numpy()))
    return pct, watts, region_acc, parity


def boot_mean(x, rng, n=N_BOOT):
    idx = rng.integers(0, len(x), size=(n, len(x)))
    return x[idx].mean(axis=1)


def region_counts(frame):
    c = frame["region"].value_counts().sort_index()
    return {int(k): int(v) for k, v in c.items()}


# ----------------------------------------------------------------------
# control model — all geometries
# ----------------------------------------------------------------------
head("Control model (all geometries in training)")
t0 = time.time()
control = mdl.train(TR, verbose=False)
print(f"  trained on {len(TR)} rows in {time.time() - t0:.1f} s")
print(f"  region coverage: {region_counts(TR)}")


# ----------------------------------------------------------------------
# per-geometry holdout
# ----------------------------------------------------------------------
rng = np.random.default_rng(BOOT_SEED)
records = []

for g in GEOMS:
    head(f"Hold out: {g}")

    tr_g = TR[TR["geometry"] != g]
    ev_g = VA[VA["geometry"] == g]
    print(f"  train rows (geometry != {g}) : {len(tr_g)}")
    print(f"  eval  rows (geometry == {g}) : {len(ev_g)}   [validation modules]")
    print(f"  training region coverage      : {region_counts(tr_g)}")
    print(f"  evaluation region coverage    : {region_counts(ev_g)}")

    if len(ev_g) < 100:
        print("  SKIPPED — fewer than 100 evaluation rows.")
        continue

    try:
        t0 = time.time()
        m_unseen = mdl.train(tr_g, verbose=False)
        print(f"  trained in {time.time() - t0:.1f} s")
    except Exception:
        print("  TRAINING FAILED for this holdout:")
        for line in traceback.format_exc().strip().splitlines()[-3:]:
            print(f"    {line}")
        continue

    try:
        u_pct, u_w, u_acc, u_par = score(m_unseen, ev_g)
        s_pct, s_w, s_acc, s_par = score(control, ev_g)
    except Exception:
        print("  SCORING FAILED for this holdout:")
        for line in traceback.format_exc().strip().splitlines()[-3:]:
            print(f"    {line}")
        continue

    u_mean, s_mean = float(u_pct.mean()), float(s_pct.mean())
    print(f"\n  {'arm':<10}{'mean %':>10}{'p99 %':>10}{'worst W':>10}{'costly %':>11}{'region acc %':>14}")
    for name, pct, w, acc in (("seen", s_pct, s_w, s_acc), ("unseen", u_pct, u_w, u_acc)):
        print(f"  {name:<10}{pct.mean():>10.3f}{np.percentile(pct, 99):>10.3f}"
              f"{w.max():>10.2f}{100.0 * np.mean(pct > 1.0):>11.2f}{acc:>14.1f}")
    print(f"\n  loss-function parity (library vs recomputed): "
          f"seen {s_par:.4f} pt, unseen {u_par:.4f} pt")

    # ---- verdict ----
    boot_u = boot_mean(u_pct, rng)
    boot_s = boot_mean(s_pct, rng)

    if s_mean < FLAT_FLOOR_PCT:
        diff = u_mean - s_mean
        d_lo, d_hi = np.percentile(boot_u - boot_s, [2.5, 97.5])
        ok = abs(diff) < FLAT_ABS_LIMIT
        print(f"\n  Criterion C2 applies (seen-arm mean {s_mean:.4f}% is below "
              f"the {FLAT_FLOOR_PCT}% floor).")
        print(f"    absolute difference : {diff:+.4f} pt   95% CI [{d_lo:+.4f}, {d_hi:+.4f}]")
        print(f"    limit               : {FLAT_ABS_LIMIT} pt")
        print(f"    VERDICT             : {'GENERALISES' if ok else 'DOES NOT GENERALISE'}")
        ratio = float("nan")
        r_lo = r_hi = float("nan")
        rule = "C2 absolute"
    else:
        ratio = u_mean / s_mean
        r_lo, r_hi = np.percentile(boot_u / boot_s, [2.5, 97.5])
        ok = (ratio <= RATIO_LIMIT) and (r_hi <= RATIO_LIMIT)
        print(f"\n  Criterion C1 applies.")
        print(f"    ratio unseen/seen   : {ratio:.3f}x   95% CI [{r_lo:.3f}, {r_hi:.3f}]")
        print(f"    limit               : {RATIO_LIMIT}x (point estimate and CI upper bound)")
        print(f"    VERDICT             : {'GENERALISES' if ok else 'DOES NOT GENERALISE'}")
        rule = "C1 ratio"

    records.append({
        "held_out_geometry": g,
        "train_rows": len(tr_g),
        "eval_rows": len(ev_g),
        "seen_mean_pct": s_mean,
        "unseen_mean_pct": u_mean,
        "seen_worst_w": float(s_w.max()),
        "unseen_worst_w": float(u_w.max()),
        "seen_costly_pct": float(100.0 * np.mean(s_pct > 1.0)),
        "unseen_costly_pct": float(100.0 * np.mean(u_pct > 1.0)),
        "seen_region_acc": s_acc,
        "unseen_region_acc": u_acc,
        "ratio": ratio,
        "ratio_ci_lo": float(r_lo),
        "ratio_ci_hi": float(r_hi),
        "rule": rule,
        "verdict": "GENERALISES" if ok else "DOES NOT GENERALISE",
    })


# ----------------------------------------------------------------------
head("Summary")

if not records:
    print("  No geometry completed. Nothing to report.")
else:
    out = pd.DataFrame(records)
    cols = ["held_out_geometry", "eval_rows", "seen_mean_pct", "unseen_mean_pct",
            "ratio", "ratio_ci_hi", "unseen_region_acc", "verdict"]
    print(out[cols].to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)
    print(f"\n  written: {OUT_CSV.relative_to(ROOT)}")

    print("\n  Per criterion C3 there is no pooled verdict. Read each row.")
    print("  A DOES NOT GENERALISE row is a finding, not a fault: check the")
    print("  training region coverage printed above before interpreting it.")

print("\n  Held-out test set was not opened by this run.")