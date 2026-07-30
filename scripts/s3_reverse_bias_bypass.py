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


def check_reverse_bias_insensitivity(mp):
    print("\n4) REVERSE-BIAS INSENSITIVITY  (avalanche off vs on)")
    off = device.analyse(device.module_iv(
        mp, [1000, 600, 300], 25.0, bd=Breakdown(factor=0.0)))["gmpp"]
    on = device.analyse(device.module_iv(
        mp, [1000, 600, 300], 25.0,
        bd=Breakdown(factor=2e-3, voltage=-15.0, exp=3.28)))["gmpp"]
    dP = abs(on["P"] - off["P"]) / off["P"] * 100
    print(f"   GMPP power  off: {off['P']:.3f} W   on: {on['P']:.3f} W   "
          f"delta: {dP:.3f}%")
    ok = dP < 0.5
    print(f"   GMPP insensitive to avalanche params (<0.5%): "
          f"{'OK' if ok else 'FAIL'}  (matters only near-threshold / sub-substring)")
    return ok


if __name__ == "__main__":
    name = pick_demo_module()
    mp = ModuleParams.from_cec(name)
    print("S3  Reverse-bias + bypass diode model\n" + "=" * 66)
    c1 = check_unshaded_consistency(mp)
    demo_multipeak(mp)
    c3 = check_bypass_activation(mp)
    c4 = check_reverse_bias_insensitivity(mp)
    print("\n" + "=" * 66)
    print(f"S3 checkpoint: {'PASS' if (c1 and c3 and c4) else 'FAIL'}  "
          f"(consistency={c1}, bypass={c3}, insensitivity={c4})")
