"""
S8 - coefficient characterisation and Gate A evaluation (Stage 4, final step).

Takes the verified simulator (S1-S5), the converged scenario set (S6), and the
resolution-verified labels (S7), and produces the four Gate A inputs:

  A. COEFFICIENT DISTRIBUTION (contribution C1) - the true GMPP coefficient
     across all scenarios: mean, spread, range, and how it varies by geometry.
     This is the database-scale characterisation the thesis is built on.
  B. REGION-ERROR RATE under sub-substring geometry - raw and costly (Gate A(i)).
  C. RECALIBRATED-CONSTANT TEST - would a single better constant (the mean, or
     the loss-minimising constant) already solve it? If yes, a conditional model
     has no headroom (Gate A(ii) fails). Tested at several fallback margins.
  D. WORST CASE IN WATTS - the largest absolute power loss and the irradiance
     level it occurs at (the plan insists losses be reported in watts, not just
     percent, so a tail at 100 W/m^2 is not mistaken for a real loss).

Then the two Gate A conditions are evaluated:
  (i)  region-error rate under sub-substring geometry stays negligible;
  (ii) a recalibrated constant does NOT already solve it AND the worst case is
       non-trivial in watts.
Both must hold to proceed to Phase 2 unchanged. The plan defines the redirects
if either fails - S8 reports the outcome, it does not decide the thesis.

Statistics must be stable (convergence, inherited from S6's converged set).
"""
import numpy as np
import pandas as pd

from gmppt import config, device, scenarios
from gmppt.device import ModuleParams

N_SCENARIOS = 2000
MARGINS = (0.01, 0.02, 0.05)         # fallback margins to report sensitivity over
NEGLIGIBLE_REGION_ERROR = 0.05       # Gate A(i): "negligible" threshold (5%)


def evaluate_all(pool):
    scen = scenarios.generate(pool, N_SCENARIOS)
    results = [scenarios.evaluate_scenario(s, device, ModuleParams) for s in scen]
    return pd.DataFrame(results)


def section_A_distribution(df):
    print("A. COEFFICIENT DISTRIBUTION  (contribution C1)")
    c = df["coeff"].dropna()
    print(f"   all scenarios: mean {c.mean():.4f}  sd {c.std():.4f}  "
          f"range {c.min():.3f}-{c.max():.3f}  (n={len(c)})")
    within = ((c - 0.80).abs() < 0.01).mean()
    print(f"   within +/-0.01 of 0.80: {within*100:.1f}%  "
          f"(so {100-within*100:.1f}% miss the fixed 0.8 at the true GMPP)")
    print("   by geometry:")
    for g, sub in df.groupby("geometry"):
        cc = sub["coeff"].dropna()
        print(f"     {g:16s} mean {cc.mean():.4f}  sd {cc.std():.4f}  "
              f"range {cc.min():.3f}-{cc.max():.3f}")
    return dict(mean=float(c.mean()), sd=float(c.std()),
                lo=float(c.min()), hi=float(c.max()))


def section_B_region_error(df):
    print("\nB. REGION-ERROR RATE  (Gate A(i))")
    out = {}
    for g in ("whole_substring", "sub_substring"):
        sub = df[df["geometry"] == g]
        raw = sub["region_error"].mean()
        print(f"   {g:16s} raw region-error {raw*100:.1f}%  (n={len(sub)})")
        out[g] = float(raw)
    sub = df[df["geometry"] == "sub_substring"]
    print("   sub-substring costly-error at several margins:")
    costly = {}
    for m in MARGINS:
        rate = (sub["power_lost_frac"] > m).mean()
        costly[m] = float(rate)
        print(f"     > {m*100:.0f}% power loss: {rate*100:.1f}%")
    return out, costly


def _loss_for_constant(scenario, k):
    """Actual power lost if the model used constant k instead of 0.8, for one
    scenario. Re-runs the curve and lands at the best k*Voc/n_sub multiple."""
    mp = ModuleParams.from_cec(scenario.module)
    c = device.module_iv(mp, scenario.irradiances, scenario.temp_c,
                         bd=config.breakdown())
    a = device.analyse(c)
    V, P = c["V"], c["P"]
    order = np.argsort(V)
    Vs, Ps = V[order], P[order]
    voc = float(Vs.max())
    gmpp_P = a["gmpp"]["P"]
    n_sub = config.N_SUBSTRINGS
    cands = [min(max(n * k * voc / n_sub, float(Vs.min())), float(Vs.max()))
             for n in range(1, n_sub + 1)]
    landed = max(0.0, max(float(np.interp(cv, Vs, Ps)) for cv in cands))
    return (gmpp_P - landed) / gmpp_P if gmpp_P > 0 else 0.0


def section_C_recalibrated(df, pool):
    print("\nC. RECALIBRATED-CONSTANT TEST  (Gate A(ii))")
    # Actually measure mean power loss for a grid of candidate constants on a
    # seeded sub-substring sample, and find the loss-minimising constant. If even
    # the BEST constant still loses meaningful power, a recalibration does not
    # solve the problem and a conditional model has headroom.
    scen = scenarios.generate(pool, N_SCENARIOS)
    sub_scen = [s for s in scen if s.geometry == "sub_substring"]
    rng = np.random.default_rng(config.seed_for("s8_recal"))
    idx = rng.choice(len(sub_scen), min(300, len(sub_scen)), replace=False)
    sample = [sub_scen[i] for i in idx]

    ks = np.round(np.linspace(0.62, 0.86, 13), 3)
    mean_loss = {}
    for k in ks:
        losses = [_loss_for_constant(s, k) for s in sample]
        mean_loss[k] = float(np.mean(losses))
    best_k = min(mean_loss, key=mean_loss.get)
    best_loss = mean_loss[best_k]
    loss_at_08 = mean_loss.get(0.80, None)
    # loss at the nearest grid point to 0.80 if 0.80 not on grid
    if loss_at_08 is None:
        nearest = min(ks, key=lambda k: abs(k - 0.80))
        loss_at_08 = mean_loss[nearest]

    print(f"   mean power loss vs true GMPP, best single constant k={best_k}: "
          f"{best_loss*100:.2f}%")
    print(f"   mean power loss at the conventional 0.80: {loss_at_08*100:.2f}%")
    print(f"   even the loss-minimising constant leaves {best_loss*100:.2f}% on "
          f"the table -> a recalibration {'does NOT solve' if best_loss>0.01 else 'may solve'} it")
    print(f"   (spread the constant must cover: coeff sd "
          f"{df[df.geometry=='sub_substring']['coeff'].std():.3f})")
    return dict(best_k=float(best_k), best_loss=float(best_loss),
                loss_at_080=float(loss_at_08))


def section_D_worst_case(df):
    print("\nD. WORST CASE IN WATTS  (not just percent)")
    df = df.copy()
    df["watts_lost"] = df["power_lost_frac"] * df["gmpp_P"]
    w = df.sort_values("watts_lost", ascending=False).iloc[0]
    print(f"   largest absolute loss: {w['watts_lost']:.1f} W "
          f"({w['power_lost_frac']*100:.1f}% of {w['gmpp_P']:.1f} W GMPP), "
          f"geometry {w['geometry']}")
    # worst percent loss and its absolute watts, to catch the "100 W/m^2 tail"
    wp = df.sort_values("power_lost_frac", ascending=False).iloc[0]
    print(f"   largest percent loss: {wp['power_lost_frac']*100:.1f}% "
          f"= {wp['watts_lost']:.1f} W (GMPP {wp['gmpp_P']:.1f} W)")
    print(f"   mean absolute loss across sub-substring: "
          f"{df[df.geometry=='sub_substring']['watts_lost'].mean():.1f} W")
    return dict(worst_watts=float(w["watts_lost"]),
                worst_pct=float(wp["power_lost_frac"]))


def evaluate_gate_a(region, costly, recal, worst):
    print("\n" + "=" * 66)
    print("GATE A EVALUATION  (both conditions must hold to proceed unchanged)")
    sub_raw = region["sub_substring"]
    cond_i_holds = sub_raw < NEGLIGIBLE_REGION_ERROR
    print(f"  (i) region-error negligible under sub-substring geometry:")
    print(f"      raw rate {sub_raw*100:.1f}%  vs negligible<{NEGLIGIBLE_REGION_ERROR*100:.0f}%"
          f"  ->  {'HOLDS' if cond_i_holds else 'FAILS'}")
    # (ii) recalibrated constant does not solve it AND worst case non-trivial
    recal_solves = recal["best_loss"] < 0.01     # best constant loses <1% => solves
    worst_trivial = worst["worst_watts"] < 5.0   # <5 W is trivial
    cond_ii_holds = (not recal_solves) and (not worst_trivial)
    print(f"  (ii) recalibrated constant doesn't solve it AND worst case non-trivial:")
    print(f"      best single constant still loses {recal['best_loss']*100:.2f}% "
          f"(solves if <1%): {'does NOT solve' if not recal_solves else 'SOLVES'}")
    print(f"      worst case {worst['worst_watts']:.1f} W (trivial if <5 W): "
          f"{'non-trivial' if not worst_trivial else 'trivial'}")
    print(f"      ->  {'HOLDS' if cond_ii_holds else 'FAILS'}")

    print("\n  OUTCOME:")
    if cond_i_holds and cond_ii_holds:
        print("   Both hold -> proceed to Phase 2 unchanged (module-level")
        print("   landing-point problem, conditional coefficient has headroom).")
    elif not cond_i_holds:
        print("   Condition (i) FAILS -> region errors are real under sub-substring")
        print("   geometry. Per the plan, the multi-peak/region framing returns to")
        print("   module level, with this characterisation as evidence of where the")
        print("   boundary lies. This is a REDIRECTION, not a project failure.")
    else:
        print("   Condition (ii) fails -> a recalibrated constant suffices or the")
        print("   worst case is trivial; the conditional model leans on C1/C2.")
    return cond_i_holds, cond_ii_holds


if __name__ == "__main__":
    print("S8  Coefficient characterisation and Gate A")
    print("  " + config.provenance())
    print("=" * 66)
    pool = pd.read_parquet(config.CEC_POOL)
    df = evaluate_all(pool)
    df.to_csv(config.RESULTS_DIR / "s8_characterisation.csv", index=False)

    dist = section_A_distribution(df)
    region, costly = section_B_region_error(df)
    recal = section_C_recalibrated(df, pool)
    worst = section_D_worst_case(df)
    ci, cii = evaluate_gate_a(region, costly, recal, worst)

    print("\n" + "=" * 66)
    print(f"S8 characterisation complete. Gate A: "
          f"(i) {'HOLDS' if ci else 'FAILS'}, (ii) {'HOLDS' if cii else 'FAILS'}")
    print(f"  Full per-scenario data -> results/s8_characterisation.csv")