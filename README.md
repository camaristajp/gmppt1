# GMPPT — Conditional Peak-Voltage Coefficient (Phase 1)

Simulation code for the research plan *A Conditional Peak-Voltage Coefficient
for Model-Based Global MPPT in Module-Level Solar Optimizers* (rev 6).
This repository currently covers **Phase 1**: simulator construction, its
verification, coefficient characterisation, and the Gate A decision.

## Environment

Validated on Python 3.12, Linux. All dependencies are pinned; the study is
reproducible from a single master seed (`gmppt/config.py: MASTER_SEED`).

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"            # installs pinned deps + the gmppt package
pytest                             # runs all verification checkpoints as tests
```

`pip install -e .` puts the `gmppt` package on the path so scripts and tests can
`from gmppt import config`. `requirements.txt` mirrors the pins for environments
that prefer it; `requirements-lock.txt` is the full transitive freeze.

## Layout

```
gmppt/        package: config (paths, seeds, FIXED protocol constants)
scripts/      one runnable file per phase step (s1_, s2_, ...)
tests/        each verification checkpoint, re-runnable as a pytest test
results/      generated outputs + the verification log (regenerated from code)
```

## Reproducing Phase 1 so far

```bash
python scripts/s1_cec_characterisation.py   # CEC V_mp/V_oc spread (Section 4)
python scripts/s2_stc_verification.py        # single-diode STC, 3 sig figs
```

## Fixed protocol constants (Section 9.10)

Set once in `gmppt/config.py` and not changed after Phase 1 begins:
convergence band ±1 % of GMPP power, residence 20 switching periods,
fallback margin 1 % of operating power.

## Status

| step | what | state |
|---|---|---|
| S1 | CEC coefficient spread (no simulator) | PASS |
| S2 | single-diode STC verification | PASS |
| S3 | reverse-bias (Bishop) + bypass diodes | not started |
| S4 | published-shading reproduction | not started |
| S5–S8 | array generalisation, scenarios, GMPP labelling, Gate A | not started |

See `results/phase1_verification_log.md` for the detailed log, including the
documented CEC `I_sc`/`I_L_ref` convention and the temperature-coefficient
caveat.
