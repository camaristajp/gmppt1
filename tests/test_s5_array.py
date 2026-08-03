"""S5 checkpoints as tests: array generalisation (modules -> string)."""
import numpy as np

from gmppt import config, device
from gmppt.device import ModuleParams


def _mp():
    return ModuleParams.from_cec(config.CANONICAL_DEMO_MODULE)


def test_n1_reduction_equals_module():
    """A string of one module must reproduce module_iv exactly."""
    mp = _mp()
    uniform = [1000.0] * config.N_SUBSTRINGS
    m = device.analyse(device.module_iv(mp, uniform, 25.0))["gmpp"]
    s = device.analyse(device.string_iv(mp, [uniform], 25.0))["gmpp"]
    assert abs(m["P"] - s["P"]) < 1e-6
    assert abs(m["V"] - s["V"]) < 1e-6


def test_series_scaling_triples_voltage_and_power():
    """Three identical unshaded modules give 3x V, 3x P, same I."""
    mp = _mp()
    uniform = [1000.0] * config.N_SUBSTRINGS
    one = device.analyse(device.module_iv(mp, uniform, 25.0))["gmpp"]
    three = device.analyse(device.string_iv(mp, [uniform] * 3, 25.0))["gmpp"]
    assert abs(three["V"] / one["V"] - 3.0) < 1e-3
    assert abs(three["P"] / one["P"] - 3.0) < 1e-3
    assert abs(three["I"] / one["I"] - 1.0) < 1e-3


def test_shaded_string_is_multipeak():
    """Modules at different irradiance produce a multi-peak string curve."""
    mp = _mp()
    patterns = [[1000.0]*config.N_SUBSTRINGS,
                [700.0]*config.N_SUBSTRINGS,
                [400.0]*config.N_SUBSTRINGS]
    c = device.string_iv(mp, patterns, 25.0)
    a = device.analyse(c)
    assert a["n_peaks"] == 3
    # module short-circuit currents scale with irradiance
    ratios = sorted(c["isc_modules"] / c["isc_modules"].max(), reverse=True)
    assert np.allclose(ratios, [1.0, 0.70, 0.40], atol=0.02)
