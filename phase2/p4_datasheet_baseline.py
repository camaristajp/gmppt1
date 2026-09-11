"""
p4_datasheet_baseline.py  --  P2.4d: the naive datasheet baseline, and the
                              complete buildable baseline set.
REVISION 2 -- calls the renamed verification function.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p4_datasheet_baseline.py
                      OVERWRITE revision 1.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\p4_datasheet_baseline.py --n 2000

PREREQUISITES
    gmppt/harness.py    revision 3
    gmppt/baselines.py  revision 6
    gmppt/datasheet.py  revision 2
    phase2/p1_harness_regression.py exits 0

WHY
    Limitation 8 in the Phase 2 verification log. The baseline set lacked the
    thing an engineer tries FIRST: the module's own V_mp/V_oc from its datasheet.
    Without it, "did you beat simply reading the datasheet?" is unanswered, and
    it is the cheapest question to ask at a defence.

WHAT THIS RUN PRODUCES
    The complete buildable baseline set, on one instrument, one scenario set,
    ordered by how much each conditions on:

      fixed 0.80          one number for every module            3 probes
      datasheet           per MODULE (nameplate)                 3 probes
      datasheet + temp    per module and TEMPERATURE (+ sensor)  3 probes
      recalibrated 0.82   one number tuned on this study's data  3 probes
      Ahmed-Salam scan    per SHADING CONDITION (a full sweep)  ~33 probes

    The first four cost the same three probes. Only the last pays for its
    conditioning, which is the trade the thesis is ultimately about.

WHAT THE PRE-RUN CHECKS ALREADY ESTABLISHED (gmppt/datasheet.py rev 2)
    module-to-module spread        s.d. 0.0152
    temperature 25->60 C           about 0.023 total
    shading, sub-substring         s.d. 0.21          (Phase 1)

    Shading dominates the other two combined by roughly an order of magnitude.
    This run tests whether that translates into loss as expected.

EXPECTATIONS -- RECORDED BEFORE THE RUN
    1. UNIFORM: the datasheet coefficient should clearly beat fixed 0.80's 0.84%.
    2. SUB-SUBSTRING: it should help little, under 0.5 pt against fixed 0.80.

    If both hold, the statement is: per-module and per-temperature conditioning --
    everything nameplate data and a sensor can supply -- closes almost none of the
    gap under shading. The coefficient must be conditioned on the SHADING, which
    requires inferring it from measurement. That rules out the two cheap
    conditional alternatives an examiner reaches for first.

    If expectation 2 fails, the datasheet coefficient carries more shading
    information than Phase 1 implies, and C3's target must be restated against it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import baselines, datasheet  # noqa: F401,E402  (registers methods)
from gmppt.harness import (  # noqa: E402
    METHODS, constant_method, metrics, recal_sample, run_method,
    scenario_set, sweep_constants, write_records,
)

OUT = Path("results/phase2")
GEOMS = ("uniform", "whole_substring", "sub_substring")

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
    print("verifying the datasheet lookup before it is run on scenarios:")
    print("\ncanonical-module coefficient (config pins 0.8107):")
    ok = datasheet.test_canonical_coefficient()
    print("\nbeta_oc availability (from the pvlib CEC table):")
    ok &= datasheet.test_beta_available()
    print("\ntemperature direction, against the simulator:")
    ok &= datasheet.test_direction_against_simulator()
    print("\nc-Si population spread:")
    pop = datasheet.describe_population()
    if not ok:
        print("\nSTOP: a datasheet check failed. Fix before running scenarios.")
        return 1

    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = scenario_set(args.n)
    geometries = [g for g in GEOMS if g in {s.geometry for s in scenarios}]
    print(f"\nscenarios: {len(scenarios)}   geometries: {geometries}")

    best_k = min(sweep_constants(recal_sample(scenarios)).items(),
                 key=lambda kv: kv[1])[0]

    runs = [
        ("fixed 0.80", METHODS["fixed_0.80"]),
        ("datasheet (per module)", METHODS["datasheet"]),
        ("datasheet + temperature", METHODS["datasheet_temp"]),
        (f"recalibrated {best_k:.3f}", constant_method(best_k)),
        ("ahmed-salam scan (realistic)", METHODS["ahmed_salam_scan"]),
    ]

    results, table = {}, []
    for name, fn in runs:
        print(f"running {name} ...")
        recs = run_method(fn, scenarios)
        slug = (name.replace(" ", "_").replace("(", "").replace(")", "")
                    .replace(".", "").replace("-", "_").replace("+", "plus"))
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
    (OUT / "buildable_baselines.md").write_text(md + "\n", encoding="utf-8")
    (OUT / "buildable_baselines.json").write_text(
        json.dumps({"population": pop, "results": results}, indent=2),
        encoding="utf-8")
    print("\n" + md)

    for g in geometries:
        print(f"\n{g}:")
        print(f"   {'method':<32} {'mean %':>8} {'worst W':>9} {'costly %':>10} "
              f"{'probes':>8}")
        for name, _ in runs:
            m = results[name][g]
            print(f"   {name:<32} {m['mean_loss_pct']:>8.2f} "
                  f"{m['worst_loss_w']:>9.1f} {m['costly_frac_pct']:>10.1f} "
                  f"{m['mean_probes']:>8.1f}")

    # -- the two declared expectations, tested -------------------------------
    print("\n" + "=" * 70)
    fx_u = results["fixed 0.80"]["uniform"]["mean_loss_pct"]
    ds_u = results["datasheet (per module)"]["uniform"]["mean_loss_pct"]
    dt_u = results["datasheet + temperature"]["uniform"]["mean_loss_pct"]
    fx_s = results["fixed 0.80"]["sub_substring"]["mean_loss_pct"]
    ds_s = results["datasheet (per module)"]["sub_substring"]["mean_loss_pct"]
    dt_s = results["datasheet + temperature"]["sub_substring"]["mean_loss_pct"]

    e1 = ds_u < fx_u
    e2 = (fx_s - ds_s) < 0.5
    print(f"\nexpectation 1 -- datasheet clearly beats fixed 0.80 on UNIFORM:")
    print(f"   {fx_u:.2f}% -> {ds_u:.2f}%  ({fx_u - ds_u:+.2f} pt)  "
          f"{'HOLDS' if e1 else 'FAILS'}")
    print(f"   with temperature correction: {dt_u:.2f}%  "
          f"({fx_u - dt_u:+.2f} pt vs fixed)")

    print(f"\nexpectation 2 -- datasheet helps little on SUB-SUBSTRING (<0.5 pt):")
    print(f"   {fx_s:.2f}% -> {ds_s:.2f}%  ({fx_s - ds_s:+.2f} pt)  "
          f"{'HOLDS' if e2 else 'FAILS'}")
    print(f"   with temperature correction: {dt_s:.2f}%  "
          f"({fx_s - dt_s:+.2f} pt vs fixed)")

    if e1 and e2:
        print("\n   BOTH HOLD. Per-module and per-temperature conditioning --")
        print("   everything nameplate data and a sensor can supply -- closes")
        print("   almost none of the gap under shading. The coefficient must be")
        print("   conditioned on the SHADING, inferred from measurement. This")
        print("   rules out the two cheap conditional alternatives.")
    else:
        print("\n   AT LEAST ONE EXPECTATION FAILED. Do not proceed on the")
        print("   assumption above -- read the per-geometry table and restate.")
    print(f"\ntable -> {OUT / 'buildable_baselines.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())