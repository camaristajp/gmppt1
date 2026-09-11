"""
p8_inc_variable_step.py  --  variable-step InC, given the same treatment as P&O.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p8_inc_variable_step.py
                      NEW FILE. gmppt/trackers.py is NOT modified -- the variant
                      is defined here and moves into the package only if adopted.

RUN FROM THE REPO ROOT:
    python phase2\\p8_inc_variable_step.py

WHY THIS RUN EXISTS -- a correction to how InC was assessed

    Fixed-step InC came out byte-identical to P&O, and the first assessment
    concluded InC "reduces to P&O". That conclusion was too broad, for two
    reasons, and this run corrects both.

    FIRST, THE WRONG FEATURE WAS TESTED. The assessment framed InC's distinction
    as the hold branch and measured whether a hold band could fire selectively.
    But the hold branch is minor. InC's real distinction is that its condition is
    POSITIONAL rather than RETROSPECTIVE: comparing dI/dV against -I/V tells you
    which side of the peak you are on from the present sample, whereas P&O learns
    whether a move helped only after making it.

    In the fixed-step implementation that advantage is definitionally absent,
    because dI/dV was computed by finite difference from the previous sample --
    making it retrospective too. The version was built in which InC's advantage
    cannot appear, and then its absence was measured. Recorded as D14.

    SECOND, THE BASELINE WAS NOT GIVEN THE TREATMENT P&O RECEIVED. P2.7 swept
    P&O's step size across a tenfold range specifically to foreclose the
    objection that the baseline was handicapped by a poor parameter choice. That
    sweep is one of the stronger pieces of Phase 2. InC was then given a single
    fixed step and a hold band that provably could never fire. Reporting it as
    equivalent to P&O on that basis would apply a different standard to the two
    baselines, which is the comparison-across-non-comparable-conditions pattern
    recorded as D2.

    Same standard, both baselines.

WHAT VARIABLE-STEP INC IS
    The standard modern form, and what most published comparisons mean by "InC".
    The step size is made proportional to the magnitude of the power slope:

        step = N * |dP/dV|,  clamped to [STEP_MIN, STEP_MAX] fractions of V_oc

    Far from the peak the slope is steep, so steps are large and convergence is
    fast. Near the peak the slope flattens, so steps shrink and steady-state
    oscillation falls. This is the trade-off fixed-step P&O cannot escape: one
    step size must serve both regimes.

    N is the scaling constant, and it is SWEPT here rather than chosen -- the
    same treatment P&O's fixed step received in P2.7.

THE PREDICTION, DECLARED BEFORE THE RUN
    Variable-step InC should beat fixed-step InC and P&O on steady efficiency and
    on convergence steps.

    Its ARRIVAL RATE should stay near 42.1%.

    The reasoning: adaptive stepping changes HOW a tracker climbs a hill, not
    WHICH hill it is on. A local method that starts on the wrong peak converges
    to the wrong peak faster and more precisely. Nothing about step sizing
    supplies information about distant regions of the curve.

    If arrival rate moves by more than about 5 pt, that reasoning is wrong -- and
    since the same reasoning is what explains why P&O traps at all, it would need
    investigating before any tracker result is reported. The prediction is
    written here so the outcome is a test rather than an interpretation.

SCOPE
    Training-module scenarios, a baseline-fairness check rather than a reportable
    comparison. All figures simulated.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config  # noqa: E402
from gmppt.harness import scenario_set  # noqa: E402
from gmppt.tracking import (DEFAULT_STEP_FRAC, N_STEPS,  # noqa: E402
                            START_FRACTION, Trajectory, _print_block,
                            perturb_and_observe, summarise, trajectory_for)
from gmppt.trackers import incremental_conductance  # noqa: E402

OUT = config.RESULTS_DIR / "phase2"

# Scaling constants swept, as P&O's fixed step was swept in P2.7.
N_SWEEP = (0.001, 0.005, 0.02, 0.05, 0.20)

STEP_MIN_FRAC = 0.0005      # floor: below this the tracker cannot move
STEP_MAX_FRAC = 0.02        # ceiling: above this it overshoots the peak

ARRIVAL_TOLERANCE_PT = 5.0  # prediction fails if arrival moves more than this


def inc_variable_step(traj: Trajectory, temp_c: float | None = None,
                      n_steps: int = N_STEPS, n_scale: float = 0.02) -> None:
    """InC with the step size proportional to |dP/dV|.

    The InC direction test is unchanged -- compare incremental conductance
    against instantaneous conductance -- and only the MAGNITUDE of each step
    varies. So any difference from fixed-step InC is attributable to the step
    rule and not to a different decision procedure.

    `temp_c` is accepted and unused so every tracker shares one runner signature.
    """
    v_min = STEP_MIN_FRAC * traj.v_oc
    v_max = STEP_MAX_FRAC * traj.v_oc

    v = START_FRACTION * traj.v_oc
    p = traj.step(v)
    i_prev, v_prev, p_prev = p / max(v, 1e-9), v, p

    v = max(v - DEFAULT_STEP_FRAC * traj.v_oc, traj.v_floor)

    for _ in range(n_steps - 1):
        p = traj.step(v)
        i = p / max(v, 1e-9)

        d_v = v - v_prev
        d_i = i - i_prev
        d_p = p - p_prev
        i_prev, v_prev, p_prev = i, v, p

        if abs(d_v) < 1e-12:
            continue

        # step magnitude from the power slope
        slope = abs(d_p / d_v)
        dv = float(min(max(n_scale * slope, v_min), v_max))

        lhs = d_i / d_v                      # incremental conductance
        rhs = -i / max(v, 1e-9)              # instantaneous conductance
        v = v + (dv if lhs > rhs else -dv)
        v = float(min(max(v, traj.v_floor), traj.v_oc))


def _po(traj, temp_c=None, n_steps=N_STEPS, **kw):
    perturb_and_observe(traj, n_steps=n_steps, **kw)


def run(fn, scenarios, **kwargs):
    recs = []
    for sc in scenarios:
        traj = trajectory_for(sc)
        fn(traj, temp_c=float(sc.temp_c), **kwargs)
        recs.append(traj.metrics())
    return recs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    args = ap.parse_args()

    print("P2.7c  variable-step InC, swept as P&O was swept")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 78)
    print("correcting two errors in the earlier InC assessment:")
    print("   D14  the hold branch was tested, but InC's real distinction is a")
    print("        POSITIONAL condition -- and the fixed-step implementation")
    print("        computed it retrospectively, so the advantage was absent by")
    print("        construction and its absence was then measured")
    print("   D2-class  P&O's step was swept over a tenfold range; InC was given")
    print("        one fixed step. Different standards for two baselines.\n")
    print("PREDICTION, declared before the run:")
    print("   variable-step InC beats fixed-step on steady efficiency and")
    print("   convergence, and its ARRIVAL RATE stays near 42.1%.")
    print("   Adaptive stepping changes HOW a tracker climbs a hill, not WHICH")
    print("   hill it is on.")
    print(f"   If arrival moves by more than {ARRIVAL_TOLERANCE_PT:.0f} pt, the")
    print("   reasoning that explains why P&O traps is wrong and must be")
    print("   investigated before any tracker result is reported.\n")

    scenarios = scenario_set(args.n)
    print(f"{len(scenarios)} scenarios (training modules; baseline-fairness")
    print("check, NOT a reportable comparison)\n")

    # -- references ----------------------------------------------------------
    print("1. REFERENCES  (fixed step, as run in P2.7)")
    refs = {}
    for name, fn in (("P&O, fixed step", _po),
                     ("InC, fixed step", incremental_conductance)):
        recs = run(fn, scenarios)
        refs[name] = summarise(recs, name)
        _print_block(refs[name])

    po = refs["P&O, fixed step"]["multi_peak"]
    inc_fixed = refs["InC, fixed step"]["multi_peak"]

    # -- the sweep -----------------------------------------------------------
    print("\n2. VARIABLE-STEP INC, SWEEPING THE SCALING CONSTANT")
    print(f"   step = N * |dP/dV|, clamped to "
          f"[{STEP_MIN_FRAC:.4f}, {STEP_MAX_FRAC:.3f}] of Voc\n")
    print(f"   {'N':>8} {'steady %':>10} {'arrival %':>11} {'conv steps':>12} "
          f"{'worst W':>9}")
    print("   " + "-" * 54)

    sweep, blocks = [], {}
    for n_scale in N_SWEEP:
        recs = run(inc_variable_step, scenarios, n_scale=n_scale)
        s = summarise(recs, f"InC variable, N={n_scale}")
        b = s["multi_peak"]
        blocks[n_scale] = s
        conv = ("-" if b["median_conv_steps"] is None
                else f"{b['median_conv_steps']:.0f}")
        sweep.append({"n_scale": n_scale,
                      "steady_eff_pct": b["steady_eff_pct"],
                      "reached_pct": b["reached_pct"],
                      "median_conv_steps": b["median_conv_steps"],
                      "worst_energy_lost_w": b["worst_energy_lost_w"]})
        print(f"   {n_scale:>8.3f} {b['steady_eff_pct']:>10.2f} "
              f"{b['reached_pct']:>11.1f} {conv:>12} "
              f"{b['worst_energy_lost_w']:>9.2f}")

    # -- the prediction, tested ---------------------------------------------
    best = max(sweep, key=lambda r: r["steady_eff_pct"])
    print(f"\n3. THE PREDICTION, TESTED")
    print(f"   best variable-step configuration: N={best['n_scale']:.3f}")
    print(f"   {'':<26} {'steady %':>10} {'arrival %':>11} {'conv':>8}")
    print("   " + "-" * 58)
    for label, b in (("P&O, fixed", po), ("InC, fixed", inc_fixed)):
        conv = ("-" if b["median_conv_steps"] is None
                else f"{b['median_conv_steps']:.0f}")
        print(f"   {label:<26} {b['steady_eff_pct']:>10.2f} "
              f"{b['reached_pct']:>11.1f} {conv:>8}")
    conv_b = ("-" if best["median_conv_steps"] is None
              else f"{best['median_conv_steps']:.0f}")
    print(f"   {'InC, variable (best)':<26} {best['steady_eff_pct']:>10.2f} "
          f"{best['reached_pct']:>11.1f} {conv_b:>8}")

    d_steady = best["steady_eff_pct"] - inc_fixed["steady_eff_pct"]
    d_arrival = best["reached_pct"] - po["reached_pct"]

    print(f"\n   steady efficiency vs fixed-step InC: {d_steady:+.2f} pt")
    print(f"   arrival rate vs P&O:                 {d_arrival:+.1f} pt "
          f"(tolerance +/-{ARRIVAL_TOLERANCE_PT:.0f})")

    arrival_held = abs(d_arrival) <= ARRIVAL_TOLERANCE_PT
    if arrival_held:
        print("\n   -> PREDICTION HOLDS on arrival rate. Adaptive stepping")
        print("      changes how the tracker climbs, not which peak it climbs.")
        print("      InC remains a LOCAL method, and the local-peak problem is")
        print("      not a step-sizing problem. This is the premise the thesis")
        print("      rests on, and it is now tested rather than assumed.")
    else:
        print("\n   -> PREDICTION FAILS. Arrival rate moved materially with step")
        print("      sizing, which contradicts the account of why P&O traps.")
        print("      STOP. Investigate before reporting any tracker result --")
        print("      the explanation underlying the whole comparison is at")
        print("      stake, not merely this baseline.")

    if d_steady > 0.05:
        print(f"\n   Variable-step InC is the stronger baseline "
              f"({d_steady:+.2f} pt steady).")
        print("   Report it as InC. Reporting only the fixed-step form would")
        print("   understate the competition, which is the mirror image of the")
        print("   error this project guards against.")
    else:
        print(f"\n   Variable stepping does not improve InC materially here")
        print(f"   ({d_steady:+.2f} pt). Report both forms and the sweep, so the")
        print("   baseline is shown to have been given a fair range rather than")
        print("   a single guessed parameter.")

    print("\n   NOTE: the arrival-rate column is the one that matters for the")
    print("   thesis. Steady efficiency and convergence describe how well a")
    print("   tracker sits on whichever peak it found; arrival describes whether")
    print("   it found the right one.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "inc_variable_step.json").write_text(
        json.dumps({"references": {k: v for k, v in refs.items()},
                    "sweep": sweep, "best": best,
                    "arrival_prediction_held": bool(arrival_held)},
                   indent=2, default=float), encoding="utf-8")
    print(f"\nresults -> {OUT / 'inc_variable_step.json'}")
    print("All figures simulated, on training modules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())