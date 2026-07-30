"""S1 checkpoint as a test: the CEC V_mp/V_oc spread reproduces Section 4.

Two populations are asserted separately:
  * the full catalogue (all technologies) reproduces the Section 4 headline;
  * the in-scope c-Si subset matches the frozen population constants in config,
    which every downstream step relies on.
"""
import s1_cec_characterisation as s1
from gmppt import config


def test_full_catalogue_reproduces_section4():
    df = s1.load_cec()
    _, stats = s1.characterise(df)
    assert stats["N"] == config.CEC_ROWS_EXPECTED == 21535
    assert round(stats["min"], 3) == 0.633
    assert round(stats["max"], 3) == 0.874
    assert round(stats["mean"], 3) == 0.810
    assert round(stats["sd"], 3) == 0.017
    assert round(stats["pct_within_0.01_of_0.80"], 1) == 40.3


def test_csi_subset_matches_frozen_population_constants():
    """The saved pool is c-Si only; its stats must match the config pins that
    downstream steps (canonical module, held-out splits) depend on."""
    df = s1.csi_subset(s1.load_cec())
    _, stats = s1.characterise(df)
    assert stats["N"] == config.CSI_POOL_N == 20946
    assert round(stats["mean"], 4) == config.CSI_COEFF_MEAN
    assert round(stats["sd"], 4) == config.CSI_COEFF_SD
    assert (round(stats["min"], 4), round(stats["max"], 4)) == config.CSI_COEFF_RANGE
