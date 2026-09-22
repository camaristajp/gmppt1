"""
p7_tracker_comparison.py  --  P2.7: the trackers, side by side.
REVISION 3 -- selectable module split (train/val); validation run is reportable.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p7_tracker_comparison.py
                      OVERWRITE revision 2.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\p7_tracker_comparison.py                 # training modules (design check)
    python phase2\\p7_tracker_comparison.py --split val     # validation modules (REPORTABLE)

WHAT CHANGED IN REVISION 3
    A --split argument selects the module set the comparison runs on:

        train  (default)  the seeded training-module set, scenario_set(n) -- a
                          design check, exactly as revisions 1-2 ran. Default so
                          nothing that referenced the old behaviour changes.
        val               scenarios drawn from the held-back VALIDATION modules,
                          via scenarios_for_modules(split.val, n) -- the same
                          mechanism p3_final_comparison.py Part A uses. THIS is
                          the reportable tracker comparison the thesis and papers
                          cite; the training run never was (it reuses modules the
                          model selection saw).

    The HELD-OUT (test) split is deliberately NOT reachable here. It is opened
    only through p3_final_comparison.py --confirm-test, which ledgers every
    opening (test_openings.json) and budgets the count. Letting this runner open
    it would be an unledgered access to the one set whose independence the whole
    project protects. Arrival/worst-case on validation is what becomes citable;
    the held-out generalisation figure stays p3's single, counted measurement.

    Reference baseline numbers quoted below (P&O 42.1%, etc.) were measured on
    training modules; the validation run will differ in the second digit. The
    CRITERIA are module-independent and unchanged.

WHAT CHANGED IN REVISION 2
    hybrid.py revision 3 renamed the private alias _seed_voltage to
    seed_voltage. The alias existed only so this runner would not need touching
    during the file split, and keeping a private-named duplicate of a public
    function is the same one-thing-two-names pattern that D16 was about. Both are
    now gone.

    Two other tidy-ups made at the same time: DEFAULT_STEP_FRAC is imported at
    the top rather than fetched through __import__ inside a loop, and _po_from is
    imported once rather than on every scenario.

    No behaviour changes. The clamp measurement runs on the same trajectories and
    should return the same 0 of 200.

WHAT THIS SUPERSEDES
    gmppt/hybrid.py once had a main() that ran the first comparison. Its verdict
    logic contained defect D10 (below) and was removed in revision 2 of that
    file. The library functions it defines are correct and are imported here.

DEFECT D10 -- the criterion that passed on an invisible margin
    hybrid.py revision 1 declared that the hybrid must beat the seed-only control
    on STEADY EFFICIENCY. It passed: 99.92% against 99.92%, identical to
    displayed precision, on a strict > comparison.

    That is the fifth instance of this project's recurring failure -- a criterion
    declared in advance that measured less than the claim depended on (D2, D4,
    D5, D8, D10). Steady efficiency is SATURATED at this level, exactly as mean
    power loss was found to be saturated in the single-shot work.

    The fine-tracking stage IS justified, but on axes where the difference is
    visible:

        arrival rate   seed only 98.2%   hybrid 99.4%    +1.2 pt
        worst case     seed only 4.47 W  hybrid 3.13 W   -1.34 W

    Condition (iii) is restated here to name those axes. Steady efficiency is
    still REPORTED, as a number rather than a criterion, so the saturation is
    visible instead of hidden behind a pass.

DEFECT D16 -- one quantity, two derivations
    hybrid.py revision 2 recovered the substring region by inverting the model's
    coefficient, int(k * N_SUB), while fallback.py read it from the classifier.
    Because predict_k clips the offset to [0, 1] inclusive, an overshooting
    offset regressor yields exactly 1.0 and the inverted region lands one
    interval too high. Revision 3 takes the region from the classifier in both
    files.

    No reported figure was affected -- the clamp was measured never to bind, and
    fallback.py's confident branch discards its region variable -- but this
    runner's clamp measurement DOES use the region, so it is re-run here against
    the corrected definition.

THE CLAMP, MEASURED RATHER THAN INFERRED
    An earlier revision found bounded and free hybrids identical in every digit
    and concluded the region clamp was not load-bearing. Plausible -- P&O started
    inside the correct region hill-climbs to that region's peak and never nears
    the boundary -- but it reasoned from an absence.

    No new instrumentation is needed. Trajectory already records v_hist, so the
    UNBOUNDED hybrid's voltage history answers it directly: if the free variant
    never leaves the seed's predicted region, the clamp could never have bound.
    Measured from data already recorded.

ACCEPTANCE -- DECLARED BEFORE THIS RUN, on multi-peak scenarios
      (i)   the hybrid reaches the GMPP on >= 90%          (P&O: 42.1%)
      (ii)  steady efficiency >= 99%                        (P&O: 76.6%)
      (iii) it beats seed-only by >= 0.5 pt on ARRIVAL RATE, or by >= 10% on
            WORST-CASE WATTS

    If (iii) fails, the honest report is that the SEED solves trapping and the
    fine-tracking stage is optional: a simpler method than the proposal
    specified, which is a result and not a shortfall.

EXPECTED BEFORE THE RUN
    InC is a local method like P&O and should trap at a similar rate. If it
    escapes local peaks where P&O does not, one implementation is wrong.

SCOPE
    Default (--split train): training-module scenarios, a design check, NOT
    reportable. With --split val the SAME comparison runs on validation modules
    and IS reportable. The held-out split is not reachable here; it is opened
    only through p3_final_comparison.py, which ledgers and budgets each opening.
    All simulated; multi-peak magnitude at full module scale awaits partner
    measurement.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, dataset  # noqa: E402
from gmppt.harness import scenario_set  # noqa: E402
from gmppt.hybrid import (SEED_PROBE_COST, _po_from, make_hybrid,  # noqa: E402
                          make_seed_only, seed_voltage)
from gmppt.model import TwoStageModel  # noqa: E402
from gmppt.tracking import (DEFAULT_STEP_FRAC, N_STEPS,  # noqa: E402
                            START_FRACTION, _print_block, parked_at_gmpp,
                            perturb_and_observe, summarise, trajectory_for)
from gmppt.trackers import incremental_conductance  # noqa: E402

OUT = config.RESULTS_DIR / "phase2"
N_SUB = int(config.N_SUBSTRINGS)

MIN_REACHED_MULTI_PCT = 90.0
MIN_STEADY_MULTI_PCT = 99.0
MIN_REACHED_GAIN_PT = 0.5
MIN_WORST_GAIN_FRAC = 0.10


def scenarios_for_modules(modules: list[str], n_target: int,
                          oversample: int = 6) -> list:
    """Scenarios restricted to a given module set.

    Copied verbatim from p3_final_comparison.py so the validation run here draws
    from the SAME mechanism as the region/seed comparison, keeping the two tables
    comparable. train_only=False so the validation modules -- held back from the
    training pool -- are reachable.
    """
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


def _oracle(traj, temp_c=None, n_steps=N_STEPS, **_):
    parked_at_gmpp(traj, n_steps=n_steps)


def _po(traj, temp_c=None, n_steps=N_STEPS, **kw):
    perturb_and_observe(traj, n_steps=n_steps, **kw)


def run(fn, scenarios, keep_traj: bool = False):
    """Run one tracker. Returns (metrics list, trajectories or None)."""
    recs, trajs = [], ([] if keep_traj else None)
    for sc in scenarios:
        traj = trajectory_for(sc)
        fn(traj, temp_c=float(sc.temp_c))
        recs.append(traj.metrics())
        if keep_traj:
            trajs.append(traj)
    return recs, trajs


def clamp_would_bind(scenarios, model) -> tuple[int, int]:
    """Would the region clamp ever have bound? Answered from v_hist.

    Runs the UNBOUNDED hybrid and asks whether its operating point ever left the
    region the seed predicted. A trajectory that never leaves is one on which the
    clamp could not have acted, so a count of zero makes the "clamp is dead code"
    conclusion a measurement rather than an inference from equal scores.

    The region comes from seed_voltage, which since hybrid.py revision 3 reads it
    from the classifier rather than inverting the coefficient (D16).
    """
    n_left, n_total = 0, 0
    for sc in scenarios:
        traj = trajectory_for(sc)
        v_seed, region = seed_voltage(traj, model, float(sc.temp_c))
        width = traj.v_oc / N_SUB
        lo, hi = region * width, (region + 1) * width
        _po_from(traj, v_seed, N_STEPS - SEED_PROBE_COST, DEFAULT_STEP_FRAC)
        after = traj.v_hist[SEED_PROBE_COST:]
        n_total += 1
        if any(v < lo - 1e-9 or v > hi + 1e-9 for v in after):
            n_left += 1
    return n_left, n_total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--split", choices=("train", "val"), default="train",
                    help="train = scenario_set (design check); "
                         "val = validation modules (reportable). The held-out "
                         "split is reachable only via p3_final_comparison.py.")
    args = ap.parse_args()

    print("P2.7  tracker comparison: P&O, InC, seed, hybrid  (revision 3)")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 78)
    print(f"equal budget: {N_STEPS} control steps for every method.")
    print(f"the seed's {SEED_PROBE_COST} feature probes are CHARGED as steps.")
    print(f"P&O and InC start at {START_FRACTION:.2f}*Voc; the hybrid starts "
          f"where the seed lands.\n")
    print("acceptance, declared before this run, on multi-peak scenarios:")
    print(f"   (i)   arrival rate >= {MIN_REACHED_MULTI_PCT:.0f}%")
    print(f"   (ii)  steady efficiency >= {MIN_STEADY_MULTI_PCT:.0f}%")
    print(f"   (iii) beats seed-only by >= {MIN_REACHED_GAIN_PT} pt arrival OR "
          f">= {100*MIN_WORST_GAIN_FRAC:.0f}% worst-case watts")
    print("   (iii) restated after D10: steady efficiency is saturated and")
    print("   cannot separate the seeded methods.\n")
    print("expected: InC traps at about P&O's rate. A large gap means one of")
    print("the two implementations is wrong.\n")

    try:
        model = TwoStageModel.load(tag="c3_two_stage_full")
    except FileNotFoundError:
        print("model 'c3_two_stage_full' not found.")
        return 1

    if args.split == "val":
        split = dataset.module_split()
        print(f"modules: {split.summary()}")
        scenarios = scenarios_for_modules(split.val, args.n)
        print(f"{len(scenarios)} scenarios on VALIDATION modules "
              f"(REPORTABLE comparison)")
    else:
        scenarios = scenario_set(args.n)
        print(f"{len(scenarios)} scenarios (training modules; design check)")

    runs = [
        ("oracle [not buildable]", _oracle),
        ("P&O", _po),
        ("InC", incremental_conductance),
        ("seed only", make_seed_only(model)),
        ("hybrid, free", make_hybrid(model, bounded=False)),
        ("hybrid, bounded", make_hybrid(model, bounded=True)),
    ]

    results = {}
    for name, fn in runs:
        print(f"\n   running {name} ...")
        recs, _ = run(fn, scenarios)
        results[name] = summarise(recs, name)
        _print_block(results[name])

    print("\n" + "=" * 78)
    print("\nMULTI-PEAK SCENARIOS -- where the thesis lives")
    print(f"   {'method':<26} {'steady %':>10} {'arrival %':>11} "
          f"{'conv steps':>12} {'worst W':>9}")
    print("   " + "-" * 72)
    for name, _ in runs:
        b = results[name]["multi_peak"]
        if not b:
            continue
        conv = ("-" if b["median_conv_steps"] is None
                else f"{b['median_conv_steps']:.0f}")
        print(f"   {name:<26} {b['steady_eff_pct']:>10.2f} "
              f"{b['reached_pct']:>11.1f} {conv:>12} "
              f"{b['worst_energy_lost_w']:>9.2f}")

    print("\n   CONVERGENCE COLUMN: median over trajectories that CONVERGED.")
    print("   P&O and InC converge on a minority of multi-peak cases, so their")
    print("   figure is conditional on success while the hybrid's is nearly")
    print("   unconditional. Never report these side by side without the")
    print("   arrival rate beside them.")

    po = results["P&O"]["multi_peak"]
    inc = results["InC"]["multi_peak"]
    seed = results["seed only"]["multi_peak"]
    free = results["hybrid, free"]["multi_peak"]
    bound = results["hybrid, bounded"]["multi_peak"]

    print("\nINC AGAINST ITS PREDICTION")
    gap = inc["reached_pct"] - po["reached_pct"]
    print(f"   P&O {po['reached_pct']:.1f}%, InC {inc['reached_pct']:.1f}%  "
          f"({gap:+.1f} pt)")
    if gap == 0.0:
        print("   -> IDENTICAL, not merely similar. Under static noiseless")
        print("      conditions with a fixed step, InC's hold branch cannot fire")
        print("      selectively and its decision reduces to P&O's. See the")
        print("      variable-step sweep in phase2/p8_inc_variable_step.py.")
    elif abs(gap) <= 10.0:
        print("   -> as expected: both are local hill-climbers. InC's edge is")
        print("      steady-state behaviour, not global search.")
    else:
        print("   -> NOT as expected. A local method should not escape local")
        print("      peaks at a materially different rate. Inspect both")
        print("      implementations before reporting either.")

    print("\nDOES THE REGION CLAMP EVER BIND?")
    n_left, n_total = clamp_would_bind(scenarios, model)
    print(f"   unbounded hybrid left the predicted region on {n_left}/{n_total}"
          f" trajectories")
    if n_left == 0:
        print("   -> MEASURED, not inferred: the search never approaches the")
        print("      boundary, so the clamp could never bind. Report the simpler")
        print("      unbounded form; the clamp is dead code.")
    else:
        print(f"   -> the clamp would act on {n_left} trajectories. bounded vs "
              f"free differ by "
              f"{bound['steady_eff_pct'] - free['steady_eff_pct']:+.3f} pt.")

    best_name, best = max(
        (("hybrid, free", free), ("hybrid, bounded", bound)),
        key=lambda kv: (kv[1]["reached_pct"], -kv[1]["worst_energy_lost_w"]))
    reach_gain = best["reached_pct"] - seed["reached_pct"]
    worst_gain = ((seed["worst_energy_lost_w"] - best["worst_energy_lost_w"])
                  / max(seed["worst_energy_lost_w"], 1e-9))

    print("\nVERDICT")
    c1 = best["reached_pct"] >= MIN_REACHED_MULTI_PCT
    c2 = best["steady_eff_pct"] >= MIN_STEADY_MULTI_PCT
    c3 = (reach_gain >= MIN_REACHED_GAIN_PT
          or worst_gain >= MIN_WORST_GAIN_FRAC)
    print(f"   best variant: {best_name}")
    print(f"   (i)   arrival {best['reached_pct']:.1f}%  -> "
          f"{'PASS' if c1 else 'FAIL'}")
    print(f"   (ii)  steady  {best['steady_eff_pct']:.2f}%  -> "
          f"{'PASS' if c2 else 'FAIL'}")
    print(f"   (iii) arrival {reach_gain:+.1f} pt, worst "
          f"{100*worst_gain:+.1f}%  -> {'PASS' if c3 else 'FAIL'}")
    print(f"   [reported, not a criterion] steady: seed-only "
          f"{seed['steady_eff_pct']:.3f}%, hybrid "
          f"{best['steady_eff_pct']:.3f}% -- saturated")

    print(f"\n   over P&O: {best['steady_eff_pct'] - po['steady_eff_pct']:+.2f}"
          f" pt steady, {best['reached_pct'] - po['reached_pct']:+.1f} pt "
          f"arrival")
    print(f"   over InC: {best['steady_eff_pct'] - inc['steady_eff_pct']:+.2f}"
          f" pt steady, {best['reached_pct'] - inc['reached_pct']:+.1f} pt "
          f"arrival")

    if c1 and c2 and c3:
        print("\n   The hybrid solves local-peak trapping and its fine-tracking")
        print("   stage earns its place -- on arrival rate and worst case, not")
        print("   on mean efficiency.")
    elif c1 and c2:
        print("\n   The SEED solves trapping; the fine-tracking stage adds")
        print("   nothing measurable. Report the simpler method.")
    else:
        print("\n   Does NOT clear the declared bar. Diagnose before PSO.")

    OUT.mkdir(parents=True, exist_ok=True)
    out_name = f"tracker_comparison_{args.split}.json"
    (OUT / out_name).write_text(
        json.dumps({"split": args.split, "results": results,
                    "clamp_left": n_left, "n_scenarios": len(scenarios)},
                   indent=2, default=float),
        encoding="utf-8")
    print(f"\nresults -> {OUT / out_name}")
    print("PSO convergence is compared in p9_pso_comparison.py.")
    if args.split == "val":
        print("Figures on VALIDATION modules -- reportable. The held-out")
        print("generalisation figure stays p3's single, counted measurement.")
    else:
        print("All figures simulated, on training modules (design check).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())