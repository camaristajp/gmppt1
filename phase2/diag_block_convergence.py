"""
diag_block_convergence.py  --  is a sequence block-convergent once D20's time
                               compression is removed? A refinement ladder that
                               tells coarseness apart from divergence.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\diag_block_convergence.py
                      NEW FILE. Nothing else is modified. gmppt/ is not touched.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\diag_block_convergence.py --sequence 10-50
    python phase2\\diag_block_convergence.py --sequence 30-100   (control)

WHY THIS RUN EXISTS -- two diagnoses of one number, which the D20 fix now lets
us tell apart

    p11 revision 5 forced BLOCKS_PER_PHASE["10-50"] = 24 on a single
    measurement: Sequence 10-50 failed p11's check 0 at 6 blocks/phase by
    0.330 pt (6 vs 12), where Sequence 30-100 converged at 6 (0.001 pt). Rev 5
    read that as CURVE SHAPE -- low-irradiance curves are steeply nonlinear, so
    coarse blocks approximate them badly, so use more blocks.

    But that 0.330 pt was measured with TIME_COMPRESSION["10-50"] = 10.0 still
    active. Rev 5 predates the D20 fix. The handoff's §7.2 reaches the OPPOSITE
    diagnosis from the same data: the gaps WIDENED with more blocks (0.330 at 6,
    2.051 at 24), and widening gaps are DIVERGENCE, not coarseness -- a coarse
    discretisation CONVERGES as it is refined. §7.2 attributes the cause to the
    10x compression having made Sequence A's ramps 10x steeper than the standard
    specifies (5-500 W/m2/s against a specified 0.5-50), not to curve shape.

    The two diagnoses predict OPPOSITE things about the refinement ladder, and
    with TIME_COMPRESSION now 1.0 everywhere they can finally be separated:

      COMPRESSION WAS THE CAUSE (§7.2 / D20 right)
        -> 10-50 now converges at 6, like 30-100. Rev 5's 24 is not merely
           unnecessary but HARMFUL: rev 5's own rev-3 history shows a higher
           block count makes degeneracy arrive EARLIER (steps are divided among
           blocks), collapsing the valid range of the period sweep.

      CURVE SHAPE WAS THE CAUSE (rev 5 right)
        -> gaps SHRINK monotonically as blocks rise and cross tolerance at some
           count. That count is the converged value -- but it must be MEASURED
           at compression 1.0, not the compression-era 24.

      STILL DIVERGES AT COMPRESSION 1.0 (§7.2's fallback branch)
        -> gaps fail to shrink toward tolerance. Block discretisation genuinely
           cannot represent this sequence's low-irradiance ramps; its dynamic
           claim must rest on Sequence B plus shading-pattern transitions, and
           its period sweep must NOT be run.

    p11 as written cannot decide this: it locks 24 and its check 0 compares only
    24 vs 48, so it never tests the 6-block prediction §7.2 named. This isolates
    that one question before p11's declared count is set.

DECLARED BEFORE THE RUN

    PRIMARY QUANTITY: the hybrid's aggregate dynamic efficiency (EN 50530 eq. 7)
    at a 100 ms control period, at blocks_per_phase along the ladder
    LADDER = (6, 12, 24, 48), for the chosen sequence, at whatever compression
    gmppt/dynamic.py currently declares (printed below and required to be 1.0 for
    this to be a D20 test).

    The gap g(n) = |eff(2n) - eff(n)| is p11's own check-0 statistic. TOLERANCE
    is dynamic.py's BLOCK_CONVERGENCE_PT, unchanged.

    VERDICT, decided automatically:
      (A) CONVERGED AT 6      g(6->12) < tol. If the sequence is 10-50, this
                              CONFIRMS D20: compression, not curve shape, caused
                              the original 0.330 pt. Recommend
                              BLOCKS_PER_PHASE[seq] = 6.
      (B) CONVERGED LATER     g(6->12) >= tol but a later g(n->2n) < tol with
                              gaps shrinking. Genuine coarseness. Recommend
                              BLOCKS_PER_PHASE[seq] = the converged n (the
                              MEASURED value, which may or may not be 24).
      (C) DIVERGENT           no g(n->2n) < tol across the ladder. If gaps
                              WIDEN, this is §7.2's "block discretisation cannot
                              represent low-irradiance ramps" -- do NOT run this
                              sequence's period sweep.

WHAT EACH VERDICT LOOKS LIKE (so the check can fire -- it is written to be
capable of every outcome)

    (A) first gap under tol, e.g.  |12-6| = 0.02
    (B) shrinking gaps crossing tol, e.g.  0.33, 0.09  -> converged at 12
    (C) flat or growing gaps, e.g.  0.33, 0.61, 1.12  -> divergent

    A gap is TRUSTED only if the finer rung is well-formed: every block holds at
    least MIN_STEPS_PER_BLOCK control steps. A rung at the one-step floor makes
    fast-slope trajectories identical and can fake OR mask convergence, so a gap
    into a degenerate rung is reported but never decides the verdict (the same
    D19 rule p11 applies).

METHOD COVERAGE
    The hybrid only, which is p11's check-0 quantity. That keeps this comparable
    to p11 check 0 and cheap. The hybrid is sample-robust (unlike P&O), so 10
    scenarios determine the gap well; --n raises it if wanted.

SCOPE
    Training-module scenarios, shaded only, 100 ms. All figures simulated.
    Divergences from EN 50530 are declared in gmppt/dynamic.py and travel with
    any figure taken from here.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config  # noqa: E402
from gmppt.dynamic import (BLOCK_CONVERGENCE_PT, SEQUENCES,  # noqa: E402
                           TIME_COMPRESSION, DynamicTrajectory,
                           aggregate_efficiency, dynamic_trajectory_for,
                           make_profile)
from gmppt.harness import scenario_set  # noqa: E402
from gmppt.hybrid import SEED_PROBE_COST, seed_voltage  # noqa: E402
from gmppt.model import TwoStageModel  # noqa: E402
from gmppt.tracking import DEFAULT_STEP_FRAC, START_FRACTION  # noqa: E402

OUT = config.RESULTS_DIR / "phase2"

# The refinement ladder. Successive rungs double the block count, so each
# adjacent pair is exactly p11's check-0 comparison (n vs 2n).
LADDER = (6, 12, 24, 48)

# Same floor p11 uses: a block holding a single control step means the profile
# has stopped shrinking and fast slopes have degenerated to identical
# trajectories. A gap into such a rung is not trustworthy.
MIN_STEPS_PER_BLOCK = 2

CONTROL_PERIOD_S = 0.1   # fixed here; this run isolates BLOCKS, not the period.


# ---------------------------------------------------------------------------
# THE HYBRID -- identical to p11's t_hybrid, so this measures p11's check-0
# quantity and nothing else.
# ---------------------------------------------------------------------------

def t_hybrid(traj: DynamicTrajectory, model: TwoStageModel,
             temp_c: float = 25.0, step_frac: float = DEFAULT_STEP_FRAC,
             **_) -> None:
    v_seed, _ = seed_voltage(traj, model, temp_c)
    n = traj.n_steps - SEED_PROBE_COST
    if n <= 0:
        return
    dv = step_frac * traj.v_oc
    v = float(min(max(v_seed, traj.v_floor), traj.v_oc))
    p_prev = traj.step(v)
    direction = -1.0
    for _ in range(n - 1):
        v = float(min(max(v + direction * dv, traj.v_floor), traj.v_oc))
        p = traj.step(v)
        if p < p_prev:
            direction = -direction
        p_prev = p


def hybrid_aggregate_at(scenarios, sequence: str, bpp: int,
                        model: TwoStageModel, cycles: int) -> tuple[float, int]:
    """Hybrid aggregate dynamic efficiency at one block count, 100 ms.

    Returns (aggregate_pct, min_block_steps_across_all_slopes). The second value
    is what decides whether the rung is well-formed enough to trust a gap into
    it -- the D19 rule, checked directly rather than proxied.
    """
    _, rows = SEQUENCES[sequence]
    profiles = [make_profile(sequence, r[1], blocks_per_phase=bpp,
                             control_period_s=CONTROL_PERIOD_S,
                             max_cycles=cycles) for r in rows]
    min_block_steps = min(int(p.block_steps.min()) for p in profiles)

    per_slope = []
    for prof in profiles:
        effs = []
        for sc in scenarios:
            traj = dynamic_trajectory_for(sc, prof)
            t_hybrid(traj, model=model, temp_c=float(sc.temp_c))
            effs.append(traj.metrics()["dynamic_efficiency_pct"])
        per_slope.append(float(np.mean(effs)))
    return aggregate_efficiency(per_slope), min_block_steps


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10,
                    help="shaded scenarios; the hybrid is sample-robust so 10 "
                         "determines the gap well")
    ap.add_argument("--sequence", default="10-50",
                    choices=list(SEQUENCES.keys()),
                    help="10-50 is the sequence in question; 30-100 is the "
                         "control that already converged at 6")
    ap.add_argument("--cycles", type=int, default=1)
    args = ap.parse_args()

    tol = float(BLOCK_CONVERGENCE_PT)
    comp = float(TIME_COMPRESSION.get(args.sequence, 1.0))

    print("diag  block-convergence refinement ladder")
    print("      coarseness vs divergence, at the D20-corrected compression")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 78)
    print(f"sequence {args.sequence}, {args.cycles} cycle(s)/slope, "
          f"control period {1000*CONTROL_PERIOD_S:.0f} ms")
    print(f"ladder {LADDER}, tolerance {tol} pt (dynamic.py BLOCK_CONVERGENCE_PT)")
    print(f"\nTIME_COMPRESSION[{args.sequence}] = {comp:g}x  "
          f"(dynamic.py, as loaded)")
    if abs(comp - 1.0) > 1e-9:
        print("   *** WARNING: compression is not 1.0. This run does NOT test")
        print("   *** D20 -- it reproduces the compression-era regime. Apply the")
        print("   *** D20 fix (TIME_COMPRESSION all 1.0) before reading a")
        print("   *** verdict about coarseness vs divergence.")
    else:
        print("   compression is off, so a persisting divergence here cannot be")
        print("   the 10x-steepened ramp -- it would be curve shape or a genuine")
        print("   discretisation limit (§7.2's fallback branch).")

    print("\nDECLARED VERDICT RULE (before the run):")
    print(f"   (A) CONVERGED AT 6   g(6->12) < {tol} pt. For 10-50 this confirms")
    print("       D20: compression, not curve shape, caused the 0.330 pt.")
    print(f"   (B) CONVERGED LATER  a later g(n->2n) < {tol} with gaps shrinking;")
    print("       genuine coarseness, converged count = the measured n.")
    print("   (C) DIVERGENT        no g(n->2n) < tol across the ladder; if gaps")
    print("       widen, block discretisation cannot represent this sequence.")
    print("   A gap into a rung whose smallest block holds fewer than")
    print(f"   {MIN_STEPS_PER_BLOCK} steps is reported but does NOT decide (D19).\n")

    try:
        model = TwoStageModel.load(tag="c3_two_stage_full")
    except FileNotFoundError:
        print("model 'c3_two_stage_full' not found.")
        return 1

    pool = scenario_set(200)
    shaded = [s for s in pool if s.geometry != "uniform"][:args.n]
    print(f"{len(shaded)} shaded scenarios drawn "
          f"(training modules; diagnostic, not reportable)")
    if len(shaded) < args.n:
        print(f"   NOTE: pool yielded only {len(shaded)} shaded scenarios; "
              "raise the pool size if short.")
    print()

    # -- walk the ladder, adaptively: stop once a trusted gap clears tol -----
    effs: dict[int, float] = {}
    mins: dict[int, int] = {}
    gaps = []           # (n_from, n_to, gap, finer_rung_degenerate)
    converged_at: int | None = None

    print(f"   {'blocks':>8} {'min blk':>9} {'hybrid eff %':>14} "
          f"{'gap vs prev':>13} {'trust':>7}")
    print("   " + "-" * 54)

    prev_n = None
    for n in LADDER:
        eff, mbs = hybrid_aggregate_at(shaded, args.sequence, n, model,
                                       args.cycles)
        effs[n], mins[n] = eff, mbs

        if prev_n is None:
            print(f"   {n:>8} {mbs:>9} {eff:>14.3f} {'--':>13} {'--':>7}")
        else:
            gap = abs(eff - effs[prev_n])
            degen = mbs < MIN_STEPS_PER_BLOCK
            gaps.append((prev_n, n, gap, degen))
            trust = "no" if degen else "yes"
            print(f"   {n:>8} {mbs:>9} {eff:>14.3f} {gap:>+13.3f} {trust:>7}")
            if degen:
                print(f"      rung {n} has a block at {mbs} step(s) "
                      f"(< {MIN_STEPS_PER_BLOCK}); this gap does not decide.")
            if (not degen) and gap < tol:
                converged_at = prev_n
                break
        prev_n = n

    trusted_gaps = [g for g in gaps if not g[3]]
    gap_values = [g[2] for g in trusted_gaps]
    shrinking = (len(gap_values) >= 2
                 and all(gap_values[i] < gap_values[i - 1] - 1e-9
                         for i in range(1, len(gap_values))))
    widening = (len(gap_values) >= 2
                and all(gap_values[i] > gap_values[i - 1] + 1e-9
                        for i in range(1, len(gap_values))))

    # -- verdict -------------------------------------------------------------
    print("\n" + "=" * 78)
    print("\nVERDICT")

    verdict = None
    recommended_bpp = None

    if converged_at is not None:
        recommended_bpp = converged_at
        if converged_at == LADDER[0]:
            verdict = "A_converged_at_6"
            print(f"   (A) CONVERGED AT {converged_at}. Doubling to "
                  f"{2*converged_at} moved efficiency "
                  f"{abs(effs[2*converged_at]-effs[converged_at]):.3f} pt "
                  f"(< {tol}).")
            if args.sequence == "10-50" and abs(comp - 1.0) <= 1e-9:
                print("       This CONFIRMS the D20 diagnosis: with compression")
                print("       removed, 10-50 converges at 6 exactly as 30-100")
                print("       does. The original 0.330 pt was the 10x-steepened")
                print("       ramp, not curve shape.")
                print("       ACTION: set BLOCKS_PER_PHASE['10-50'] = 6 in p11")
                print("       (matching 30-100). Rev 5's 24 was a compression-")
                print("       era artefact and would shrink the period sweep's")
                print("       valid range for no benefit.")
            else:
                print(f"       ACTION: BLOCKS_PER_PHASE['{args.sequence}'] = 6 "
                      "is adequate.")
        else:
            verdict = "B_converged_later"
            print(f"   (B) CONVERGED AT {converged_at}. g(6->12) exceeded "
                  f"{tol} but the ladder converged by {converged_at}, with")
            print(f"       {'shrinking' if shrinking else 'non-monotone'} gaps.")
            print("       This is genuine coarseness: low-irradiance curves do")
            print("       need finer blocks. But the converged count is the")
            print(f"       MEASURED {converged_at}, not the compression-era 24.")
            print(f"       ACTION: set BLOCKS_PER_PHASE['{args.sequence}'] = "
                  f"{converged_at} in p11, then re-run its check 0 to confirm.")
            if converged_at != 24:
                print("       NOTE: this differs from rev 5's 24 -- rev 5's")
                print("       value was chosen under compression and is not")
                print("       vindicated by this measurement.")
    else:
        verdict = "C_divergent"
        print("   (C) DIVERGENT. No trusted gap cleared tolerance across the")
        print(f"       ladder {LADDER}.")
        if widening:
            print("       The gaps WIDEN as blocks are added. That is the exact")
            print("       signature §7.2 named: block discretisation cannot")
            print("       represent this sequence's low-irradiance ramps.")
        elif trusted_gaps:
            print("       The gaps do not shrink to tolerance within the ladder.")
        else:
            print("       Every refinement rung degenerated before a gap could")
            print("       be trusted -- the sequence's fast slopes hit the step")
            print("       floor at these block counts.")
        print("       ACTION: do NOT run this sequence's period sweep (p11).")
        print("       Its dynamic claim rests on Sequence B (99.833%) plus")
        print("       shading-pattern transitions, which stress peak RELOCATION")
        print("       -- the thing EN 50530 ramps cannot produce anyway.")

    payload = {"sequence": args.sequence,
               "cycles": args.cycles,
               "control_period_s": CONTROL_PERIOD_S,
               "time_compression": comp,
               "n_scenarios": len(shaded),
               "ladder": list(LADDER),
               "tolerance_pt": tol,
               "min_steps_per_block_rule": MIN_STEPS_PER_BLOCK,
               "efficiency_by_blocks": {str(k): v for k, v in effs.items()},
               "min_block_steps_by_blocks": {str(k): v for k, v in mins.items()},
               "gaps": [{"from": a, "to": b, "gap_pt": g,
                         "finer_rung_degenerate": d} for a, b, g, d in gaps],
               "gaps_shrinking": bool(shrinking),
               "gaps_widening": bool(widening),
               "converged_at": converged_at,
               "verdict": verdict,
               "recommended_blocks_per_phase": recommended_bpp}
    OUT.mkdir(parents=True, exist_ok=True)
    dest = OUT / f"block_convergence_{args.sequence}.json"
    dest.write_text(json.dumps(payload, indent=2, default=float),
                    encoding="utf-8")
    print(f"\nresults -> {dest}")
    print("\nAll figures simulated, on training modules, at the compression")
    print("dynamic.py currently declares. This diagnostic settles the block")
    print("count BEFORE p11's declared value is set for this sequence.")
    return 0 if verdict != "C_divergent" else 1


if __name__ == "__main__":
    raise SystemExit(main())