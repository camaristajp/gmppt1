"""
p3_ahmed_salam.py  --  P2.4: Ahmed-Salam conditional alpha vs the static baselines.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p3_ahmed_salam.py
                      OVERWRITE the scaffold stub.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\p3_ahmed_salam.py --n 2000

PREREQUISITES
    1. The two-line Context patch applied to gmppt/harness.py (see baselines.py).
    2. gmppt/baselines.py revision 2 in place.
    3. phase2/p1_harness_regression.py exits 0.

WHY THIS RUN MATTERS
    Fixed-0.80 and the recalibrated constant cannot adapt at all, so beating them
    proves little. Ahmed-Salam already varies its prediction with conditions. This
    is the first honest test of whether a CONDITIONAL coefficient has headroom at
    module scale -- and it is better to learn that now than in Phase 3.

    Two outcomes, both informative:
      Ahmed-Salam wins clearly  -> conditional adaptation pays at N=3; C3 must
                                   then beat this, not merely the constants.
      Ahmed-Salam barely moves  -> the published method targets long strings (the
                                   paper says the 0.8 model is "reasonably valid"
                                   below five modules), and the module-scale
                                   problem is the coefficient VALUE, not the
                                   region offset. That is C3's opening, stated
                                   with a measured number.

    Either way this is reported as an UPPER BOUND on Ahmed-Salam: the method is
    given true per-substring irradiance, which a real optimizer cannot measure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import baselines  # noqa: F401,E402  (registers "ahmed_salam")
from gmppt.harness import (  # noqa: E402
    METHODS, constant_method, metrics, recal_sample, run_method,
    scenario_set, sweep_constants, write_records,
)

OUT = Path("results/phase2")
PRIMARY = "sub_substring"

SHOW = [
    ("mean_loss_pct", "mean loss %", "{:.2f}"),
    ("median_loss_pct", "median %", "{:.2f}"),
    ("worst_loss_pct", "worst %", "{:.2f}"),
    ("worst_loss_w", "worst W", "{:.1f}"),
    ("costly_frac_pct", "costly %", "{:.1f}"),
    ("region_error_pct", "region err %", "{:.1f}"),
    ("mean_probes", "probes", "{:.1f}"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()

    print("equation (27) check against the paper's worked example:")
    if not baselines.test_ahmed_salam_paper_example():
        print("\nSTOP: the reimplementation does not reproduce the paper's own")
        print("numbers. Fix that before running it on scenarios.")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = scenario_set(args.n)
    geometries = sorted({s.geometry for s in scenarios})
    print(f"\nscenarios: {len(scenarios)}   geometries: {geometries}")

    best_k = min(sweep_constants(recal_sample(scenarios)).items(),
                 key=lambda kv: kv[1])[0]

    runs = {
        "fixed 0.80": METHODS["fixed_0.80"],
        f"recalibrated {best_k:.3f}": constant_method(best_k),
        "ahmed-salam (true G)": METHODS["ahmed_salam"],
    }

    results, table = {}, []
    for name, fn in runs.items():
        print(f"running {name} ...")
        recs = run_method(fn, scenarios)
        slug = name.replace(" ", "_").replace("(", "").replace(")", "")
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
    (OUT / "ahmed_salam_table.md").write_text(md + "\n", encoding="utf-8")
    (OUT / "ahmed_salam.json").write_text(json.dumps(results, indent=2),
                                          encoding="utf-8")
    print("\n" + md)

    # -- the comparison that decides the next step --------------------------
    base = results[f"recalibrated {best_k:.3f}"][PRIMARY]
    asm = results["ahmed-salam (true G)"][PRIMARY]
    d_mean = base["mean_loss_pct"] - asm["mean_loss_pct"]
    d_region = base["region_error_pct"] - asm["region_error_pct"]
    print(f"\non {PRIMARY}, Ahmed-Salam vs the best constant:")
    print(f"   mean loss   {base['mean_loss_pct']:.2f}% -> "
          f"{asm['mean_loss_pct']:.2f}%   ({d_mean:+.2f} pt)")
    print(f"   region err  {base['region_error_pct']:.1f}% -> "
          f"{asm['region_error_pct']:.1f}%   ({d_region:+.1f} pt)")
    print(f"   costly      {base['costly_frac_pct']:.1f}% -> "
          f"{asm['costly_frac_pct']:.1f}%")
    print("\n   Read the region-error and costly columns separately. Ahmed-Salam")
    print("   corrects WHERE THE REGION STARTS; it still lands at 0.80 inside")
    print("   the region. A large region-error gain with little costly-fraction")
    print("   gain is the expected signature, and is precisely C3's opening.")
    print(f"\ntable -> {OUT / 'ahmed_salam_table.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())