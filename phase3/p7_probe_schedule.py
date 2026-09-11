"""
p7_probe_schedule.py  --  Phase 3, step 7: justify the probe schedule.
REVISION 2 -- generator bug fixed; robust tail metric; multi-seed variance.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase3\\p7_probe_schedule.py
                      OVERWRITE revision 1.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase3\\p7_probe_schedule.py

    Features are rebuilt from the stored curves at each schedule, so nothing is
    re-simulated. With 3 seeds per configuration expect roughly 15-25 minutes.

WHAT REVISION 1 GOT WRONG

  1. SCHEDULE GENERATOR BUG. For counts above 5, schedule("current", n) merged
     the base positions with a linspace, sorted, then truncated with [:n].
     Truncating a sorted list keeps the LOWEST n, so at 6 features the schedule
     became 0.15-0.55 with nothing above 0.55 V_oc -- region 2, which is 54.5% of
     scenarios, was invisible. Hence 69.6% classifier accuracy and 8.5% loss.
     Those rows were an artefact, not a finding.

     Revision 2 defines "current" only where it exists: the incumbent five
     positions, and principled subsets below that. Extending an arbitrary
     five-point set to six is meaningless, so it is not attempted.

  2. THE ACCEPTANCE RULE WAS TOO NARROW. It selected on mean loss alone and
     therefore chose spread-4, which halves nothing and DOUBLES the worst case to
     23.0 W -- worse than the fixed 0.80 rule's 15.9 W. Adopting it would have
     destroyed C4, currently the strongest contribution.

     This is the third declared rule in this project to optimise one axis while
     the claim rested on several: the uncost-matched ablation verdict (log D2),
     the sign-blind drift threshold (D4), and this. Each was declared in advance,
     which is right, and each was underspecified. The corrective adopted here:
     A DECLARED CRITERION MUST NAME EVERY AXIS THE CLAIM RESTS ON. C3's claim
     rests on mean loss, tail, and probe count, so all three appear below.

  3. THE TAIL METRIC WAS AN EXTREME ORDER STATISTIC. worst_loss_w is the maximum
     over ~3,970 rows and does not behave monotonically in the data -- uniform
     gave 24.3 W at 4 probes, 3.6 W at 6, and 8.6 W at 8. That is sampling noise
     in a single maximum. Revision 2 selects on the 99th percentile of loss and
     reports the max alongside it for context only.

WHAT CHANGING THE SCHEDULE ACTUALLY COSTS -- read before adopting anything
    FEATURE_NAMES is derived from PROBE_FRACTIONS, so a change alters the feature
    count and invalidates:
      * results/phase3/c3_two_stage_full.pkl   (trained on the old width)
      * the p20..p85 columns of full_features.parquet (rebuildable from the
        stored curves, no re-simulation needed)
      * every Phase 3 figure -- the log needs a NEW SECTION, not an edit
      * the classical scan-then-bisect baseline, which uses the same positions,
        so P3.5 and P3.7 must be re-run
      * A THIRD HELD-OUT OPENING. The set has been opened twice. Each opening
        costs a little of its independence, and three begins to matter.

    Against that, the funded target is >= 99.5% static tracking efficiency and C3
    already delivers 99.92% on held-out data. An improvement to 99.94% does not
    change whether the target is met.

    The bar for adopting a change is therefore deliberately high, and stated
    below. The primary purpose of this run is to JUSTIFY the schedule, not to
    improve it.

ACCEPTANCE -- DECLARED BEFORE THE RUN, on all three axes
    A schedule replaces the incumbent only if, averaged over seeds, it:
      (a) improves mean loss by more than 0.05 pt, AND
      (b) does not worsen the 99th-percentile loss, AND
      (c) uses no more probes,
    OR it matches within 0.05 pt on both loss axes at STRICTLY FEWER probes.

    In addition the win must exceed the seed-to-seed spread. A difference smaller
    than the variance across random seeds is not a difference.

    Ties go to the incumbent. Swapping schedules for noise-level differences is
    how a tuned choice gets mistaken for a derived one.

A NOTE ON THE MEASUREMENT PATH
    Features here are rebuilt from the 256-point stored curves, whereas the real
    extractor probes the full simulator curve through ctx.probe. The oracle check
    in gmppt/dataset.py bounded that difference at 0.037% worst case. Adequate
    for CHOOSING between schedules; any adopted schedule must be re-measured
    through the harness before its numbers are reported.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, dataset  # noqa: E402
from gmppt.features import PROBE_FRACTIONS, module_scalars  # noqa: E402

OUT = config.RESULTS_DIR / "phase3"
FIGS = OUT / "figures"
N_SUB = int(config.N_SUBSTRINGS)
CURVE_POINTS = dataset.CURVE_POINTS

COUNTS = (3, 4, 5, 6, 8)
SEEDS = (0, 1, 2)
TIE_PT = 0.05


def schedule(kind: str, n: int) -> tuple[float, ...] | None:
    """Probe positions as fractions of V_oc. None where undefined.

    Each family is defined so that positions span the usable range at every
    count. The revision-1 bug was a family that silently lost its upper
    positions; returning None is preferable to returning something malformed.
    """
    if kind == "uniform":
        return tuple(np.round(np.linspace(0.15, 0.90, n), 4))

    if kind == "spread":
        return tuple(np.round(np.linspace(0.10, 0.92, n), 4))

    if kind == "boundary":
        # P2.5: peaks sit near (r + 0.8) / N_SUB. Probe those first, then fill
        # the gaps between them.
        peaks = [round((r + 0.80) / N_SUB, 4) for r in range(N_SUB)]
        if n <= len(peaks):
            return tuple(peaks[-n:])
        fill = list(np.round(np.linspace(0.12, 0.95, n - len(peaks) + 2)[1:-1], 4))
        pos = sorted(set(peaks + fill))
        return tuple(pos) if len(pos) == n else None

    if kind == "current":
        base = list(PROBE_FRACTIONS)
        if n == len(base):
            return tuple(base)
        if n < len(base):
            # keep the endpoints and spread the rest -- never drop the top
            idx = np.unique(np.linspace(0, len(base) - 1, n).round().astype(int))
            return tuple(base[i] for i in idx) if len(idx) == n else None
        return None          # the incumbent is a five-point set; not extended

    raise ValueError(kind)


def features_from_curves(curves: np.ndarray, df: pd.DataFrame,
                         fracs: tuple[float, ...]) -> np.ndarray:
    """Rebuild the feature matrix at an arbitrary probe schedule.

    Curves are stored on a normalised V/V_oc grid, so a fraction indexes it
    directly. Mirrors extract_features: probed powers normalised by the largest
    probed power, then the module scalars.
    """
    grid = np.linspace(0.0, 1.0, CURVE_POINTS)
    fr = np.asarray(fracs, float)

    probed = np.vstack([np.interp(fr, grid, curves[i])
                        for i in df["row_id"].to_numpy(int)])
    p_max = probed.max(axis=1)
    shape = probed / np.where(p_max > 0, p_max, 1.0)[:, None]

    v_oc = df["v_oc"].to_numpy(float)
    scal = np.array([module_scalars(m) for m in df["module"]], dtype=float)
    p_max_norm = p_max / np.where(v_oc > 0, v_oc, 1.0)

    return np.column_stack([shape, p_max_norm, v_oc, scal,
                            df["temp_c"].to_numpy(float)])


def train_and_score(x_tr, tr, x_va, va, curves, seed: int) -> dict:
    """Two-stage model on an arbitrary feature matrix. Proxy metric."""
    from sklearn.ensemble import (HistGradientBoostingClassifier,
                                  HistGradientBoostingRegressor)
    base = (int(config.seed_for("probe_sweep")) + seed * 9973) % 2**31

    clf = HistGradientBoostingClassifier(max_iter=250, learning_rate=0.06,
                                         early_stopping=False,
                                         random_state=base)
    clf.fit(x_tr, tr["region"].to_numpy(int))
    r_hat = clf.predict(x_va)

    k = np.empty(len(va), dtype=float)
    for r in range(N_SUB):
        sel_tr = tr["region"].to_numpy(int) == r
        sel_va = r_hat == r
        if not sel_va.any():
            continue
        if sel_tr.sum() < 20:
            k[sel_va] = (r + 0.5) / N_SUB
            continue
        reg = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06,
                                            early_stopping=False,
                                            random_state=base + r + 1)
        reg.fit(x_tr[sel_tr], tr["offset"].to_numpy(float)[sel_tr])
        k[sel_va] = (r + np.clip(reg.predict(x_va[sel_va]), 0, 1)) / N_SUB

    p_gmpp = va["p_gmpp"].to_numpy(float)
    loss = dataset.power_loss_for_k(curves, va["row_id"].to_numpy(int), k, p_gmpp)
    watts = loss * p_gmpp
    return {
        "mean_loss_pct": 100 * float(loss.mean()),
        "p99_loss_pct": 100 * float(np.percentile(loss, 99)),
        "p99_loss_w": float(np.percentile(watts, 99)),
        "max_loss_w": float(watts.max()),          # context only -- noisy
        "costly_frac_pct": 100 * float((loss > 0.01).mean()),
        "region_acc_pct": 100 * float((r_hat == va["region"].to_numpy(int)).mean()),
    }


def aggregate(runs: list[dict]) -> dict:
    keys = [k for k in runs[0] if isinstance(runs[0][k], float)]
    out = {}
    for k in keys:
        vals = np.array([r[k] for r in runs], dtype=float)
        out[k] = float(vals.mean())
        out[k + "_sd"] = float(vals.std())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="full")
    ap.add_argument("--seeds", type=int, default=len(SEEDS))
    args = ap.parse_args()

    try:
        import sklearn  # noqa: F401
    except ImportError:
        print("scikit-learn is required:  pip install scikit-learn")
        return 1

    print("PHASE 3 / P7  probe schedule  (revision 2)")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 74)
    print(f"incumbent: {[f'{f:.2f}' for f in PROBE_FRACTIONS]}  "
          f"({len(PROBE_FRACTIONS)} features + 1 landing = "
          f"{len(PROBE_FRACTIONS)+1} probes)")
    print("\nacceptance, on all three axes: a schedule replaces the incumbent")
    print(f"only if it improves mean loss by > {TIE_PT} pt WITHOUT worsening the")
    print("p99 loss and WITHOUT using more probes, or matches within "
          f"{TIE_PT} pt on")
    print("both loss axes at strictly fewer probes. The win must also exceed the")
    print("seed-to-seed spread. Ties go to the incumbent.")
    print("\nselection uses the 99th percentile, not the maximum: a single-sample")
    print("maximum over ~4,000 rows is too noisy to choose on.\n")

    df, curves = dataset.load(tag=args.tag)
    df["row_id"] = np.arange(len(df))
    df = dataset.assign_split(df, dataset.module_split())
    tr = df[df["split"] == "train"].reset_index(drop=True)
    va = df[df["split"] == "val"].reset_index(drop=True)
    print(f"{len(df)} rows: train {len(tr)}, val {len(va)}   "
          f"({args.seeds} seeds per configuration)")
    print("held-out modules are not touched\n")

    rows = []
    print(f"   {'placement':<10} {'n':>3} {'probes':>7} {'mean %':>15} "
          f"{'p99 %':>9} {'p99 W':>8} {'max W':>8} {'reg acc %':>10}")
    print("   " + "-" * 78)
    for kind in ("current", "uniform", "spread", "boundary"):
        for n in COUNTS:
            fr = schedule(kind, n)
            if fr is None or len(fr) != n:
                continue
            x_tr = features_from_curves(curves, tr, fr)
            x_va = features_from_curves(curves, va, fr)
            runs = [train_and_score(x_tr, tr, x_va, va, curves, s)
                    for s in range(args.seeds)]
            m = aggregate(runs)
            m.update(placement=kind, n_probes=n, total_probes=n + 1,
                     fractions=[float(f) for f in fr])
            rows.append(m)
            print(f"   {kind:<10} {n:>3} {n+1:>7} "
                  f"{m['mean_loss_pct']:>8.3f} +/-{m['mean_loss_pct_sd']:<5.3f} "
                  f"{m['p99_loss_pct']:>9.3f} {m['p99_loss_w']:>8.2f} "
                  f"{m['max_loss_w']:>8.1f} {m['region_acc_pct']:>10.1f}")

    # -- verdict -------------------------------------------------------------
    inc = next(r for r in rows if r["placement"] == "current"
               and r["n_probes"] == len(PROBE_FRACTIONS))
    print("\n" + "=" * 74)
    print(f"\nINCUMBENT  {inc['n_probes']} features / {inc['total_probes']} probes")
    print(f"   mean {inc['mean_loss_pct']:.3f}% (+/-{inc['mean_loss_pct_sd']:.3f}), "
          f"p99 {inc['p99_loss_pct']:.3f}% / {inc['p99_loss_w']:.2f} W")

    noise = max(inc["mean_loss_pct_sd"], TIE_PT)

    strictly_better = [
        r for r in rows
        if r["n_probes"] <= inc["n_probes"]
        and r["mean_loss_pct"] < inc["mean_loss_pct"] - max(TIE_PT, noise)
        and r["p99_loss_w"] <= inc["p99_loss_w"]
    ]
    cheaper_equal = [
        r for r in rows
        if r["n_probes"] < inc["n_probes"]
        and r["mean_loss_pct"] <= inc["mean_loss_pct"] + TIE_PT
        and r["p99_loss_w"] <= inc["p99_loss_w"] + 0.5
    ]

    if strictly_better or cheaper_equal:
        pool = strictly_better + cheaper_equal
        best = min(pool, key=lambda r: (r["n_probes"], r["mean_loss_pct"]))
        print(f"\n   -> A SCHEDULE CLEARS ALL THREE AXES: {best['placement']}, "
              f"{best['n_probes']} features / {best['total_probes']} probes")
        print(f"      mean {best['mean_loss_pct']:.3f}% "
              f"(+/-{best['mean_loss_pct_sd']:.3f}), "
              f"p99 {best['p99_loss_pct']:.3f}% / {best['p99_loss_w']:.2f} W")
        print(f"      positions: {[round(f, 3) for f in best['fractions']]}")
        print("\n      BEFORE ADOPTING, weigh the cost listed at the top of this")
        print("      file: a new model, a restated Phase 3 log, re-run baselines,")
        print("      and a THIRD held-out opening -- against a funded target that")
        print("      is already exceeded (99.92% vs the required 99.5%).")
        print("      Adopt only if the gain is judged worth that.")
    else:
        print("\n   -> THE INCUMBENT STANDS. No schedule improves mean loss "
              "without")
        print("      worsening the tail or spending more probes, beyond the")
        print("      seed-to-seed spread.")
        print("\n      This is the useful outcome. The schedule is no longer an")
        print("      arbitrary choice: it is the survivor of a sweep over count")
        print("      and placement, and the table is the evidence. Nothing")
        print("      downstream changes.")

    # -- does placement matter? ---------------------------------------------
    print("\nDOES PLACEMENT MATTER, OR ONLY COUNT?")
    for n in COUNTS:
        at_n = [r for r in rows if r["n_probes"] == n]
        if len(at_n) < 2:
            continue
        lo = min(at_n, key=lambda r: r["mean_loss_pct"])
        hi = max(at_n, key=lambda r: r["mean_loss_pct"])
        spread = hi["mean_loss_pct"] - lo["mean_loss_pct"]
        sd = max(r["mean_loss_pct_sd"] for r in at_n)
        verdict = "within seed noise" if spread <= 2 * sd else "real"
        print(f"   {n} features: {lo['placement']} {lo['mean_loss_pct']:.3f}% .. "
              f"{hi['placement']} {hi['mean_loss_pct']:.3f}%   "
              f"spread {spread:.3f} pt ({verdict})")
    print("   Where a spread is within seed noise, placement is immaterial at")
    print("   that count and only the number of probes matters -- which")
    print("   independently justifies not tuning the positions.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "probe_schedule_sweep.json").write_text(
        json.dumps({"incumbent": inc, "sweep": rows, "seeds": args.seeds},
                   indent=2, default=float), encoding="utf-8")
    print(f"\nresults -> {OUT / 'probe_schedule_sweep.json'}")

    # -- figure --------------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        FIGS.mkdir(parents=True, exist_ok=True)
        colours = {"current": "#C0504D", "uniform": "#1F3864",
                   "spread": "#C8842A", "boundary": "#3F7D5A"}
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 5))
        for kind, col in colours.items():
            sel = sorted([r for r in rows if r["placement"] == kind],
                         key=lambda r: r["n_probes"])
            if not sel:
                continue
            x = [r["total_probes"] for r in sel]
            ax1.errorbar(x, [r["mean_loss_pct"] for r in sel],
                         yerr=[r["mean_loss_pct_sd"] for r in sel],
                         fmt="o-", color=col, lw=1.8, capsize=3, label=kind)
            ax2.plot(x, [r["p99_loss_w"] for r in sel], "o-", color=col, lw=1.8,
                     label=kind)
        for ax, lab, title in ((ax1, "mean power loss (%)", "Mean"),
                               (ax2, "99th-percentile loss (W)", "Tail")):
            ax.set_xlabel("total probes per decision", fontsize=10)
            ax.set_ylabel(lab, fontsize=10)
            ax.set_title(f"{title} — lower is better", fontsize=11.5)
            ax.grid(alpha=0.25)
            ax.legend(fontsize=9)
        ax1.plot(inc["total_probes"], inc["mean_loss_pct"], "o", color="#C0504D",
                 ms=14, mfc="none", mew=2.2)
        ax2.plot(inc["total_probes"], inc["p99_loss_w"], "o", color="#C0504D",
                 ms=14, mfc="none", mew=2.2)
        fig.suptitle("Probe schedule: how many, and where "
                     f"(validation modules, {args.seeds} seeds)", fontsize=13)
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        fig.savefig(FIGS / "probe_schedule_sweep.png", dpi=150)
        plt.close(fig)
        print(f"figure  -> {FIGS / 'probe_schedule_sweep.png'}")
    except ImportError:
        print("   matplotlib not installed; skipping figure")

    return 0


if __name__ == "__main__":
    sys.exit(main())