"""Smoke test: the viz style loads and figures are written to disk."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from gmppt import viz


def test_save_fig_writes_png(tmp_path=None):
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2], [0, 1, 4])
    path = viz.save_fig(fig, "_smoke_test")
    assert path.exists() and path.suffix == ".png"
    path.unlink()  # clean up the smoke artefact


def test_fig_dir_exists():
    assert viz.FIG_DIR.exists()
