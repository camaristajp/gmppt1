"""S3 checkpoints as tests, driven directly off the gmppt.device package."""
import numpy as np
import pytest
from pvlib import pvsystem

from gmppt import config, device
from gmppt.device import ModuleParams, Breakdown, Bypass
import s3_reverse_bias_bypass as s3


@pytest.fixture(scope="module")
def mp():
    return ModuleParams.from_cec(s3.pick_demo_module())


def test_unshaded_composition_matches_direct_module(mp):
    """Three uniform substrings in series reproduce the single-diode module."""
    G, T = config.STC_IRRADIANCE, config.STC_TEMPERATURE
    p = pvsystem.calcparams_cec(G, T, mp.alpha_sc, mp.a_ref, mp.I_L_ref,
                                mp.I_o_ref, mp.R_sh_ref, mp.R_s, mp.Adjust,
                                EgRef=config.EG_REF, dEgdT=config.DEG_DT)
    direct = pvsystem.singlediode(*p)
    comp = device.analyse(device.module_iv(mp, [G, G, G], T))["gmpp"]
    # P_mp and V_mp within 0.1% (composition is exact up to grid resolution)
    assert abs(comp["P"] - direct["p_mp"]) / direct["p_mp"] < 1e-3
    assert abs(comp["V"] - direct["v_mp"]) / direct["v_mp"] < 1e-3


def test_three_distinct_irradiances_give_up_to_three_peaks(mp):
    a = device.analyse(device.module_iv(mp, [1000, 600, 300], 25.0))
    assert 1 <= a["n_peaks"] <= 3
    assert a["gmpp"]["P"] > 0


def test_shading_reduces_power_below_uniform(mp):
    uniform = device.analyse(device.module_iv(mp, [1000, 1000, 1000], 25.0))
    shaded = device.analyse(device.module_iv(mp, [1000, 600, 300], 25.0))
    assert shaded["gmpp"]["P"] < uniform["gmpp"]["P"]


def test_bypass_clamps_shaded_substring_near_minus_0p6V(mp):
    frac = 1.0 / config.N_SUBSTRINGS
    sub = device.scale_to_substring(mp, frac)
    v, i_elem = device.substring_element_iv(sub, 200.0, 25.0,
                                            Breakdown(), Bypass(temp_c=25.0))
    bright_isc = device.module_iv(
        mp, [1000, 1000, 1000], 25.0)["isc_substrings"][0]
    v_clamp = float(np.interp(bright_isc, i_elem[::-1], v[::-1]))
    assert -0.8 < v_clamp < -0.3


def test_gmpp_insensitive_to_avalanche_parameters(mp):
    off = device.analyse(device.module_iv(
        mp, [1000, 600, 300], 25.0, bd=Breakdown(factor=0.0)))["gmpp"]
    on = device.analyse(device.module_iv(
        mp, [1000, 600, 300], 25.0,
        bd=Breakdown(factor=2e-3, voltage=-15.0, exp=3.28)))["gmpp"]
    assert abs(on["P"] - off["P"]) / off["P"] < 5e-3
