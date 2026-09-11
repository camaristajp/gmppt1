"""
p8_api_probe_and_geometry_audit.py
Destination:  C:\\Users\\user\\gmppt\\phase3\\p8_api_probe_and_geometry_audit.py
Run from:     C:\\Users\\user\\gmppt>  python phase3\\p8_api_probe_and_geometry_audit.py

Two jobs, no simulation, no training, no writes.

  A. Print the API surface of the gmppt package so the geometry-holdout runner
     can be written against real signatures rather than guessed ones.
  B. Close open item 13 — count the geometry label directly on the built
     dataset, with names attached, and reconcile against the P3.6 log.

Read-only. Nothing is modified. Every section is wrapped so a failure in one
prints a diagnostic and the rest still runs.
"""

import inspect
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

LOGGED_SHARES = {"target": (40.0, 15.0, 45.0), "reported": (40.4, 14.9, 44.7)}
RULE = "-" * 78


def head(title):
    print("\n" + RULE)
    print(title)
    print(RULE)


def safe(label, fn):
    try:
        fn()
    except Exception:
        print(f"  [FAILED] {label}")
        for line in traceback.format_exc().strip().splitlines()[-3:]:
            print(f"    {line}")


# ----------------------------------------------------------------------
# A1. environment
# ----------------------------------------------------------------------
head("A1. Environment")
print(f"  repo root      : {ROOT}")
print(f"  python         : {sys.version.split()[0]}")
print(f"  cwd            : {os.getcwd()}")
for mod in ("numpy", "pandas", "sklearn", "pvlib"):
    try:
        m = __import__(mod)
        print(f"  {mod:<15}: {getattr(m, '__version__', '?')}")
    except Exception as e:
        print(f"  {mod:<15}: NOT IMPORTABLE ({e})")


# ----------------------------------------------------------------------
# A2. package layout
# ----------------------------------------------------------------------
head("A2. Package layout")


def _layout():
    for sub in ("gmppt", "phase2", "phase3", "results", "data"):
        d = ROOT / sub
        if not d.is_dir():
            print(f"  {sub}/ : ABSENT")
            continue
        names = sorted(p.name for p in d.iterdir() if p.is_file())
        print(f"  {sub}/ : {len(names)} files")
        for n in names[:25]:
            print(f"      {n}")
        if len(names) > 25:
            print(f"      ... and {len(names) - 25} more")


safe("layout", _layout)


# ----------------------------------------------------------------------
# A3. public API of each module
# ----------------------------------------------------------------------
head("A3. Public API surface")

MODULES = [
    "gmppt.dataset",
    "gmppt.features",
    "gmppt.model",
    "gmppt.scenarios",
    "gmppt.device",
    "gmppt.tracking",
    "gmppt.trackers",
    "gmppt.hybrid",
]


def _api():
    import importlib

    for name in MODULES:
        try:
            mod = importlib.import_module(name)
        except Exception as e:
            print(f"\n  {name}: NOT IMPORTABLE ({type(e).__name__}: {e})")
            continue
        print(f"\n  {name}")
        consts, funcs, classes = [], [], []
        for attr in sorted(dir(mod)):
            if attr.startswith("_"):
                continue
            obj = getattr(mod, attr)
            if getattr(obj, "__module__", None) not in (name, None):
                continue
            if inspect.isclass(obj):
                classes.append((attr, obj))
            elif inspect.isfunction(obj):
                funcs.append((attr, obj))
            elif isinstance(obj, (int, float, str, bool, tuple, list, dict)):
                consts.append((attr, obj))
        for attr, val in consts:
            r = repr(val)
            print(f"      const  {attr} = {r if len(r) <= 90 else r[:87] + '...'}")
        for attr, obj in funcs:
            try:
                sig = str(inspect.signature(obj))
            except Exception:
                sig = "(?)"
            print(f"      def    {attr}{sig}")
        for attr, obj in classes:
            try:
                sig = str(inspect.signature(obj))
            except Exception:
                sig = "(?)"
            print(f"      class  {attr}{sig}")
            for m in sorted(dir(obj)):
                if m.startswith("_"):
                    continue
                mo = getattr(obj, m, None)
                if inspect.isfunction(mo):
                    try:
                        ms = str(inspect.signature(mo))
                    except Exception:
                        ms = "(?)"
                    print(f"          .{m}{ms}")


safe("api", _api)


# ----------------------------------------------------------------------
# B1. locate the built dataset
# ----------------------------------------------------------------------
head("B1. Built dataset artefacts")

CANDIDATE_DIRS = [ROOT / "results", ROOT / "data", ROOT / "results" / "phase3", ROOT]
EXTS = {".npz", ".npy", ".parquet", ".pkl", ".pickle", ".joblib", ".csv", ".h5", ".feather"}

found = []


def _find():
    seen = set()
    for d in CANDIDATE_DIRS:
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix.lower() in EXTS and p not in seen:
                seen.add(p)
                found.append(p)
    if not found:
        print("  No dataset artefacts found in results/, data/ or the repo root.")
        return
    for p in sorted(found, key=lambda q: q.stat().st_size, reverse=True)[:30]:
        mb = p.stat().st_size / 1e6
        print(f"  {mb:9.2f} MB   {p.relative_to(ROOT)}")


safe("find", _find)


# ----------------------------------------------------------------------
# B2. schema of the largest artefact
# ----------------------------------------------------------------------
head("B2. Schema of the largest artefact")


def _schema():
    if not found:
        print("  Skipped — nothing found in B1.")
        return
    p = max(found, key=lambda q: q.stat().st_size)
    print(f"  file: {p.relative_to(ROOT)}")
    suf = p.suffix.lower()

    if suf == ".npz":
        import numpy as np

        with np.load(p, allow_pickle=True) as z:
            for k in z.files:
                a = z[k]
                print(f"    key {k:<28} shape={a.shape} dtype={a.dtype}")
                if a.dtype.kind in "US" and a.size:
                    vals, counts = np.unique(a, return_counts=True)
                    if len(vals) <= 12:
                        print(f"        values: {dict(zip(vals.tolist(), counts.tolist()))}")
    elif suf in (".parquet", ".feather", ".csv"):
        import pandas as pd

        df = pd.read_parquet(p) if suf == ".parquet" else (
            pd.read_feather(p) if suf == ".feather" else pd.read_csv(p, nrows=200000)
        )
        print(f"    shape: {df.shape}")
        for c in df.columns:
            print(f"    col {c:<30} {df[c].dtype}")
    else:
        import pickle

        with open(p, "rb") as fh:
            obj = pickle.load(fh)
        print(f"    type: {type(obj)}")
        if isinstance(obj, dict):
            for k, v in obj.items():
                print(f"    key {str(k):<28} {type(v).__name__} "
                      f"{getattr(v, 'shape', getattr(v, '__len__', lambda: '?')())}")


safe("schema", _schema)


# ----------------------------------------------------------------------
# B3. geometry audit — open item 13
# ----------------------------------------------------------------------
head("B3. Geometry audit (open item 13)")


def _geometry():
    import numpy as np

    if not found:
        print("  Skipped — no dataset artefact located.")
        return

    tally = None
    source = None
    for p in sorted(found, key=lambda q: q.stat().st_size, reverse=True):
        if p.suffix.lower() != ".npz":
            continue
        with np.load(p, allow_pickle=True) as z:
            for k in z.files:
                if "geom" not in k.lower():
                    continue
                a = z[k]
                vals, counts = np.unique(a.astype(str), return_counts=True)
                tally = dict(zip(vals.tolist(), counts.tolist()))
                source = f"{p.relative_to(ROOT)}::{k}"
                break
        if tally:
            break

    if tally is None:
        print("  No column or key containing 'geom' was found.")
        print("  ACTION: paste the B2 schema block back and the audit will be re-aimed.")
        return

    total = sum(tally.values())
    print(f"  source : {source}")
    print(f"  total  : {total} scenarios\n")
    print(f"  {'geometry label':<24}{'count':>10}{'share %':>10}")
    for name in sorted(tally):
        c = tally[name]
        print(f"  {name:<24}{c:>10}{100.0 * c / total:>10.1f}")

    print("\n  Reconciliation against the P3.6 log")
    print(f"    logged targets  (uniform / sub / whole) : {LOGGED_SHARES['target']}")
    print(f"    logged reported (uniform / sub / whole) : {LOGGED_SHARES['reported']}")
    print("    measured above is authoritative; the log line is the one under suspicion.")

    subs = [n for n in tally if "sub" in n.lower() and "whole" not in n.lower()]
    if subs:
        share = 100.0 * sum(tally[n] for n in subs) / total
        print(f"\n    sub-substring share (measured): {share:.1f}%")
        if abs(share - 14.9) > 3.0:
            print("    >>> DIVERGES from the logged 14.9%. Open item 13 is confirmed.")
            print("    >>> Any pooled all-geometry figure must be recomputed before use.")
        else:
            print("    >>> Consistent with the logged 14.9%. Open item 13 closes as a false alarm.")


safe("geometry", _geometry)


head("Done")
print("  Paste this entire output back. Sections A3 and B2 determine how the")
print("  leave-one-geometry-out runner is written; B3 determines whether it")
print("  needs to wait for a dataset rebuild.")