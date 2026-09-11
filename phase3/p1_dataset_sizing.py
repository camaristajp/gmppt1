"""
p1_dataset_sizing.py  --  Phase 3, step 1: how much training data is needed?

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase3\\p1_dataset_sizing.py
                      NEW FOLDER phase3\\ -- create it, and put an empty
                      __init__.py beside this file if you want it importable.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase3\\p1_dataset_sizing.py --n 2000

PREREQUISITES
    gmppt/features.py  (3/3 pass)
    gmppt/dataset.py   (split and scoring verified)
    scikit-learn:  pip install scikit-learn

WHAT QUESTION THIS ANSWERS
    The funded proposal (§4.2) commits to "tens of thousands" of training
    scenarios. That number is a deliverable, not an open choice. What is open is
    whether that many are NEEDED -- and the plan's own standard (§9.11) is that a
    count is justified by convergence, not by feel. S6 did not simply pick 2,000
    scenarios; it showed the statistics had stopped moving.

    This run applies the same standard to training. It builds a pilot set, trains
    at increasing sizes, and reports where performance stops improving.

    Four things come out of it:
      1. BUILD TIME per scenario -> schedule the full run instead of guessing.
      2. IS THE CURVE STILL RISING at the pilot size? If yes, the large set is
         genuinely needed. If it has flattened, the extra scenarios are delivered
         as promised but shown to be surplus -- itself a reportable finding.
      3. IS REGION 0 LEARNABLE? It was 8.7% of scenarios in the features check.
         A thin class that never improves is a model problem, not a data problem,
         and no amount of extra data fixes it.
      4. DO THE TWO METRICS TRACK? Coefficient error is what training optimises;
         power loss is what the thesis reports. They are not interchangeable -- a
         k error of 0.02 costs little on a flat peak and a lot on a steep one. If
         they diverge here, that shapes the Month-3 objective decision.

WHAT THIS RUN IS NOT
    Not the C3 model. The learner here is a stock gradient-boosting regressor,
    chosen because it is strong on small tabular data with no tuning. It is a
    PROBE for how much data the problem needs, not a candidate architecture. A
    weak learner would plateau early and understate the requirement, so the
    reported curve is specific to this learner and is read as a lower bound on
    the data appetite of a stronger one.

TEST SET DISCIPLINE
    The held-out 20% of modules is NOT touched here. Scenarios are generated with
    train_only=True, which draws from training modules only; the validation slice
    is carved from those by module. The held-out set is opened once, at the end
    of Phase 3, through the harness.

    (This also corrects a faulty check in gmppt/dataset.py: its geometry-balance
    test expected test-module scenarios in a train_only=True set, which cannot
    happen. Train and test scenario sets are generated separately by design.)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, dataset  # noqa: E402
from gmppt.features import FEATURE_NAMES  # noqa: E402
from gmppt.harness import scenario_set  # noqa: E402

OUT = config.RESULTS_DIR / "phase3"
FIGS = OUT / "figures"

TRAIN_FRACTIONS = (0.125, 0.25, 0.5, 1.0)   # of the available training rows
N_SUBSTRINGS = int(config.N_SUBSTRINGS)


def make_model():
    from sklearn.ensemble import HistGradientBoostingRegressor
    return HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.06, max_depth=None,
        early_stopping=False, random_state=int(config.seed_for("c3_pilot")) % 2**31)


def fit_and_score(tr: pd.DataFrame, va: pd.DataFrame,
                  curves: np.ndarray) -> dict:
    """Train on tr, evaluate on va. Both metrics, plus a per-region breakdown."""
    x_tr = tr[list(FEATURE_NAMES)].to_numpy(float)
    y_tr = tr["k_true"].to_numpy(float)
    x_va = va[list(FEATURE_NAMES)].to_numpy(float)
    y_va = va["k_true"].to_numpy(float)

    model = make_model()
    model.fit(x_tr, y_tr)
    k_pred = model.predict(x_va)

    loss = dataset.power_loss_for_k(curves, va["row_id"].to_numpy(int),
                                    k_pred, va["p_gmpp"].to_numpy(float))
    m = dataset.report_metrics(y_va, k_pred, loss)

    by_region = {}
    for r in range(N_SUBSTRINGS):
        sel = va["region"].to_numpy(int) == r
        if sel.sum() == 0:
            continue
        by_region[int(r)] = {
            "n": int(sel.sum()),
            "k_mae": float(np.mean(np.abs(k_pred[sel] - y_va[sel]))),
            "mean_loss_pct": 100 * float(loss[sel].mean()),
        }
    m["by_region"] = by_region

    by_geom = {}
    for g, sub in va.groupby("geometry"):
        sel = va["geometry"].to_numpy() == g
        by_geom[str(g)] = {
            "n": int(sel.sum()),
            "mean_loss_pct": 100 * float(loss[sel].mean()),
        }
    m["by_geometry"] = by_geom
    return m


def baseline_scores(va: pd.DataFrame, curves: np.ndarray) -> dict:
    """Two reference points the model must beat, on the SAME validation rows.

    fixed 0.80        the industry default, as a single landing
    train-mean k      predicting the training mean every time -- the floor any
                      model must clear to have learned anything at all
    """
    rows = va["row_id"].to_numpy(int)
    p_gmpp = va["p_gmpp"].to_numpy(float)
    y = va["k_true"].to_numpy(float)
    out = {}
    for label, k in (("fixed 0.80", np.full(len(va), 0.80)),
                     ("predict mean k", np.full(len(va), float(y.mean())))):
        loss = dataset.power_loss_for_k(curves, rows, k, p_gmpp)
        out[label] = dataset.report_metrics(y, k, loss, label)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000,
                    help="pilot scenario count (funded spec is tens of thousands "
                         "for the full run; this sizes it)")
    ap.add_argument("--tag", default="pilot")
    args = ap.parse_args()

    try:
        import sklearn  # noqa: F401
    except ImportError:
        print("scikit-learn is required:  pip install scikit-learn")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    print("PHASE 3 / P1  dataset sizing")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 70)
    print("The funded proposal commits to tens of thousands of scenarios.")
    print("This run measures whether that many are NEEDED, and how long they take.")
    print("The held-out 20% of modules is NOT touched here.\n")

    # -- build ---------------------------------------------------------------
    print(f"1. BUILD  ({args.n} scenarios, train modules only)")
    t0 = time.perf_counter()
    scenarios = scenario_set(args.n)
    df, curves = dataset.build(scenarios)
    build_s = time.perf_counter() - t0

    df["row_id"] = np.arange(len(df))
    per = build_s / max(len(df), 1)
    print(f"   {len(df)} rows in {build_s/60:.1f} min "
          f"({per:.3f} s/scenario)")
    for n_full in (10_000, 20_000, 50_000):
        print(f"   projected for {n_full:>6,}: {per*n_full/60:>6.1f} min")
    dataset.save(df, curves, tag=args.tag)

    # -- split ---------------------------------------------------------------
    print("\n2. SPLIT  (by module -- the leakage guard)")
    split = dataset.module_split()
    df = dataset.assign_split(df, split)
    tr_all = df[df["split"] == "train"].reset_index(drop=True)
    va = df[df["split"] == "val"].reset_index(drop=True)
    n_test_rows = int((df["split"] == "test").sum())
    print(f"   rows: train {len(tr_all)}, val {len(va)}, test {n_test_rows}")
    print(f"   (test rows are 0 by design -- train_only=True excludes held-out "
          f"modules)")
    if len(va) < 50:
        print("   WARNING: validation set is small; increase --n")

    print("\n   region distribution in validation:")
    for r, cnt in va["region"].value_counts().sort_index().items():
        print(f"     region {r}: {cnt:>5}  ({100*cnt/len(va):>4.1f}%)")

    # -- references ----------------------------------------------------------
    print("\n3. REFERENCE POINTS  (same validation rows)")
    refs = baseline_scores(va, curves)

    # -- learning curve ------------------------------------------------------
    print("\n4. LEARNING CURVE  (does performance stop improving?)")
    rng = np.random.default_rng(config.seed_for("c3_sizing"))
    order = rng.permutation(len(tr_all))
    results = []
    print(f"   {'train rows':>11} {'k MAE':>8} {'mean loss %':>12} "
          f"{'costly %':>9} {'worst %':>8}")
    for frac in TRAIN_FRACTIONS:
        n = max(30, int(round(frac * len(tr_all))))
        sub = tr_all.iloc[order[:n]]
        m = fit_and_score(sub, va, curves)
        m["train_rows"] = n
        results.append(m)
        print(f"   {n:>11} {m['k_mae']:>8.4f} {m['mean_loss_pct']:>12.2f} "
              f"{m['costly_frac_pct']:>9.1f} {m['worst_loss_pct']:>8.1f}")

    # -- read the curve ------------------------------------------------------
    print("\n5. READING THE CURVE")
    last, prev = results[-1], results[-2]
    d_loss = prev["mean_loss_pct"] - last["mean_loss_pct"]
    d_mae = prev["k_mae"] - last["k_mae"]
    print(f"   last doubling of data changed mean loss by {d_loss:+.3f} pt "
          f"and k MAE by {d_mae:+.4f}")
    if d_loss > 0.20:
        verdict = ("STILL RISING -- more data helps. The funded tens of thousands "
                   "is justified on evidence, not only on commitment.")
    elif d_loss > 0.05:
        verdict = ("FLATTENING -- gains are small but real. Build the full set; "
                   "expect modest improvement.")
    else:
        verdict = ("PLATEAUED at this size -- the bottleneck is the model or the "
                   "features, not the data. Deliver the full set as promised, and "
                   "report that the extra scenarios were surplus.")
    print(f"   -> {verdict}")

    print(f"\n   vs the references on the same rows:")
    print(f"     fixed 0.80      {refs['fixed 0.80']['mean_loss_pct']:.2f}%")
    print(f"     predict mean k  {refs['predict mean k']['mean_loss_pct']:.2f}%")
    print(f"     model (full)    {last['mean_loss_pct']:.2f}%")
    print("   The model must clear 'predict mean k' to have learned anything.")
    print("   Beating fixed 0.80 here is NOT the thesis claim -- that comes from")
    print("   the harness on held-out modules, against the full baseline table.")

    print("\n6. PER-REGION  (region 0 was the thin class)")
    print(f"   {'region':>7} {'n':>6} {'k MAE':>8} {'mean loss %':>12}")
    for r, d in sorted(last["by_region"].items()):
        print(f"   {r:>7} {d['n']:>6} {d['k_mae']:>8.4f} "
              f"{d['mean_loss_pct']:>12.2f}")
    print("   A region that does not improve with data is a MODEL problem.")

    print("\n7. PER-GEOMETRY")
    for g, d in sorted(last["by_geometry"].items()):
        print(f"   {g:<18} n={d['n']:>5}  mean loss {d['mean_loss_pct']:.2f}%")

    payload = {"n_scenarios": int(args.n), "n_rows": int(len(df)),
               "build_seconds": build_s, "seconds_per_scenario": per,
               "references": refs, "learning_curve": results,
               "verdict": verdict}
    (OUT / "sizing_study.json").write_text(json.dumps(payload, indent=2,
                                                      default=float),
                                           encoding="utf-8")
    print(f"\nresults -> {OUT / 'sizing_study.json'}")

    # -- figure --------------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        FIGS.mkdir(parents=True, exist_ok=True)
        NAVY, CORAL, GREY = "#1F3864", "#C0504D", "#BBBBBB"
        xs = [r["train_rows"] for r in results]
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))
        ax1.plot(xs, [r["mean_loss_pct"] for r in results], "o-",
                 color=NAVY, lw=1.8)
        ax1.axhline(refs["fixed 0.80"]["mean_loss_pct"], color=CORAL, ls="--",
                    lw=1.4, label="fixed 0.80")
        ax1.axhline(refs["predict mean k"]["mean_loss_pct"], color=GREY,
                    ls=":", lw=1.4, label="predict mean k")
        ax1.set_xscale("log")
        ax1.set_xlabel("training rows", fontsize=9)
        ax1.set_ylabel("validation mean power loss (%)", fontsize=9)
        ax1.legend(fontsize=8)
        ax1.grid(alpha=0.25)
        ax1.set_title("Does more data help?", fontsize=10.5)

        for r in range(N_SUBSTRINGS):
            ys = [res["by_region"].get(r, {}).get("mean_loss_pct", np.nan)
                  for res in results]
            ax2.plot(xs, ys, "o-", lw=1.6, label=f"region {r}")
        ax2.set_xscale("log")
        ax2.set_xlabel("training rows", fontsize=9)
        ax2.set_ylabel("validation mean power loss (%)", fontsize=9)
        ax2.legend(fontsize=8)
        ax2.grid(alpha=0.25)
        ax2.set_title("Which region is hard?", fontsize=10.5)

        fig.suptitle("Dataset sizing: learning curve on held-out modules",
                     fontsize=12.5)
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        fig.savefig(FIGS / "sizing_learning_curve.png", dpi=150)
        plt.close(fig)
        print(f"figure  -> {FIGS / 'sizing_learning_curve.png'}")
    except ImportError:
        print("   matplotlib not installed; skipping figure")

    return 0


if __name__ == "__main__":
    sys.exit(main())