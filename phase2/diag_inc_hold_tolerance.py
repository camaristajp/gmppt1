"""
diag_inc_hold_tolerance.py  --  what should InC's hold band actually be?

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\diag_inc_hold_tolerance.py

RUN FROM THE REPO ROOT:
    python phase2\\diag_inc_hold_tolerance.py

WHY
    InC came out byte-identical to P&O because its hold branch never fired. The
    branch tests whether dI/dV equals -I/V, and "equals" was coded as an absolute
    tolerance of 1e-6 -- a number chosen without measuring anything, in the same
    category as the original probe schedule and the P&O step size, both of which
    this project has since converted from guesses into swept evidence.

    Two problems with 1e-6 specifically:

    UNITS. Both sides are conductances in amps per volt. An absolute tolerance
    therefore scales with the module: the same band means different things on a
    300 W panel and a 100 W panel. The natural quantity is the RELATIVE
    difference |lhs - rhs| / |rhs|, which is dimensionless and transfers.

    SCALE. Nobody measured how close the two sides actually get. This run does.

WHAT IS MEASURED
    P&O is walked over a set of scenarios. At every step the two conductances are
    computed and their relative difference recorded, tagged by whether the
    trajectory is TRAVELLING (first 75% of steps) or SETTLED (last 25%, the same
    steady-state convention the tracking layer already uses).

    A hold band is only useful if the quantity is SMALL when settled and LARGE
    while travelling. If the two distributions overlap, no band separates them
    and InC cannot distinguish the states on a discrete voltage grid.

DECLARED BEFORE THE RUN
    A band is usable if it fires on at least 50% of settled steps and fewer than
    5% of travelling steps. A band that fires while travelling would freeze the
    tracker in the wrong place, which is worse than not holding at all.

    If no candidate band clears both, the honest outcome is to report that InC
    reduces to P&O under static noiseless conditions and to defer its distinct
    behaviour to the dynamic harness. That is a finding about the algorithms,
    not a failure.

NOTE ON THE PREVIOUS DIAGNOSTIC (D12)
    diag_inc_vs_po.py printed a min|lhs-rhs| column header and never populated
    it, so the one number needed to choose this tolerance was missing and the run
    had to be repeated. The column is populated here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt.harness import scenario_set  # noqa: E402
from gmppt.tracking import (DEFAULT_STEP_FRAC, N_STEPS,  # noqa: E402
                            START_FRACTION, STEADY_FRACTION, trajectory_for)

N_SCENARIOS = 50
CANDIDATE_BANDS = (1e-6, 1e-4, 1e-3, 1e-2, 0.05, 0.10, 0.20, 0.50)

MIN_FIRE_SETTLED = 0.50      # band must fire on >= 50% of settled steps
MAX_FIRE_TRAVEL = 0.05       # and on < 5% of travelling steps


def walk_and_record(traj, step_frac=DEFAULT_STEP_FRAC, n_steps=N_STEPS):
    """Walk P&O, recording the InC comparison at every step.

    Returns (relative_diff, absolute_diff) arrays, one entry per step after the
    first two (the comparison needs a previous sample).
    """
    dv = step_frac * traj.v_oc
    v = START_FRACTION * traj.v_oc
    p = traj.step(v)
    i_prev, v_prev = p / max(v, 1e-9), v
    p_prev = p
    direction = -1.0

    rel, absol = [], []
    for _ in range(n_steps - 1):
        v = float(min(max(v + direction * dv, traj.v_floor), traj.v_oc))
        p = traj.step(v)
        i = p / max(v, 1e-9)

        d_v, d_i = v - v_prev, i - i_prev
        if abs(d_v) > 1e-12:
            lhs = d_i / d_v                     # incremental conductance
            rhs = -i / max(v, 1e-9)             # instantaneous conductance
            a = abs(lhs - rhs)
            absol.append(a)
            rel.append(a / max(abs(rhs), 1e-12))

        i_prev, v_prev = i, v
        if p < p_prev:
            direction = -direction
        p_prev = p

    return np.asarray(rel), np.asarray(absol)


def main() -> int:
    print("InC hold band: what should the tolerance be?")
    print("=" * 74)
    print(f"{N_SCENARIOS} scenarios, step {100*DEFAULT_STEP_FRAC:.1f}% of Voc")
    print(f"settled = last {100*STEADY_FRACTION:.0f}% of steps, "
          f"travelling = the rest\n")
    print("declared before the run: a band is usable if it fires on")
    print(f"   >= {100*MIN_FIRE_SETTLED:.0f}% of settled steps AND "
          f"< {100*MAX_FIRE_TRAVEL:.0f}% of travelling steps.")
    print("A band that fires while travelling freezes the tracker in the wrong")
    print("place, which is worse than never holding.\n")

    scenarios = scenario_set(N_SCENARIOS)

    rel_travel, rel_settled = [], []
    abs_travel, abs_settled = [], []

    for sc in scenarios:
        traj = trajectory_for(sc)
        rel, absol = walk_and_record(traj)
        if len(rel) < 10:
            continue
        k = max(1, int(round(STEADY_FRACTION * len(rel))))
        rel_travel.append(rel[:-k])
        rel_settled.append(rel[-k:])
        abs_travel.append(absol[:-k])
        abs_settled.append(absol[-k:])

    rel_travel = np.concatenate(rel_travel)
    rel_settled = np.concatenate(rel_settled)
    abs_travel = np.concatenate(abs_travel)
    abs_settled = np.concatenate(abs_settled)

    print("1. THE QUANTITY, MEASURED")
    print(f"   {'':<12} {'n':>8} {'min':>12} {'median':>12} {'p90':>12}")
    print("   " + "-" * 58)
    for name, arr in (("travelling", rel_travel), ("settled", rel_settled)):
        print(f"   rel {name:<8} {len(arr):>8} {arr.min():>12.3e} "
              f"{np.median(arr):>12.3e} {np.percentile(arr, 90):>12.3e}")
    for name, arr in (("travelling", abs_travel), ("settled", abs_settled)):
        print(f"   abs {name:<8} {len(arr):>8} {arr.min():>12.3e} "
              f"{np.median(arr):>12.3e} {np.percentile(arr, 90):>12.3e}")

    print(f"\n   smallest relative difference ever observed: "
          f"{min(rel_travel.min(), rel_settled.min()):.3e}")
    print(f"   smallest absolute difference ever observed: "
          f"{min(abs_travel.min(), abs_settled.min()):.3e}")
    print("   (the incumbent band was 1e-6, ABSOLUTE -- compare it to the row")
    print("    above to see whether it could ever have fired)")

    print("\n2. CANDIDATE BANDS  (relative)")
    print(f"   {'band':>10} {'fires settled %':>17} {'fires travel %':>16} "
          f"{'usable':>8}")
    print("   " + "-" * 55)
    usable = []
    for b in CANDIDATE_BANDS:
        f_set = float((rel_settled < b).mean())
        f_tra = float((rel_travel < b).mean())
        ok = f_set >= MIN_FIRE_SETTLED and f_tra < MAX_FIRE_TRAVEL
        if ok:
            usable.append((b, f_set, f_tra))
        print(f"   {b:>10.0e} {100*f_set:>17.1f} {100*f_tra:>16.1f} "
              f"{('YES' if ok else 'no'):>8}")

    print("\n3. VERDICT")
    if usable:
        b, f_set, f_tra = usable[0]
        print(f"   -> A usable band exists: {b:.0e} relative.")
        print(f"      Fires on {100*f_set:.1f}% of settled steps and "
              f"{100*f_tra:.1f}% while travelling.")
        print("      InC can distinguish the peak from the approach. Adopt this")
        print("      band, then SWEEP it the way the P&O step size was swept, so")
        print("      the choice is evidenced rather than tuned.")
        print("      Expected effect: InC holds at the peak and gains a little")
        print("      steady efficiency over P&O. Arrival rate should stay at")
        print("      42.1% -- holding still at one peak does not help you find a")
        print("      different one. If arrival moves, something is wrong.")
    else:
        print("   -> NO usable band. The two distributions overlap: any band")
        print("      wide enough to fire at the peak also fires while")
        print("      travelling, which would freeze the tracker in the wrong")
        print("      place.")
        print("      Report that InC reduces to P&O under static, noiseless")
        print("      conditions -- they make the same decision from the same")
        print("      information -- and defer InC's distinct behaviour to the")
        print("      dynamic harness, where irradiance changes give the hold")
        print("      branch something to do. That is a finding about the")
        print("      algorithms, not a shortfall.")

    print("\nAll figures simulated, on training-module scenarios.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())