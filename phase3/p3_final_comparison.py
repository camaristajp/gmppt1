"""
p3_final_comparison.py  --  Phase 3, step 3: C3 beside the baselines.
REVISION 2 -- selectable model tag; classical scan-then-bisect added.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase3\\p3_final_comparison.py
                      OVERWRITE revision 1.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase3\\p3_final_comparison.py --model-tag c3_two_stage_full

    Add --confirm-test only when ready to open the held-out modules.

WHAT CHANGED IN REVISION 2

  1. MODEL TAG. Revision 1 loaded the default pickle, which is the PILOT model
     trained on 2,000 scenarios. P3.6 retrained on 20,000 and saved as
     'c3_two_stage_full'. Reporting a pilot figure while a full-scale model
     exists would understate the result and misdescribe what was run, so the tag
     is now explicit and printed in the header.

  2. CLASSICAL SCAN-THEN-BISECT ADDED. P3.5 found that scanning the five fixed
     probe positions and then bisecting around the winner reaches 0.578% at 9
     probes and 0.231% at 11 -- beating Ahmed-Salam's 1.52% at 63 probes by a
     wide margin. That baseline was absent from the Phase 2 set and from
     revision 1 of this table. Its absence was a genuine gap in the comparison:
     it is the most obvious method an engineer would try, and it is strong.

     Two budgets are included, 9 and 11 probes, bracketing C3's 6. Reporting only
     the budget that flatters C3 would be the same error as comparing a
     single-landing 0.80 against a three-candidate rule.

  3. TEST OPENINGS ARE COUNTED. The held-out set was opened once on 2026-08-18
     with the pilot model. Each opening costs a little of its independence, so
     the script now appends to a ledger at results/phase3/test_openings.json and
     prints how many times it has been opened. Two openings -- once for the
     pilot, once for the final model -- is standard and defensible. Five is not.

WHAT THIS RUN PRODUCES
    PART A -- validation modules. Repeatable; run freely while tuning.
    PART B -- held-out modules. The measurement that says whether C3 learned the
              physics of the curve or the identities of its training modules.

COST NOTE
    The probes column is not decoration. C3 spends 6 per decision, the constants
    3, the classical search 9 or 11, and the realistic Ahmed-Salam scan ~33
    (P2.4c showed 30 performs the same as 240; the 63 reported here is the
    default budget, not the requirement). A module-level optimizer runs this
    every control cycle on MCU-class hardware, and a sequential search is also
    exposed to conditions changing mid-search. Accuracy figures should never be
    read without this column.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import baselines, config, datasheet, dataset  # noqa: F401,E402
from gmppt.features import PROBE_FRACTIONS  # noqa: E402
from gmppt.harness import (METHODS, Context, constant_method, metrics,  # noqa: E402
                           recal_sample, run_method, scenario_set,
                           sweep_constants, write_records)
from gmppt.model import TwoStageModel  # noqa: E402

OUT = config.RESULTS_DIR / "phase3"
LEDGER = OUT / "test_openings.json"
GEOMS = ("uniform", "whole_substring", "sub_substring")
N_SUB = int(config.N_SUBSTRINGS)

SHOW = [
    ("mean_loss_pct", "mean loss %", "{:.2f}"),
    ("median_loss_pct", "median %", "{:.2f}"),
    ("worst_loss_pct", "worst %", "{:.2f}"),
    ("worst_loss_w", "worst W", "{:.1f}"),
    ("costly_frac_pct", "costly %", "{:.1f}"),
    ("region_error_pct", "region err %", "{:.1f}"),
    ("mean_probes", "probes", "{:.1f}"),
]


# ---------------------------------------------------------------------------
# The classical baseline that was missing
# ---------------------------------------------------------------------------

def make_scan_refine(steps: int):
    """Scan the fixed probe positions, then bisect around the winner.

    Given the SAME starting positions as C3's feature probes, so the comparison
    isolates what is done with the measurements from where they are taken. Each
    bisection step costs two probes, so the budget is 5 + 2*steps.
    """
    def fn(ctx: Context) -> float:
        vs = [f * ctx.v_oc for f in PROBE_FRACTIONS]
        powers = [ctx.probe(v) for v in vs]
        i = int(np.argmax(powers))
        best_v, best_p = vs[i], powers[i]
        span = ctx.v_oc / (2.0 * N_SUB)
        for _ in range(steps):
            span *= 0.5
            for cand in (best_v - span, best_v + span):
                cand = min(max(cand, 0.02 * ctx.v_oc), ctx.v_oc)
                p = ctx.probe(cand)
                if p > best_p:
                    best_v, best_p = cand, p
        return best_v

    fn.__name__ = f"scan_refine_{steps}"
    return fn


# ---------------------------------------------------------------------------

def scenarios_for_modules(modules: list[str], n_target: int,
                          oversample: int = 6) -> list:
    """Scenarios restricted to a given module set."""
    from gmppt import scenarios as scen
    want = set(modules)
    out = []
    raw = scen.generate(dataset.pool(), n_target * oversample, train_only=False)
    for sc in raw:
        if str(sc.module) in want:
            out.append(sc)
            if len(out) >= n_target:
                break
    return out


def record_opening(tag: str, n: int, result: float) -> int:
    """Append to the held-out opening ledger and return the count."""
    entries = []
    if LEDGER.exists():
        try:
            entries = json.loads(LEDGER.read_text(encoding="utf-8"))
        except Exception:
            entries = []
    entries.append({
        "opened_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_tag": tag, "n_scenarios": int(n),
        "c3_mean_loss_all_pct": float(result),
    })
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return len(entries)


def run_all(scenarios: list, model: TwoStageModel, label: str) -> dict:
    n_sub_scen = len([s for s in scenarios if s.geometry == "sub_substring"])
    best_k = (min(sweep_constants(recal_sample(scenarios)).items(),
                  key=lambda kv: kv[1])[0] if n_sub_scen > 20 else 0.82)

    runs = [
        ("fixed 0.80", METHODS["fixed_0.80"]),
        ("datasheet (per module)", METHODS["datasheet"]),
        (f"recalibrated {best_k:.3f}", constant_method(best_k)),
        ("classical scan+bisect x2", make_scan_refine(2)),
        ("classical scan+bisect x3", make_scan_refine(3)),
        ("ahmed-salam scan", METHODS["ahmed_salam_scan"]),
        ("C3 two-stage", model.as_method()),
    ]

    geometries = [g for g in GEOMS if g in {s.geometry for s in scenarios}]
    results, table = {}, []
    for name, fn in runs:
        print(f"   running {name} ...")
        recs = run_method(fn, scenarios)
        slug = (name.replace(" ", "_").replace("(", "").replace(")", "")
                    .replace(".", "").replace("-", "_").replace("+", "plus"))
        write_records(recs, OUT / f"{label}_{slug}.csv")
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
    (OUT / f"{label}_comparison.md").write_text(md + "\n", encoding="utf-8")
    print("\n" + md)
    return results


def summarise(results: dict, geometries: list[str], label: str) -> None:
    for g in geometries:
        print(f"\n{g}  ({label}):")
        print(f"   {'method':<28} {'mean %':>8} {'worst W':>9} "
              f"{'costly %':>10} {'probes':>8}")
        for name, blocks in results.items():
            m = blocks.get(g)
            if not m or not m.get("n"):
                continue
            print(f"   {name:<28} {m['mean_loss_pct']:>8.2f} "
                  f"{m['worst_loss_w']:>9.1f} {m['costly_frac_pct']:>10.1f} "
                  f"{m['mean_probes']:>8.1f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--model-tag", default="c3_two_stage_full",
                    help="c3_two_stage_full (20,000 scenarios) or "
                         "c3_two_stage (2,000 pilot)")
    ap.add_argument("--confirm-test", action="store_true")
    args = ap.parse_args()

    print("PHASE 3 / P3  final comparison  (revision 2)")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print(f"  model: {args.model_tag}")
    print("=" * 70)

    try:
        model = TwoStageModel.load(tag=args.model_tag)
    except FileNotFoundError:
        print(f"model '{args.model_tag}' not found in {OUT}.")
        print("Run  python phase3\\p6_build_full_dataset.py --n 20000 --retrain")
        return 1

    split = dataset.module_split()
    print(f"modules: {split.summary()}")
    OUT.mkdir(parents=True, exist_ok=True)
    payload = {"model_tag": args.model_tag}

    # ---------------------------------------------------------------- Part A
    print(f"\nPART A  VALIDATION COMPARISON  ({args.n} scenarios)")
    va_scen = scenarios_for_modules(split.val, args.n)
    print(f"   {len(va_scen)} scenarios on validation modules\n")
    va_results = run_all(va_scen, model, "val")
    geoms = [g for g in GEOMS if g in {s.geometry for s in va_scen}]
    summarise(va_results, geoms, "validation modules")
    payload["validation"] = va_results

    if "whole_substring" in geoms:
        c3 = va_results["C3 two-stage"]["whole_substring"]
        print("\n   C3 against each baseline, whole_substring:")
        for name, blocks in va_results.items():
            if name == "C3 two-stage":
                continue
            b = blocks.get("whole_substring")
            if not b:
                continue
            print(f"     {name:<28} {b['mean_loss_pct']:>6.2f}% at "
                  f"{b['mean_probes']:>4.0f} probes  ->  C3 "
                  f"{c3['mean_loss_pct']:.2f}% at {c3['mean_probes']:.0f}  "
                  f"({b['mean_loss_pct'] - c3['mean_loss_pct']:+.2f} pt)")

    # ---------------------------------------------------------------- Part B
    if not args.confirm_test:
        print("\nPART B  HELD-OUT TEST -- NOT RUN")
        if LEDGER.exists():
            n_prev = len(json.loads(LEDGER.read_text(encoding="utf-8")))
            print(f"   the held-out set has been opened {n_prev} time(s) so far")
        print("   When ready:  python phase3\\p3_final_comparison.py "
              f"--model-tag {args.model_tag} --confirm-test")
    else:
        print(f"\nPART B  HELD-OUT TEST  ({args.n} scenarios, "
              f"{len(split.test)} reserved modules)")
        te_scen = scenarios_for_modules(split.test, args.n)
        print(f"   {len(te_scen)} scenarios on held-out modules\n")
        te_results = run_all(te_scen, model, "test")
        tgeoms = [g for g in GEOMS if g in {s.geometry for s in te_scen}]
        summarise(te_results, tgeoms, "HELD-OUT modules")
        payload["test"] = te_results

        v = va_results["C3 two-stage"]["all"]["mean_loss_pct"]
        t = te_results["C3 two-stage"]["all"]["mean_loss_pct"]
        n_open = record_opening(args.model_tag, len(te_scen), t)
        print(f"\n   GENERALISATION GAP: validation {v:.3f}%  ->  "
              f"held-out {t:.3f}%   ({t - v:+.3f} pt)")
        if abs(t - v) < 0.30:
            print("   No measurable degradation on unseen module designs. The C3")
            print("   claim stands on held-out data.")
            print("   (Note: c-Si module designs are similar -- population "
                  "coefficient")
            print("   s.d. is 0.0152 -- so this is a WEAK generalisation test. "
                  "The")
            print("   harder question, generalisation across shading conditions, "
                  "is")
            print("   covered by the scenario set itself.)")
        else:
            print("   The model degrades on unseen modules. Suspect "
                  "k_datasheet,")
            print("   n_cells and isc_over_voc, which identify a module fairly")
            print("   precisely; drop or coarsen them and retrain.")
        print(f"\n   HELD-OUT SET OPENED {n_open} TIME(S) IN TOTAL")
        print(f"   ledger -> {LEDGER}")
        if n_open > 2:
            print("   More than two openings erodes the independence of this "
                  "set.")
            print("   Report the count in the thesis alongside the figure.")

    (OUT / "final_comparison.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")
    print(f"\nresults -> {OUT / 'final_comparison.json'}")
    print("\nRead the probes column beside every accuracy figure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())