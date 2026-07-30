"""S1 checkpoint as a test: the CEC V_mp/V_oc spread reproduces Section 4."""
import s1_cec_characterisation as s1


def test_cec_spread_reproduces_section4():
    df = s1.load_cec()
    _, stats = s1.characterise(df)
    assert stats["N"] == 21535
    assert round(stats["min"], 3) == 0.633
    assert round(stats["max"], 3) == 0.874
    assert round(stats["mean"], 3) == 0.810
    assert round(stats["sd"], 3) == 0.017
    assert round(stats["pct_within_0.01_of_0.80"], 1) == 40.3
