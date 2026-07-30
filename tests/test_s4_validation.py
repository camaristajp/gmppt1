"""S4 checkpoints as tests: external validation of the simulator.

Leg 2 (single-diode vs Sandia measurement model) is the gated quantitative
check and needs no external dependency. Leg 1 (Basoglu structural) needs PySAM
for the parameter fit and is skipped if unavailable.
"""
import numpy as np
import pytest

import s4_external_validation as s4


def test_electrical_twins_exist():
    """CEC and Sandia share enough c-Si electrical twins to validate against."""
    pairs, _, _ = s4.find_electrical_twins()
    assert len(pairs) >= 50, f"only {len(pairs)} twin pairs; expected >= 50"


def test_single_diode_agrees_with_sandia_measurement():
    """Leg 2: single-diode form agrees with the measurement-derived Sandia model
    to a stated tolerance near STC and at operating heat."""
    ok, rows, npairs, nused = s4.leg2_sandia()
    assert nused >= 50
    # near-STC Pmp mean < 3%, operating-heat Pmp mean < 6%
    pmp25 = [r for r in rows if r[0] == 25 and r[1] == "Pmp"][0][2]
    pmp55 = [r for r in rows if r[0] == 55 and r[1] == "Pmp"][0][2]
    assert pmp25 < 3.0, f"near-STC Pmp divergence {pmp25:.1f}% >= 3%"
    assert pmp55 < 6.0, f"55C Pmp divergence {pmp55:.1f}% >= 6%"


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("PySAM") is None,
    reason="Basoglu parameter fit needs PySAM (optional dependency)")
def test_basoglu_multipeak_structure():
    """Leg 1: Basoglu's two cases reproduce the correct peak COUNT (structure),
    independent of the magnitude gap (his source is under-specified)."""
    from gmppt import device
    mp = s4.basoglu_module_params()
    for name, irr, theo, expt, exp_peaks in s4.BASOGLU_CASES:
        a = device.analyse(device.module_iv(mp, irr, 25.0))
        assert a["n_peaks"] == exp_peaks, (
            f"{name}: {a['n_peaks']} peaks, expected {exp_peaks}")
