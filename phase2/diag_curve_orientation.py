"""Diagnostic: what does module_iv actually return, and what does
curve_and_ceiling return? One scenario, no conclusions drawn."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, device
from gmppt.device import ModuleParams
from gmppt.harness import scenario_set, curve_and_ceiling

sc = scenario_set(3)[0]
print(f"scenario: {sc.module}  {sc.geometry}  T={sc.temp_c}")

mp = ModuleParams.from_cec(sc.module)
c = device.module_iv(mp, sc.irradiances, sc.temp_c,
                     n_substrings=int(config.N_SUBSTRINGS),
                     bd=config.breakdown())
V = np.asarray(c["V"], float)
P = np.asarray(c["P"], float)

print("\n--- device.module_iv ---")
print(f"  keys        : {list(c.keys())}")
print(f"  V len       : {len(V)}")
print(f"  V[0], V[-1] : {V[0]:.4f}, {V[-1]:.4f}")
print(f"  V min, max  : {V.min():.4f}, {V.max():.4f}")
print(f"  ascending?  : {bool(np.all(np.diff(V) > 0))}")
print(f"  descending? : {bool(np.all(np.diff(V) < 0))}")
print(f"  any V < 0   : {bool((V < 0).any())}  (count {(V<0).sum()})")
print(f"  P min, max  : {P.min():.4f}, {P.max():.4f}")

a = device.analyse(c)
print(f"  analyse gmpp: V={a['gmpp']['V']:.4f}  P={a['gmpp']['P']:.4f}")
print(f"  n_peaks     : {a['n_peaks']}")
print(f"  interp at v_gmpp using raw V: "
      f"{float(np.interp(a['gmpp']['V'], V, P)):.4f}   (should equal P above)")

print("\n--- harness.curve_and_ceiling ---")
out = curve_and_ceiling(sc)
print(f"  returns {len(out)} items, types {[type(o).__name__ for o in out]}")
for i, o in enumerate(out):
    if isinstance(o, np.ndarray):
        print(f"  [{i}] array len {len(o)}  first {o[0]:.4f}  last {o[-1]:.4f}  "
              f"ascending {bool(np.all(np.diff(o) > 0))}")
    else:
        print(f"  [{i}] {o}")