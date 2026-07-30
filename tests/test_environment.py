"""Environment sanity: the pins hold and the fixed protocol constants are set."""
import numpy, scipy, pandas, pvlib, pyarrow
from gmppt import config


def test_pinned_versions():
    expected = {
        numpy: "2.4.4", scipy: "1.17.1", pandas: "3.0.2",
        pvlib: "0.15.2", pyarrow: "25.0.0",
    }
    for mod, ver in expected.items():
        assert mod.__version__ == ver, f"{mod.__name__} {mod.__version__} != {ver}"


def test_fixed_protocol_constants():
    # Section 9.10: these three are set once and never changed.
    assert config.CONVERGENCE_BAND_FRAC == 0.01
    assert config.RESIDENCE_PERIODS == 20
    assert config.FALLBACK_MARGIN_FRAC == 0.01


def test_seed_determinism():
    assert config.seed_for("scenario_gen") == config.seed_for("scenario_gen")
    assert config.seed_for("scenario_gen") != config.seed_for("module_split")


def test_paths_exist():
    assert config.PROJECT_ROOT.exists()
    assert config.RESULTS_DIR.exists()
