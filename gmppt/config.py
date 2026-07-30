"""
Central configuration for the GMPPT Phase 1 codebase.

Two kinds of constant live here:

1. FIXED PROTOCOL CONSTANTS (Section 9.10). These are "set here and not changed
   once Phase 1 begins." Changing them mid-study invalidates cross-phase
   comparison, so they live in exactly one place and are imported everywhere.

2. Reproducibility settings: the master seed and derived per-purpose seeds, and
   the project paths. Everything random in this project derives its seed from
   MASTER_SEED so a single number reproduces the entire study.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

# --------------------------------------------------------------------------
# Paths (resolved relative to the project root, independent of CWD)
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = PROJECT_ROOT / "results"
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)

CEC_POOL = RESULTS_DIR / "cec_pool.parquet"
VERIFICATION_LOG = RESULTS_DIR / "phase1_verification_log.md"

# --------------------------------------------------------------------------
# Reproducibility
# --------------------------------------------------------------------------
MASTER_SEED = 20260901  # study start month; arbitrary but recorded

def seed_for(purpose: str) -> int:
    """Deterministic per-purpose seed derived from the master seed.

    Using a named sub-seed (e.g. 'scenario_gen', 'module_split') keeps streams
    independent and reproducible without threading one global RNG through the
    whole codebase. Same MASTER_SEED + same purpose string -> same seed, always.
    """
    h = hashlib.sha256(f"{MASTER_SEED}:{purpose}".encode()).hexdigest()
    return int(h[:8], 16)

# --------------------------------------------------------------------------
# FIXED PROTOCOL CONSTANTS (Section 9.10) -- do not change after Phase 1 begins
# --------------------------------------------------------------------------
CONVERGENCE_BAND_FRAC = 0.01   # +/-1% of global-peak power (convergence band)
RESIDENCE_PERIODS = 20         # consecutive switching periods inside the band
FALLBACK_MARGIN_FRAC = 0.01    # fallback margin: 1% of current operating power

# --------------------------------------------------------------------------
# Standard test conditions and the study's operating grid (Section 4)
# --------------------------------------------------------------------------
STC_IRRADIANCE = 1000.0        # W/m^2
STC_TEMPERATURE = 25.0         # deg C
TEMPERATURES_C = (25.0, 45.0, 60.0)          # Section 4 temperature set
IRRADIANCE_RANGE = (100.0, 1000.0)           # W/m^2, per-substring range

# Fractional-Voc coefficients
ALPHA_FIXED = 0.80             # the conventional constant (all baselines)
ALPHA_RECAL_PRELIM = 0.87      # Section 4 recalibrated constant (indicative)

# CEC single-diode bandgap defaults (pvlib calcparams_cec)
EG_REF = 1.121                 # eV
DEG_DT = -0.0002677            # eV/K

# Module architecture in scope (Section 8.1)
N_SUBSTRINGS = 3               # conventional full-cell c-Si, three bypass diodes
CSI_TECHNOLOGIES = ("Mono-c-Si", "Multi-c-Si")

# Verification tolerance
STC_SIG_FIGS = 3               # datasheet reproduction requirement (Section 9.2)
