"""Count the geometry mix on both generation paths. Seconds, no simulation."""
from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import dataset
from gmppt.harness import scenario_set
from phase3.p3_final_comparison import scenarios_for_modules

DECLARED = {"uniform": 40.0, "whole_substring": 15.0, "sub_substring": 45.0}
N = 2000

def report(label, scenarios):
    c = Counter(str(s.geometry) for s in scenarios)
    n = sum(c.values())
    print(f"\n{label}  (n={n})")
    print(f"   {'geometry':<18} {'count':>7} {'actual %':>10} {'plan %':>9} {'gap':>8}")
    print("   " + "-" * 55)
    for g in ("uniform", "whole_substring", "sub_substring"):
        k = c.get(g, 0)
        pct = 100.0 * k / max(n, 1)
        want = DECLARED[g]
        print(f"   {g:<18} {k:>7} {pct:>10.1f} {want:>9.1f} {pct-want:>+8.1f}")
    extra = set(c) - set(DECLARED)
    if extra:
        print(f"   UNEXPECTED geometries present: {sorted(extra)}")
    return {g: 100.0 * c.get(g, 0) / max(n, 1) for g in DECLARED}

print("Geometry mix: what the generator actually produces")
print("=" * 64)
print(f"plan states 40/15/45 (uniform / whole_substring / sub_substring)")

a = report("scenario_set  (train_only=True)", scenario_set(N))

split = dataset.module_split()
b = report("scenarios_for_modules(split.val)", scenarios_for_modules(split.val, N))

print("\nDO THE TWO PATHS AGREE?")
worst = max(abs(a[g] - b[g]) for g in DECLARED)
print(f"   largest difference between paths: {worst:.1f} pt")
if worst > 3.0:
    print("   -> NO. The two generation paths produce different mixes, so a")
    print("      figure from one path cannot be compared with a figure from")
    print("      the other without reweighting. This is the more serious of")
    print("      the two problems and must be resolved first.")
else:
    print("   -> yes, within sampling noise. A single mix describes both.")

print("\nDOES EITHER MATCH THE PLAN?")
for label, mix in (("scenario_set", a), ("scenarios_for_modules", b)):
    gap = max(abs(mix[g] - DECLARED[g]) for g in DECLARED)
    print(f"   {label:<24} largest gap from plan: {gap:.1f} pt"
          f"   {'MATCHES' if gap <= 3.0 else 'DOES NOT MATCH'}")

print("\nNOTE: 'uniform' is not the same as 'single-peak'. A whole_substring")
print("scenario with mild shading can still present one peak. Compare this")
print("table against n_peaks separately before drawing conclusions.")