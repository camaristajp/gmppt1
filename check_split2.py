"""
check_split2.py -- which split does the DASHBOARD show, compared with the split p7 reports on?

p7 --split val uses gmppt.dataset.module_split().val  (not scenarios.split_modules).
The dashboard's Explore dropdown uses scenarios.split_modules(pool)[1].
This script checks how those two relate. Read-only.

    python check_split2.py
"""
import pandas as pd
from gmppt import config, dataset, scenarios

pool = pd.read_parquet(config.CEC_POOL)
names = set(map(str, pool.index))
sc_train, sc_held = map(lambda s: set(map(str, s)), scenarios.split_modules(pool))

split = dataset.module_split()
print("dataset.module_split():", getattr(split, "summary", lambda: "")())

# every list-like attribute of the split object that holds module names
sets = {}
for attr, v in vars(split).items():
    try:
        s = {str(x) for x in v} & names
    except TypeError:
        continue
    if s:
        sets[attr] = s
print("\n[A] Split sets and their overlap with scenarios.split_modules")
for attr, s in sets.items():
    print(f"  {attr:<10} n={len(s):>6}   in scenarios-heldout={len(s & sc_held):>6}   "
          f"in scenarios-train={len(s & sc_train):>6}")

# the dashboard dropdown, reproduced from gmppt_app._validation_modules()
h = pool.loc[sorted(sc_held)].copy()
h["P"] = h["V_mp_ref"] * h["I_mp_ref"]
dropdown = []
for nc, lo, hi in [(72, 330, 350), (60, 270, 290), (72, 300, 330)]:
    s = h[(h["N_s"] == nc) & (h["P"].between(lo, hi))].sort_values("P")
    if len(s):
        dropdown.append(str(s.index[len(s) // 2]))

check = dropdown + ["LG_Electronics_Inc__LG375N2K_G4",      # dashboard demo module
                    "LG_Electronics_Inc__LG370N2K_G4",      # near-twin siblings
                    "LG_Electronics_Inc__LG380N2K_G4"]
print("\n[B] Which split each dashboard module belongs to")
for m in dict.fromkeys(check):
    where = [a for a, s in sets.items() if m in s] or ["(none)"]
    tag = "dropdown" if m in dropdown else "demo/sibling"
    print(f"  {tag:<13} {m:<55} -> {', '.join(where)}")

print("\nInterpretation:")
print("  dropdown -> 'val'            : matches p7; the 'unseen' claim is sound.")
print("  dropdown -> test / held-out  : the dashboard exposes the reserved test set -- fix.")
print("  demo     -> 'train'          : the demo is a TRAINING module -- the on-screen\n"
      "                                 'held-out validation module' label is false.")
print("  siblings -> 'train' while the shown module is 'val': unseen by name, but a\n"
      "                                 near-identical module was trained on -- disclose.")