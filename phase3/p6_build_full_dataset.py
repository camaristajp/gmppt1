"""
p6_build_full_dataset.py  --  Phase 3, step 6: build the funded-scale dataset.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase3\\p6_build_full_dataset.py
                      NEW FILE.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase3\\p6_build_full_dataset.py --n 20000

    Roughly 62 minutes at the measured 0.187 s/scenario. Unattended.
    Add --retrain to train the two-stage model on it in the same run.

WHY
    The funded proposal (Section 4.2) commits to "tens of thousands" of training
    scenarios. Every Phase 3 result to date rests on a 2,000-scenario pilot.
    This closes that gap.

    The pilot was not chosen arbitrarily -- P3.2 measured the learning curve and
    found it flattening, with the last doubling of data worth 0.078 pt. So the
    expectation is that the full set changes the headline figures little. Two
    things make it worth building anyway:

      1. It is a funded deliverable, not an optimisation.
      2. The flattening was measured on PLAIN REGRESSION. The two-stage model
         adopted in P3.3 has a different shape, and region 0 -- which carried
         half the loss before the architecture change -- rests on 36 validation
         scenarios in the pilot. At 20,000 it would rest on roughly 350. A
         figure resting on 36 samples is not one to put in a thesis.

WHAT IS AND IS NOT EXPECTED TO MOVE
    Expected to stay put: mean loss, the probe count, the cost ratio. The
    learning curve says so.

    Expected to firm up: region-0 figures, the worst case, and the costly
    fraction -- all tail quantities that a small sample estimates poorly. The
    validation worst case of 46.26% on whole-substring turned out to be a single
    dim-panel outlier that did not recur on held-out data; ten times the data
    will say which of the two readings was the anomaly.

    If the headline figures move MORE than about 0.1 pt, that is itself worth
    investigating: it would mean the pilot was not representative, and the
    learning curve in P3.2 understated the data appetite.

TEST SET DISCIPLINE
    This script generates TRAINING scenarios only (train_only=True excludes
    held-out modules) and does not touch the test set. The held-out set has been
    opened once, on 2026-08-18, and the result is recorded in the Phase 3 log. It
    may be opened once more for the final figure after retraining -- that is the
    standard pattern, provided each opening is recorded.

DISK
    Features parquet is small. Curves are 256 float32 per scenario: about 20 MB
    at 20,000 scenarios. Both are written under results/phase3/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, dataset  # noqa: E402
from gmppt.harness import scenario_set  # noqa: E402

OUT = config.RESULTS_DIR / "phase3"

PILOT = {                      # P3.2 / P3.5, for the comparison at the end
    "n_scenarios": 2000,
    "val_mean_loss_all": 0.397,
    "test_mean_loss_all": 0.292,
    "val_whole_substring": 0.28,
    "test_whole_substring": 0.11,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20000,
                    help="scenario count; the proposal commits to tens of thousands")
    ap.add_argument("--tag", default="full")
    ap.add_argument("--retrain", action="store_true",
                    help="train the two-stage model on the result")
    args = ap.parse_args()

    print("PHASE 3 / P6  full dataset build")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 70)
    print(f"target: {args.n:,} scenarios (funded proposal Section 4.2)")
    print(f"pilot:  {PILOT['n_scenarios']:,} scenarios")
    print("training modules only -- the held-out set is not touched here\n")

    # -- build ---------------------------------------------------------------
    print("1. GENERATE AND SIMULATE")
    t0 = time.perf_counter()
    scenarios = scenario_set(args.n)
    print(f"   {len(scenarios)} scenarios generated")
    df, curves = dataset.build(scenarios)
    build_s = time.perf_counter() - t0

    df["row_id"] = np.arange(len(df))
    print(f"\n   {len(df)} rows in {build_s/60:.1f} min "
          f"({build_s/max(len(df),1):.3f} s/scenario)")
    dataset.save(df, curves, tag=args.tag)

    # -- composition ---------------------------------------------------------
    print("\n2. COMPOSITION  (does the larger set look like the pilot?)")
    print(f"   {'geometry':<18} {'n':>7} {'share':>8} {'k mean':>9} {'k sd':>8}")
    for g, sub in df.groupby("geometry"):
        print(f"   {g:<18} {len(sub):>7} {100*len(sub)/len(df):>7.1f}% "
              f"{sub['k_true'].mean():>9.4f} {sub['k_true'].std():>8.4f}")

    print("\n   region distribution (which substring interval holds the GMPP):")
    for r, cnt in df["region"].value_counts().sort_index().items():
        print(f"     region {r}: {cnt:>7}  ({100*cnt/len(df):>5.1f}%)")

    split = dataset.assign_split(df, dataset.module_split())
    tr = split[split["split"] == "train"]
    va = split[split["split"] == "val"]
    print(f"\n   after the module split: train {len(tr)}, val {len(va)}")
    r0_val = int((va["region"] == 0).sum())
    print(f"   region-0 validation rows: {r0_val}  "
          f"(pilot had 36 -- this is the figure that was too thin)")

    payload = {"n_requested": args.n, "n_rows": int(len(df)),
               "build_seconds": build_s,
               "region_0_val_rows": r0_val,
               "geometry_shares": {str(g): float(len(s) / len(df))
                                   for g, s in df.groupby("geometry")}}

    # -- retrain -------------------------------------------------------------
    if args.retrain:
        from gmppt import model as c3model
        print("\n3. RETRAIN  (two-stage, on the full training rows)")
        m = c3model.train(tr.reset_index(drop=True))
        path = m.save(tag="c3_two_stage_full")
        print(f"   model -> {path}")

        print("\n   quick validation check (proxy metric, not the harness):")
        from gmppt.features import FEATURE_NAMES
        k = m.predict_k(va[list(FEATURE_NAMES)].to_numpy(float))
        loss = dataset.power_loss_for_k(curves, va["row_id"].to_numpy(int), k,
                                        va["p_gmpp"].to_numpy(float))
        mean_all = 100 * float(loss.mean())
        print(f"     mean loss (all geometries): {mean_all:.3f}%   "
              f"pilot was {PILOT['val_mean_loss_all']:.3f}%")
        print(f"     costly (>1%): {100*float((loss>0.01).mean()):.1f}%")
        print(f"     worst: {100*float(loss.max()):.1f}%")
        for g in sorted(va["geometry"].unique()):
            sel = va["geometry"].to_numpy() == g
            print(f"     {g:<18} {100*float(loss[sel].mean()):.3f}%")
        for r in sorted(va["region"].unique()):
            sel = va["region"].to_numpy() == r
            print(f"     region {r}: {100*float(loss[sel].mean()):.3f}%  "
                  f"(n={int(sel.sum())})")

        drift = abs(mean_all - PILOT["val_mean_loss_all"])
        payload["full_val_mean_loss"] = mean_all
        payload["drift_from_pilot_pt"] = drift
        print(f"\n   drift from the pilot: {drift:.3f} pt")
        if drift <= 0.10:
            print("   -> The pilot was representative. The learning curve in P3.2")
            print("      was right that data volume was not the bottleneck; the")
            print("      full set firms up the tail figures rather than moving")
            print("      the headline.")
        else:
            print("   -> The headline moved more than expected. The pilot was NOT")
            print("      representative, and P3.2's learning curve understated the")
            print("      data appetite -- likely because it was measured on plain")
            print("      regression rather than the two-stage form. Investigate")
            print("      before reporting either figure.")

        print("\n   NOTE: this is the stored-curve proxy. The figures that go in")
        print("   the thesis come from the harness -- re-run p3_final_comparison")
        print("   against the retrained model.")

    (OUT / "full_dataset_build.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")
    print(f"\nresults -> {OUT / 'full_dataset_build.json'}")

    print("\nNEXT")
    print("   1. Point gmppt/model.py's default tag at the retrained model, or")
    print("      load 'c3_two_stage_full' explicitly in the comparison scripts.")
    print("   2. Re-run phase3\\p3_final_comparison.py (Part A) on the new model.")
    print("   3. Add the classical scan-then-bisect to the comparison table -- it")
    print("      reaches 0.231% at 11 probes and is currently absent.")
    print("   4. Open the held-out set once more for the final figure, and record")
    print("      that opening in the Phase 3 log.")
    return 0


if __name__ == "__main__":
    sys.exit(main())