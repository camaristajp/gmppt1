"""Scenario page physics wiring: the series path is the validated string_iv,
the parallel path is the additive array_iv, and both reduce to the existing
module_iv in their N = 1 special cases. (Brief §22, §25, T2–T6, T12.)

Run:  python -m pytest tests/test_scenario_physics.py -q
"""
from __future__ import annotations

import numpy as np
import pytest

from gmppt import config, device
from gmppt.device import ModuleParams

N = config.N_SUBSTRINGS
T = 43.0


def _mp():
    return ModuleParams.from_cec(config.CANONICAL_DEMO_MODULE)


def _uniform(g=1000.0):
    return [float(g)] * N


def _sorted(c):
    o = np.argsort(c["V"])
    return c["V"][o], c["I"][o], c["P"][o]


# --------------------------------------------------------------------------- #
# T2 / T3 — one module through module_iv and through string_iv are the same
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("irr", [_uniform(), [910.0, 300.0, 600.0], [800.0, 800.0, 200.0]])
def test_T3_one_module_string_equals_module(irr):
    mp = _mp()
    m = device.module_iv(mp, irr, T, bd=config.breakdown())
    s = device.string_iv(mp, [irr], T, bd=config.breakdown())
    assert np.array_equal(m["I"], s["I"]) and np.allclose(m["V"], s["V"], atol=1e-9)
    am, as_ = device.analyse(m), device.analyse(s)
    for k in ("V", "I", "P"):
        assert abs(am["gmpp"][k] - as_["gmpp"][k]) < 1e-9, k
    assert am["n_peaks"] == as_["n_peaks"]


def test_T2_default_one_panel_output_is_module_iv():
    """The Scenario page's 1S×1P default draws the selected panel with
    module_iv exactly as the pre-revision page did (same call, same args)."""
    import re
    src = open("gmppt_app.py", encoding="utf-8").read()
    fn = src.split("def _sim(")[1].split("\ndef ")[0]
    assert "_eng.module_iv(mp, irr, T, bd=_gcfg.breakdown())" in fn
    assert re.search(r"det = _sim\(name, _key\(sel_irr\), T\)", src), \
        "the selected panel's curve still comes from _sim -> module_iv"


# --------------------------------------------------------------------------- #
# T4 — a one-string array is the string, exactly
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("string", [[_uniform()], [_uniform(), [910.0, 300.0, 600.0]],
                                    [[700.0] * N, [1000.0] * N, [400.0] * N]])
def test_T4_one_string_array_equals_string(string):
    mp = _mp()
    s = device.string_iv(mp, string, T, bd=config.breakdown())
    a = device.array_iv(mp, [string], T, bd=config.breakdown())
    vs, is_, ps = _sorted(s)
    assert np.allclose(a["V"], vs) and np.allclose(a["I"], is_) and np.allclose(a["P"], ps)
    ga, gs = device.analyse(a)["gmpp"], device.analyse(s)["gmpp"]
    for k in ("V", "I", "P"):
        assert abs(ga[k] - gs[k]) < 1e-9, k
    assert device.analyse(a)["n_peaks"] == device.analyse(s)["n_peaks"]
    assert a["n_strings"] == 1 and a["blocking_diodes"] is True


# --------------------------------------------------------------------------- #
# T5 — two identical strings: 2x current, 2x power, same V_mp
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n_series", [1, 3])
def test_T5_two_identical_strings_double_current_and_power(n_series):
    mp = _mp()
    string = [_uniform()] * n_series
    s = device.analyse(device.string_iv(mp, string, T, bd=config.breakdown()))["gmpp"]
    a_curve = device.array_iv(mp, [string, string], T, bd=config.breakdown())
    a = device.analyse(a_curve)["gmpp"]
    assert abs(a["P"] / s["P"] - 2.0) < 5e-3, a["P"] / s["P"]
    assert abs(a["I"] / s["I"] - 2.0) < 5e-3, a["I"] / s["I"]
    assert abs(a["V"] - s["V"]) < 0.02 * s["V"], (a["V"], s["V"])
    # the whole curve, not just the peak: I_array(V) = 2 I_string(V) on the shared grid
    vs, is_, _ = _sorted(device.string_iv(mp, string, T, bd=config.breakdown()))
    i2 = 2 * np.interp(a_curve["V"], vs, is_, right=0.0)
    m = a_curve["V"] < 0.98 * vs.max()          # away from the knee at V_oc
    assert np.allclose(a_curve["I"][m], i2[m], rtol=5e-3, atol=1e-3)


# --------------------------------------------------------------------------- #
# T6 — blocking: a weak string can never subtract from a healthy one
# --------------------------------------------------------------------------- #
def test_T6_blocking_diodes_protect_the_healthy_string():
    mp = _mp()
    healthy = [_uniform()] * 2
    shaded = [[150.0] * N, [150.0, 100.0, 150.0]]
    p_alone = device.analyse(device.string_iv(mp, healthy, T, bd=config.breakdown()))["gmpp"]["P"]
    arr = device.array_iv(mp, [healthy, shaded], T, bd=config.breakdown(), blocking_diodes=True)
    p_arr = device.analyse(arr)["gmpp"]["P"]
    assert p_arr >= p_alone - 1e-6, (p_arr, p_alone)
    assert (arr["I"] >= 0).all(), "no string contribution is ever negative"
    # above the weak string's V_oc the array current equals the healthy string alone
    vs, is_, _ = _sorted(device.string_iv(mp, healthy, T, bd=config.breakdown()))
    voc_weak = min(arr["voc_strings"])
    m = arr["V"] > voc_weak + 0.5
    assert m.any()
    assert np.allclose(arr["I"][m], np.interp(arr["V"][m], vs, is_, right=0.0), rtol=5e-3, atol=1e-3)


def test_T6_unprotected_case_is_refused_not_faked():
    """blocking_diodes=False is the explicitly unprotected comparison case. The
    engine has no forward-conduction branch above V_oc, so reverse current
    cannot be computed; the function must say so rather than return the
    protected result under another name."""
    mp = _mp()
    with pytest.raises(NotImplementedError) as ex:
        device.array_iv(mp, [[_uniform()], [[150.0] * N]], T, bd=config.breakdown(),
                        blocking_diodes=False)
    assert "V_oc" in str(ex.value) and "unprotected" in str(ex.value)


# --------------------------------------------------------------------------- #
# T12 — identical unshaded system: per-panel optimisers == one shared tracker
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n_series,n_parallel", [(1, 1), (2, 1), (1, 2), (3, 2)])
def test_T12_unshaded_system_optimised_equals_shared(n_series, n_parallel):
    mp = _mp()
    one = device.analyse(device.module_iv(mp, _uniform(), T, bd=config.breakdown()))["gmpp"]["P"]
    optimised = one * n_series * n_parallel
    strings = [[_uniform()] * n_series] * n_parallel
    shared = device.analyse(device.array_iv(mp, strings, T, bd=config.breakdown()))["gmpp"]["P"]
    assert abs(shared / optimised - 1.0) < 5e-3, (shared, optimised)


def test_array_iv_shape_is_what_analyse_expects():
    mp = _mp()
    a = device.array_iv(mp, [[_uniform()], [[500.0] * N]], T, bd=config.breakdown())
    assert set(a) >= {"I", "V", "P", "voc_strings", "isc_strings", "n_strings"}
    assert np.all(np.diff(a["V"]) > 0), "ascending voltage grid"
    r = device.analyse(a)
    assert r["n_peaks"] >= 1 and r["gmpp"]["P"] > 0


def test_existing_device_behaviour_untouched():
    """The additive change must leave every existing entry point as it was."""
    import inspect
    for fn in ("module_iv", "string_iv", "analyse", "substring_element_iv",
               "substring_element_iv_subshaded", "scale_to_substring"):
        assert callable(getattr(device, fn))
    sig = inspect.signature(device.string_iv)
    assert list(sig.parameters) == ["mp", "module_irradiances", "T", "n_substrings", "bd", "bp", "n_points"]
    sig = inspect.signature(device.array_iv)
    assert list(sig.parameters) == ["mp", "string_irradiances", "T", "n_substrings", "bd", "bp",
                                    "blocking_diodes", "n_points"]
