"""
p5_cost_frontier.py  --  Phase 3, step 5: map the cost-accuracy frontier.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase3\\p5_cost_frontier.py
                      NEW FILE.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase3\\p5_cost_frontier.py

WHY THIS RUN EXISTS
    P3.4 found something that changes how the thesis must be argued. A simple
    classical search -- scan five fixed points, then bisect around the winner --
    reaches 0.12% mean loss on whole-substring shading at 17 probes. That beats
    C3's 0.28% at 6 probes on accuracy, and it beats the published Ahmed-Salam
    method (1.52% at ~63 probes) decisively.

    That baseline was absent from the Phase 2 set. Its absence was a gap in the
    comparison, and the honest response is to add it properly rather than sample
    it once at whichever budget happened to be convenient.

    P3.4 also exposed a defect in its own verdict logic: it compared C3 against
    "the better naive control" WITHOUT matching probe cost, and so concluded the
    probe schedule carried the result. Cost-matched, C3 beats the 5-probe naive
    scan by 1.62 pt -- the learning does carry it. The comparison is only
    meaningful along a fixed budget.

WHAT THIS RUN PRODUCES
    The hill-climb at a range of budgets, so the classical method appears as a
    CURVE rather than a point, and C3's position on the frontier becomes a
    measured claim rather than an assertion from one sample.

    The question the curve answers: at what budget does the classical search
    first match C3? If it needs three times the measurements, that ratio is the
    contribution, stated precisely.

THE COST AXIS IS NOT DECORATION
    A module-level optimizer runs this every control cycle on MCU-class hardware.
    Seventeen sequential readings take time, and the proposal explicitly targets
    rapidly changing irradiance, where conditions can shift mid-search. A
    one-shot prediction and a 17-step search are different propositions even at
    equal accuracy. This run measures the accuracy side; the timing side needs
    the gated time-domain layer.

DECLARED BEFORE RUNNING
    C3's contribution is stated as a COST RATIO: the smallest classical budget
    that matches C3's mean loss, divided by C3's 6 probes.

        ratio >= 2.0   the cost claim is substantial and stands as the headline
        1.3 - 2.0      real but modest; report it as such, not as a headline
        < 1.3          the classical search is competitive at similar cost and
                       the learned model's advantage is not measurement cost

    Fixed here, before the run, so the outcome is a test rather than a reading.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import baselines, config, datasheet, dataset  # noqa: F401,E402
from gmppt.features import PROBE_FRACTIONS  # noqa: E402
from gmppt.harness import (METHODS, Context, constant_method, metrics,  # noqa: E402
                           run_method, write_records)
from gmppt.model import TwoStageModel  # noqa: E402
from phase3.p3_final_comparison import scenarios_for_modules  # noqa: E402

OUT = config.RESULTS_DIR / "phase3"
FIGS = OUT / "figures"
N_SUB = int(config.N_SUBSTRINGS)
GEOMS = ("uniform", "whole_substring", "sub_substring")

REFINE_STEPS = (0, 1, 2, 3, 4, 6, 8)     # bisection steps after the scan
RATIO_SUBSTANTIAL = 2.0
RATIO_MODEST = 1.3


def make_scan_refine(steps: int):
    """Scan the fixed probe positions, then bisect around the winner.

    steps=0 is the plain best-of-five scan. Each additional step halves the
    search span and costs two probes, so the budget is 5 + 2*steps. This is the
    classical method C3 is being compared against, and it is deliberately given
    the SAME starting positions as C3's feature probes so the comparison isolates
    what is done with the measurements rather than where they are taken.
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--geometry", default="whole_substring")
    args = ap.parse_args()

    print("PHASE 3 / P5  cost-accuracy frontier")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 70)
    print("declared: contribution is the cost ratio -- the smallest classical")
    print(f"          budget matching C3, divided by C3's 6 probes.")
    print(f"          >= {RATIO_SUBSTANTIAL} substantial | "
          f"{RATIO_MODEST}-{RATIO_SUBSTANTIAL} modest | "
          f"< {RATIO_MODEST} not a cost advantage\n")

    try:
        model = TwoStageModel.load()
    except FileNotFoundError:
        print("trained model not found. Run  python -m gmppt.model  first.")
        return 1

    split = dataset.module_split()
    scenarios = scenarios_for_modules(split.val, args.n)
    print(f"{len(scenarios)} scenarios on validation modules")
    print(f"probe schedule: {[f'{f:.2f}' for f in PROBE_FRACTIONS]} of Voc\n")

    geometries = [g for g in GEOMS if g in {s.geometry for s in scenarios}]
    key = args.geometry if args.geometry in geometries else "all"

    rows = []

    # -- the classical curve -------------------------------------------------
    print("1. CLASSICAL SEARCH AT INCREASING BUDGET")
    print(f"   {'steps':>6} {'probes':>8} {'mean %':>9} {'worst %':>9} "
          f"{'worst W':>9} {'costly %':>10}")
    for steps in REFINE_STEPS:
        recs = run_method(make_scan_refine(steps), scenarios)
        m = metrics(recs, geometry=key if key != "all" else None)
        rows.append({"method": f"scan+refine x{steps}", "steps": steps, **m})
        print(f"   {steps:>6} {m['mean_probes']:>8.0f} "
              f"{m['mean_loss_pct']:>9.3f} {m['worst_loss_pct']:>9.1f} "
              f"{m['worst_loss_w']:>9.1f} {m['costly_frac_pct']:>10.1f}")

    # -- reference points ----------------------------------------------------
    print("\n2. REFERENCE POINTS")
    refs = [("C3 two-stage", model.as_method()),
            ("ahmed-salam scan", METHODS["ahmed_salam_scan"]),
            ("recalibrated 0.82", constant_method(0.82)),
            ("fixed 0.80", METHODS["fixed_0.80"])]
    ref_rows = []
    print(f"   {'method':<22} {'probes':>8} {'mean %':>9} {'worst %':>9} "
          f"{'worst W':>9} {'costly %':>10}")
    for name, fn in refs:
        recs = run_method(fn, scenarios)
        write_records(recs, OUT / f"frontier_{name.replace(' ', '_')}.csv")
        m = metrics(recs, geometry=key if key != "all" else None)
        ref_rows.append({"method": name, **m})
        print(f"   {name:<22} {m['mean_probes']:>8.0f} "
              f"{m['mean_loss_pct']:>9.3f} {m['worst_loss_pct']:>9.1f} "
              f"{m['worst_loss_w']:>9.1f} {m['costly_frac_pct']:>10.1f}")

    # -- the verdict ---------------------------------------------------------
    c3 = next(r for r in ref_rows if r["method"] == "C3 two-stage")
    c3_loss, c3_probes = c3["mean_loss_pct"], c3["mean_probes"]

    matching = [r for r in rows if r["mean_loss_pct"] <= c3_loss]
    print("\n" + "=" * 70)
    print(f"\nVERDICT on {key}")
    print(f"   C3: {c3_loss:.3f}% at {c3_probes:.0f} probes")

    if matching:
        first = min(matching, key=lambda r: r["mean_probes"])
        ratio = first["mean_probes"] / c3_probes
        print(f"   smallest classical budget matching it: "
              f"{first['mean_probes']:.0f} probes "
              f"({first['method']}, {first['mean_loss_pct']:.3f}%)")
        print(f"   COST RATIO: {ratio:.2f}x")
        if ratio >= RATIO_SUBSTANTIAL:
            print(f"\n   -> SUBSTANTIAL. The classical search needs "
                  f"{ratio:.1f} times the measurements to reach the same\n"
                  f"      accuracy. Cost is the headline claim, stated as a "
                  f"measured ratio.")
        elif ratio >= RATIO_MODEST:
            print(f"\n   -> MODEST. Real but not headline-sized. Report the "
                  f"ratio plainly and lean\n      on the one-shot property "
                  f"(robustness to changing conditions) instead.")
        else:
            print(f"\n   -> NOT A COST ADVANTAGE. The classical search is "
                  f"competitive at similar cost.\n      C3's case must rest on "
                  f"something else -- one-shot prediction under\n      changing "
                  f"irradiance, or noise robustness -- and that needs the "
                  f"time-domain\n      layer to demonstrate.")
    else:
        top = min(rows, key=lambda r: r["mean_loss_pct"])
        print(f"   no classical budget tested reaches C3 "
              f"(best {top['mean_loss_pct']:.3f}% at "
              f"{top['mean_probes']:.0f} probes)")
        print("\n   -> C3 IS UNMATCHED at every budget tested. Extend "
              "REFINE_STEPS before\n      claiming this: an unmatched result "
              "usually means the sweep stopped early.")

    print("\nNOTE ON THE TAIL")
    print("   Read worst % and worst W together. A method whose catastrophic")
    print("   misses fall on dim panels shows a large percentage and a small")
    print("   wattage. C4 is about the WATTS.")

    # -- figure --------------------------------------------------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        FIGS.mkdir(parents=True, exist_ok=True)
        NAVY, CORAL, AMBER = "#1F3864", "#C0504D", "#C8842A"
        fig, ax = plt.subplots(figsize=(8.2, 5))
        ax.plot([r["mean_probes"] for r in rows],
                [r["mean_loss_pct"] for r in rows], "o-", color=AMBER, lw=1.8,
                label="classical scan + refine")
        for r in ref_rows:
            col = CORAL if r["method"].startswith("C3") else NAVY
            ax.plot(r["mean_probes"], r["mean_loss_pct"], "o", color=col,
                    ms=10 if col == CORAL else 8)
            ax.annotate(r["method"], (r["mean_probes"], r["mean_loss_pct"]),
                        textcoords="offset points", xytext=(9, 4), fontsize=9,
                        color="#555")
        ax.set_xscale("log")
        ax.set_xlabel("probes per decision", fontsize=10)
        ax.set_ylabel("mean power loss (%)", fontsize=10)
        ax.set_title(f"Cost–accuracy frontier ({key}, validation modules)",
                     fontsize=12)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(FIGS / "cost_frontier.png", dpi=150)
        plt.close(fig)
        print(f"\nfigure  -> {FIGS / 'cost_frontier.png'}")
    except ImportError:
        print("\n   matplotlib not installed; skipping figure")

    (OUT / "cost_frontier.json").write_text(
        json.dumps({"geometry": key, "classical": rows, "references": ref_rows},
                   indent=2, default=float), encoding="utf-8")
    print(f"results -> {OUT / 'cost_frontier.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())