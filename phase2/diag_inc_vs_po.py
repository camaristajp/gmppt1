"""Are P&O and InC taking the same trajectory, and why? No conclusions drawn."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt.harness import scenario_set
from gmppt.tracking import (DEFAULT_STEP_FRAC, N_STEPS, START_FRACTION,
                            trajectory_for)

HOLD_TOL = 1e-6


def inc_instrumented(traj, step_frac=DEFAULT_STEP_FRAC, n_steps=N_STEPS):
    """InC with the hold branch counted."""
    holds = 0
    dv = step_frac * traj.v_oc
    v = START_FRACTION * traj.v_oc
    p = traj.step(v)
    i_prev, v_prev = p / max(v, 1e-9), v
    v = max(v - dv, traj.v_floor)
    for _ in range(n_steps - 1):
        p = traj.step(v)
        i = p / max(v, 1e-9)
        d_v, d_i = v - v_prev, i - i_prev
        i_prev, v_prev = i, v
        if abs(d_v) < 1e-12:
            if abs(d_i) < 1e-12:
                holds += 1
                continue
            v = v + (dv if d_i > 0 else -dv)
        else:
            lhs, rhs = d_i / d_v, -i / max(v, 1e-9)
            if abs(lhs - rhs) < HOLD_TOL:
                holds += 1
                continue
            v = v + (dv if lhs > rhs else -dv)
        v = float(min(max(v, traj.v_floor), traj.v_oc))
    return holds


scenarios = scenario_set(20)
print(f"{len(scenarios)} scenarios, step {100*DEFAULT_STEP_FRAC:.1f}% Voc\n")
print(f"{'#':>3} {'identical?':>11} {'first diff':>11} {'InC holds':>10} "
      f"{'min|lhs-rhs|':>13}")
print("-" * 52)

total_holds, n_identical = 0, 0
for n, sc in enumerate(scenarios):
    t_po = trajectory_for(sc)
    from gmppt.tracking import perturb_and_observe
    perturb_and_observe(t_po)

    t_inc = trajectory_for(sc)
    holds = inc_instrumented(t_inc)
    total_holds += holds

    a = np.asarray(t_po.v_hist)
    b = np.asarray(t_inc.v_hist)
    same = len(a) == len(b) and np.allclose(a, b, atol=1e-12)
    n_identical += bool(same)
    if same:
        first = "-"
    else:
        k = min(len(a), len(b))
        d = np.nonzero(~np.isclose(a[:k], b[:k], atol=1e-12))[0]
        first = str(d[0]) if len(d) else "len only"

    # how close does the InC hold test ever get to firing?
    print(f"{n:>3} {str(same):>11} {first:>11} {holds:>10}")

print(f"\nidentical trajectories: {n_identical}/{len(scenarios)}")
print(f"total InC hold events:  {total_holds}")
print("\nIf trajectories are identical AND holds are 0, InC has reduced to P&O")
print("because its hold branch never fires on a discrete voltage grid.")