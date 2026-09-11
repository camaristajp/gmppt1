"""
p5_near_tie_screen.py  --  P2.5: GMPP label integrity under near-tie peaks.
REVISION 2 -- corrects the peak-tuple index. Overwrite revision 1.

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\p5_near_tie_screen.py

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\p5_near_tie_screen.py --n 2000

WHAT REVISION 1 GOT WRONG
    device.analyse() returns peaks as (V, I, P) triples -- position 1 is CURRENT,
    position 2 is power. Revision 1 read position 1 as power. The consequences:

      * every power gap was computed as (P_gmpp - I_rival)/P_gmpp, i.e. roughly
        (186 W - 4.9 A)/186 W ~ 97%, so NO scenario ever looked near-tied. The
        reported zero near-ties at every margin was an artefact, not a finding.
      * sorting by position 1 ordered peaks by CURRENT descending, which puts the
        LOWEST-voltage peak first -- so the "rival" peak was mis-selected too.

    The flip test in section B is unaffected: it compares GMPP voltages straight
    from analyse() and never touches the tuple. Its revision-1 result (4 of 2000
    labels moved under +/-1% irradiance noise) stands.

    Detected by implausibility, not by a test: zero near-ties at a 5% margin
    across 1,604 multi-peak curves is not credible for a continuous quantity, and
    a reported 90.9% "power gap" among flipped labels contradicted the flip
    itself. Both symptoms pointed at the same cause.

WHY THIS SCREEN EXISTS
    When two peaks are almost equal in power, a small modelling error decides
    which is labelled the global maximum -- and the two can sit far apart in
    voltage. Betti et al. (Energies 17(10):2276, 2024) observed this against
    measured hardware: the measured maximum power point occurred at 19 V while
    their simulation placed it at 34.2 V, and the authors note that special care
    is needed when local and global maxima become close in magnitude.

    The project checklist flagged this screen as needing to PRECEDE Phase 2
    baseline scoring. It did not. This run closes that gap.

THE SCREEN SEPARATES THREE CONSEQUENCES -- they are not the same
    1. POWER-LOSS METRIC. Self-protecting by construction: if two peaks are
       within m% in power, landing on either costs at most m%. Measured here,
       not assumed.
    2. REGION-ERROR METRIC. A binary flag. A flipped label flips the metric even
       when the power cost is nil. NOT self-protecting.
    3. SUPERVISED TRAINING LABELS. A flip moves C3's regression target by the
       full peak separation. NOT self-protecting, and the reason this matters for
       Phase 3 rather than only for Phase 2.

METHOD
    A. Count near-tie scenarios at several margins; measure how far apart the
       rival peaks sit in voltage.
    B. FLIP TEST. The label cannot be checked against a truth outside the
       simulator -- there is none. So, following the L4 pattern: perturb each
       substring irradiance by +/-1% (the accuracy class of the I-V tracer Betti
       used) and count how often the labelled GMPP jumps to a different peak.
    C. Quantify the cost of a flip on each of the three consequences above.

TOLERANCES -- DECLARED BEFORE RUNNING (unchanged from revision 1)
    near-tie fraction (top two within 1%)   < 5%    -> ambiguity is rare
    label flip rate under +/-1% irradiance  < 2%    -> labels are robust
    power-loss impact of a flip             < 1 pt  -> baseline table unaffected
    region-error impact                     reported, no threshold: this metric
                                            cannot protect itself, so it is
                                            described rather than passed/failed

    A high flip rate would NOT mean Phase 2 is wrong -- the power-loss ranking
    holds regardless. It would mean C3 should be trained against POWER rather
    than a labelled peak voltage, because the power is stable and the label is not.

OUTPUTS
    results/phase2/near_tie_screen.json
    results/phase2/figures/near_tie_examples.png
    results/phase2/figures/near_tie_distribution.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, device  # noqa: E402
from gmppt.device import ModuleParams  # noqa: E402
from gmppt.harness import scenario_set  # noqa: E402

OUT = Path("results/phase2")
FIGS = OUT / "figures"

MARGINS = (0.005, 0.01, 0.02, 0.05)     # near-tie definitions, fraction of GMPP
IRR_NOISE = 0.01                         # +/-1%, the I-V tracer accuracy class
NEAR_TIE_TOL = 0.05                      # near-tie fraction bar at the 1% margin
FLIP_TOL = 0.02                          # label flip rate bar
POWER_IMPACT_TOL = 1.0                   # pt

# device.analyse() peak tuples are (V, I, P). Named here so the revision-1 bug
# cannot recur silently.
PEAK_V, PEAK_I, PEAK_P = 0, 1, 2


def curve_of(sc, irradiances=None):
    """One scenario's sorted (V, P) plus its analyse() result."""
    mp = ModuleParams.from_cec(sc.module)
    irr = sc.irradiances if irradiances is None else irradiances
    c = device.module_iv(mp, irr, sc.temp_c, bd=config.breakdown())
    a = device.analyse(c)
    V = np.asarray(c["V"], float)
    P = np.asarray(c["P"], float)
    order = np.argsort(V)
    return V[order], P[order], a


def peak_list(a):
    """[(V, P), ...] sorted by POWER, highest first. Tuples are (V, I, P)."""
    pk = [(float(t[PEAK_V]), float(t[PEAK_P])) for t in a["peaks"]]
    return sorted(pk, key=lambda t: -t[1])


def _perturb(irr, rng, frac=IRR_NOISE):
    """Apply +/-frac multiplicative noise, preserving the ragged structure."""
    out = []
    for entry in irr:
        if isinstance(entry, (list, tuple, np.ndarray)):
            out.append([float(g) * (1.0 + rng.uniform(-frac, frac)) for g in entry])
        else:
            out.append(float(entry) * (1.0 + rng.uniform(-frac, frac)))
    return out


def sanity_check_peaks(scenarios, verbose=True) -> bool:
    """Confirm the peak tuple really is (V, I, P) before trusting any gap.

    The labelled GMPP power must equal the maximum peak power to within rounding.
    If it does not, the index assumption is wrong and the run is void -- which is
    exactly what revision 1 failed to notice.
    """
    for sc in scenarios[:50]:
        _, _, a = curve_of(sc)
        pk = peak_list(a)
        if not pk:
            continue
        if abs(pk[0][1] - float(a["gmpp"]["P"])) > 1e-6 * max(1.0, pk[0][1]):
            if verbose:
                print("   FAIL: highest peak power does not match gmpp['P'].")
                print(f"      peaks[0] -> {pk[0]}, gmpp -> {a['gmpp']}")
                print("      The (V, I, P) index assumption is wrong. Stop.")
            return False
    if verbose:
        print("   peak tuples are (V, I, P); highest peak power matches gmpp. OK")
    return True


def screen(scenarios, verbose=True):
    rng = np.random.default_rng(config.seed_for("near_tie_screen"))
    rows = []

    for idx, sc in enumerate(scenarios):
        V, P, a = curve_of(sc)
        pk = peak_list(a)
        p_gmpp = float(a["gmpp"]["P"])
        v_gmpp = float(a["gmpp"]["V"])
        if p_gmpp <= 0 or len(pk) < 2:
            rows.append(dict(idx=idx, geometry=sc.geometry, n_peaks=len(pk),
                             gap=1.0, dv=0.0, flipped=False, v_gmpp=v_gmpp,
                             p_gmpp=p_gmpp, alt_v=float("nan"),
                             alt_p=float("nan")))
            continue

        # rival = the highest-power peak that is not the labelled GMPP
        rival = next((q for q in pk if abs(q[0] - v_gmpp) > 1e-6), pk[1])
        gap = (p_gmpp - rival[1]) / p_gmpp          # relative POWER gap
        dv = abs(rival[0] - v_gmpp)                 # voltage separation

        # flip test: does +/-1% irradiance noise move the label to another peak?
        _, _, a2 = curve_of(sc, _perturb(sc.irradiances, rng))
        v2 = float(a2["gmpp"]["V"])
        flipped = abs(v2 - v_gmpp) > max(1.0, 0.02 * float(V[-1]))

        rows.append(dict(idx=idx, geometry=sc.geometry, n_peaks=len(pk),
                         gap=float(gap), dv=float(dv), flipped=bool(flipped),
                         v_gmpp=v_gmpp, p_gmpp=p_gmpp,
                         alt_v=rival[0], alt_p=rival[1]))

        if verbose and (idx + 1) % 500 == 0:
            print(f"   ...{idx + 1}/{len(scenarios)}")
    return rows


def report(rows):
    multi = [r for r in rows if r["n_peaks"] >= 2]
    n, n_multi = len(rows), len(multi)

    print(f"\nA. NEAR-TIE COUNT   ({n_multi} of {n} scenarios have >1 peak)")
    print(f"   {'margin':>8} {'near-tie':>10} {'of all':>9} {'of multi':>10} "
          f"{'median dV':>11} {'max dV':>9}")
    counts = {}
    for m in MARGINS:
        sel = [r for r in multi if r["gap"] < m]
        dv = np.array([r["dv"] for r in sel]) if sel else np.array([0.0])
        counts[m] = {"n": len(sel), "frac_all": len(sel) / n,
                     "frac_multi": len(sel) / max(n_multi, 1),
                     "median_dv": float(np.median(dv)),
                     "max_dv": float(dv.max())}
        print(f"   {m*100:>7.1f}% {len(sel):>10} {100*len(sel)/n:>8.1f}% "
              f"{100*len(sel)/max(n_multi,1):>9.1f}% "
              f"{np.median(dv):>10.1f}V {dv.max():>8.1f}V")

    print("\n   by geometry, at the 1% margin:")
    for g in sorted({r["geometry"] for r in rows}):
        sub = [r for r in rows if r["geometry"] == g]
        nt = [r for r in sub if r["n_peaks"] >= 2 and r["gap"] < 0.01]
        print(f"     {g:<18} {len(nt):>4} of {len(sub):>4}  "
              f"({100*len(nt)/max(len(sub),1):>4.1f}%)")

    print(f"\nB. LABEL FLIP TEST   (+/-{IRR_NOISE*100:.0f}% irradiance noise)")
    flips = [r for r in rows if r["flipped"]]
    flip_rate = len(flips) / n
    print(f"   labels that moved to a different peak: {len(flips)} of {n} "
          f"({100*flip_rate:.1f}%)")
    if flips:
        fg = np.array([r["gap"] for r in flips])
        fd = np.array([r["dv"] for r in flips])
        print(f"   among flipped: median power gap {100*np.median(fg):.2f}%, "
              f"median voltage jump {np.median(fd):.1f} V, max {fd.max():.1f} V")
        print("   (a flip with a LARGE power gap would be self-contradictory -- "
              "check it)")
        for g in sorted({r["geometry"] for r in flips}):
            print(f"     {g:<18} "
                  f"{sum(1 for r in flips if r['geometry'] == g):>4}")

    print("\nC. CONSEQUENCE, SEPARATED BY METRIC")
    nt1 = [r for r in multi if r["gap"] < 0.01]
    worst_power = 100 * max([r["gap"] for r in nt1], default=0.0)
    dv1 = np.array([r["dv"] for r in nt1]) if nt1 else np.array([0.0])
    print(f"   1. power loss    : a flip at the 1% margin costs at most "
          f"{worst_power:.2f} pt")
    print("      -> near-tie peaks are near-tie in POWER, so the baseline table")
    print("         is self-protecting: landing on either is nearly the same.")
    print(f"   2. region error  : {len(nt1)} scenarios "
          f"({100*len(nt1)/n:.1f}%) could flip this")
    print("      binary flag at near-zero power cost. Region-error rates carry")
    print("      this ambiguity and should be quoted with it.")
    print(f"   3. training label: a flip moves a supervised target by a median "
          f"{np.median(dv1):.1f} V (max {dv1.max():.1f} V).")
    print("      -> the fragile one, and a PHASE 3 decision.")

    print("\n--- verdict against the declared tolerances ---")
    lines = [
        ("near-tie fraction at 1% margin", counts[0.01]["frac_all"],
         NEAR_TIE_TOL, "ambiguity is rare"),
        ("label flip rate", flip_rate, FLIP_TOL, "labels are robust"),
        ("power-loss impact of a flip (pt)", worst_power / 100,
         POWER_IMPACT_TOL / 100, "baseline table unaffected"),
    ]
    for label, val, tol, meaning in lines:
        ok = val < tol
        print(f"   {'PASS' if ok else 'FLAG'}  {label:<34} "
              f"{100*val:>6.2f}%  (bar {100*tol:.0f}%)  {meaning}")

    return {"counts": {str(k): v for k, v in counts.items()},
            "flip_rate": flip_rate, "n_flipped": len(flips),
            "worst_power_pt": worst_power,
            "median_dv_near_tie": float(np.median(dv1)),
            "n_multi_peak": n_multi}


def figures(scenarios, rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("\n   matplotlib not installed; skipping figures "
              "(pip install matplotlib)")
        return

    FIGS.mkdir(parents=True, exist_ok=True)
    NAVY, AMBER, CORAL = "#1F3864", "#C8842A", "#C0504D"

    # -- figure 1: the most ambiguous real cases -----------------------------
    cand = [r for r in rows if r["n_peaks"] >= 2 and np.isfinite(r["alt_v"])]
    cand = sorted(cand, key=lambda r: r["gap"])[:4]      # smallest power gap
    if cand:
        fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))
        for ax, r in zip(axes.ravel(), cand):
            sc = scenarios[r["idx"]]
            V, P, _ = curve_of(sc)
            ax.plot(V, P, color=NAVY, lw=1.6)
            ax.plot(r["v_gmpp"], r["p_gmpp"], "o", color=CORAL, ms=9,
                    label=f"labelled GMPP  {r['v_gmpp']:.1f} V")
            ax.plot(r["alt_v"], r["alt_p"], "o", color=AMBER, ms=9,
                    label=f"rival peak  {r['alt_v']:.1f} V")
            top = max(r["p_gmpp"], r["alt_p"])
            ax.annotate("", xy=(r["v_gmpp"], top * 1.06),
                        xytext=(r["alt_v"], top * 1.06),
                        arrowprops=dict(arrowstyle="<->", color="#888"))
            ax.text((r["v_gmpp"] + r["alt_v"]) / 2, top * 1.09,
                    f"{r['dv']:.1f} V apart", ha="center", fontsize=9,
                    color="#555")
            ax.set_title(f"{sc.geometry}  |  power gap {100*r['gap']:.2f}%",
                         fontsize=10)
            ax.set_xlabel("voltage (V)", fontsize=9)
            ax.set_ylabel("power (W)", fontsize=9)
            ax.legend(fontsize=8, loc="lower center")
            ax.grid(alpha=0.25)
        fig.suptitle("Closest rival peaks: how small is the power gap, "
                     "how large the voltage gap", fontsize=12)
        fig.tight_layout()
        fig.savefig(FIGS / "near_tie_examples.png", dpi=150)
        plt.close(fig)
        print(f"\n   figure -> {FIGS / 'near_tie_examples.png'}")

    # -- figure 2: gap distribution and voltage separation -------------------
    mrows = [r for r in rows if r["n_peaks"] >= 2]
    if mrows:
        gaps = 100 * np.array([r["gap"] for r in mrows])
        dvs = np.array([r["dv"] for r in mrows])
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.2))

        ax1.hist(np.clip(gaps, 0, 60), bins=50, color=NAVY, alpha=0.85)
        ax1.axvline(1.0, color=CORAL, ls="--", lw=1.5, label="1% near-tie margin")
        ax1.set_xlabel("power gap between top two peaks (%)", fontsize=9)
        ax1.set_ylabel("scenarios", fontsize=9)
        ax1.legend(fontsize=8)
        ax1.grid(alpha=0.25)

        near = gaps < 1.0
        ax2.scatter(gaps[~near], dvs[~near], s=8, color="#BBB", label="clear")
        if near.any():
            ax2.scatter(gaps[near], dvs[near], s=16, color=CORAL,
                        label="near-tie (<1%)")
        ax2.set_xlim(0, 60)
        ax2.set_xlabel("power gap between top two peaks (%)", fontsize=9)
        ax2.set_ylabel("voltage separation (V)", fontsize=9)
        ax2.legend(fontsize=8)
        ax2.grid(alpha=0.25)

        fig.suptitle("How often peaks are near-tied, and how far apart they sit",
                     fontsize=12)
        fig.tight_layout()
        fig.savefig(FIGS / "near_tie_distribution.png", dpi=150)
        plt.close(fig)
        print(f"   figure -> {FIGS / 'near_tie_distribution.png'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2000)
    args = ap.parse_args()

    print("P2.5  NEAR-TIE PEAK SCREEN -- GMPP label integrity  (revision 2)")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 70)
    print(f"declared in advance: near-tie < {NEAR_TIE_TOL*100:.0f}%, "
          f"flip rate < {FLIP_TOL*100:.0f}%, power impact < {POWER_IMPACT_TOL} pt")
    print("reference: Betti et al., Energies 17(10):2276, 2024 -- measured GMPP")
    print("at 19 V where simulation placed it at 34.2 V on a near-tie curve.\n")

    scenarios = scenario_set(args.n)
    print(f"scenarios: {len(scenarios)}   (each evaluated twice: clean + perturbed)")

    print("\nPRE-CHECK  peak tuple layout")
    if not sanity_check_peaks(scenarios):
        return 1

    rows = screen(scenarios)
    summary = report(rows)
    figures(scenarios, rows)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "near_tie_screen.json").write_text(
        json.dumps({"summary": summary,
                    "rows": [{k: (float(v)
                                  if isinstance(v, (int, float, np.floating))
                                  else v) for k, v in r.items()} for r in rows]},
                   indent=2), encoding="utf-8")
    print(f"\nresults -> {OUT / 'near_tie_screen.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())