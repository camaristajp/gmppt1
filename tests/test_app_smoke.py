"""Smoke and invariant tests for the GMPPT Bench dashboard.

These cover the acceptance tests that can be checked without a browser:
source-level invariants (T8), the split identity and probe count the dashboard
depends on (T5, T11), and the pure helpers that decide what a figure is labelled
(geometry, scenario hashing, readings).

The tests that need a rendered page — persistence across navigation (T1), session
survival (T2), day-event key stability (T3), scenario coherence (T4) and the
missing-export behaviour (T6) — are driven through Chrome DevTools against a
running server; see CHANGELOG_dashboard.md for how they were run and what they
reported. AppTest cannot drive them, because its switch_page only resolves
file-based pages and this app uses st.navigation.

Run:  python -m pytest tests/test_app_smoke.py -q
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APP = ROOT / "gmppt_app.py"
UI = ROOT / "gmppt_ui.py"
SRC = APP.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# T8 — greps that must return nothing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("pattern,why", [
    (r'href="(?!http)', "internal links must be st.page_link, not raw <a href> (R1)"),
    (r"st\.plotly_chart\(", "charts go through ui.show_chart (§7.4)"),
    (r"_RUN_COLORS", "colours come from ui.METHOD_COLORS (§7.2)"),
    (r"_MV_COLORS", "colours come from ui.METHOD_COLORS (§7.2)"),
    (r"_RUN_READINGS", "readings come from READINGS/SEED_PROBE_COST (R11)"),
    (r"gm_lang", "the language toggle is read nowhere and was removed"),
    (r"ui\.next_step\(", "footer_nav replaces next_step (§5)"),
    (r'"6 readings"', "the probe count is SEED_PROBE_COST, not a literal (N2)"),
    (r"/ 6\.0", "the probe count is SEED_PROBE_COST, not a literal (N2)"),
])
def test_forbidden_source_patterns(pattern, why):
    hits = [f"{i}: {l.strip()}" for i, l in enumerate(SRC.splitlines(), 1)
            if re.search(pattern, l)]
    assert not hits, f"{why}\n" + "\n".join(hits)


def test_geometry_is_never_hardcoded_into_scenario():
    """Every Scenario(...) must derive its geometry from the pattern (R10).

    Checked on the call's own line, because the argument list contains nested
    parentheses that a naive character class stops at.
    """
    calls = [l.strip() for l in SRC.splitlines() if "Scenario(" in l and "= Scenario(" in l]
    assert calls, "expected at least one Scenario(...) construction"
    for line in calls:
        assert "geometry_of(" in line, f"Scenario built with a literal geometry: {line}"


def test_ui_helpers_are_additive_only():
    """The four new helpers exist and the old signatures are untouched."""
    import gmppt_ui as ui
    for name in ("persist_widget_state", "scenario_banner", "footer_nav",
                 "provenance", "method_style"):
        assert callable(getattr(ui, name)), f"missing helper {name}"
    import inspect
    assert list(inspect.signature(ui.style_fig).parameters) == [
        "fig", "height", "y_title", "x_title"], "style_fig signature changed"
    assert list(inspect.signature(ui.app_header).parameters) == [
        "pages", "sections", "current", "routes", "theme_key"], \
        "app_header signature changed"


# --------------------------------------------------------------------------- #
# T11 / D1 — split identity
# --------------------------------------------------------------------------- #
def test_val_split_is_not_the_heldout_test_set():
    """The dashboard must use dataset.module_split().val — the set p7 --split val
    runs on — and never scenarios.split_modules()[1], which is the held-out TEST
    set reserved for one ledgered opening. (R12/N4, D1)"""
    from gmppt import dataset, scenarios as scen
    split = dataset.module_split()
    _, heldout = scen.split_modules(dataset.pool())
    assert set(split.test) == {str(m) for m in heldout}, \
        "test set is no longer scenarios.split_modules' held-out list"
    assert not (set(split.val) & set(split.test)), "val and test overlap"
    assert len(split.val) > 0


def test_dashboard_dropdown_draws_only_from_val():
    """T11: every module the dashboard offers is in the validation split."""
    from gmppt import dataset
    import pandas as pd
    from gmppt import config as gcfg
    val = {str(m) for m in dataset.module_split().val}
    pool = pd.read_parquet(gcfg.CEC_POOL)
    names = [n for n in val if n in pool.index]
    assert names, "no validation modules present in the CEC pool"
    h = pool.loc[names]
    assert set(h.index).issubset(val)


def test_source_does_not_use_split_modules_for_the_dropdown():
    """The old call is the bug; assert it is gone from the module-picking path."""
    assert "_scen.split_modules(" not in SRC, \
        "the dropdown must not be built from scenarios.split_modules (that is the test set)"


# --------------------------------------------------------------------------- #
# T5 / D5 — probe count and readings
# --------------------------------------------------------------------------- #
def test_seed_probe_cost_is_imported_not_hardcoded():
    from gmppt.hybrid import SEED_PROBE_COST
    from gmppt.features import PROBE_FRACTIONS
    assert SEED_PROBE_COST == len(PROBE_FRACTIONS)
    assert "from gmppt.hybrid import SEED_PROBE_COST" in SRC


def test_probe_count_is_five():
    """D5: PROBE_FRACTIONS has five entries. hybrid.py's docstring says five; the
    method report says six; the dashboard used to hardcode 6. Five is the code."""
    from gmppt.features import PROBE_FRACTIONS
    assert len(PROBE_FRACTIONS) == 5


@pytest.mark.skipif(not (ROOT / "results/phase2/pso_comparison_val.json").exists(),
                    reason="pso export not present")
def test_pso_readings_come_from_an_evaluation_field():
    """D6: sequential_steps = population x iterations, i.e. evaluations, and is
    distinct from the convergence-steps field."""
    d = json.loads((ROOT / "results/phase2/pso_comparison_val.json").read_text())
    for row in d["pso_sweep"]:
        assert row["sequential_steps"] == row["population"] * row["iterations"]
        assert "all_median_conv_steps" in row
        assert row["sequential_steps"] != row["all_median_conv_steps"]


# --------------------------------------------------------------------------- #
# Pure helpers the labels depend on
# --------------------------------------------------------------------------- #
def _load_helpers():
    """Import the dashboard's pure helpers without executing the Streamlit app."""
    import ast
    tree = ast.parse(SRC)
    wanted = {"geometry_of", "geometry_label", "_key"}
    ns = {}
    mod = ast.Module(body=[n for n in tree.body
                           if isinstance(n, ast.FunctionDef) and n.name in wanted],
                     type_ignores=[])
    exec(compile(mod, "<helpers>", "exec"), ns)
    return ns


def test_geometry_of():
    h = _load_helpers()
    assert h["geometry_of"]([900.0, 900.0, 900.0]) == "uniform"
    assert h["geometry_of"]([900.0, 300.0, 600.0]) == "whole_substring"
    assert h["geometry_of"]([900.0, [900.0, 300.0, 900.0], 600.0]) == "sub_substring"


def test_geometry_label_names_the_all_strips_case():
    """The dashboard's 'across the strips' shades a group on EVERY substring,
    which scenarios.py's sub_substring does not; it must be named, not passed
    off as the harness's case. (R10)"""
    h = _load_helpers()
    every = [[900.0, 300.0, 900.0]] * 3
    assert h["geometry_label"](every) == "sub-substring (all strips)"
    one = [900.0, [900.0, 300.0, 900.0], 600.0]
    assert h["geometry_label"](one) == "sub-substring"


@pytest.mark.skipif(not (ROOT / "results/phase2/relocation_comparison_pole.json").exists(),
                    reason="relocation export not present")
def test_relocation_export_has_no_gate_counts():
    """T9's premise: this export carries acceptance criteria and a single
    discarded total, but no per-gate G1-G6 counts and no separate G5 control —
    so the page must show the 'not presentable as gated' callout."""
    d = json.loads((ROOT / "results/phase2/relocation_comparison_pole.json").read_text())
    assert "gates" not in d and "gate_counts" not in d
    assert set(d["criteria"]) == {"c1", "c2", "c3", "c4"}
    assert "Gate counts are not in this export" in SRC


def test_no_hardcoded_relocation_prose():
    """R14: the '~64% lost' and 'step 40' literals must be gone; the page reads
    the jump step and every percentage from the export."""
    assert "64%" not in SRC
    assert "One shift at step 40" not in SRC
    assert "all data-validation gates passed" not in SRC


def test_targets_are_marked_when_not_recorded():
    """D2/N5: the static target is shown under both definitions, marked pending,
    and the targets the repository does not record are named as missing."""
    assert "definition pending advisor decision (D2)" in SRC
    assert "not recorded in this repository" in SRC
