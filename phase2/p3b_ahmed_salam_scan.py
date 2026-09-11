"""
p3b_ahmed_salam_scan.py  --  P2.4b: the Ahmed-Salam comparison, final form.
REVISION 2 -- drops the invalid scan-G variant; compares anchoring-matched.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p3b_ahmed_salam_scan.py
                      OVERWRITE revision 1.

PREREQUISITES
    gmppt/harness.py    revision 3
    gmppt/baselines.py  revision 6
    phase2/p1_harness_regression.py exits 0

WHAT CHANGED IN REVISION 2
    1. scan-G removed. It scored WORSE than the fully inferred scan variant
       despite having more information, because of a padding defect in the
       glue code. It answered one question -- does group-size knowledge help? --
       and revision 1 already answered it: no. Removed rather than repaired.

    2. The headline comparison is now ANCHORING-MATCHED. Revision 1 printed the
       oracle-absolute row against the realistic row, which conflated the alpha
       anchoring choice with the information difference. Oracle-ratio against
       realistic-scan isolates the information question properly, because both
       use ratio anchoring.

    3. Probe cost is reported against the p3c finding that 30 probes performs
       identically to 240, so the honest cost is ~33 probes, not the 63 the
       default budget implies.

WHAT THIS RUN ESTABLISHES
    The final baseline set for C3. Three static baselines an optimizer could
    actually run (fixed, recalibrated, realistic Ahmed-Salam), plus two oracle
    rows marking the ceiling that unmeasurable irradiance would buy.

    Read three things:
      - realistic vs recalibrated : what the published conditional method buys
      - realistic vs oracle-ratio : whether any information is left in the scan
      - the probes column         : what that accuracy costs per control cycle

    And read the worst-W column separately from the mean. No method tested so
    far has bounded the worst case; that is C4's opening and it has no prior art.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import baselines  # noqa: E402  (registers the ahmed_salam variants)
from gmppt.harness import (  # noqa: E402
    METHODS, constant_method, metrics, recal_sample, run_method,
    scenario_set, sweep_constants, write_records,
)

OUT = Path("results/phase2")
PRIMARY = "sub_substring"
FAIR = "whole_substring"      # the geometry Ahmed-Salam was designed for

SHOW = [
    ("mean_loss_pct", "mean loss %", "{:.2f}"),
    ("median_loss_pct", "median %", "{:.2f}"),
    ("worst_loss_pct", "worst %", "{:.2f}"),
    ("worst_loss_w", "worst W", "{:.1f}"),
    ("costly_frac_pct", "costly %", "{:.1f}"),
    ("region_error_pct", "region err %", "{:.1f}"),
    ("mean_probes", "probes", "{:.1f}"),
]

LADDER = [
    ("ahmed-salam oracle (abs a)", "ahmed_salam"),
    ("ahmed-salam oracle (ratio)", "ahmed_salam_ratio"),
    ("ahmed-salam scan (realistic)", "ahmed_salam_scan"),
]

BUILDABLE = {"fixed 0.80", "ahmed-salam scan (realistic)"}   # + recalibrated


def main() -> int:
    print("verifying the reimplementation before it is run on scenarios:")
    ok = baselines.test_ahmed_salam_paper_example()
    print("\nragged irradiance reduction:")
    ok &= baselines.test_ragged_irradiances()
    print("\ndetector invariance:")
    ok &= baselines.test_detector_invariance()
    print("\ngroup-size estimator (our extension, not the paper's):")
    ok &= baselines.test_group_size_estimator()
    if not ok:
        print("\nSTOP: a verification check failed. Fix before running scenarios.")
        return 1

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = scenario_set(args.n)
    geometries = sorted({s.geometry for s in scenarios})
    print(f"\nscenarios: {len(scenarios)}   geometries: {geometries}")

    best_k = min(sweep_constants(recal_sample(scenarios)).items(),
                 key=lambda kv: kv[1])[0]
    recal_name = f"recalibrated {best_k:.3f}"

    runs = [("fixed 0.80", METHODS["fixed_0.80"]),
            (recal_name, constant_method(best_k))]
    runs += [(label, METHODS[key]) for label, key in LADDER]

    results, table = {}, []
    for name, fn in runs:
        print(f"running {name} ...")
        recs = run_method(fn, scenarios)
        slug = (name.replace(" ", "_").replace("(", "").replace(")", "")
                    .replace(".", "").replace("-", "_"))
        write_records(recs, OUT / f"{slug}.csv")
        results[name] = {"all": metrics(recs),
                         **{g: metrics(recs, geometry=g) for g in geometries}}
        for subset in ["all"] + geometries:
            m = results[name][subset]
            if m.get("n"):
                table.append({"method": name, "subset": subset, **m})

    head = "| method | subset | " + " | ".join(l for _, l, _ in SHOW) + " |"
    rule = "|---|---|" + "|".join("---" for _ in SHOW) + "|"
    body = [f"| {r['method']} | {r['subset']} | "
            + " | ".join(f.format(r[k]) for k, _, f in SHOW) + " |"
            for r in table]
    md = "\n".join([head, rule] + body)
    (OUT / "ahmed_salam_ladder.md").write_text(md + "\n", encoding="utf-8")
    (OUT / "ahmed_salam_ladder.json").write_text(json.dumps(results, indent=2),
                                                 encoding="utf-8")
    print("\n" + md)

    for subset, note in ((FAIR, "THE FAIR COMPARISON -- the method's design scope"),
                         (PRIMARY, "outside the method's design scope")):
        print(f"\n{subset}  ({note}):")
        print(f"   {'variant':<30} {'mean %':>8} {'worst W':>9} {'costly %':>10} "
              f"{'region %':>10} {'probes':>8}")
        for name, _ in runs:
            m = results[name][subset]
            mark = "" if name in BUILDABLE or name == recal_name else "  [oracle]"
            print(f"   {name:<30} {m['mean_loss_pct']:>8.2f} "
                  f"{m['worst_loss_w']:>9.1f} {m['costly_frac_pct']:>10.1f} "
                  f"{m['region_error_pct']:>10.1f} {m['mean_probes']:>8.1f}{mark}")

    # -- the two readings that matter, stated explicitly ---------------------
    print("\n" + "=" * 70)
    for subset in (FAIR, PRIMARY):
        rec = results[recal_name][subset]["mean_loss_pct"]
        real = results["ahmed-salam scan (realistic)"][subset]["mean_loss_pct"]
        orc_r = results["ahmed-salam oracle (ratio)"][subset]["mean_loss_pct"]
        probes = results["ahmed-salam scan (realistic)"][subset]["mean_probes"]
        print(f"\n{subset}:")
        print(f"   what the published method buys over the best constant: "
              f"{rec:.2f}% -> {real:.2f}%  ({rec - real:+.2f} pt)")
        print(f"   cost of that gain: {probes:.0f} probes vs 3 "
              f"({probes/3:.0f}x)  -- p3c: 30 probes performs the same as 240,")
        print(f"      so the honest cost is ~33 probes ({33/3:.0f}x)")
        print(f"   information left in the scan (anchoring-matched): "
              f"oracle-ratio {orc_r:.2f}% vs realistic {real:.2f}%  "
              f"({orc_r - real:+.2f} pt)")

    print("\n   A realistic row at or below the oracle row means eq. (14) fully")
    print("   recovers the irradiance information -- measured current ratios are")
    print("   as good as, or better than, nominal irradiance. In that case C3")
    print("   cannot claim to extract unrecovered information; the claim is COST")
    print("   and the unbounded WORST CASE.")
    print(f"\ntable -> {OUT / 'ahmed_salam_ladder.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())