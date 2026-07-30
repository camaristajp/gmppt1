"""S2 checkpoint as a test: gated STC quantities match datasheet to 3 sig figs.

Requires the CEC pool from S1. The test regenerates it if absent so the suite is
self-contained.
"""
import pandas as pd
import pytest
from pvlib import pvsystem

from gmppt import config
import s2_stc_verification as s2
import s1_cec_characterisation as s1


@pytest.fixture(scope="module")
def span():
    if not config.CEC_POOL.exists():
        df = s1.load_cec()
        ratio, _ = s1.characterise(df)
        df.assign(vmp_voc=ratio).to_parquet(config.CEC_POOL)
    pool = pd.read_parquet(config.CEC_POOL)
    full = pvsystem.retrieve_sam("CECMod").T
    for c in s2.CEC_PARAMS + ["beta_oc", "gamma_r"]:
        pool[c] = pd.to_numeric(full.loc[pool.index, c], errors="coerce")
    pool = pool.dropna(subset=s2.CEC_PARAMS + s2.TEMP_REF)
    return s2.pick_span(pool)


def test_gated_stc_quantities_match_to_3_sig_figs(span):
    """V_oc, V_mp, I_mp must match datasheet to 3 sig figs on every span module."""
    failures = []
    for idx, row in span.iterrows():
        stc, _ = s2.verify_module(row)
        for name, got, ref, rel, ok3, gated in stc:
            if gated and not ok3:
                failures.append((idx, name, got, ref, rel))
    assert not failures, f"3-sig-fig gate failures: {failures}"


def test_isc_bracketed_by_iscref_and_ilref(span):
    """Model I_sc must sit between datasheet I_sc_ref and I_L_ref: the offset from
    datasheet is explained by the CEC parameterisation (I_L_ref >= I_sc_ref plus
    series/shunt resistance), not a simulator error."""
    tol = 1e-3
    for idx, row in span.iterrows():
        stc, _ = s2.verify_module(row)
        isc = [r for r in stc if r[0] == "I_sc"][0][1]
        lo = row["I_sc_ref"] * (1 - tol)
        hi = row["I_L_ref"] * (1 + tol)
        assert lo <= isc <= hi, (
            f"{idx}: I_sc={isc:.4f} outside [{lo:.4f}, {hi:.4f}]")
