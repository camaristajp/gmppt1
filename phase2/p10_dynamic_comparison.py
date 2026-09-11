"""
p10_dynamic_comparison.py  --  P2.8: the trackers under EN 50530 ramps.
REVISION 3 -- scenario count raised from a debugging default to a declared
              value; per-method sample spread now reported.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p10_dynamic_comparison.py
                      OVERWRITE revision 2.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\p10_dynamic_comparison.py

    Roughly 60-90 minutes at the declared scenario count. Curves are cached per
    scenario and profile and shared across methods, so simulator cost is paid
    once rather than once per method.

WHAT CHANGED IN REVISION 3 -- defect D21

    Revision 2 ran on 12 shaded and 12 unshaded scenarios. That number was a
    DEBUGGING DEFAULT set while the harness still carried defects D17, D18 and
    D19, chosen so failing runs would fail quickly. Once the harness worked it
    was never revisited, and the reported 99.911% therefore rests on 12
    scenarios.

    It is also inconsistent with the rest of the project by more than an order
    of magnitude:

        static tracker comparison (p7)        200 scenarios
        seed comparison, validation modules   778 scenarios
        DYNAMIC comparison (p10 revision 2)    12 scenarios

    Cost was not the constraint. Simulator calls scale as scenarios x slopes x
    blocks; 12 scenarios cost about 8 minutes, and 100 costs about an hour --
    long, but well within what this project has spent on single runs. The
    trajectory stepping itself is interpolation and costs almost nothing.

    THE PRACTICAL CONSEQUENCE IS CONCENTRATED IN P&O. Its outcome is bimodal --
    it either reaches the global peak or it does not -- so its mean is
    essentially the proportion of scenarios on which it succeeded, and it is
    highly sensitive to the draw. The p11 sweep on TEN scenarios gave P&O
    74.22% where this run on TWELVE gave 69.80%: a 4.4 point swing from two
    scenarios. The hybrid, which succeeds almost always, was stable across the
    same draws.

    Revision 3 declares N_SCENARIOS at 100 -- the same order of magnitude as the
    static comparison it must be read beside -- and reports the per-scenario
    standard error for every method, so sample sensitivity is visible in the
    output rather than inferred afterwards.

WHAT CHANGED IN REVISION 2

    dynamic.py revision 3 fixed defect D17: blocks now carry INDIVIDUAL step
    counts derived from the standard's phase times and a declared control
    period, so a 7 s ramp occupies a tenth of the control steps of a 70 s ramp.
    Revision 1 of this runner constructed DynamicTrajectory with a single
    steps_per_block, which no longer exists.

    The 'always' reseed policy walks the per-block step counts rather than
    assuming a constant block length, and the seed's probe overhead is reported
    separately from the efficiency -- revision 1 reported only their sum and
    read the result as "re-seeding does not help" when part of it was
    "re-seeding is expensive on short blocks".

WHAT THIS CLOSES
    The last funded target with no evidence: dynamic tracking efficiency >= 99%
    under EN 50530.

THE INSTRUMENT IS VALIDATED
    gmppt/dynamic.py revision 3 passes 6/6 checks: the Annex B tables reproduce
    their published totals, SLOPE CHANGES THE STEP COUNT, the aggregation
    reproduces Alonso & Chenlo's printed sequence totals, the available power
    varies more than threefold, the peak voltage moves, and P&O on uniform
    scenarios lands inside the band of three commercially measured inverters.

    Block discretisation is converged: doubling the block count moves efficiency
    by 0.001 pt against a declared tolerance of 0.1 pt.

A PROPERTY OF THIS PROFILE, MEASURED AND DECLARED BEFORE THE RUN
    The harness measured the GMPP voltage moving only about 2% of V_oc across a
    full 300-1000 W/m2 excursion: under proportional scaling the current scales
    with irradiance while the peak VOLTAGE shifts only logarithmically.

    So this profile moves the available POWER a great deal and the peak LOCATION
    barely at all. It is a test of dynamic POWER tracking, not of dynamic peak
    RELOCATION -- and peak relocation is what this project is about.

    Any separation seen here between the hybrid and the local methods is
    therefore inherited from the STATIC trapping result: a tracker that starts on
    the wrong peak stays on it. That is a real effect and worth reporting, but it
    is not evidence of superior dynamic response.

RE-SEEDING POLICIES -- two built, the third deliberately deferred
    never    the seed fires once at the start; P&O carries the rest.
    always   the seed re-fires at every block boundary, costing 5 probes each.
    trigger  re-seed on detected change. The funded proposal names it. NOT BUILT.

    The trigger is deferred because building a detection mechanism before
    measuring whether re-seeding helps would be building machinery for a problem
    not shown to exist. Note the direction of the gap: if `always` is WORSE, the
    gap is the cost a trigger would need to avoid, which is an argument FOR a
    trigger rather than against one.

ACCEPTANCE -- DECLARED BEFORE THE RUN

    (1) The hybrid reaches >= 99% dynamic efficiency, aggregated per EN 50530
        eq. (7), on shaded scenarios. The funded target.

    (2) A difference counts only if it exceeds 0.1 pt AND exceeds twice the
        larger of the two methods' standard errors. Revision 2 used the 0.1 pt
        threshold alone; with the sample size now declared, the statistical test
        can be applied properly.

    (3) `always` re-seeding is credited only if it beats `never` by >= 0.1 pt.
        If it is WORSE, report the probe overhead separately from the tracking
        benefit -- they are different quantities.

    (4) EFFICIENCY MUST FALL AS SLOPE RISES, by at least 0.2 pt between the
        slowest and fastest slope, for at least one method WHOSE COST IS
        INDEPENDENT OF BLOCK LENGTH. Revision 2's version of this criterion
        passed on the re-seeding variant, whose fixed 5-probe cost per block
        becomes a larger fraction as blocks shorten -- arithmetic rather than
        tracking difficulty. That was defect D18, and the exclusion is now
        written into the criterion.

SCOPE
    Training-module scenarios: a design check, NOT reportable. All figures
    simulated. Divergences from the standard are declared in gmppt/dynamic.py
    and travel with any figure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config  # noqa: E402
from gmppt.dynamic import (CONTROL_PERIOD_S, SEQUENCES,  # noqa: E402
                           TIME_COMPRESSION, DynamicTrajectory,
                           aggregate_efficiency, dynamic_trajectory_for,
                           make_profile)
from gmppt.harness import scenario_set  # noqa: E402
from gmppt.hybrid import SEED_PROBE_COST, seed_voltage  # noqa: E402
from gmppt.model import TwoStageModel  # noqa: E402
from gmppt.pso import DEFAULT_ITERATIONS, DEFAULT_POPULATION  # noqa: E402
from gmppt.tracking import DEFAULT_STEP_FRAC, START_FRACTION  # noqa: E402

OUT = config.RESULTS_DIR / "phase2"
N_SUB = int(config.N_SUBSTRINGS)

# DECLARED, not a default. 100 per geometry group, matching the order of
# magnitude of the static tracker comparison (200) that this table must be read
# beside. Revision 2's 12 was a debugging default and is recorded as D21.
N_SCENARIOS = 100

# Scenario pool. Must be large enough that N_SCENARIOS of each geometry can be
# drawn; the generator's measured mix is roughly 15/44/41 uniform / whole /
# sub-substring, so a pool of 800 yields about 120 uniform and 680 shaded.
POOL_SIZE = 800

MIN_DYNAMIC_EFF_PCT = 99.0      # criterion (1), the funded target
RESOLUTION_PT = 0.1             # criteria (2) and (3)
SE_FACTOR = 2.0                 # criterion (2), standard errors
MIN_SLOPE_SENSITIVITY_PT = 0.2  # criterion (4)

# Methods whose per-block cost is FIXED, so slope sensitivity measures tracking
# difficulty rather than probe overhead. Criterion (4) is decided on these only.
BLOCK_COST_INDEPENDENT = ("oracle [not buildable]", "P&O", "InC",
                          "seed only, no reseed", "hybrid, no reseed")


# ---------------------------------------------------------------------------
# TRACKERS, written against DynamicTrajectory
# ---------------------------------------------------------------------------

def t_oracle(traj: DynamicTrajectory, model=None, **_) -> None:
    """Park at the true peak of whichever curve is active. Not buildable."""
    for _ in range(traj.n_steps):
        traj.step(traj.curves[traj.block_index][2])


def t_po(traj: DynamicTrajectory, model=None,
         step_frac: float = DEFAULT_STEP_FRAC, **_) -> None:
    """Textbook P&O. Identical logic to the static baseline."""
    dv = step_frac * traj.v_oc
    v = START_FRACTION * traj.v_oc
    p_prev = traj.step(v)
    direction = -1.0
    for _ in range(traj.n_steps - 1):
        v = v + direction * dv
        p = traj.step(v)
        if p < p_prev:
            direction = -direction
        p_prev = p


def t_inc(traj: DynamicTrajectory, model=None,
          step_frac: float = DEFAULT_STEP_FRAC, **_) -> None:
    """Fixed-step InC. Under STATIC conditions it reduces to P&O (D11, D14).

    A moving profile is the one place its positional condition could differ, so
    any gap here -- and only here -- would be InC's genuine distinguishing
    behaviour finally becoming visible.
    """
    dv = step_frac * traj.v_oc
    v = START_FRACTION * traj.v_oc
    p = traj.step(v)
    i_prev, v_prev = p / max(v, 1e-9), v
    v = max(v - dv, traj.v_floor)
    for _ in range(traj.n_steps - 1):
        p = traj.step(v)
        i = p / max(v, 1e-9)
        d_v, d_i = v - v_prev, i - i_prev
        i_prev, v_prev = i, v
        if abs(d_v) < 1e-12:
            if abs(d_i) < 1e-12:
                continue
            v = v + (dv if d_i > 0 else -dv)
        else:
            lhs, rhs = d_i / d_v, -i / max(v, 1e-9)
            if abs(lhs - rhs) < 1e-6:
                continue
            v = v + (dv if lhs > rhs else -dv)
        v = float(min(max(v, traj.v_floor), traj.v_oc))


def t_pso(traj: DynamicTrajectory, model=None, seed: int = 0,
          population: int = DEFAULT_POPULATION,
          iterations: int = DEFAULT_ITERATIONS, **_) -> None:
    """PSO searches once, then holds at the global best.

    NOT re-initialised on change, for the same reason the seed's trigger is not:
    detection is a separate mechanism and is deferred. Under a moving profile
    the held position goes stale, which is the behaviour worth measuring -- a
    swarm must re-search where a seed re-predicts.
    """
    from gmppt.pso import (C_COGNITIVE, C_SOCIAL, INERTIA, V_MAX_FRAC,
                           V_MIN_FRAC, VEL_MAX_FRAC)

    rng = np.random.default_rng(
        (int(config.seed_for("pso_dynamic")) + seed * 7919) % 2**31)
    v_lo = max(V_MIN_FRAC * traj.v_oc, traj.v_floor)
    v_hi = V_MAX_FRAC * traj.v_oc
    vel_max = VEL_MAX_FRAC * traj.v_oc

    base = np.linspace(v_lo, v_hi, population)
    jitter = (rng.random(population) - 0.5) * (v_hi - v_lo) / (2 * population)
    x = np.clip(base + jitter, v_lo, v_hi)
    vel = np.zeros(population)

    p_best_x, p_best_p = x.copy(), np.full(population, -np.inf)
    g_best_x, g_best_p = float(x[0]), -np.inf
    used, budget = 0, traj.n_steps

    for _ in range(iterations):
        for i in range(population):
            if used >= budget:
                break
            p = traj.step(float(x[i]))
            used += 1
            if p > p_best_p[i]:
                p_best_p[i], p_best_x[i] = p, float(x[i])
            if p > g_best_p:
                g_best_p, g_best_x = p, float(x[i])
        if used >= budget:
            break
        r1, r2 = rng.random(population), rng.random(population)
        vel = np.clip(INERTIA * vel + C_COGNITIVE * r1 * (p_best_x - x)
                      + C_SOCIAL * r2 * (g_best_x - x), -vel_max, vel_max)
        x = np.clip(x + vel, v_lo, v_hi)

    while used < budget:
        traj.step(g_best_x)
        used += 1


def _po_from(traj: DynamicTrajectory, v_start: float, n_steps: int,
             step_frac: float) -> float:
    """P&O from a given start for n_steps. Returns the final voltage."""
    if n_steps <= 0:
        return v_start
    dv = step_frac * traj.v_oc
    v = float(min(max(v_start, traj.v_floor), traj.v_oc))
    p_prev = traj.step(v)
    direction = -1.0
    for _ in range(n_steps - 1):
        v = float(min(max(v + direction * dv, traj.v_floor), traj.v_oc))
        p = traj.step(v)
        if p < p_prev:
            direction = -direction
        p_prev = p
    return v


def make_hybrid_dynamic(reseed: str):
    """The hybrid under a moving profile.

    reseed='never'   the seed fires once; P&O carries the remainder.
    reseed='always'  the seed re-fires at every block boundary. SCHEDULED, not
                     detected -- a detection trigger is deferred.

    The 'always' policy walks the per-block step counts (D17: blocks have
    different lengths). The seed costs a FIXED 5 probes per block, so on a short
    block that is a large fraction and on a long one it is negligible. The probe
    overhead is counted and reported separately from the efficiency, because
    they are different quantities.
    """
    def fn(traj: DynamicTrajectory, model: TwoStageModel,
           temp_c: float = 25.0, step_frac: float = DEFAULT_STEP_FRAC,
           **_) -> None:
        if reseed == "never":
            v_seed, _ = seed_voltage(traj, model, temp_c)
            _po_from(traj, v_seed, traj.n_steps - SEED_PROBE_COST, step_frac)
            return

        probes_spent = 0
        for n_in_block in np.asarray(traj.block_steps, int):
            if traj._k >= traj.n_steps:
                break
            if n_in_block <= SEED_PROBE_COST:
                # Block too short to seed AND track; track only, and record that
                # the seed was skipped rather than silently overrunning.
                _po_from(traj, traj.v_hist[-1] if traj.v_hist
                         else START_FRACTION * traj.v_oc,
                         int(n_in_block), step_frac)
                continue
            v_seed, _ = seed_voltage(traj, model, temp_c)
            probes_spent += SEED_PROBE_COST
            _po_from(traj, v_seed, int(n_in_block) - SEED_PROBE_COST, step_frac)
        setattr(traj, "reseed_probes", probes_spent)

    fn.__name__ = f"hybrid_reseed_{reseed}"
    return fn


def t_seed_only(traj: DynamicTrajectory, model: TwoStageModel,
                temp_c: float = 25.0, **_) -> None:
    """Seed once, hold. The control that shows what P&O adds under motion."""
    v_seed, _ = seed_voltage(traj, model, temp_c)
    for _ in range(traj.n_steps - SEED_PROBE_COST):
        traj.step(v_seed)


# ---------------------------------------------------------------------------
# RUNNER
# ---------------------------------------------------------------------------

def build_curve_cache(scenarios, profiles, label: str = "") -> dict:
    """Simulate every (scenario, profile) pair ONCE.

    Every method then runs on identical curve sequences -- the equal-conditions
    requirement -- and the simulator cost is paid once rather than per method.
    """
    cache = {}
    total = len(scenarios) * len(profiles)
    done = 0
    for si, sc in enumerate(scenarios):
        for pi, prof in enumerate(profiles):
            traj = dynamic_trajectory_for(sc, prof)
            cache[(si, pi)] = (traj.curves, prof.block_steps, prof.scored)
            done += 1
            if done % 100 == 0:
                print(f"      ...{done}/{total} curve sets{label}")
    return cache


def run_method(fn, scenarios, profiles, cache, model, **kw) -> dict:
    """One method across every scenario and profile.

    Returns the per-slope means, the eq. (7) aggregate, and the PER-SCENARIO
    spread -- pooled across slopes -- so sample sensitivity is visible in the
    output. That spread is what distinguishes a method whose mean is stable
    (the hybrid) from one whose mean is essentially a success proportion (P&O).
    """
    per_profile = {}
    per_scenario_all = []
    probe_overhead = []
    for pi, prof in enumerate(profiles):
        effs = []
        for si, sc in enumerate(scenarios):
            curves, block_steps, scored = cache[(si, pi)]
            traj = DynamicTrajectory(curves=curves, block_steps=block_steps,
                                     scored=scored, profile_name=prof.name,
                                     module=str(sc.module),
                                     geometry=str(sc.geometry))
            fn(traj, model=model, temp_c=float(sc.temp_c), **kw)
            effs.append(traj.metrics()["dynamic_efficiency_pct"])
            rp = getattr(traj, "reseed_probes", None)
            if rp is not None:
                probe_overhead.append(100.0 * rp / max(traj.n_steps, 1))
        per_profile[prof.name] = float(np.mean(effs))
        per_scenario_all.extend(effs)

    arr = np.asarray(per_scenario_all, dtype=float)
    n = max(len(arr), 1)
    out = {"per_profile": per_profile,
           "aggregate_pct": aggregate_efficiency(list(per_profile.values())),
           "scenario_sd_pct": float(arr.std(ddof=1)) if n > 1 else 0.0,
           "scenario_se_pct": (float(arr.std(ddof=1) / np.sqrt(n))
                               if n > 1 else 0.0),
           "n_trajectories": int(n)}
    if probe_overhead:
        out["reseed_probe_overhead_pct"] = float(np.mean(probe_overhead))
    return out


def separable(a: dict, b: dict) -> bool:
    """Criterion (2): a difference must exceed 0.1 pt AND twice the larger SE."""
    diff = abs(a["aggregate_pct"] - b["aggregate_pct"])
    se = max(a["scenario_se_pct"], b["scenario_se_pct"])
    return diff > RESOLUTION_PT and diff > SE_FACTOR * se


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=N_SCENARIOS,
                    help="scenarios per geometry group; declared at "
                         f"{N_SCENARIOS}, matching the static comparison's "
                         "order of magnitude")
    ap.add_argument("--sequence", default="30-100",
                    choices=list(SEQUENCES.keys()))
    ap.add_argument("--cycles", type=int, default=1,
                    help="repetitions per slope; the standard runs up to 10")
    args = ap.parse_args()

    print("P2.8  dynamic tracker comparison, EN 50530 ramps  (revision 3)")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 78)
    print(f"sequence {args.sequence}, all Annex B slopes, "
          f"{args.cycles} cycle(s) per slope")
    print(f"control period {1000*CONTROL_PERIOD_S:.0f} ms (DECLARED, not "
          f"measured), time compression "
          f"{TIME_COMPRESSION.get(args.sequence, 1.0):g}x")
    print("cycles capped for tractability; the standard runs up to 10. A")
    print("DIVERGENCE, and it must be stated with any figure.\n")
    print(f"SCENARIO COUNT: {args.n} per geometry group, DECLARED (D21).")
    print("Revision 2 used 12, a debugging default set while the harness still")
    print("carried defects D17-D19 and never revisited. That was inconsistent")
    print("with the static tracker comparison's 200 by more than an order of")
    print("magnitude, and cost was not the constraint.\n")
    print("acceptance, declared before this run:")
    print(f"   (1) hybrid reaches >= {MIN_DYNAMIC_EFF_PCT:.0f}% on shaded "
          f"scenarios (the funded target)")
    print(f"   (2) a difference counts only if it exceeds {RESOLUTION_PT} pt "
          f"AND {SE_FACTOR:.0f}x the")
    print("       larger standard error")
    print(f"   (3) 'always' re-seeding credited only if it beats 'never' by "
          f">= {RESOLUTION_PT} pt;")
    print("       if WORSE, report probe overhead separately from tracking")
    print("       benefit -- they are different quantities")
    print(f"   (4) efficiency must FALL as slope rises, by >= "
          f"{MIN_SLOPE_SENSITIVITY_PT} pt, for at least one")
    print("       method whose cost is INDEPENDENT of block length. Revision 2")
    print("       let this pass on the re-seeding variant, whose fixed 5-probe")
    print("       cost per block grows as blocks shorten -- arithmetic, not")
    print("       tracking difficulty. That was D18\n")
    print("DECLARED PROPERTY: the peak moves only ~2% of Voc across a full")
    print("excursion, so this profile tests dynamic POWER tracking, not peak")
    print("RELOCATION. Any hybrid-over-P&O gap seen here is inherited from the")
    print("STATIC trapping result, not evidence of dynamic superiority.\n")

    try:
        model = TwoStageModel.load(tag="c3_two_stage_full")
    except FileNotFoundError:
        print("model 'c3_two_stage_full' not found.")
        return 1

    pool = scenario_set(POOL_SIZE)
    uniform = [s for s in pool if s.geometry == "uniform"][:args.n]
    shaded = [s for s in pool if s.geometry != "uniform"][:args.n]
    print(f"pool of {len(pool)} scenarios -> {len(uniform)} uniform, "
          f"{len(shaded)} shaded (training modules; design check)")
    if len(uniform) < args.n or len(shaded) < args.n:
        print(f"   NOTE: the pool did not yield {args.n} of each geometry.")
        print(f"   Raise POOL_SIZE (currently {POOL_SIZE}) if the counts above")
        print("   are short of the declared value.")

    _, rows = SEQUENCES[args.sequence]
    profiles = [make_profile(args.sequence, r[1], max_cycles=args.cycles)
                for r in rows]
    print(f"\n   {'slope':>8} {'blocks':>8} {'steps':>8} {'scored':>8}")
    for prof in profiles:
        print(f"   {prof.slope_w_m2_s:>8.0f} {prof.n_blocks:>8} "
              f"{prof.n_steps:>8} {prof.scored_steps:>8}")
    n_traj = (len(uniform) + len(shaded)) * len(profiles)
    print(f"\n   {n_traj} trajectories per method, "
          f"{n_traj * 7} in total across seven methods")
    print(f"   curve cache: {n_traj} simulator-backed curve sets, built once "
          f"and shared\n")

    methods = [
        ("oracle [not buildable]", t_oracle),
        ("P&O", t_po),
        ("InC", t_inc),
        ("PSO", t_pso),
        ("seed only, no reseed", t_seed_only),
        ("hybrid, no reseed", make_hybrid_dynamic("never")),
        ("hybrid, reseed each block", make_hybrid_dynamic("always")),
    ]

    results = {}
    for label, group in (("uniform", uniform), ("shaded", shaded)):
        if not group:
            continue
        print(f"\n{label.upper()} SCENARIOS  (n = {len(group)})")
        print("   building curve cache ...")
        cache = build_curve_cache(group, profiles, f"  [{label}]")

        block = {}
        for name, fn in methods:
            print(f"   running {name} ...")
            block[name] = run_method(fn, group, profiles, cache, model)
        results[label] = block

        print(f"\n   {'method':<28} {'dyn eff %':>11} {'sd':>8} {'se':>8}")
        print("   " + "-" * 58)
        for name, _ in methods:
            b = block[name]
            print(f"   {name:<28} {b['aggregate_pct']:>11.3f} "
                  f"{b['scenario_sd_pct']:>8.3f} {b['scenario_se_pct']:>8.3f}")
        print("   sd = spread across individual trajectories; se = standard")
        print("   error of the mean. A large sd with a small se means the mean")
        print("   is well determined despite variable outcomes -- which is the")
        print("   signature of a bimodal method like P&O.")

    if "shaded" in results:
        print("\nPER-SLOPE, SHADED SCENARIOS")
        names = [n for n, _ in methods]
        hdr = "   " + f"{'slope':<22}" + "".join(f"{n[:11]:>13}" for n in names)
        print(hdr)
        print("   " + "-" * (len(hdr) - 3))
        for prof in profiles:
            row = "   " + f"{prof.name:<22}"
            for n in names:
                row += f"{results['shaded'][n]['per_profile'][prof.name]:>13.3f}"
            print(row)

    print("\n" + "=" * 78)
    print("\nVERDICT")
    if "shaded" not in results:
        print("   no shaded scenarios drawn -- nothing to judge.")
        return 1

    sh = results["shaded"]
    hyb = sh["hybrid, no reseed"]
    hyb_rs = sh["hybrid, reseed each block"]
    po = sh["P&O"]
    inc = sh["InC"]
    seed = sh["seed only, no reseed"]
    pso = sh["PSO"]

    c1 = hyb["aggregate_pct"] >= MIN_DYNAMIC_EFF_PCT
    print(f"   (1) hybrid {hyb['aggregate_pct']:.3f}% "
          f"+/-{hyb['scenario_se_pct']:.3f} (se) vs target "
          f"{MIN_DYNAMIC_EFF_PCT:.0f}%  -> {'PASS' if c1 else 'FAIL'}")

    d_reseed = hyb_rs["aggregate_pct"] - hyb["aggregate_pct"]
    c3 = d_reseed >= RESOLUTION_PT
    overhead = hyb_rs.get("reseed_probe_overhead_pct", float("nan"))
    print(f"\n   (3) reseed each block {hyb_rs['aggregate_pct']:.3f}% vs never "
          f"{hyb['aggregate_pct']:.3f}%  ({d_reseed:+.3f} pt)")
    print(f"       -> {'credited' if c3 else 'NOT credited'}")
    print(f"       probe overhead: {overhead:.1f}% of control steps spent on")
    print("       re-seeding. Separate that from the tracking benefit -- a")
    print("       negative total can mean the seed costs more than it recovers,")
    print("       which is an argument FOR a detection trigger, not against.")

    # -- criterion (4): slope sensitivity, block-cost-independent methods only
    print("\n   (4) SLOPE SENSITIVITY  (block-cost-independent methods only)")
    slow_name = profiles[0].name
    fast_name = profiles[-1].name
    sensitivities = {}
    print(f"       {'method':<28} {'slow':>9} {'fast':>9} {'drop':>9} "
          f"{'counts':>8}")
    for name, _ in methods:
        pp = sh[name]["per_profile"]
        drop = pp[slow_name] - pp[fast_name]
        sensitivities[name] = drop
        counts = "yes" if name in BLOCK_COST_INDEPENDENT else "no"
        print(f"       {name:<28} {pp[slow_name]:>9.3f} "
              f"{pp[fast_name]:>9.3f} {drop:>+9.3f} {counts:>8}")
    eligible = {k: v for k, v in sensitivities.items()
                if k in BLOCK_COST_INDEPENDENT}
    best_sens = max(eligible.values()) if eligible else float("nan")
    c4 = best_sens >= MIN_SLOPE_SENSITIVITY_PT
    print(f"       largest eligible drop: {best_sens:+.3f} pt "
          f"(bar {MIN_SLOPE_SENSITIVITY_PT})  -> {'PASS' if c4 else 'FAIL'}")
    if not c4:
        print("       Efficiency does not fall as the ramp gets faster for any")
        print("       method whose cost is fixed per block. At this control")
        print("       rate no slope in this sequence is difficult, so the run")
        print("       measures a STATIC quantity and no dynamic conclusion may")
        print("       be drawn from the method ranking.")

    # -- separability, using the standard errors now available ---------------
    print("\n   (2) SEPARABILITY  (0.1 pt AND 2x the larger standard error)")
    pairs = [("hybrid, no reseed", "PSO"),
             ("hybrid, no reseed", "seed only, no reseed"),
             ("hybrid, no reseed", "P&O"),
             ("P&O", "InC")]
    for a, b in pairs:
        diff = sh[a]["aggregate_pct"] - sh[b]["aggregate_pct"]
        se = max(sh[a]["scenario_se_pct"], sh[b]["scenario_se_pct"])
        ok = separable(sh[a], sh[b])
        print(f"       {a[:20]:<22} vs {b[:20]:<22} {diff:>+8.3f} pt "
              f"(2se {SE_FACTOR*se:.3f})  "
              f"{'separable' if ok else 'NOT separable'}")

    print(f"\n   [reported] PSO {pso['aggregate_pct']:.3f}%, seed only "
          f"{seed['aggregate_pct']:.3f}%, P&O {po['aggregate_pct']:.3f}%, "
          f"InC {inc['aggregate_pct']:.3f}%")
    print(f"   P&O trajectory spread: sd {po['scenario_sd_pct']:.2f} pt over "
          f"{po['n_trajectories']} trajectories.")
    print("   P&O's outcome is bimodal -- it reaches the global peak or it does")
    print("   not -- so its mean is essentially the success proportion. Quote")
    print("   no P&O figure without its scenario count.")

    gap_po = hyb["aggregate_pct"] - po["aggregate_pct"]
    if gap_po >= 1.0:
        print(f"\n   NOTE: the hybrid leads P&O by {gap_po:.3f} pt. Given the")
        print("   declared property above -- the peak moves ~2% of Voc -- that")
        print("   gap is INHERITED FROM STATIC TRAPPING, not evidence of better")
        print("   dynamic response. A tracker that starts on the wrong peak")
        print("   stays on it whether or not the irradiance is ramping. Report")
        print("   it as the static result it is.")

    if "uniform" in results:
        u = results["uniform"]
        print(f"\n   uniform-scenario control: P&O "
              f"{u['P&O']['aggregate_pct']:.3f}%, hybrid "
              f"{u['hybrid, no reseed']['aggregate_pct']:.3f}%")
        print("   Published inverters on this sequence: 85.13 - 99.21%. Scoring")
        print("   above them is expected: this simulation is noiseless and")
        print("   quasi-static, so it measures the ALGORITHM without the")
        print("   converter losses real hardware carries.")

    payload = {"sequence": args.sequence, "cycles": args.cycles,
               "control_period_s": CONTROL_PERIOD_S,
               "time_compression": TIME_COMPRESSION.get(args.sequence, 1.0),
               "n_declared": args.n, "pool_size": POOL_SIZE,
               "n_uniform": len(uniform), "n_shaded": len(shaded),
               "n_trajectories_per_method": n_traj,
               "profile_blocks": {p.name: int(p.n_blocks) for p in profiles},
               "profile_steps": {p.name: int(p.n_steps) for p in profiles},
               "results": results,
               "slope_sensitivity_pt": sensitivities,
               "criterion_1_pass": bool(c1),
               "reseed_credited": bool(c3),
               "slope_sensitive": bool(c4)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"dynamic_comparison_{args.sequence}.json").write_text(
        json.dumps(payload, indent=2, default=float), encoding="utf-8")
    print(f"\nresults -> {OUT / f'dynamic_comparison_{args.sequence}.json'}")
    print("\nAll figures simulated, on training modules. Divergences from")
    print("EN 50530 are declared in gmppt/dynamic.py and travel with any")
    print("figure taken from here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())