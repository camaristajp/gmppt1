"""
check_split.py -- which module set is "validation", and did the model train on it?

Run from the repo root (the folder that contains gmppt/, phase2/, results/):
    python check_split.py

Read-only: it loads files and prints findings; it changes nothing.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from gmppt import config, scenarios

DEMO = "LG_Electronics_Inc__LG375N2K_G4"   # _RUN_DEMO / _MV_DEMO in gmppt_app.py


def hr(t):
    print("\n" + "=" * 78 + f"\n{t}\n" + "=" * 78)


# ---------------------------------------------------------------- [1] the split
pool = pd.read_parquet(config.CEC_POOL)
names = set(map(str, pool.index))
train, heldout = scenarios.split_modules(pool)
train, heldout = set(map(str, train)), set(map(str, heldout))
hr("[1] scenarios.split_modules")
print(f"train = {len(train)}   heldout (20% reserve) = {len(heldout)}   "
      f"overlap = {len(train & heldout)}")

# ---------------------------------------------------------------- [2] p7's --split val
hr("[2] How phase2/p7_tracker_comparison.py defines the splits (read these lines)")
p7 = Path("phase2/p7_tracker_comparison.py")
if p7.exists():
    pat = re.compile(r"split|heldout|held_out|\bval\b|valid|train_mod|module", re.I)
    for i, line in enumerate(p7.read_text(encoding="utf-8").splitlines(), 1):
        if pat.search(line):
            print(f"  p7:{i:>4}  {line.rstrip()}")
else:
    print("  p7_tracker_comparison.py not found at phase2/ -- locate it and rerun.")


# ---------------------------------------------------------------- [3] modules inside the exports
def collect(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k in names:
                acc.add(k)
            collect(v, acc)
    elif isinstance(o, list):
        for v in o:
            collect(v, acc)
    elif isinstance(o, str) and o in names:
        acc.add(o)


hr("[3] Module names found inside results/phase2/*_val.json")
val_mods: set[str] = set()
for f in sorted(Path(config.RESULTS_DIR, "phase2").glob("*val*.json")):
    acc: set[str] = set()
    try:
        collect(json.loads(f.read_text(encoding="utf-8")), acc)
    except Exception as e:
        print(f"  {f.name}: unreadable ({e})")
        continue
    val_mods |= acc
    print(f"  {f.name:<45} modules={len(acc):>4}  in heldout={len(acc & heldout):>4}  "
          f"in train={len(acc & train):>4}")
if not val_mods:
    print("  No module names stored in the exports -- use the p7 lines in [2] instead.")

# ---------------------------------------------------------------- [4] the model's own training list
hr("[4] Training modules recorded inside the trained model (strongest check)")
model_train: set[str] = set()
try:
    from gmppt.model import TwoStageModel
    m = TwoStageModel.load("c3_two_stage_full")
    for attr, v in vars(m).items():
        if isinstance(v, (list, tuple, set, np.ndarray, pd.Index)):
            s = {str(x) for x in list(v)[:100000]} & names
            if s:
                print(f"  attribute '{attr}': {len(s)} module names")
                model_train |= s
    if not model_train:
        print("  The model object stores no module list. Check the training script / its "
              "log for which modules it used, or save that list with the model next time.")
except Exception as e:
    print(f"  Could not load the model ({e}).")

# ---------------------------------------------------------------- [5] verdict
hr("[5] Verdict")
if val_mods:
    if val_mods <= heldout:
        print("  CASE B: the 'val' exports use the 20% HELD-OUT RESERVE.\n"
              "  The model never trained on them, but this is the set the plan keeps for a\n"
              "  single final evaluation. Browsing it in the dashboard spends that set.")
    elif val_mods <= train:
        print("  CASE A-candidate: 'val' modules sit inside split_modules' TRAIN side, so\n"
              "  validation is carved out of it somewhere else (see [2]). 'Unseen by the\n"
              "  model' is only true if the model's training excluded them -- see [4].")
    else:
        print("  MIXED: 'val' exports contain modules from both sides. Investigate before\n"
              "  making any 'unseen' claim.")
if model_train and val_mods:
    leak = val_mods & model_train
    print(f"  Overlap between val modules and the model's training list: {len(leak)}"
          + ("  <-- the 'unseen' claim is FALSE for these" if leak else "  (clean)"))

print(f"\n  Demo module {DEMO}:")
print(f"    in heldout: {DEMO in heldout}   in train: {DEMO in train}   "
      f"in val exports: {DEMO in val_mods if val_mods else 'n/a'}   "
      f"in model training list: {DEMO in model_train if model_train else 'n/a'}")

# ---------------------------------------------------------------- [6] near-twin siblings
hr("[6] Nearest TRAINING module to the demo module (near-twin check)")
cols = [c for c in ("V_mp_ref", "I_mp_ref", "V_oc_ref", "I_sc_ref", "N_s") if c in pool.columns]
ref_set = model_train or train
if DEMO in names and cols:
    X = pool[cols].apply(pd.to_numeric, errors="coerce")
    Z = (X - X.mean()) / X.std(ddof=0)
    cand = [n for n in ref_set if n in Z.index and n != DEMO]
    d = np.sqrt(((Z.loc[cand] - Z.loc[DEMO]) ** 2).sum(axis=1)).sort_values()
    print(f"  compared on {cols}; closest 5 training modules (z-score distance):")
    for n, dist in d.head(5).items():
        print(f"    {dist:6.3f}  {n}")
    print("  Distance near 0 = a practically identical module was in training.")
else:
    print("  Demo module or parameter columns not found in the pool.")