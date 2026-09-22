"""
export_transition_dataset.py  --  write the generated relocation sequences to
                                  Parquet (dashboard playback + journal figures).

PLACE THIS FILE AT:   C:\\Users\\user\\gmppt\\phase2\\export_transition_dataset.py
                      NEW FILE.

RUN FROM THE REPO ROOT (C:\\Users\\user\\gmppt):
    python phase2\\export_transition_dataset.py --n 8

WHAT IT WRITES
    One row per (module, family, time-step) of the sun-driven shading sequences
    from transition.py -- the SAME generator the tracker comparison (p12) uses,
    so the dataset the dashboard plays back is the dataset the paper reports.
    Columns:
        module, family, step, local_time, elevation_deg, azimuth_deg,
        band_centre_xc, cloud_opacity, base_irradiance_w,
        irr_sub0..2 (per-substring irradiance, W/m^2),
        shade_frac_sub0..2 (fraction of each substring under the band),
        gmpp_v, gmpp_p, gmpp_region, n_peaks

    Written to Parquet (columnar, compact, dashboard-friendly). If no Parquet
    engine is installed it falls back to CSV and says so.

TIME-OF-DAY IS PHYSICAL
    local_time / elevation / azimuth come from pvlib.solarposition for the
    DECLARED synthetic site (Jeju reference). The shadow position (band_centre)
    is driven by that azimuth, so every row's shading follows the real sun.

"RANDOM SHADE", WHERE IT IS PHYSICALLY APPLICABLE
    Pole/structural shadows are geometric and DETERMINISTIC -> cloud_opacity = 1.
    Clouds genuinely fluctuate, so for the "cloud" family a SEEDED, smoothed
    random opacity in [OPACITY_MIN, 1.0] dims the overall irradiance (a passing
    cloud), while the BETWEEN-substring pattern that creates the peaks stays
    sun-driven. Seeded from config.seed_for, so the dataset is reproducible; the
    random part is labelled (the cloud_opacity column) and never touches the pole
    family. This keeps provenance clean: geometry is physical, cloud brightness
    is declared-stochastic.

SCOPE
    Validation modules, declared synthetic site (Jeju reference) -- travels with
    the data. All simulated.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gmppt import config, dataset, device  # noqa: E402
from gmppt.device import ModuleParams  # noqa: E402
from phase2.transition import (BASE_IRRADIANCE, N_SUB,  # noqa: E402
                               REFERENCE_DATE, TRANSITION_FAMILIES,
                               band_centre_from_azimuth, gmpp_region,
                               irradiances_for_step, solar_over_day,
                               substring_shade_fractions)

OUT = config.RESULTS_DIR / "phase2"

# Declared cloud-opacity random walk (cloud family only; pole stays 1.0).
OPACITY_MIN = 0.55
OPACITY_STEP_SD = 0.03      # per-step gaussian increment before clipping


def cloud_opacity_series(n: int, seed_tag: str = "cloud_opacity") -> np.ndarray:
    """Seeded, smoothed random overall-brightness series in [OPACITY_MIN, 1.0].

    A correlated walk, not white noise -- a passing cloud dims and clears
    smoothly. Deterministic given config.seed_for, so the dataset reproduces.
    """
    rng = np.random.default_rng(int(config.seed_for(seed_tag)) % 2**31)
    o = np.empty(n, float)
    cur = 1.0
    for i in range(n):
        cur = float(np.clip(cur + rng.normal(0.0, OPACITY_STEP_SD),
                            OPACITY_MIN, 1.0))
        o[i] = cur
    return o


def rows_for(module: str, family: str, temp_c: float = 25.0) -> list[dict]:
    """One row per time-step of a sun-driven sequence for (module, family)."""
    ss = float(TRANSITION_FAMILIES[family]["sample_seconds"])
    times, elev, az = solar_over_day(date=REFERENCE_DATE, sample_seconds=ss)
    xc = band_centre_from_azimuth(az)
    opacity = (cloud_opacity_series(len(xc)) if family == "cloud"
               else np.ones(len(xc)))
    mp = ModuleParams.from_cec(module)

    rows = []
    for i in range(len(xc)):
        shade = substring_shade_fractions(float(xc[i]))
        base_g = float(BASE_IRRADIANCE * opacity[i])
        irr = irradiances_for_step(base_g, shade)
        c = device.module_iv(mp, irr, temp_c,
                             n_substrings=N_SUB, bd=config.breakdown())
        a = device.analyse(c)
        V = np.asarray(c["V"], float)
        v_oc = float(V.max())
        v_gmpp = float(a["gmpp"]["V"])
        row = {"module": module, "family": family, "step": i,
               "local_time": str(times[i]),
               "elevation_deg": float(elev[i]), "azimuth_deg": float(az[i]),
               "band_centre_xc": float(xc[i]),
               "cloud_opacity": float(opacity[i]),
               "base_irradiance_w": base_g,
               "gmpp_v": v_gmpp, "gmpp_p": float(a["gmpp"]["P"]),
               "gmpp_region": gmpp_region(v_gmpp, v_oc),
               "n_peaks": int(a.get("n_peaks", 0))}
        for s in range(N_SUB):
            row[f"irr_sub{s}"] = float(irr[s])
            row[f"shade_frac_sub{s}"] = float(shade[s])
        rows.append(row)
    return rows


def write_table(df: pd.DataFrame, stem: Path) -> Path:
    """Write Parquet if an engine is available, else CSV. Return the path used."""
    pq = stem.with_suffix(".parquet")
    try:
        df.to_parquet(pq, index=False)
        return pq
    except Exception as e:                      # no pyarrow/fastparquet
        csv = stem.with_suffix(".csv")
        df.to_csv(csv, index=False)
        print(f"   (Parquet engine unavailable: {type(e).__name__}. Wrote CSV "
              f"instead. For Parquet: pip install pyarrow --break-system-packages)")
        return csv


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8,
                    help="number of validation modules to export")
    ap.add_argument("--families", nargs="+", default=list(TRANSITION_FAMILIES),
                    choices=list(TRANSITION_FAMILIES))
    args = ap.parse_args()

    print("export transition dataset  (sun-driven relocation sequences)")
    try:
        print("  " + config.provenance())
    except Exception:
        pass
    print("=" * 78)
    print(f"DECLARED SYNTHETIC site (Jeju reference), {REFERENCE_DATE}; "
          f"families {args.families}")
    print("time-of-day/elevation/azimuth are physical (pvlib); pole shade is")
    print("deterministic; cloud shade adds a SEEDED opacity walk (labelled).\n")

    split = dataset.module_split()
    modules = list(split.val)[:args.n]
    print(f"exporting {len(modules)} validation modules x {len(args.families)} "
          f"families ...")

    all_rows = []
    for mod in modules:
        for fam in args.families:
            all_rows.extend(rows_for(str(mod), fam))
    df = pd.DataFrame(all_rows)
    print(f"   {len(df)} rows, {df.shape[1]} columns")
    print(f"   relocation events (gmpp_region changes) per (module,family): "
          f"see gmpp_region column")

    OUT.mkdir(parents=True, exist_ok=True)
    stem = OUT / "transition_dataset"
    path = write_table(df, stem)
    print(f"\ndataset -> {path}")
    print("Columns: module, family, step, local_time, elevation_deg, "
          "azimuth_deg, band_centre_xc,")
    print("         cloud_opacity, base_irradiance_w, irr_sub0..2, "
          "shade_frac_sub0..2,")
    print("         gmpp_v, gmpp_p, gmpp_region, n_peaks")
    print("Validation modules; declared synthetic site (Jeju reference). "
          "All simulated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())