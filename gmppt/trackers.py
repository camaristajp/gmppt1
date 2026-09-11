"""
trackers.py  --  time-domain baselines: P&O, InC, PSO.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\gmppt\\trackers.py
                      OVERWRITE the gated stub.

WHY THE STUB IS REPLACED
    The stub gated all three baselines behind Month-3 sign-off of the Gate A
    redirection. That gate was mis-scoped for the BASELINES: the funded proposal
    commits to implementing P&O, InC and PSO in Months 1-3 (section 4.1) and to
    benchmarking against them (section 4.4). No outcome of the Month-3 meeting
    removes that commitment -- they are required under either framing.

    The stub also carried the signature fn(ctx) -> voltage, which is the
    SINGLE-SHOT interface. A tracker holds an operating point and steps it over
    time; it does not return a voltage. Filling those stubs in against Context
    would have produced plausible numbers measuring the wrong thing, which is the
    error class recorded as defect D2. These are written against Trajectory.

    The HYBRID remains where the redirection genuinely bears, and lives in
    gmppt/hybrid.py.

WHAT IS HERE
    P&O is re-exported from gmppt.tracking, where it was defined and verified by
    the four layer checks. It is not reimplemented -- one definition, one
    behaviour.

    InC is defined here. PSO stays gated, for a stated reason (below).

INCREMENTAL CONDUCTANCE
    InC compares incremental conductance dI/dV against instantaneous conductance
    -I/V. At the peak dP/dV = 0, equivalently dI/dV = -I/V; above it the point is
    left of the peak and voltage should rise, below it voltage should fall. Where
    the two are within tolerance the point is HELD, which is InC's advantage over
    P&O: it can sit still at the peak rather than oscillating across it.

    Current is derived as I = P / V. That is exact rather than approximate, and
    it is how the quantity is obtained on hardware sensing both anyway.

    InC is a LOCAL method, like P&O. Its advantage is steady-state behaviour, not
    global search, so it is EXPECTED to be trapped at approximately P&O's rate.
    If it escapes local peaks where P&O does not, one of the two implementations
    is wrong. That expectation is recorded here, before the numbers are read.

WHY PSO IS STILL GATED
    Not on Month-3 -- on an unmade decision. PSO evaluates a POPULATION of
    candidate voltages per iteration, and a control step commands ONE voltage.
    How a population maps onto control steps determines PSO's cost, and the
    funded convergence-time target is defined against metaheuristics, so that
    mapping IS the comparison.

    Choosing it casually would decide the benchmark by an implementation detail.
    It is deferred to its own step where the decision is declared before any
    number is produced.
"""

from __future__ import annotations

from .tracking import (DEFAULT_STEP_FRAC, N_STEPS, START_FRACTION,  # noqa: F401
                       Trajectory, perturb_and_observe)

__all__ = ["perturb_and_observe", "incremental_conductance", "pso"]


def incremental_conductance(traj: Trajectory, temp_c: float | None = None,
                            n_steps: int = N_STEPS,
                            step_frac: float = DEFAULT_STEP_FRAC) -> None:
    """Textbook InC. Starts where P&O starts, so any difference is the method.

    `temp_c` is accepted and unused: it lets every tracker share one runner
    signature with the seeded methods, which do need the module temperature.
    """
    dv = step_frac * traj.v_oc
    v = START_FRACTION * traj.v_oc
    p = traj.step(v)
    i_prev, v_prev = p / max(v, 1e-9), v

    v = max(v - dv, traj.v_floor)      # first move down-voltage, as P&O does

    for _ in range(n_steps - 1):
        p = traj.step(v)
        i = p / max(v, 1e-9)

        d_v, d_i = v - v_prev, i - i_prev
        i_prev, v_prev = i, v

        if abs(d_v) < 1e-12:
            if abs(d_i) < 1e-12:
                continue                        # at the peak, hold
            v = v + (dv if d_i > 0 else -dv)
        else:
            lhs = d_i / d_v                     # incremental conductance
            rhs = -i / max(v, 1e-9)             # instantaneous conductance
            if abs(lhs - rhs) < 1e-6:
                continue                        # at the peak, hold
            v = v + (dv if lhs > rhs else -dv)

        v = float(min(max(v, traj.v_floor), traj.v_oc))


def pso(traj: Trajectory, *args, **kwargs):
    raise NotImplementedError(
        "PSO is gated on a declared decision about how a population evaluation "
        "maps onto control steps. That mapping determines PSO's cost, and the "
        "funded convergence-time target is defined against metaheuristics, so "
        "the mapping is the comparison. Declare it before implementing."
    )