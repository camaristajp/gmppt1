"""
p2_static_baselines.py  --  P2.3: the two static baselines, one table.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p2_static_baselines.py
                      OVERWRITE the scaffold version -- that one was written
                      against harness revision 1 and will not run.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\p2_static_baselines.py --n 2000

PREREQUISITE
    phase2\\p1_harness_regression.py must exit 0. This script reports numbers; it
    does not verify the instrument. If p1 has not passed, nothing here is trusted.

WHAT THIS PRODUCES
    Neither baseline is new -- both are known from Phase 1. The point is the
    TABLE FORMAT: every later method (Ahmed-Salam, Basoglu, the trackers, and the
    learned coefficient C3) drops into these same columns, on the same scenarios,
    scored by the same instrument. That is what makes the final comparison a
    result rather than a collection of separately-produced numbers.

    Outputs to results/phase2/:
      fixed_080.csv          per-scenario records, fixed 0.80
      constant_<k>.csv       per-scenario records, best recalibrated constant
      k_sweep.csv            the full loss-vs-k curve (C2 evidence)
      static_baselines.json  machine-readable metrics
      baseline_table.md      the table, ready to paste into the plan
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt.harness import (  # noqa: E402
    METHODS, constant_method, metrics, recal_sample, run_method,
    scenario_set, sweep_constants, write_records,
)

OUT = Path("results/phase2")
PRIMARY_GEOMETRY = "sub_substring"     # the geometry Gate A(i) turns on

COLUMNS = [
    ("n", "n", "{:.0f}"),
    ("mean_loss_pct", "mean loss %", "{:.2f}"),
    ("median_loss_pct", "median %", "{:.2f}"),
    ("p95_loss_pct", "p95 %", "{:.2f}"),
    ("worst_loss_pct", "worst %", "{:.2f}"),
    ("worst_loss_w", "worst W", "{:.1f}"),
    ("costly_frac_pct", "costly %", "{:.1f}"),
    ("region_error_pct", "region err %", "{:.1f}"),
    ("mean_probes", "probes", "{:.1f}"),
]


def table_rows(name: str, recs, geometries) -> list[dict]:
    rows = [{"method": name, "subset": "all", **metrics(recs)}]
    for g in geometries:
        m = metrics(recs, geometry=g)
        if m.get("n"):
            rows.append({"method": name, "subset": g, **m})
    return rows


def render(rows: list[dict]) -> str:
    head = "| method | subset | " + " | ".join(lbl for _, lbl, _ in COLUMNS) + " |"
    rule = "|---|---|" + "|".join("---" for _ in COLUMNS) + "|"
    body = []
    for r in rows:
        cells = [fmt.format(r[key]) if key in r else "-" for key, _, fmt in COLUMNS]
        body.append(f"| {r['method']} | {r['subset']} | " + " | ".join(cells) + " |")
    return "\n".join([head, rule] + body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = scenario_set(args.n)
    geometries = sorted({s.geometry for s in scenarios})
    print(f"scenarios: {len(scenarios)}   geometries: {geometries}")

    rows: list[dict] = []

    # -- baseline 1: the conventional fixed coefficient ----------------------
    print("\nrunning fixed 0.80 ...")
    recs_080 = run_method(METHODS["fixed_0.80"], scenarios)
    write_records(recs_080, OUT / "fixed_080.csv")
    rows += table_rows("fixed 0.80", recs_080, geometries)

    # -- the k sweep: C2's evidence, not just its answer ---------------------
    # Run on the same 300-scenario sub-substring sample S8 used, so the reported
    # optimum is comparable with Phase 1 rather than a parallel figure.
    print("sweeping constants on the S8 recalibration sample ...")
    sample = recal_sample(scenarios)
    losses = sweep_constants(sample)
    best_k = min(losses, key=losses.get)
    pd.DataFrame(
        [{"k": k, "mean_loss_pct": v} for k, v in sorted(losses.items())]
    ).to_csv(OUT / "k_sweep.csv", index=False)
    print(f"   best k = {best_k:.3f} at {losses[best_k]:.2f}% "
          f"(0.80 gives {losses.get(0.80, float('nan')):.2f}%)")
    print(f"   sweep -> {OUT / 'k_sweep.csv'}")

    # -- baseline 2: the recalibrated constant, scored on the full set -------
    print(f"running recalibrated constant k={best_k:.3f} ...")
    recs_k = run_method(constant_method(best_k), scenarios)
    write_records(recs_k, OUT / f"constant_{best_k:.3f}.csv")
    rows += table_rows(f"recalibrated {best_k:.3f}", recs_k, geometries)

    # -- persist -------------------------------------------------------------
    (OUT / "static_baselines.json").write_text(
        json.dumps({"best_k": best_k, "k_sweep": losses, "rows": rows}, indent=2),
        encoding="utf-8")
    md = render(rows)
    (OUT / "baseline_table.md").write_text(md + "\n", encoding="utf-8")

    print("\n" + md)

    # -- consistency note ----------------------------------------------------
    sub = next(r for r in rows
               if r["method"] == "fixed 0.80" and r["subset"] == PRIMARY_GEOMETRY)
    print(f"\nfixed 0.80 on {PRIMARY_GEOMETRY}: mean {sub['mean_loss_pct']:.2f}%, "
          f"costly {sub['costly_frac_pct']:.1f}%, "
          f"region err {sub['region_error_pct']:.1f}%")
    print("   (these must match the p1 regression run -- same instrument, "
          "same scenarios)")
    print(f"\ntable -> {OUT / 'baseline_table.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())