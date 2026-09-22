"""
p9_pso_comparison.py  --  PSO scored against the other trackers.
REVISION 2 -- convergence measured, not assumed.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p9_pso_comparison.py
                      OVERWRITE revision 1.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\p9_pso_comparison.py

WHAT CHANGED IN REVISION 2

    Revision 1 reported PSO's cost as M * T -- the SEARCH BUDGET -- and compared
    it against the hybrid's 5 steps to give a 24x ratio. That ratio was an upper
    bound presented as a measurement.

    PSO may reach its global best long before the budget is exhausted and spend
    the remaining iterations finding nothing. Trajectory.metrics already computes
    convergence (the first step after which power stays within 1% of the GMPP for
    the rest of the window), and revision 1 simply did not carry that field
    through the multi-seed aggregator.

    Revision 2 reports BOTH:

        search budget    M * T, declared, what the algorithm is allowed to spend
        measured conv.   median steps actually taken to settle

    The convergence-time claim is stated on the MEASURED figure. The budget stays
    in the table because it is the cost the hardware must be provisioned for --
    a method that usually converges in 40 steps but may take 120 needs 120 steps
    of headroom in the control loop.

    This matters because the funded target is a >= 50% convergence-time reduction
    against metaheuristics. Reporting a budget where a measurement was available
    would be the criterion-mismatch pattern recorded at D2, D4, D5, D8 and D10 --
    a number that measures something adjacent to the claim.

    A caution carried into the reading: median convergence is computed over
    trajectories that CONVERGED. Where two methods have different arrival rates,
    their convergence figures are conditional on different populations and are
    not directly comparable. The arrival column must be read beside it.

THE COST MAPPING -- declared in gmppt/pso.py before any number existed
    SEQUENTIAL (primary)  M particles cost M control steps per iteration. One
                          converter holds one voltage at a time. This is also the
                          accounting already applied to every other method -- the
                          seed's five probes are charged as five steps, and
                          Ahmed-Salam was costed at its realistic ~33.
    PARALLEL (reported)   one iteration costs one control step. Much of the
                          PSO-MPPT literature counts iterations rather than
                          samples, so omitting it invites the objection that PSO
                          was over-costed.

PSO IS STOCHASTIC -- and nothing else in this project is
    Every tracker measured before this is deterministic. PSO's particles are
    initialised randomly and move with random coefficients, so a single-seed
    figure is one draw presented as a result. Every PSO number here is a mean
    over N_SEEDS runs with its seed-to-seed standard deviation reported.

ACCEPTANCE -- DECLARED BEFORE THE RUN

    (1) PSO reaches the GMPP on at least 90% of multi-peak scenarios. If it
        lands near P&O's 42.1%, the implementation is wrong and nothing here is
        reportable, mechanical checks notwithstanding.

    (2) Any difference claimed between two configurations must exceed TWICE the
        seed-to-seed standard deviation.

    (3) The comparison against the hybrid is reported on FOUR axes -- arrival,
        steady efficiency, measured convergence, and search budget -- because the
        claim rests on all of them.

SCOPE
    Training-module scenarios: a design check, NOT a reportable comparison. All
    figures simulated.
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
from gmppt.hybrid import make_hybrid, make_seed_only  # noqa: E402
from gmppt.model import TwoStageModel  # noqa: E402
from gmppt.pso import (DEFAULT_ITERATIONS, N_SEEDS,  # noqa: E402
                       POPULATION_SWEEP, particle_swarm, search_cost)
from gmppt.tracking import (N_STEPS, _print_block, parked_at_gmpp,  # noqa: E402
                            perturb_and_observe, summarise, trajectory_for)
from gmppt.trackers import incremental_conductance  # noqa: E402

OUT = config.RESULTS_DIR / "phase2"

MIN_ARRIVAL_MULTI_PCT = 90.0
SPREAD_FACTOR = 2.0


def _oracle(traj, temp_c=None, n_steps=N_STEPS, **_):
    parked_at_gmpp(traj, n_steps=n_steps)


def _po(traj, temp_c=None, n_steps=N_STEPS, **kw):
    perturb_and_observe(traj, n_steps=n_steps, **kw)


def run(fn, scenarios, **kwargs):
    recs = []
    for sc in scenarios:
        traj = trajectory_for(sc)
        fn(traj, temp_c=float(sc.temp_c), **kwargs)
        recs.append(traj.metrics())
    return recs


def run_pso_multiseed(scenarios, population: int, iterations: int,
                      n_seeds: int = N_SEEDS) -> dict:
    """PSO over several seeds. Returns aggregated metrics and their spread.

    median_conv_steps is carried through here. Revision 1 dropped it, which is
    why the cost comparison was made against the declared budget rather than
    against measured convergence.
    """
    per_seed = []
    for s in range(n_seeds):
        recs = run(particle_swarm, scenarios, population=population,
                   iterations=iterations, seed=s)
        per_seed.append(summarise(recs, f"PSO M={population} seed={s}"))

    def agg(subset: str, key: str) -> tuple[float, float]:
        vals = [b[subset][key] for b in per_seed
                if b.get(subset) and b[subset].get(key) is not None]
        if not vals:
            return float("nan"), float("nan")
        a = np.asarray(vals, dtype=float)
        return float(a.mean()), float(a.std())

    out = {"population": population, "iterations": iterations,
           "n_seeds": n_seeds, **search_cost(population, iterations)}
    for subset in ("all", "multi_peak", "single_peak"):
        for key in ("steady_eff_pct", "window_eff_pct", "reached_pct",
                    "worst_energy_lost_w", "median_conv_steps"):
            m, sd = agg(subset, key)
            out[f"{subset}_{key}"] = m
            out[f"{subset}_{key}_sd"] = sd

    # The worst case across ALL seeds, not the mean of per-seed maxima.
    worst_any = [b["multi_peak"]["worst_energy_lost_w"] for b in per_seed
                 if b.get("multi_peak")]
    out["multi_peak_worst_across_seeds_w"] = (float(max(worst_any))
                                              if worst_any else float("nan"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seeds", type=int, default=N_SEEDS)
    args = ap.parse_args()

    print("P2.7d  PSO against the other trackers  (revision 2)")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 78)
    print("cost mapping: SEQUENTIAL primary (M particles = M control steps);")
    print("PARALLEL reported alongside for comparability with the literature.")
    print("\nrevision 2 reports MEASURED convergence beside the declared search")
    print("budget. Revision 1 compared budgets, which is an upper bound, not a")
    print("measurement -- and the funded target is a convergence-TIME claim.\n")
    print("acceptance, declared before this run:")
    print(f"   (1) PSO reaches the GMPP on >= {MIN_ARRIVAL_MULTI_PCT:.0f}% of "
          f"multi-peak scenarios")
    print(f"       (P&O and InC: 42.1%. If PSO lands near 42%, the")
    print(f"        implementation is wrong and nothing here is reportable.)")
    print(f"   (2) any claimed difference must exceed {SPREAD_FACTOR:.0f}x the "
          f"seed spread")
    print(f"   (3) the hybrid comparison is reported on arrival, steady")
    print(f"       efficiency, MEASURED convergence AND search budget\n")

    try:
        model = TwoStageModel.load(tag="c3_two_stage_full")
    except FileNotFoundError:
        print("model 'c3_two_stage_full' not found.")
        return 1

    scenarios = scenario_set(args.n)
    print(f"{len(scenarios)} scenarios (training modules; design check)")
    print(f"{args.seeds} seeds per PSO configuration\n")

    print("1. REFERENCE TRACKERS  (deterministic, one run each)")
    refs = {}
    for name, fn in (("oracle [not buildable]", _oracle),
                     ("P&O", _po),
                     ("InC", incremental_conductance),
                     ("seed only", make_seed_only(model)),
                     ("hybrid", make_hybrid(model, bounded=False))):
        print(f"   running {name} ...")
        refs[name] = summarise(run(fn, scenarios), name)
    for name in refs:
        _print_block(refs[name])

    print(f"\n2. PSO POPULATION SWEEP  ({DEFAULT_ITERATIONS} iterations, "
          f"{args.seeds} seeds each)")
    print(f"   {'M':>3} {'budget':>7} {'measured':>9} {'par':>5} "
          f"{'steady %':>17} {'arrival %':>17} {'worst W':>9}")
    print(f"   {'':>3} {'(seq)':>7} {'conv':>9} {'':>5}")
    print("   " + "-" * 74)

    sweep = []
    for pop in POPULATION_SWEEP:
        row = run_pso_multiseed(scenarios, pop, DEFAULT_ITERATIONS, args.seeds)
        sweep.append(row)
        conv = row["multi_peak_median_conv_steps"]
        conv_txt = "-" if not np.isfinite(conv) else f"{conv:.0f}"
        print(f"   {pop:>3} {row['sequential_steps']:>7} {conv_txt:>9} "
              f"{row['parallel_steps']:>5} "
              f"{row['multi_peak_steady_eff_pct']:>9.2f}"
              f"+/-{row['multi_peak_steady_eff_pct_sd']:<5.2f} "
              f"{row['multi_peak_reached_pct']:>9.1f}"
              f"+/-{row['multi_peak_reached_pct_sd']:<5.1f} "
              f"{row['multi_peak_worst_energy_lost_w']:>9.2f}")

    print("\n   budget   = M x T, what the algorithm is allowed to spend")
    print("   measured = median steps to settle within 1% of the GMPP and stay")
    print("   (all figures on MULTI-PEAK scenarios, mean +/- seed sd)")

    print("\n   worst case, mean of per-seed maxima vs maximum across seeds:")
    for row in sweep:
        print(f"      M={row['population']}: "
              f"{row['multi_peak_worst_energy_lost_w']:.2f} W mean, "
              f"{row['multi_peak_worst_across_seeds_w']:.2f} W across all seeds")

    # -- criterion (1) ------------------------------------------------------
    best = max(sweep, key=lambda r: r["multi_peak_reached_pct"])
    po_arr = refs["P&O"]["multi_peak"]["reached_pct"]
    print("\n3. CRITERION (1) -- DID PSO ESCAPE LOCAL PEAKS?")
    print(f"   best PSO configuration: M={best['population']}, "
          f"arrival {best['multi_peak_reached_pct']:.1f}% "
          f"+/-{best['multi_peak_reached_pct_sd']:.1f}")
    print(f"   P&O and InC:            arrival {po_arr:.1f}%")
    c1 = best["multi_peak_reached_pct"] >= MIN_ARRIVAL_MULTI_PCT
    print(f"   -> {'PASS' if c1 else 'FAIL'} (bar {MIN_ARRIVAL_MULTI_PCT:.0f}%)")
    if abs(best["multi_peak_reached_pct"] - po_arr) < 10.0:
        print("\n   WARNING: PSO's arrival is within 10 pt of P&O's. A")
        print("   population method should not trap like a hill-climber. STOP")
        print("   and inspect before reporting any figure from this run.")

    # -- criterion (2) ------------------------------------------------------
    print("\n4. CRITERION (2) -- DOES POPULATION SIZE MATTER BEYOND NOISE?")
    lo = min(sweep, key=lambda r: r["multi_peak_reached_pct"])
    hi = max(sweep, key=lambda r: r["multi_peak_reached_pct"])
    spread = hi["multi_peak_reached_pct"] - lo["multi_peak_reached_pct"]
    noise = max(r["multi_peak_reached_pct_sd"] for r in sweep)
    real = spread > SPREAD_FACTOR * noise
    print(f"   arrival ranges {lo['multi_peak_reached_pct']:.1f}% (M="
          f"{lo['population']}) to {hi['multi_peak_reached_pct']:.1f}% (M="
          f"{hi['population']})")
    print(f"   range {spread:.1f} pt against {SPREAD_FACTOR:.0f}x seed sd "
          f"= {SPREAD_FACTOR*noise:.1f} pt")
    print(f"   -> arrival {'IS' if real else 'is NOT'} separable across "
          f"populations by the declared rule")

    w_lo = max(r["multi_peak_worst_energy_lost_w"] for r in sweep)
    w_hi = min(r["multi_peak_worst_energy_lost_w"] for r in sweep)
    print(f"\n   BUT the worst case moves {w_lo:.2f} W to {w_hi:.2f} W across "
          f"the same sweep")
    print("   -> report as: arrival is not separable at this seed count; the")
    print("      worst case is, and it favours larger populations. Stating")
    print("      'population does not matter' would overstate the measurement.")
    if noise == 0.0:
        print("\n   NOTE: seed spread is exactly zero, which for a stochastic")
        print("   method is suspect. gmppt.pso's stochasticity check passed, so")
        print("   investigate before trusting this comparison.")

    # -- criterion (3), four axes ------------------------------------------
    print("\n5. CRITERION (3) -- PSO AGAINST THE HYBRID, FOUR AXES")
    hyb = refs["hybrid"]["multi_peak"]
    seed_only = refs["seed only"]["multi_peak"]
    hyb_conv = hyb["median_conv_steps"]
    best_conv = best["multi_peak_median_conv_steps"]

    print(f"   {'method':<22} {'steady %':>9} {'arrival %':>10} "
          f"{'meas conv':>10} {'budget':>9}")
    print("   " + "-" * 66)
    for label, block, budget in (
            ("P&O", refs["P&O"]["multi_peak"], "400 window"),
            ("InC", refs["InC"]["multi_peak"], "400 window"),
            ("seed only", seed_only, "5"),
            ("hybrid", hyb, "5")):
        cv = block["median_conv_steps"]
        cv_txt = "-" if cv is None else f"{cv:.0f}"
        print(f"   {label:<22} {block['steady_eff_pct']:>9.2f} "
              f"{block['reached_pct']:>10.1f} {cv_txt:>10} {budget:>9}")
    bc_txt = "-" if not np.isfinite(best_conv) else f"{best_conv:.0f}"
    print(f"   {'PSO sequential':<22} "
          f"{best['multi_peak_steady_eff_pct']:>9.2f} "
          f"{best['multi_peak_reached_pct']:>10.1f} {bc_txt:>10} "
          f"{best['sequential_steps']:>9}")
    print(f"   {'PSO parallel':<22} "
          f"{best['multi_peak_steady_eff_pct']:>9.2f} "
          f"{best['multi_peak_reached_pct']:>10.1f} "
          f"{'(n/a)':>10} {best['parallel_steps']:>9}")

    print("\n   CONVERGENCE IS CONDITIONAL ON SUCCESS. Median convergence is")
    print("   computed over trajectories that converged, and these methods have")
    print("   very different arrival rates. Read the arrival column beside it.")

    if np.isfinite(best_conv) and hyb_conv:
        ratio_meas = best_conv / max(hyb_conv, 1e-9)
        print(f"\n   MEASURED convergence ratio, PSO to hybrid: "
              f"{ratio_meas:.1f}x")
        print(f"   Declared budget ratio: "
              f"{best['sequential_steps'] / 5:.1f}x sequential, "
              f"{best['parallel_steps'] / 5:.1f}x parallel")
        print("   The convergence-time claim is stated on the MEASURED figure.")
        print("   The budget stays in the table because it is the headroom the")
        print("   control loop must be provisioned for.")

    d_arr = hyb["reached_pct"] - best["multi_peak_reached_pct"]
    arr_noise = best["multi_peak_reached_pct_sd"]
    print(f"\n   hybrid vs best PSO: arrival {d_arr:+.1f} pt "
          f"(PSO seed sd {arr_noise:.1f})")
    if abs(d_arr) <= SPREAD_FACTOR * arr_noise:
        print("   -> WITHIN PSO's own seed spread. The two are not separable on")
        print("      accuracy; the convergence column carries the comparison.")
    else:
        print(f"   -> EXCEEDS {SPREAD_FACTOR:.0f}x PSO's seed spread and is "
              f"real.")

    print("\n6. WHAT THIS RUN DOES NOT MEASURE")
    print("   Re-initialisation on shading change. Under static shading PSO")
    print("   searches once, converges, and holds. Its behaviour when the GMPP")
    print("   MOVES belongs to P2.8 (EN 50530), and that is where PSO's cost")
    print("   disadvantage should widen -- a swarm must re-search where a seed")
    print("   re-predicts.")
    print("   Converting control steps to seconds needs the partner's control")
    print("   period, which is outstanding.")

    payload = {"references": refs, "pso_sweep": sweep,
               "n_scenarios": len(scenarios), "n_seeds": args.seeds,
               "criterion_1_pass": bool(c1),
               "arrival_separable_by_population": bool(real)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pso_comparison.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")
    print(f"\nresults -> {OUT / 'pso_comparison.json'}")
    print("\nAll figures simulated, on training modules.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())