"""
S5 - array generalisation (Stage 3, standalone insurance step).

S3 built module-level composition: substrings in series, composed in the current
domain (one current, sum the voltages), with a bypass diode across each substring.
S5 generalises that ONE LEVEL UP: modules in series form a string, composed the
exact same way, with a bypass diode across each module. The array-capable
simulator is the same code applied recursively - that is the whole point.

Why S5 exists (WORKFLOW / plan Section 10, Gate A note): array-capability is
INSURANCE. If Gate A(ii) later finds a recalibrated constant already solves the
module-level problem, the study redirects to string level - and that redirect
must cost 2-3 weeks, not two months, because the string simulator already exists.
S5 is scheduled immediately after Stage 2 (while the S3 composition code is fresh)
but kept a standalone checkpoint so it cannot be quietly dropped.

Three checkpoints:
  1. N=1 REDUCTION - a string of one module reproduces module_iv exactly. The
     generalisation must not change the base case.
  2. SERIES SCALING - N identical unshaded modules give N x the voltage and power
     at the same current (correct series composition).
  3. STRING-LEVEL MULTI-PEAK - modules at different irradiance produce a
     multi-peak string curve via module-level bypass, the same mechanism S3
     showed for substrings. Confirms shaded strings compose correctly.
"""
import numpy as np

from gmppt import config, device
from gmppt.device import ModuleParams


def check_n1_reduction(mp):
    """A one-module string must equal the module exactly."""
    print("1) N=1 REDUCTION  (string of one module == module_iv)")
    uniform = [1000.0] * config.N_SUBSTRINGS
    m = device.analyse(device.module_iv(mp, uniform, 25.0))["gmpp"]
    s = device.analyse(device.string_iv(mp, [uniform], 25.0))["gmpp"]
    dP = abs(m["P"] - s["P"])
    dV = abs(m["V"] - s["V"])
    ok = dP < 1e-6 and dV < 1e-6
    print(f"   module GMPP: {m['P']:.4f} W at {m['V']:.4f} V")
    print(f"   string GMPP: {s['P']:.4f} W at {s['V']:.4f} V")
    print(f"   identical to 1e-6: {'OK' if ok else 'FAIL'}")
    return ok


def check_series_scaling(mp, n=3):
    """N identical unshaded modules -> N x V, N x P, same I."""
    print(f"\n2) SERIES SCALING  ({n} identical unshaded modules)")
    uniform = [1000.0] * config.N_SUBSTRINGS
    one = device.analyse(device.module_iv(mp, uniform, 25.0))["gmpp"]
    many = device.analyse(device.string_iv(mp, [uniform] * n, 25.0))["gmpp"]
    rV, rP, rI = many["V"] / one["V"], many["P"] / one["P"], many["I"] / one["I"]
    ok = abs(rV - n) < 1e-3 and abs(rP - n) < 1e-3 and abs(rI - 1) < 1e-3
    print(f"   1 module : V={one['V']:.2f} I={one['I']:.2f} P={one['P']:.2f}")
    print(f"   {n} modules: V={many['V']:.2f} I={many['I']:.2f} P={many['P']:.2f}")
    print(f"   ratios V={rV:.4f} (=>{n})  P={rP:.4f} (=>{n})  I={rI:.4f} (=>1): "
          f"{'OK' if ok else 'FAIL'}")
    return ok


def check_string_multipeak(mp):
    """Modules at different irradiance -> string-level multi-peak."""
    print("\n3) STRING-LEVEL MULTI-PEAK  (3 modules at 1000/700/400 W/m^2)")
    patterns = [[1000.0]*config.N_SUBSTRINGS,
                [700.0]*config.N_SUBSTRINGS,
                [400.0]*config.N_SUBSTRINGS]
    c = device.string_iv(mp, patterns, 25.0)
    a = device.analyse(c)
    # module Isc should scale with irradiance: 1.00 / 0.70 / 0.40
    ratios = c["isc_modules"] / c["isc_modules"].max()
    scaling_ok = np.allclose(sorted(ratios, reverse=True), [1.0, 0.70, 0.40],
                             atol=0.02)
    peaks_ok = a["n_peaks"] == 3
    ok = scaling_ok and peaks_ok
    print(f"   module Isc: {np.round(c['isc_modules'], 2)} "
          f"(ratios {np.round(sorted(ratios, reverse=True), 3)})")
    print(f"   peaks found: {a['n_peaks']}  (expect 3, one per irradiance level)")
    for V, I, P in a["peaks"]:
        tag = "  <- GMPP" if abs(P - a["gmpp"]["P"]) < 1e-6 else ""
        print(f"     V={V:6.1f}  I={I:5.2f}  P={P:6.1f} W{tag}")
    print(f"   irradiance scaling + 3 peaks: {'OK' if ok else 'FAIL'}")
    return ok, c, a


def make_figure(mp, c, a):
    from gmppt import viz
    import matplotlib.pyplot as plt
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(10, 4))
    axl.plot(c["V"], c["I"], color=viz.BLUE, lw=1.6)
    axl.set_xlabel("String voltage (V)"); axl.set_ylabel("Current (A)")
    axl.set_title("Stepped I-V (module bypass switching)")
    axr.plot(c["V"], c["P"], color=viz.BLUE, lw=1.6, label="P-V")
    g = a["gmpp"]
    axr.scatter([g["V"]], [g["P"]], color=viz.ORANGE, s=90, zorder=5,
                label="global peak")
    locals_ = [(V, P) for V, I, P in a["peaks"] if abs(P - g["P"]) > 1e-6]
    if locals_:
        axr.scatter([v for v, _ in locals_], [p for _, p in locals_],
                    color=viz.GRAY, s=55, zorder=4, label="local peaks")
    axr.set_xlabel("String voltage (V)"); axr.set_ylabel("Power (W)")
    axr.set_title(f"String multi-peak: {a['n_peaks']} peaks, "
                  f"GMPP {g['P']:.1f} W")
    axr.legend(fontsize=8)
    fig.suptitle(f"S5 array generalisation — 3 modules in series "
                 f"({config.CANONICAL_DEMO_MODULE})", fontsize=10)
    plt.tight_layout()
    return viz.save_fig(fig, "s5_string_multipeak")


if __name__ == "__main__":
    print("S5  Array generalisation (modules in series -> string)")
    print("  " + config.provenance())
    print("=" * 66)
    mp = ModuleParams.from_cec(config.CANONICAL_DEMO_MODULE)
    print(f"  canonical module: {config.CANONICAL_DEMO_MODULE} (N_s={mp.N_s})")

    ok1 = check_n1_reduction(mp)
    ok2 = check_series_scaling(mp)
    ok3, c, a = check_string_multipeak(mp)

    path = make_figure(mp, c, a)
    print(f"\n   Figure -> {path.relative_to(config.PROJECT_ROOT)}")

    all_ok = ok1 and ok2 and ok3
    print("\n" + "=" * 66)
    print(f"S5 checkpoint: {'PASS' if all_ok else 'FAIL'}  "
          f"(n1_reduction={ok1}, series_scaling={ok2}, string_multipeak={ok3})")
    print("  Array-capable: the single module is the N=1 special case, and a")
    print("  short string composes correctly. Insurance for a Gate A(ii) redirect")
    print("  to string level is in place.")
