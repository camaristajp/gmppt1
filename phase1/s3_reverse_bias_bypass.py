"""
S3 - reverse-bias + bypass diodes: verification and multi-peak demonstration.

Checkpoints (S3's own; the published-shading match is S4):
  1. UNSHADED CONSISTENCY. Three uniform substrings composed in series must
     reproduce the direct single-diode module (V_oc, I_sc, V_mp, I_mp, P_mp) to
     3 sig figs. This proves the substring scaling and current-domain
     composition are correct.
  2. MULTI-PEAK. Under three distinct substring irradiances the P-V curve shows
     the expected staircase with up to three peaks, and a global peak is found.
  3. BYPASS ACTIVATION. A shaded substring is clamped near -0.6 V.
  4. REVERSE-BIAS INSENSITIVITY. Turning the avalanche term on/off barely moves
     the GMPP (the bypass diode clamps first) - the reassuring result that
     justifies the default and localises where the parameter matters (S6).
"""
import numpy as np
import pandas as pd
from pvlib import pvsystem

from gmppt import config, device
from gmppt.device import ModuleParams, Breakdown, Bypass


def pick_demo_module():
    """A ~300 W c-Si module with cell count divisible by 3 (echoes Section 4)."""
    full = pvsystem.retrieve_sam("CECMod").T
    pool = pd.read_parquet(config.CEC_POOL)
    csi = pool[pool["Technology"].isin(config.CSI_TECHNOLOGIES)].copy()
    csi["N_s"] = pd.to_numeric(full.loc[csi.index, "N_s"], errors="coerce")
    csi["P"] = csi["V_mp_ref"] * csi["I_mp_ref"]
    cand = csi[(csi["N_s"] % 3 == 0) & csi["P"].between(280, 320)]
    return cand.sort_values("P").index[len(cand) // 2]


def round_sig(x, s=3):
    return 0.0 if x == 0 else round(x, -int(np.floor(np.log10(abs(x)))) + s - 1)


def check_unshaded_consistency(mp):
    """Composed 3x uniform substrings vs direct single-diode module."""
    G, T = config.STC_IRRADIANCE, config.STC_TEMPERATURE
    # direct module
    p = pvsystem.calcparams_cec(
        G, T, mp.alpha_sc, mp.a_ref, mp.I_L_ref, mp.I_o_ref,
        mp.R_sh_ref, mp.R_s, mp.Adjust,
        EgRef=config.EG_REF, dEgdT=config.DEG_DT)
    direct = pvsystem.singlediode(*p)
    # composed
    curve = device.module_iv(mp, [G, G, G], T)
    comp = device.analyse(curve)["gmpp"]
    # module Isc / Voc from the composed curve
    isc_c = float(np.interp(0.0, curve["V"][::-1], (curve["I"])[::-1]))
    voc_c = float(np.interp(0.0, curve["I"], curve["V"]))
    rows = [
        ("V_oc", voc_c, float(direct["v_oc"])),
        ("I_sc", isc_c, float(direct["i_sc"])),
        ("V_mp", comp["V"], float(direct["v_mp"])),
        ("I_mp", comp["I"], float(direct["i_mp"])),
        ("P_mp", comp["P"], float(direct["p_mp"])),
    ]
    ok = True
    print(f"1) UNSHADED CONSISTENCY  ({mp.name}, N_s={mp.N_s})")
    print(f"   {'qty':5s} {'composed':>10s} {'direct':>10s} {'rel%':>8s} 3sig")
    for name, c, d in rows:
        rel = abs(c - d) / abs(d) * 100
        ok3 = round_sig(c) == round_sig(d)
        ok &= ok3
        print(f"   {name:5s} {c:10.4f} {d:10.4f} {rel:8.4f}  "
              f"{'OK' if ok3 else 'FAIL'}")
    return ok


def demo_multipeak(mp):
    print("\n2) MULTI-PEAK  (substrings at 1000 / 600 / 300 W/m^2, 25 C)")
    curve = device.module_iv(mp, [1000, 600, 300], 25.0)
    a = device.analyse(curve)
    print(f"   substring Isc: {np.round(curve['isc_substrings'], 3)}")
    print(f"   peaks found  : {a['n_peaks']}  (<= 3 distinct irradiances)")
    for k, (V, I, P) in enumerate(a["peaks"], 1):
        tag = "  <- GMPP" if abs(P - a["gmpp"]["P"]) < 1e-6 else ""
        print(f"     peak {k}: V={V:6.2f}  I={I:5.2f}  P={P:7.2f} W{tag}")
    # save for plotting / visualisation
    np.savez(config.RESULTS_DIR / "s3_multipeak.npz",
             I=curve["I"], V=curve["V"], P=curve["P"])
    return a


def check_bypass_activation(mp):
    print("\n3) BYPASS ACTIVATION  (one substring at 200 W/m^2)")
    # isolate a single shaded substring's element curve
    frac = 1.0 / config.N_SUBSTRINGS
    sub = device.scale_to_substring(mp, frac)
    v, i_elem = device.substring_element_iv(sub, 200.0, 25.0, Breakdown(),
                                            Bypass(temp_c=25.0))
    # voltage where the element carries the bright-substring Isc (~forced through)
    bright = device.module_iv(mp, [1000, 1000, 1000], 25.0)["isc_substrings"][0]
    v_at_bright = float(np.interp(bright, i_elem[::-1], v[::-1]))
    print(f"   at forced current {bright:.2f} A the shaded substring sits at "
          f"V = {v_at_bright:+.3f} V")
    ok = -0.8 < v_at_bright < -0.3
    print(f"   clamped near -0.6 V by the bypass diode: "
          f"{'OK' if ok else 'FAIL'}")
    return ok


def check_reverse_bias_sweep(mp):
    """Record the GMPP over a SWEPT RANGE of avalanche parameters (Stage 2
    done-criterion: reverse-bias params recorded as a swept range). The bypass
    clamps first, so the GMPP should be invariant across the plausible range."""
    print("\n4) REVERSE-BIAS SWEEP  (GMPP vs avalanche parameters)")
    factors = [0.0, 1e-4, 1e-3, 5e-3, 1e-2, 5e-2]      # breakdown_factor range
    voltages = [-30.0, -20.0, -15.0, -10.0]            # breakdown_voltage range
    base = device.analyse(device.module_iv(
        mp, [1000, 600, 300], 25.0, bd=Breakdown(factor=0.0)))["gmpp"]["P"]
    records = []
    max_dev = 0.0
    for f in factors:
        for vbr in voltages:
            P = device.analyse(device.module_iv(
                mp, [1000, 600, 300], 25.0,
                bd=Breakdown(factor=f, voltage=vbr, exp=3.28)))["gmpp"]["P"]
            dev = abs(P - base) / base * 100
            max_dev = max(max_dev, dev)
            records.append((f, vbr, P, dev))
    tbl = pd.DataFrame(records,
                       columns=["breakdown_factor", "breakdown_voltage",
                                "gmpp_W", "dev_pct"])
    tbl.to_csv(config.RESULTS_DIR / "s3_reverse_bias_sweep.csv", index=False)
    print(f"   swept {len(factors)}x{len(voltages)} = {len(records)} combinations")
    print(f"   base GMPP {base:.3f} W;  max deviation over the range: "
          f"{max_dev:.4f}%")
    ok = max_dev < 0.5
    print(f"   GMPP invariant across the swept range (<0.5%): "
          f"{'OK' if ok else 'FAIL'}  -> avalanche params inert until near-"
          f"threshold / sub-substring (S6)")
    return ok, tbl, base


def make_figures(mp, sweep_tbl, base):
    """S3 figures: the multi-peak curve and the reverse-bias sweep."""
    from gmppt import viz
    import matplotlib.pyplot as plt

    # multi-peak I-V and P-V
    c = device.module_iv(mp, [1000, 600, 300], 25.0)
    a = device.analyse(c)
    m = c["V"] >= 0
    V, I, P = c["V"][m], c["I"][m], c["P"][m]
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(9.2, 3.8))
    axl.plot(V, I, color=viz.BLUE, lw=2)
    axl.set_xlabel("Module voltage (V)"); axl.set_ylabel("Current (A)")
    axl.set_title("Stepped I–V (bypass switching)")
    axr.plot(V, P, color=viz.BLUE, lw=2, label="P–V")
    for k, (vv, ii, pp) in enumerate(a["peaks"]):
        is_g = abs(pp - a["gmpp"]["P"]) < 1e-6
        axr.plot(vv, pp, "o", ms=9 if is_g else 6,
                 color=viz.ORANGE if is_g else viz.GRAY,
                 label="global peak" if is_g else ("local peaks" if k == 0 or
                       (k == 1 and abs(a["peaks"][0][2]-a["gmpp"]["P"])<1e-6) else None))
    axr.set_xlabel("Module voltage (V)"); axr.set_ylabel("Power (W)")
    axr.set_title(f"Multi-peak P–V: {a['n_peaks']} peaks, "
                  f"GMPP {a['gmpp']['P']:.1f} W")
    axr.legend(fontsize=8)
    fig.suptitle(f"{mp.name[:40]}  |  substrings 1000 / 600 / 300 W/m²",
                 fontsize=10)
    p1 = viz.save_fig(fig, "s3_multipeak")

    # reverse-bias sweep
    tbl = sweep_tbl
    fig2, ax2 = plt.subplots(figsize=(6.6, 3.8))
    for vbr, sub in tbl.groupby("breakdown_voltage"):
        ax2.plot(sub["breakdown_factor"], sub["gmpp_W"], "o-",
                 label=f"V_br={vbr:.0f} V", lw=1.5, ms=4)
    ax2.set_xscale("symlog", linthresh=1e-4)
    ax2.axhline(base, color=viz.GRAY, ls="--", lw=1, label="baseline (off)")
    ax2.set_xlabel("breakdown_factor (swept)")
    ax2.set_ylabel("GMPP power (W)")
    ax2.set_title("Reverse-bias sweep: GMPP invariant (bypass clamps first)")
    ax2.legend(fontsize=8, ncol=2)
    p2 = viz.save_fig(fig2, "s3_reverse_bias_sweep")
    print(f"\n   Figures -> {p1.relative_to(config.PROJECT_ROOT)}, "
          f"{p2.relative_to(config.PROJECT_ROOT)}")


if __name__ == "__main__":
    name = pick_demo_module()
    mp = ModuleParams.from_cec(name)
    print("S3  Reverse-bias + bypass diode model\n" + "=" * 66)
    c1 = check_unshaded_consistency(mp)
    demo_multipeak(mp)
    c3 = check_bypass_activation(mp)
    c4, sweep_tbl, base = check_reverse_bias_sweep(mp)
    make_figures(mp, sweep_tbl, base)
    print("\n" + "=" * 66)
    print(f"S3 checkpoint: {'PASS' if (c1 and c3 and c4) else 'FAIL'}  "
          f"(consistency={c1}, bypass={c3}, sweep_invariant={c4})")
