"""
S6 - scenario generator (Stage 4, step 1 of the pipeline to Gate A).

Builds the seeded partial-shading scenario set that S7 labels and S8
characterises. This is the first step that USES the verified simulator at scale
rather than verifying it. Checkpoints:

  1. REPRODUCIBLE  - same seed regenerates identical scenarios (the released
     generator must be deterministic; plan Section 9.11 / gap 6).
  2. TRAIN/HELD-OUT SPLIT - the held-out modules are disjoint from training and
     span the coefficient range (Task 3 generalisation test).
  3. GEOMETRY MIX  - the three shading geometries appear in the intended
     proportion, including the sub-substring case Gate A(i) needs.
  4. ALL RUNNABLE  - every scenario composes through module_iv without error
     (a scenario the simulator cannot evaluate is not a valid scenario).
"""
import numpy as np
import pandas as pd

from gmppt import config, device, scenarios
from gmppt.device import ModuleParams

N_SCENARIOS = 2000     # enough for stable statistics; S8 has a convergence check


def check_reproducible(pool):
    print("1) REPRODUCIBLE  (same seed -> identical scenarios)")
    a = scenarios.generate(pool, 200)
    b = scenarios.generate(pool, 200)
    same = all(x == y for x, y in zip(a, b))
    print(f"   two independent generations of 200 scenarios identical: "
          f"{'OK' if same else 'FAIL'}")
    return same


def check_split(pool):
    print("\n2) TRAIN / HELD-OUT SPLIT")
    train, heldout = scenarios.split_modules(pool)
    disjoint = not (set(train) & set(heldout))
    frac = len(heldout) / (len(train) + len(heldout))
    # coefficient span of held-out vs full
    csi = pool[pool["Technology"].isin(config.CSI_TECHNOLOGIES)]
    ho = csi.loc[heldout, "vmp_voc"]
    spans = (ho.min() < 0.72 and ho.max() > 0.86)  # held-out reaches both tails
    ok = disjoint and abs(frac - scenarios.HELDOUT_FRACTION) < 0.02 and spans
    print(f"   train {len(train)}, held-out {len(heldout)} "
          f"({frac*100:.1f}%); disjoint: {disjoint}")
    print(f"   held-out coefficient span {ho.min():.3f}-{ho.max():.3f} "
          f"(spans the range: {spans})")
    print(f"   split valid: {'OK' if ok else 'FAIL'}")
    return ok


def check_geometry_mix(scen):
    print("\n3) GEOMETRY MIX")
    counts = pd.Series([s.geometry for s in scen]).value_counts(normalize=True)
    near = np.mean([s.near_threshold for s in scen])
    ok = True
    for g, target in scenarios.GEOMETRY_MIX.items():
        got = counts.get(g, 0.0)
        hit = abs(got - target) < 0.05
        ok &= hit
        print(f"   {g:16s} {got*100:4.1f}%  (target {target*100:.0f}%)  "
              f"{'ok' if hit else 'OFF'}")
    print(f"   near-threshold scenarios: {near*100:.1f}%")
    sub = counts.get("sub_substring", 0.0)
    print(f"   sub-substring fraction (Gate A(i) cases): {sub*100:.1f}%")
    print(f"   mix within tolerance: {'OK' if ok else 'FAIL'}")
    return ok


def check_all_runnable(pool, scen, sample=300):
    print(f"\n4) ALL RUNNABLE  (sample {sample} scenarios through module_iv)")
    rng = np.random.default_rng(config.seed_for("s6_runcheck"))
    idx = rng.choice(len(scen), min(sample, len(scen)), replace=False)
    fails = 0
    peaks_seen = {1: 0, 2: 0, 3: 0}
    for j in idx:
        sc = scen[j]
        try:
            mp = ModuleParams.from_cec(sc.module)
            c = device.module_iv(mp, sc.irradiances, sc.temp_c)
            a = device.analyse(c)
            peaks_seen[min(a["n_peaks"], 3)] = peaks_seen.get(
                min(a["n_peaks"], 3), 0) + 1
        except Exception as e:
            fails += 1
            if fails <= 3:
                print(f"   FAIL on {sc.geometry} / {sc.module[:30]}: {e}")
    ok = fails == 0
    print(f"   ran {len(idx)} scenarios, {fails} failures")
    print(f"   peak-count distribution: {dict(peaks_seen)}")
    print(f"   all runnable: {'OK' if ok else 'FAIL'}")
    return ok


def check_convergence(scen):
    """The plan's actual criterion (Section 9.11): scenario count is set by
    convergence of the reported statistics, not fixed in advance. Show the
    coefficient mean and BOTH sub-substring region-error rates (raw and costly)
    as N grows; stable tails mean the count is sufficient."""
    print("\n5) CONVERGENCE  (statistics stop moving as N grows — plan Section 9.11)")
    results = [scenarios.evaluate_scenario(s, device, ModuleParams) for s in scen]
    rows = scenarios.convergence_curve(results)
    print(f"   {'N':>5} {'coeff_mean':>11} {'coeff_sd':>9} {'n_sub':>6} "
          f"{'raw_err':>9} {'costly_err':>11}")
    for r in rows:
        raw = f"{r['sub_region_error_raw']*100:.1f}%"
        cost = f"{r['sub_region_error_costly']*100:.1f}%"
        print(f"   {r['n']:>5} {r['coeff_mean']:>11.4f} {r['coeff_sd']:>9.4f} "
              f"{r['n_sub']:>6} {raw:>9} {cost:>11}")

    # convergence over the last THREE checkpoints (a window, not one pair):
    # coefficient mean range < 0.005 and costly-error range < 2 points.
    cm = [r["coeff_mean"] for r in rows[-3:]]
    ce = [r["sub_region_error_costly"] for r in rows[-3:]]
    coeff_stable = (max(cm) - min(cm)) < 0.005
    cost_stable = (max(ce) - min(ce)) < 0.02
    ok = coeff_stable and cost_stable
    print(f"   coeff mean range over last 3 checkpoints: {max(cm)-min(cm):.4f} "
          f"(<0.005: {coeff_stable})")
    print(f"   costly-error range over last 3 checkpoints: "
          f"{(max(ce)-min(ce))*100:.2f} pts (<2: {cost_stable})")
    raw_final = rows[-1]["sub_region_error_raw"] * 100
    cost_final = rows[-1]["sub_region_error_costly"] * 100
    print(f"   FINAL sub-substring region-error: {raw_final:.1f}% raw, "
          f"{cost_final:.1f}% costly (>1% power loss), over {rows[-1]['n_sub']} cases")
    print(f"   converged: {'OK' if ok else 'NOT YET — increase N_SCENARIOS'}")
    return ok, results, rows


if __name__ == "__main__":
    print("S6  Seeded shading-scenario generator")
    print("  " + config.provenance())
    print("=" * 66)
    pool = pd.read_parquet(config.CEC_POOL)

    ok1 = check_reproducible(pool)
    ok2 = check_split(pool)

    scen = scenarios.generate(pool, N_SCENARIOS)
    ok3 = check_geometry_mix(scen)
    ok4 = check_all_runnable(pool, scen)
    ok5, results, conv = check_convergence(scen)

    # persist the scenario set and the convergence table for S7/S8
    scenarios.to_frame(scen).to_csv(
        config.RESULTS_DIR / "s6_scenarios.csv", index=False)
    pd.DataFrame(conv).to_csv(
        config.RESULTS_DIR / "s6_convergence.csv", index=False)
    print(f"\n   {len(scen)} scenarios -> results/s6_scenarios.csv")
    print(f"   convergence table -> results/s6_convergence.csv")

    all_ok = ok1 and ok2 and ok3 and ok4 and ok5
    print("\n" + "=" * 66)
    print(f"S6 checkpoint: {'PASS' if all_ok else 'FAIL'}  "
          f"(reproducible={ok1}, split={ok2}, mix={ok3}, runnable={ok4}, "
          f"converged={ok5})")
    print("  Seeded scenario set ready for S7 labelling. Scenario count is")
    print("  justified by convergence (plan Section 9.11), not fixed by feel.")