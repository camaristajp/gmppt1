"""
p8_c4_fallback.py  --  Phase 3, step 8: what the fallback can certify.
REVISION 2 -- one sweep scored three ways; vacuous-bound branch added.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase3\\p8_c4_fallback.py
                      OVERWRITE revision 1.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase3\\p8_c4_fallback.py

    Add --confirm-test only once a threshold has been chosen AND the bound is
    non-vacuous. That would be the THIRD opening of the held-out set; it has been
    opened twice.

WHAT CHANGED IN REVISION 2

  1. ONE SWEEP, THREE GEOMETRIES. Revision 1 called sweep_thresholds once per
     geometry, re-simulating the whole scenario set each time -- roughly 33 full
     passes over 800 scenarios. The records already carry the geometry, so
     gmppt/fallback.py now scores one pass for every geometry. About a threefold
     saving with identical numbers.

  2. THE VACUOUS-BOUND BRANCH. Revision 1 had exactly two outcomes: a threshold
     was accepted, or none was. The quick check produced neither -- thresholds
     WERE accepted, and the bound they yielded (11.92 W) was nearly three times
     worse than the unguarded model's measured worst case (4.22 W), because the
     fallback rule's own tail dominates.

     Revision 1 would have printed that as a successful claim. A bound worse than
     the measurement it replaces is not a bound worth reporting, and that text is
     exactly what gets pasted into a log or a paper. The branch now exists and
     says so plainly.

  3. THE GEOMETRY SCOPE IS PRINTED WITH THE NUMBER. Revision 1 chose the
     threshold on whole_substring and printed the bound unqualified. Every other
     Phase 3 headline is geometry-scoped; this one now travels with its label,
     and sub_substring is reported beside it rather than silently dropped.

WHAT THIS CLOSES
    P3.7 measured a worst case of 2.4 W on held-out whole-substring scenarios --
    the largest loss that OCCURRED on 800 scenarios. An observation, not a bound.
    A bound requires a rule that acts when the model is unreliable.

WHAT MAY AND MAY NOT BE CLAIMED
    With the fallback active, worst-case loss is bounded by the worse of the
    guarded model's worst case and the fallback rule's own worst case. Only the
    second is a property of a deterministic rule rather than of a learned model,
    so only it can be stated as a bound -- and if it exceeds the unguarded
    measured maximum, the exercise yields nothing worth claiming.

    If no threshold satisfies the declared conditions, OR if the bound is
    vacuous, the correct outcome is to report the measured worst case and state
    plainly that no certified bound is claimed. That is a finding about the
    confidence signal and the available fallback, not a failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, dataset, fallback  # noqa: E402
from gmppt.harness import metrics, run_method, write_records  # noqa: E402
from gmppt.model import TwoStageModel  # noqa: E402
from phase3.p3_final_comparison import scenarios_for_modules  # noqa: E402

OUT = config.RESULTS_DIR / "phase3"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=800)
    ap.add_argument("--model-tag", default="c3_two_stage_full")
    ap.add_argument("--scope", default="whole_substring",
                    choices=["whole_substring", "sub_substring", "all"],
                    help="geometry the threshold is chosen on; the reported "
                         "figure is scoped to it and labelled as such")
    ap.add_argument("--confirm-test", action="store_true",
                    help="evaluate the chosen threshold on held-out modules "
                         "(a THIRD opening -- use once, and record it)")
    args = ap.parse_args()

    print("PHASE 3 / P8  the confidence-gated fallback  (revision 2)")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print(f"  model: {args.model_tag}   scope: {args.scope}")
    print("=" * 74)

    try:
        model = TwoStageModel.load(tag=args.model_tag)
    except FileNotFoundError:
        print(f"model '{args.model_tag}' not found in {OUT}.")
        return 1

    # -- mechanical checks: a guard that cannot fire would pass a sweep -------
    print("\n1. MECHANICAL CHECKS")
    guarded = fallback.GuardedModel(model=model)
    ok = fallback.test_probe_cost(guarded)
    print()
    ok &= fallback.test_threshold_extremes(guarded)
    if not ok:
        print("\nSTOP. A guard that cannot fire, or that fires unconditionally,")
        print("would pass the threshold sweep silently. Fix before proceeding.")
        return 1

    split = dataset.module_split()
    va = scenarios_for_modules(split.val, args.n)
    print(f"\n{len(va)} scenarios on validation modules")

    present = sorted({str(s.geometry) for s in va})
    print(f"geometries present: {', '.join(present)}")

    # -- one sweep, scored for every geometry --------------------------------
    print("\n2. THRESHOLD SWEEP  (one pass per configuration, scored three ways)")
    sweep = fallback.sweep_thresholds(model, va)

    payload = {"model_tag": args.model_tag, "scope": args.scope,
               "n_scenarios": len(va), "sweep": sweep, "verdicts": {}}

    for geom in sweep:
        if not sweep[geom]:
            continue
        print(f"\n3. ACCEPTANCE -- {geom}")
        t, reason, info = fallback.choose_threshold(sweep[geom])
        print(f"\n   -> {reason}")
        payload["verdicts"][geom] = {"chosen_threshold": t, "verdict": reason,
                                     **info}

    # -- the claim, or the honest absence of one -----------------------------
    print("\n" + "=" * 74)
    scope = args.scope
    if scope not in sweep or not sweep[scope]:
        print(f"\nSCOPE '{scope}' WAS NOT TESTED -- no scenarios of that "
              f"geometry were generated.")
        print("This is not a failed test. Re-run with a scope present in the")
        print(f"scenario set: {', '.join(present)}")
        v = None
    else:
        v = payload["verdicts"][scope]
        base = sweep[scope][fallback.NO_FALLBACK]
        rule = sweep[scope][fallback.RULE_ALONE]

        if v["chosen_threshold"] is None:
            print(f"\nNO CERTIFIED BOUND IS CLAIMED  [{scope}]")
            print("No threshold satisfied all three declared conditions.")
            print(f"Report the measured worst case: "
                  f"{base['worst_loss_w']:.2f} W at "
                  f"{base['mean_probes']:.1f} probes, mean loss "
                  f"{base['mean_loss_pct']:.3f}%.")
            print("State that the confidence signal does not separate the tail")
            print("cases well enough to support a bound. This is a finding about")
            print("the signal, not a failure.")
        elif v["vacuous"]:
            print(f"\nNO CERTIFIED BOUND IS CLAIMED  [{scope}]")
            print(f"A threshold ({v['chosen_threshold']:.3f}) does satisfy all "
                  f"three conditions and")
            print(f"improves the guarded worst case to "
                  f"{v['guarded_worst_w']:.2f} W. But the bound is the WORSE of")
            print(f"that and the fallback rule's own worst case "
                  f"({rule['worst_loss_w']:.2f} W), giving")
            print(f"{v['bound_w']:.2f} W -- no better than the unguarded "
                  f"measured maximum of {base['worst_loss_w']:.2f} W.")
            print("\nCertifying would make the reportable number worse than not")
            print("certifying. Report the measured worst case instead.")
            print("\nWHAT REMAINS REPORTABLE, and it is not nothing:")
            print(f"   The learned model beats the classical rule it was meant "
                  f"to be insured by,")
            print(f"   on BOTH axes -- mean loss "
                  f"{base['mean_loss_pct']:.3f}% against "
                  f"{rule['mean_loss_pct']:.3f}%, worst case "
                  f"{base['worst_loss_w']:.2f} W")
            print(f"   against {rule['worst_loss_w']:.2f} W. The seed is "
                  f"strictly better than its own fallback.")
        else:
            print(f"\nBOUNDED WORST CASE, as the evidence supports it  [{scope}]")
            print(f"   With the fallback active at confidence threshold "
                  f"{v['chosen_threshold']:.3f},")
            print(f"   worst-case loss does not exceed {v['bound_w']:.2f} W on "
                  f"the declared scenario")
            print(f"   distribution, for {scope} geometry -- the worse of the "
                  f"guarded model")
            print(f"   ({v['guarded_worst_w']:.2f} W) and the three-candidate "
                  f"probe rule it defers to")
            print(f"   ({rule['worst_loss_w']:.2f} W).")
            print(f"\n   Cost: {v['mean_probes']:.1f} probes on average; the "
                  f"fallback fires on")
            print(f"   {v['trigger_frac_pct']:.1f}% of scenarios. Mean loss "
                  f"{v['guarded_mean_pct']:.3f}%.")
            print("\n   Scope this claim to the declared distribution AND to the")
            print("   geometry named above. It is not a universal guarantee.")

        # the other geometries, reported beside the headline rather than dropped
        print(f"\n   Other geometries, unguarded model:")
        for g in sweep:
            if g == scope or not sweep[g]:
                continue
            b = sweep[g][fallback.NO_FALLBACK]
            print(f"     {g:<18} mean {b['mean_loss_pct']:>6.3f}%   "
                  f"worst {b['worst_loss_w']:>6.2f} W")

    # -- optional held-out confirmation --------------------------------------
    if args.confirm_test:
        if v is None or v["chosen_threshold"] is None:
            print("\n4. HELD-OUT CONFIRMATION SKIPPED -- no threshold accepted.")
        elif v["vacuous"]:
            print("\n4. HELD-OUT CONFIRMATION SKIPPED -- the bound is vacuous.")
            print("   Spending a third opening of the held-out set to confirm a")
            print("   bound that is not worth claiming would be a poor trade.")
        else:
            t = v["chosen_threshold"]
            print(f"\n4. HELD-OUT CONFIRMATION  (threshold {t:.3f})")
            print("   THIS IS A THIRD OPENING OF THE HELD-OUT SET. Record it.\n")
            te = scenarios_for_modules(split.test, args.n)
            g = fallback.GuardedModel(model=model, threshold=t)
            g.reset()
            recs = run_method(g.as_method(), te)
            write_records(recs, OUT / "test_guarded.csv")
            for geom in ("whole_substring", "sub_substring", None):
                m = metrics(recs, geometry=geom)
                if not m.get("n"):
                    continue
                trig = fallback._trigger_pct(g.log, geom or "all")
                print(f"   {(geom or 'all'):<18} mean {m['mean_loss_pct']:>6.3f}%"
                      f"   worst {m['worst_loss_w']:>6.2f} W   "
                      f"probes {m['mean_probes']:.1f}   fires {trig:.1f}%")
            payload["held_out"] = {"threshold": t}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "c4_fallback.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")
    print(f"\nresults -> {OUT / 'c4_fallback.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())