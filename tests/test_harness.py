"""Tests for the Phase 2 comparison harness.

RUN:   python -m pytest tests/test_harness.py -v

These are unit tests on the harness mechanics, not on PV physics. They use a
synthetic two-peak curve so they run in milliseconds and do not depend on the
CEC database or pvlib.
"""

import numpy as np
import pytest

from gmppt.harness import Context, _peak_regions, metrics


def _synthetic():
    v = np.linspace(0, 40, 401)
    p = 100 * np.exp(-((v - 12) ** 2) / 8) + 160 * np.exp(-((v - 30) ** 2) / 10)
    return v, p


def test_two_peaks_detected():
    v, p = _synthetic()
    regions = _peak_regions(v, p)
    assert regions.max() == 1, "synthetic curve must split into two regions"


def test_single_peak_is_one_region():
    v = np.linspace(0, 40, 401)
    p = 160 * np.exp(-((v - 30) ** 2) / 10)
    assert _peak_regions(v, p).max() == 0


def test_probe_is_counted():
    v, p = _synthetic()
    ctx = Context(v_oc=40.0, i_sc=None, module="m", geometry="g",
                  rng=np.random.default_rng(0), _V=v, _P=p)
    for x in (10.0, 20.0, 30.0):
        ctx.probe(x)
    assert ctx.n_probes == 3


def test_probe_returns_power_at_voltage():
    v, p = _synthetic()
    ctx = Context(v_oc=40.0, i_sc=None, module="m", geometry="g",
                  rng=np.random.default_rng(0), _V=v, _P=p)
    assert ctx.probe(30.0) == pytest.approx(160.0, rel=0.02)


def test_context_hides_the_ceiling():
    """The method-facing contract must not expose the answer."""
    public = {f for f in dir(Context) if not f.startswith("_")}
    assert not {"p_gmpp", "v_gmpp", "ceiling", "k_true"} & public


def test_metrics_empty_set():
    assert metrics([])["n"] == 0
