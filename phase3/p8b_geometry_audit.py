"""
p8b_geometry_audit.py
Destination:  C:\\Users\\user\\gmppt\\phase3\\p8b_geometry_audit.py
Run from:     C:\\Users\\user\\gmppt>  python phase3\\p8b_geometry_audit.py

Corrects two loader bugs in p8: .npy was opened with pickle, and the geometry
search looked only inside .npz files while the labels live in the parquet.

Read-only. No simulation, no training, no writes.

Purpose: close open item 13 by measuring the geometry composition directly,
and print the column contract the leave-one-geometry-out runner needs.
"""

import sys
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FEATURES = ROOT / "results" / "phase3" / "full_features.parquet"
CURVES = ROOT / "results" / "phase3" / "full_curves.npy"

# Per-geometry held-out results as logged at P3.7, for the reconciliation below.
LOGGED_PER_GEOM = {"uniform": 0.00, "whole_substring": 0.08, "sub_substring": 0.39}
LOGGED_POOLED = 0.21
RULE = "-" * 78


def head(t):
    print("\n" + RULE)
    print(t)
    print(RULE)


def safe(label, fn):
    try:
        fn()
    except Exception:
        print(f"  [FAILED] {label}")
        for line in traceback.format_exc().strip().splitlines()[-4:]:
            print(f"    {line}")


# ----------------------------------------------------------------------
head("1. Generator's declared mix")


def _declared():
    from gmppt.scenarios import GEOMETRY_MIX, HELDOUT_FRACTION

    for k, v in GEOMETRY_MIX.items():
        print(f"  {k:<20} {100 * v:>6.1f}%")
    print(f"  held-out fraction    {100 * HELDOUT_FRACTION:>6.1f}%")


safe("declared", _declared)


# ----------------------------------------------------------------------
head("2. Feature table schema")

df = None


def _schema():
    global df
    df = pd.read_parquet(FEATURES)
    print(f"  file  : {FEATURES.relative_to(ROOT)}")
    print(f"  shape : {df.shape[0]} rows x {df.shape[1]} cols\n")
    for c in df.columns:
        s = df[c]
        if s.dtype == object or str(s.dtype).startswith("str") or s.dtype.name == "category":
            n = s.nunique()
            extra = f"{n} unique" + (f"  {sorted(s.unique().tolist())}" if n <= 8 else "")
        else:
            extra = f"min={s.min():.4g}  max={s.max():.4g}"
        print(f"    {c:<22} {str(s.dtype):<12} {extra}")


safe("schema", _schema)


# ----------------------------------------------------------------------
head("3. Curve array")


def _curves():
    a = np.load(CURVES, mmap_mode="r")
    print(f"  file  : {CURVES.relative_to(ROOT)}")
    print(f"  shape : {a.shape}   dtype {a.dtype}")
    print(f"  rows match feature table: {a.shape[0] == (0 if df is None else len(df))}")


safe("curves", _curves)


# ----------------------------------------------------------------------
head("4. Geometry composition (open item 13)")


def _geom():
    if df is None:
        print("  Skipped — feature table not loaded.")
        return

    gcol = next((c for c in df.columns if "geom" in c.lower()), None)
    if gcol is None:
        print("  No geometry column. Columns are listed in section 2.")
        return
    print(f"  geometry column: '{gcol}'")

    scol = next((c for c in df.columns if c.lower() in ("split", "set", "fold")), None)
    total = len(df)

    print(f"\n  {'geometry':<20}{'count':>9}{'share %':>10}")
    counts = df[gcol].value_counts()
    for name in counts.index:
        c = int(counts[name])
        print(f"  {str(name):<20}{c:>9}{100.0 * c / total:>10.1f}")

    if scol:
        print(f"\n  By split ('{scol}') — shares within each split")
        tab = pd.crosstab(df[scol], df[gcol], normalize="index") * 100
        print(tab.round(1).to_string())
        print(f"\n  Row counts per split x geometry")
        print(pd.crosstab(df[scol], df[gcol]).to_string())
    else:
        print("\n  No split column found; per-split shares not computed.")

    # ------------------------------------------------------------------
    print("\n  Reconciliation with the P3.7 pooled held-out figure")
    shares = {str(k): float(v) / total for k, v in counts.items()}
    pooled = sum(shares.get(g, 0.0) * loss for g, loss in LOGGED_PER_GEOM.items())
    print(f"    per-geometry losses (logged) : {LOGGED_PER_GEOM}")
    print(f"    weighted by measured shares  : {pooled:.3f} %")
    print(f"    pooled figure logged at P3.7 : {LOGGED_POOLED:.3f} %")
    if abs(pooled - LOGGED_POOLED) <= 0.05:
        print("    >>> CONSISTENT. The pooled figure was correctly weighted;")
        print("    >>> only the geometry labels in the P3.6 log were permuted.")
    else:
        print("    >>> INCONSISTENT. Do not quote the pooled figure until resolved.")

    # ------------------------------------------------------------------
    print("\n  Viability of leave-one-geometry-out")
    for name in counts.index:
        held = int(counts[name])
        print(f"    hold out {str(name):<18} train on {total - held:>6} rows, score on {held:>6}")


safe("geom", _geom)


head("Done")
print("  Paste sections 2 and 4 back. Section 2 fixes the column names the")
print("  holdout runner needs; section 4 states whether any figure must move.")