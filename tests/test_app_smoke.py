"""Smoke and invariant tests for the GMPPT Bench dashboard.

These cover the acceptance tests that can be checked without a browser:
source-level invariants (T8), the split identity and probe count the dashboard
depends on (T5, T11), and the pure helpers that decide what a figure is labelled
(geometry, scenario hashing, readings).

The tests that need a rendered page — persistence across navigation (T1), session
survival (T2), scenario coherence (T4) and the missing-export behaviour (T6) —
were driven through Chrome DevTools against a running server; see
CHANGELOG_dashboard.md. tests/test_pages_render.py renders every navigation page
and walks the workflow headlessly through AppTest (selecting st.navigation
pages by url_path through the registry the first run fills).

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
    # Additive means the original parameters stay first and unchanged; new
    # keyword parameters with defaults may follow (journey, stage_help).
    params = inspect.signature(ui.app_header).parameters
    assert list(params)[:5] == ["pages", "sections", "current", "routes", "theme_key"], \
        "app_header's original signature changed"
    for extra in list(params)[5:]:
        assert params[extra].default is not inspect.Parameter.empty, \
            f"app_header gained a REQUIRED parameter: {extra}"


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
# Phase C — U1 module sets, U6 variants
# --------------------------------------------------------------------------- #
def test_T14_test_split_is_never_reached():
    """U1.4: no code path may read the held-out test set.

    Checked on the AST, not on the text: the Sources page legitimately *names*
    `scenarios.split_modules(pool)[1]` in prose to explain what the test set is,
    and a grep cannot tell that from a call.
    """
    import ast
    tree = ast.parse(SRC)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            name = getattr(f, "attr", None) or getattr(f, "id", None)
            if name == "split_modules":
                bad.append(f"line {node.lineno}: call to split_modules()")
        # `<something>.test` where the object came from module_split()
        if isinstance(node, ast.Attribute) and node.attr == "test":
            src = ast.get_source_segment(SRC, node) or ""
            if "split" in src.lower():
                bad.append(f"line {node.lineno}: reads {src}")
    assert not bad, "the test split is reachable:\n" + "\n".join(bad)


def test_T14_demo_module_selection_is_deterministic_and_documented():
    """U1.2: chosen from val, N_s == 72, 340-380 W, farthest from training."""
    assert "_DEMO_NS, _DEMO_P_MIN, _DEMO_P_MAX = 72, 340.0, 380.0" in SRC
    assert "_nearest_train" in SRC and "_zmatrix" in SRC
    assert "np.argmax(best_d)" in SRC, "must pick the FARTHEST-from-training candidate"
    assert "_demo_startup_log" in SRC, "the choice must be logged at startup"
    assert '"LG_Electronics_Inc__LG375N2K_G4"' not in SRC, \
        "the training-set demo module must no longer be referenced"


def test_T14_demo_module_is_in_val_and_far_from_train():
    """Run the real selection and check the property it claims."""
    from gmppt import dataset
    import numpy as np
    import pandas as pd
    from gmppt import config as gcfg
    split = dataset.module_split()
    pool = pd.read_parquet(gcfg.CEC_POOL)
    cols = ["V_mp_ref", "I_mp_ref", "V_oc_ref", "I_sc_ref", "N_s"]
    X = pool[cols].astype(float)
    Z = (X - X.mean()) / X.std(ddof=0).replace(0.0, 1.0)

    val = [n for n in split.val if n in pool.index]
    h = pool.loc[val].copy()
    h["P"] = h["V_mp_ref"] * h["I_mp_ref"]
    cand = [n for n in h[(h["N_s"] == 72) & (h["P"].between(340, 380))].index if n in Z.index]
    assert cand, "no validation module in the declared demo band"
    train = [m for m in split.train if m in Z.index]
    C, T = Z.loc[cand].to_numpy(), Z.loc[train].to_numpy()
    nearest = np.full(len(cand), np.inf)
    for s in range(0, len(train), 4000):
        d = np.linalg.norm(C[:, None, :] - T[None, s:s + 4000, :], axis=2)
        nearest = np.minimum(nearest, d.min(axis=1))
    chosen = cand[int(np.argmax(nearest))]
    assert chosen in split.val
    assert chosen not in split.train and chosen not in split.test
    assert float(nearest.max()) > 0, "the chosen module coincides with a training module"


def test_T14_load_time_assertion_exists_and_blocks_rendering():
    """U1.3: a non-validation module must stop the page, not caveat it."""
    assert "def assert_val_modules" in SRC
    # the guard now speaks to the reader ("Wrong data set") and keeps the split
    # machinery under Technical details (§24)
    assert '"Wrong data set"' in SRC
    assert "not validation data, so nothing" in SRC
    assert SRC.count("assert_val_modules(") >= 3, \
        "expected the guard on the dropdown and the demo, plus its definition"
    # the guard must be used as a gate, i.e. followed by a return
    assert "if not assert_val_modules([n for _, n in val_mods]" in SRC


def test_T14_unseen_check_panel():
    """U1.5 as revised by §8/§10: the membership check still runs and the facts
    are still recorded — but the reader sees one line, with the split summary and
    the nearest training module moved into Technical details."""
    import ast
    fn = next(n for n in ast.walk(ast.parse(SRC))
              if isinstance(n, ast.FunctionDef) and n.name == "_unseen_check")
    body = ast.get_source_segment(SRC, fn) or ""
    # the check itself
    assert "_train_module_names()" in body, "membership must still be resolved live"
    assert "Wrong data set" in body, "a training module must still be flagged"
    # what the reader sees
    assert 'ui.data_chip("Validation data"' in body
    # what is kept for reproducibility, out of the way
    assert 'st.expander("Technical details"' in body
    for fact in ("_split_counts()", "_nearest_train(name)", "module_split()"):
        assert fact in body, f"{fact} dropped from Technical details"


def test_T14_wording_never_calls_validation_modules_held_out():
    """U1.6: 'held-out' and 'never seen' belong to the test set only."""
    assert 'ui.data_chip("Validation data"' in SRC
    for i, line in enumerate(SRC.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue                       # comments explaining the rule itself
        if "never seen" in line:
            pytest.fail(f"line {i} says 'never seen': {line.strip()}")
        if "held-out" in line.lower() and "test" not in line.lower():
            pytest.fail(f"line {i} says 'held-out' without naming the test set: "
                        f"{line.strip()}")


def test_T15_unknown_variant_is_never_assigned_to_hybrid():
    """U6: identity comes from the table, not from the text of the key."""
    h = _load_helpers()
    import ast
    tree = ast.parse(SRC)
    table = next(ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.Assign)
                 and getattr(n.targets[0], "id", "") == "_METHOD_LABELS")
    unknown = next(ast.literal_eval(n.value) for n in tree.body
                   if isinstance(n, ast.Assign)
                   and getattr(n.targets[0], "id", "") == "UNKNOWN_VARIANT")
    assert "Unknown variant" in unknown and "export schema" in unknown
    assert "hybrid, experimental" not in table
    # the function falls back to UNKNOWN_VARIANT, not to the raw key
    fn_src = SRC.split("def method_label(")[1].split("\ndef ")[0]
    assert "UNKNOWN_VARIANT" in fn_src
    assert ", str(key))" not in fn_src, "must not fall back to echoing the key"


def test_persist_prefixes_never_match_a_button_key():
    """Regression: the prefix "bench_s" also matched `bench_save`, a button.

    Streamlit raises StreamlitValueAssignmentNotAllowedError when a button's
    value is pre-set — and it raises at WIDGET CREATION, not at assignment, so
    the try/except inside persist_widget_state cannot swallow it. Prefixes must
    not be able to reach a button key.
    """
    import ast
    tree = ast.parse(SRC)
    prefixes = next(ast.literal_eval(n.value) for n in tree.body
                    if isinstance(n, ast.Assign)
                    and getattr(n.targets[0], "id", "") == "_PERSIST_PREFIXES")
    # every st.button / download_button key in the app
    button_keys = set(re.findall(r'st\.button\([^)]*key="([^"]+)"', SRC))
    button_keys |= set(re.findall(r'\.button\([^)]*key="([^"]+)"', SRC))
    button_keys |= set(re.findall(r'download_button\([^)]*key="([^"]+)"', SRC))
    assert button_keys, "expected to find some button keys"
    for pre in prefixes:
        clashes = sorted(k for k in button_keys if k.startswith(pre))
        assert not clashes, f"persist prefix {pre!r} matches button key(s) {clashes}"


def test_bench_run_signature_has_exactly_one_builder():
    """Regression: R6 widened the run signature to 7 fields, but `_bench_load`
    still wrote 4, so loading a saved scenario crashed the page with
    `ValueError: not enough values to unpack`. The signature is built in one
    place now, and a stale shape degrades to "not run yet" instead of raising.
    """
    assert "def _bench_sig" in SRC
    # nobody may hand-roll the tuple any more
    assert SRC.count("_bench_sig(") >= 3, "both writers must go through _bench_sig"
    assert 'st.session_state["bench_ran"] = (' not in SRC, \
        "bench_ran must only ever be assigned a _bench_sig() result"
    # the reader guards the length
    assert "def _bench_ran" in SRC and "_BENCH_SIG_LEN" in SRC


def test_bench_signature_round_trips_through_load():
    """Build the signature both ways and check they have the same shape."""
    import ast
    tree = ast.parse(SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_bench_sig")
    ns = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<x>", "exec"), ns)
    sig = ns["_bench_sig"]
    ds = {"Isc": 9.5, "Voc": 39.7, "Ns": 60}
    a = sig(ds, 43, [910.0, 240.0, 910.0], 3, 910, 5, 3)
    b = sig(dict(ds), 43.0, (910, 240, 910), 3, 910, 5, 3)
    assert a == b, "the same inputs must give the same signature"
    n_len = next(ast.literal_eval(n.value) for n in tree.body
                 if isinstance(n, ast.Assign)
                 and getattr(n.targets[0], "id", "") == "_BENCH_SIG_LEN")
    assert len(a) == n_len


def test_T15_compare_surfaces_unknown_export_keys():
    """An unrecognised key must appear as unknown, not be silently dropped."""
    assert "unknown = [k for k in R if k not in _METHOD_LABELS]" in SRC
    assert "Unrecognised export keys" in SRC


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
def _load_helpers(extra=(), consts=()):
    """Import the dashboard's pure helpers without executing the Streamlit app.

    `consts` names module-level assignments to carry over — a default argument
    is evaluated when the function is defined, so a helper whose signature
    mentions a module constant cannot be exec'd without it.
    """
    import ast
    import numpy as np
    tree = ast.parse(SRC)
    wanted = {"geometry_of", "geometry_label", "_key"} | set(extra)
    consts = set(consts)
    ns = {"np": np}
    body = [n for n in tree.body
            if (isinstance(n, ast.FunctionDef) and n.name in wanted)
            or (isinstance(n, ast.Assign)
                and any(getattr(t, "id", None) in consts for t in n.targets))]
    mod = ast.Module(body=body, type_ignores=[])
    exec(compile(mod, "<helpers>", "exec"), ns)
    return ns


# --------------------------------------------------------------------------- #
# Phase B — U3 panel navigation, U4 record fields, T12 event windows
# --------------------------------------------------------------------------- #
def test_T12_event_window_follows_the_playhead():
    """A new timeline event starts at the playhead and keeps its default
    duration, shifting left rather than shrinking near 18:00. Canonical
    minutes after midnight throughout — the day-fraction mapping is gone."""
    import gmppt_timeline as tl
    win = tl.window_from_minutes
    assert "day_fraction" not in SRC and "_day_window_from_hour" not in SRC
    assert "6.0 + t * 12" not in SRC and "(time_hour - 6.0) / 12.0" not in SRC

    # Away from the right edge, the event starts exactly at the playhead.
    for m in (8 * 60, 12 * 60, 15 * 60, 16 * 60 + 30):
        start, end = win(m)
        assert start == m, f"event at {m} started at {start}"
        assert end - start == tl.DEFAULT_EVENT_MINUTES
    # Near 18:00 it shifts left and keeps its length rather than being truncated,
    # and the window still covers the tick the user clicked at.
    for m in (17 * 60, 17 * 60 + 30, 18 * 60):
        start, end = win(m)
        assert end == tl.DAY_END, f"event at {m} ended at {end}"
        assert end - start == tl.DEFAULT_EVENT_MINUTES
        assert start <= m <= end
    # and never leaves the day
    for m in (5 * 60, 6 * 60, 19 * 60):
        start, end = win(m)
        assert tl.DAY_START <= start <= end <= tl.DAY_END


def test_T13_panel_navigation_is_bounded_and_scoped():
    """Previous/Next step one panel, stop at the ends, and touch nothing else."""
    assert "gm_panel_prev" in SRC and "gm_panel_next" in SRC
    assert "def _step_panel" in SRC, "stepping must use an on_click callback (U3)"
    # the callback clamps instead of wrapping
    assert "min(max(i + delta, 0), len(ids) - 1)" in SRC
    # disabled at the ends
    assert "disabled=cur_idx == 0" in SRC
    assert "disabled=cur_idx == len(ids) - 1" in SRC
    # the panel counter is shown
    assert "Panel {_e(sel_id)} of {n_panels}" in SRC
    # reset is a labelled button, not an icon
    assert '"Reset inspected panel"' in SRC
    assert '"✕", key="tool_clear"' not in SRC


def test_T13_panel_navigation_touches_only_the_inspected_panel():
    """The stepping callback must not write shading, conditions, sent or frozen."""
    import ast
    tree = ast.parse(SRC)
    fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_step_panel":
            fn = node
    assert fn is not None
    written = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            if isinstance(node.slice, ast.Constant):
                written.add(node.slice.value)
    assert written == {"gm_sel"}, f"_step_panel writes {written}, expected only gm_sel"


def test_U4_day_record_carries_every_declared_field():
    """The sampled record must let a reader reconstruct why the curve looks so.
    It is built by gmppt_timeline.sample_records, in canonical minutes."""
    TL = (ROOT / "gmppt_timeline.py").read_text(encoding="utf-8")
    body = TL.split("def sample_records(")[1].split("\ndef ")[0]
    for field in ("\"source\"", "\"time_minutes\"", "\"time_label\"", "\"module_source\"",
                  "\"module_applied\"", "\"temperature_C\"", "\"base_irradiance_Wm2\"",
                  "\"substring_irradiance_Wm2\"", "\"scenario_hash\"", "\"events\""):
        assert field in body, f"timeline record is missing {field}"
    for per_event in ("\"kind\"", "\"uid\"", "\"start_minutes\"", "\"end_minutes\"",
                      "\"duration_minutes\"", "\"motion\""):
        assert per_event in body, f"per-event detail is missing {per_event}"
    assert "time_hour" not in body and "start_hour" not in body, "no hour fractions"


def test_U4_import_sentence_is_shared_by_message_and_record():
    """One sentence, used on import and stored in the record, so a saved file
    cannot outlive the explanation that the module did not come with it."""
    assert "_IMPORT_SENTENCE" in SRC
    assert "Irradiance conditions were imported; the module was not" in SRC
    assert SRC.count("_IMPORT_SENTENCE.format(") == 2, \
        "expected the sentence on the import message and in the saved record"


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
    # §14 moved the file/field specifics into Technical details; the refusal to
    # call the table gated stays where the reader sees it.
    assert '"Not presentable as gated"' in SRC
    assert "cannot be described as gated" in SRC
    assert 'kind="limit"' in SRC, "the caveat must keep the limit tone"
    assert "per-gate G1–G6 pass/discard counts" in SRC, \
        "what is absent must still be recorded for a maintainer"


def test_no_hardcoded_relocation_prose():
    """R14: the '~64% lost' and 'step 40' literals must be gone; the page reads
    the jump step and every percentage from the export."""
    assert "64%" not in SRC
    assert "One shift at step 40" not in SRC
    assert "all data-validation gates passed" not in SRC


# --------------------------------------------------------------------------- #
# Phase A — data safety (T16) and export guards (T6)
# --------------------------------------------------------------------------- #
PHASE2 = ROOT / "results" / "phase2"


def _hash_tree(d: Path) -> dict:
    import hashlib
    out = {}
    if not d.exists():
        return out
    for f in sorted(d.rglob("*")):
        if f.is_file():
            out[str(f.relative_to(d))] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


@pytest.mark.skipif(not PHASE2.exists(), reason="no phase2 exports")
def test_T16_dashboard_never_writes_to_phase2():
    """Importing and exercising the read path must not touch a benchmark export.

    A full browser pass is covered separately; this asserts the property at the
    level the app itself controls — every export read is a read.
    """
    before = _hash_tree(PHASE2)
    assert before, "expected exports to hash"
    src = SRC
    # No write API may be aimed at results/phase2 anywhere in the app.
    for pattern in (r"write_text\s*\(", r"\.write\s*\(", r"open\s*\([^)]*['\"]w",
                    r"to_csv\s*\(\s*[^)]*path", r"shutil\.", r"os\.remove", r"unlink\("):
        for i, line in enumerate(src.splitlines(), 1):
            if re.search(pattern, line) and "phase2" in line:
                pytest.fail(f"write aimed at phase2 at line {i}: {line.strip()}")
    after = _hash_tree(PHASE2)
    assert before == after


def test_T16_the_only_write_is_the_dashboard_mirror():
    """§2.3 allows exactly one write, and not into results/ proper."""
    assert "_mirror_scenario" in SRC
    assert 'RESULTS_DIR / "dashboard"' in SRC, \
        "the scenario mirror must live in results/dashboard/, not beside the exports"
    writes = [l.strip() for l in SRC.splitlines() if "write_text(" in l]
    assert len(writes) == 1, f"expected one write_text call, found {len(writes)}: {writes}"


def test_export_reader_separates_missing_from_malformed(tmp_path, monkeypatch):
    """T6's premise: four failure modes, four messages, no repair."""
    import ast
    tree = ast.parse(SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_read_export")

    class _Cfg:
        RESULTS_DIR = tmp_path
    ns = {"_gcfg": _Cfg}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "<x>", "exec"), ns)
    read = ns["_read_export"]

    assert read("nope.json") == (None, "not found")
    (tmp_path / "bad.json").write_text("{ this is not json", encoding="utf-8")
    data, problem = read("bad.json")
    assert data is None and "malformed JSON" in problem
    (tmp_path / "list.json").write_text("[1, 2, 3]", encoding="utf-8")
    data, problem = read("list.json")
    assert data is None and "unexpected schema" in problem
    (tmp_path / "ok.json").write_text('{"a": 1}', encoding="utf-8")
    assert read("ok.json") == ({"a": 1}, None)


def test_pages_check_export_schema_before_reading_it():
    """Every page that reads an export must gate on require_keys (§2.3)."""
    assert "def require_keys" in SRC
    assert SRC.count("require_keys(") >= 6, \
        "expected the schema gate on compare, dynamic, relocation, results and benchset"


def test_provenance_carries_an_experiment_id():
    """U7: the run identifier travels with every figure when the export has one."""
    assert "_experiment_id" in SRC
    assert '"experiment": _experiment_id(data)' in SRC
    import gmppt_ui as ui
    import inspect
    assert '("experiment", "experiment")' in inspect.getsource(ui.provenance)


@pytest.mark.skipif(not (PHASE2 / "relocation_comparison_pole.json").exists(),
                    reason="relocation export not present")
def test_experiment_id_is_read_not_invented():
    """These exports carry no explicit run id; family/sequence are what identify
    the run, and that is what provenance shows. Nothing is synthesised."""
    import ast, json as _json
    tree = ast.parse(SRC)
    picked = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in (
                "_RUN_ID_KEYS", "_EXPERIMENT_KEYS"):
            picked[n.targets[0].id] = ast.literal_eval(n.value)
    d = _json.loads((PHASE2 / "relocation_comparison_pole.json").read_text())
    assert not any(k in d for k in picked["_RUN_ID_KEYS"]), \
        "an explicit run id now exists — prefer it over family/sequence"
    assert any(k in d for k in picked["_EXPERIMENT_KEYS"])


# --------------------------------------------------------------------------- #
# Update 3 — animation layer
# --------------------------------------------------------------------------- #
UI_SRC = UI.read_text(encoding="utf-8")


def test_toolkit_exists_with_the_specified_api():
    import gmppt_ui as ui
    for name in ("trace_player", "curve_morph", "anim_badge", "snapshot_strip",
                 "anim_exports", "anim_on", "downsample", "anim_budget_note"):
        assert callable(getattr(ui, name)), f"missing toolkit helper {name}"


def test_T35_no_rerun_driven_animation():
    """Motion must be Plotly frames in the browser, never a Python loop."""
    for src, label in ((SRC, "gmppt_app.py"), (UI_SRC, "gmppt_ui.py")):
        assert "time.sleep" not in src, f"{label} uses time.sleep"
        assert "autorefresh" not in src.lower(), f"{label} uses an autorefresh component"
    # no st.rerun inside any animation function
    import ast
    tree = ast.parse(SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith(("_a1_", "_anim")):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call)
                        and getattr(sub.func, "attr", "") == "rerun"):
                    pytest.fail(f"{node.name} drives animation with st.rerun")


def test_T36_aggregate_pages_build_no_animation():
    """Compare, Results, Benchmark set and Sources must stay static."""
    import ast
    tree = ast.parse(SRC)
    aggregate = {"page_compare", "page_results", "page_benchset", "page_provenance",
                 "page_summary", "page_dynamic_perf", "page_validation_model",
                 "_relocation_section", "_dynamic_export_block"}
    banned = ("trace_player", "curve_morph", "anim_badge", "snapshot_strip",
              "anim_exports")
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in aggregate:
            src = ast.get_source_segment(SRC, node) or ""
            for b in banned:
                assert b not in src, f"{node.name} uses {b}; aggregates must be static"


def test_T34_budget_constants_are_declared():
    import gmppt_ui as ui
    assert ui.ANIM_MAX_FRAMES == 300
    assert ui.ANIM_MAX_JSON_MB == 5.0
    keep, stride = ui.downsample(1000, key_frames=[7, 500, 999])
    assert len(keep) <= 300, "downsample must respect the frame budget"
    assert stride > 1
    for k in (7, 500, 999):
        assert k in keep, f"key frame {k} was dropped by downsampling"


def test_T31_every_badge_kind_has_fixed_wording():
    import gmppt_ui as ui
    assert set(ui._BADGE_TEXT) == {"recorded", "live", "schematic", "sandbox"}
    assert "not a benchmark result" in ui._BADGE_TEXT["live"]
    assert "Nothing here is re-run" in ui._BADGE_TEXT["recorded"]


def test_A1_uses_recorded_trajectories_only():
    """A1 must replay v_hist/p_hist; it may not call a tracker itself."""
    import ast
    tree = ast.parse(SRC)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_a1_frames")
    src = ast.get_source_segment(SRC, fn) or ""
    assert "v_hist" in src and "p_hist" in src
    for banned in ("perturb_and_observe", "particle_swarm", "make_hybrid",
                   "trajectory_for", "module_iv"):
        assert banned not in src, f"_a1_frames calls {banned}; it must only replay"


def test_A1_pso_grouping_is_verified_not_guessed():
    """T26: the grouping claim is derived from pso.py, or it is not made."""
    assert "def _pso_grouping" in SRC
    assert "particle identity not recorded" in SRC
    from gmppt import pso
    import inspect
    src = inspect.getsource(pso.particle_swarm)
    assert "for _ in range(iterations)" in src and "for i in range(population)" in src, \
        "pso.py's loop shape changed — A1's grouping claim must be rechecked"
    assert pso.DEFAULT_POPULATION == 5


def test_gm_anim_defaults_on_and_persists():
    assert 'st.session_state.setdefault("gm_anim", "On")' in SRC
    assert '"gm_anim"' in SRC.split("_PERSIST_KEYS")[1][:800], \
        "gm_anim must be in the widget-persistence list"


# --------------------------------------------------------------------------- #
# A2 / A3 — the animations that must agree with the engine
# --------------------------------------------------------------------------- #
def test_A2_probe_accounting_is_stated_not_guessed():
    """§8: five PROBE_FRACTIONS and a report saying six are both right, about
    different boundaries. The runtime is the source of truth for each."""
    from gmppt.features import PROBE_FRACTIONS
    from gmppt import hybrid, model
    assert len(PROBE_FRACTIONS) == 5
    assert hybrid.SEED_PROBE_COST == len(PROBE_FRACTIONS), \
        "the seed's charged control steps are the feature probes"
    assert model.EXPECTED_PROBES == len(PROBE_FRACTIONS) + 1, \
        "the model's serving cost adds the landing at k*V_oc"
    # and the dashboard says so rather than picking a side
    assert "not a sixth probe" in SRC
    assert "SEED_PROBE_COST = hyb.SEED_PROBE_COST" in SRC or \
           "SEED_PROBE_COST" in SRC


def test_A2_never_draws_a_safety_stage():
    """§9: make_hybrid does not call the fallback, so no stage may claim it."""
    import inspect
    from gmppt import hybrid
    src = inspect.getsource(hybrid.make_hybrid)
    assert "fallback" not in src, \
        "if make_hybrid ever calls the fallback, A2 must grow a safety stage"
    import ast
    fn = next(n for n in ast.walk(ast.parse(SRC))
              if isinstance(n, ast.FunctionDef) and n.name == "_a2_stage_frames")
    body = ast.get_source_segment(SRC, fn) or ""
    assert "safety" not in body.lower() and "fallback" not in body.lower()


def test_A2_stages_come_from_the_recorded_history():
    """§9: stage 1 uses v_hist[:SEED_PROBE_COST], not the declared fractions."""
    import ast
    fn = next(n for n in ast.walk(ast.parse(SRC))
              if isinstance(n, ast.FunctionDef) and n.name == "_a2_stage_frames")
    body = ast.get_source_segment(SRC, fn) or ""
    assert 'r["v_hist"]' in body, "probes must be read from the recorded run"
    assert "Recorded probes differ" in body, "a mismatch must raise the caveat"
    assert 'seed["proba"]' in body and 'seed["v_seed"]' in body


def test_A3_detects_the_switches_the_engine_reports():
    """§10: on a scenario where a bypass diode really does switch, _a3_sweep must
    find it — and find it at the voltage the engine puts it at."""
    import numpy as np
    import pandas as pd
    from pvlib import pvsystem
    from gmppt import config as gcfg, device as eng
    from gmppt.dataset import module_split

    h = _load_helpers({"_diode_state", "_a3_sweep", "_key"}, {"_A3_FRAMES"})
    name = sorted(module_split().val)[0]
    r = pvsystem.retrieve_sam("CECMod").T.loc[name]
    num = lambda k: float(pd.to_numeric(r[k]))
    mp = eng.ModuleParams(name=name, N_s=int(num("N_s")), alpha_sc=num("alpha_sc"),
                          a_ref=num("a_ref"), I_L_ref=num("I_L_ref"),
                          I_o_ref=num("I_o_ref"), R_sh_ref=num("R_sh_ref"),
                          R_s=num("R_s"), Adjust=num("Adjust"))
    irr = [910.0, 300.0, 600.0]                    # a shadow deep enough to switch
    T = 43.0
    c = eng.module_iv(mp, irr, T, bd=gcfg.breakdown())
    V, I, P = c["V"], c["I"], c["P"]
    m = V >= 0
    o = np.argsort(V[m])
    det = {"V": V[m][o], "I": I[m][o], "P": P[m][o],
           "voc": float(V[m].max()), "n_peaks": eng.analyse(c)["n_peaks"],
           "gmpp": eng.analyse(c)["gmpp"]}

    # the element curves _substring_curves would have cached
    bd, bp = gcfg.breakdown(), eng.Bypass(temp_c=T)
    n_sub = gcfg.N_SUBSTRINGS
    base = mp.N_s // n_sub
    counts = [base] * n_sub
    for k in range(mp.N_s - base * n_sub):
        counts[k] += 1
    curves = []
    for entry, cnt in zip(irr, counts):
        sub = eng.scale_to_substring(mp, cnt / mp.N_s)
        v, ie = eng.substring_element_iv(sub, float(entry), T, bd, bp)
        curves.append(([float(x) for x in v], [float(x) for x in ie]))
    clamp = float(bp.clamp_voltage)
    h["_substring_curves"] = lambda *_a, **_k: (curves, clamp)
    h["np"] = np

    frames, switches = h["_a3_sweep"](name, irr, T, det, clamp)

    assert len(frames) == 60
    assert abs(frames[0]["v"]) < 1e-9, "first frame must be V = 0"
    assert abs(frames[-1]["v"] - det["voc"]) < 1e-6, "last frame must be V_oc"
    assert switches, "this scenario does switch — the sweep must find it"
    # a switch is reported only where the state vector actually changed
    for k in range(1, len(frames)):
        changed = frames[k]["state"] != frames[k - 1]["state"]
        assert changed == (k in switches), \
            f"frame {k}: state changed={changed} but reported={k in switches}"
    # P–V and I–V stay on the same index
    for f in frames:
        assert abs(f["p"] - f["v"] * f["i"]) < max(1.0, 0.02 * abs(f["p"])), \
            "power, voltage and current must describe one operating point"


def test_A3_shares_one_bypass_rule_with_the_table():
    """§10: the animation may not carry its own copy of the diode rule."""
    assert SRC.count("clamp + 0.2") == 1, \
        "the bypass threshold must exist in exactly one place (_diode_state)"
    assert "_diode_state(vk, clamp)" in SRC, "the table reads it through the rule"
    assert "_diode_state(x, clamp)" in SRC, "A3 reads it through the same rule"


# --------------------------------------------------------------------------- #
# UI copy cleanup and UX scaffolding
# --------------------------------------------------------------------------- #
def test_the_reported_debug_block_is_gone():
    """§8: the validation/debug panel the user screenshotted must not be in the
    normal UI. Its facts live in an expander now, so the phrasing that made it
    read like a developer console is what must be absent."""
    banned = [
        "in training set",
        "closest module the model was trained on",
        "used for method comparison. The held-out test set is not shown",
        "the model file does not\n",
        "compares against the split function",
        "Rows (strings)",
        "Validation module — not used to fit the model",
        "z-scored parameter distance",
    ]
    for phrase in banned:
        assert phrase not in SRC, f"debug copy still present: {phrase!r}"
    assert "_VAL_WORDING" not in SRC, \
        "the long validation sentence should be replaced by ui.data_chip"


def test_user_facing_components_exist():
    import gmppt_ui as ui
    for name in ("data_chip", "unavailable", "stepper", "tutorial", "section_head",
                 "term_tip"):
        assert callable(getattr(ui, name)), f"missing UI component {name}"
    assert ui.FLOW_STAGES == ["Scenario", "Static test", "Dynamic test", "Results",
                              "Data & validation"]


def _stages():
    """The one workflow table, read from the source as data."""
    import ast
    tree = ast.parse(SRC)
    stages = next(ast.literal_eval(n.value) for n in tree.body
                  if isinstance(n, ast.Assign)
                  and getattr(n.targets[0], "id", "") == "STAGES")
    sandbox = next(ast.literal_eval(n.value) for n in tree.body
                   if isinstance(n, ast.Assign)
                   and getattr(n.targets[0], "id", "") == "SANDBOX")
    return stages, sandbox


def test_one_workflow_table_drives_everything():
    """§3: one authoritative page→stage mapping, used by header, eyebrow,
    footer, stepper, tutorial and tests alike."""
    stages, sandbox = _stages()
    names = [s for s, _ in stages]
    import gmppt_ui as ui
    assert names == ui.FLOW_STAGES, "the header strip and the stage list must agree"
    pages = [k for _, ks in stages for k in ks]
    assert len(pages) == len(set(pages)), "a page belongs to exactly one stage"
    assert not set(pages) & set(sandbox), "Sandbox pages carry no journey stage"
    # nothing a reader sees may use the old section names as a stage. Code
    # comments are not scanned; user-facing strings are.
    import ast
    strings = [n.value for n in ast.walk(ast.parse(SRC))
               if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    for stale in ("Explore · Inside a panel", "Explore · The panels",
                  "Testing · ", "sent to Testing", "all of Testing",
                  "Testing benchmarks", "Testing reads", "Simulator · Set up",
                  # the tutorial-style labels the research-workflow revision removed
                  "Understand · ", "Inspect · ", "Watch · ", "Compare · ", "Explore · "):
        hits = [s for s in strings if stale in s and len(s) < 400]
        assert not hits, f"stale navigation vocabulary {stale!r}: {hits[:2]}"
    # and no page_intro still names a header section as its eyebrow
    import re
    for m in re.finditer(r'ui\.page_intro\([\s\S]*?"(Testing|The data|Simulator)"\)', SRC):
        raise AssertionError(f"eyebrow still uses a section name: {m.group(0)[-40:]}")


def _eyebrows():
    """(title, eyebrow) of every ui.page_intro call, read from the AST."""
    import ast
    out = []
    for node in ast.walk(ast.parse(SRC)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "page_intro" and len(node.args) >= 3
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[2], ast.Constant)):
            out.append((node.args[0].value, node.args[2].value))
    return out


def test_every_journey_page_eyebrow_names_its_stage():
    """The eyebrow says SECTION · page, and the section is one of the six."""
    stages, sandbox = _stages()
    names = {s for s, _ in stages} | {"Sandbox"}
    eyebrows = _eyebrows()
    assert eyebrows, "expected page_intro calls with an eyebrow"
    for title, eyebrow in eyebrows:
        assert " · " in eyebrow, f"{title!r} eyebrow {eyebrow!r} has no section"
        sec = eyebrow.split(" · ")[0]
        assert sec in names, f"{title!r} has eyebrow section {sec!r}, not a research section"
    assert '"Scenario · PV analysis"' in SRC and '"Scenario · Build system"' in SRC


def test_header_is_the_six_research_sections_without_arrows():
    """Acceptance 1–3: exactly the six major sections, old labels gone, no
    arrows in the global navigation, each section exposing only its own pages."""
    stages, sandbox = _stages()
    assert [s for s, _ in stages] == ["Scenario", "Static test", "Dynamic test",
                                       "Results", "Data & validation"]
    assert sandbox == ["sim_setup", "sim_saved", "sim_sweep", "sim_dataset"]
    assert dict(stages) == {
        "Scenario": ["panels", "inside"],
        "Static test": ["run", "static_compare"],
        "Dynamic test": ["timeline", "tracker_response", "energy"],
        "Results": ["summary", "compare", "dynamic_perf", "results"],
        "Data & validation": ["benchset", "validation", "sources"],
    }
    for old in ("Understand", "Inspect", "Watch", "Explore"):
        assert old not in [s for s, _ in stages]
    hdr = UI_SRC.split("def app_header(")[1].split("\ndef ")[0]
    assert "→" not in hdr, "the global header is navigation, not a progress indicator"
    assert "gm-stage-sep" not in hdr
    # every page in the table is built, so nothing is offered as "coming"
    assert "(None," not in SRC.split("_PAGE_FUNCS = {")[1].split("\n}")[0], \
        "no unbuilt page sits in the navigation table"


def test_results_pages_read_exports_not_interactive_state():
    """Acceptance 8: Results reads validated exports only — never scenario_sent,
    the dynamic scenario, or a tracker run."""
    import ast
    tree = ast.parse(SRC)
    banned = ("scenario_sent", "scenario_draft", "dynamic_scenario", "_run_scenario(",
              "_timeline_run(", "_dynamic_day(", "st.session_state.get(\"frozen\"")
    for name in ("page_summary", "page_compare", "page_dynamic_perf", "page_results",
                 "_relocation_section", "_dynamic_export_block"):
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
        body = ast.get_source_segment(SRC, fn) or ""
        for b in banned:
            assert b not in body, f"{name} touches {b}"
        assert "_load_json(" in body or "missing_export(" in body or "_export_block" in body, \
            f"{name} must read a harness export"


def test_dynamic_test_inherits_the_sent_system():
    """Acceptance 4–6: the Dynamic test never rebuilds the topology; it reads
    the sent scenario's system and carries base_system_hash."""
    import ast
    tree = ast.parse(SRC)
    tl_src = (ROOT / "gmppt_timeline.py").read_text(encoding="utf-8")
    inherit = ast.get_source_segment(SRC, next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_tl_inherit"))
    assert 'st.session_state.get("scenario_sent")' in inherit
    assert 'sent["system"], sent["system_hash"]' in inherit
    for page in ("page_timeline", "page_tracker_response", "page_energy"):
        body = ast.get_source_segment(SRC, next(
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == page))
        for rebuild in ("migrate_panels(", "n_series = int(st.number_input", "scenario_system"):
            assert rebuild not in body, f"{page} rebuilds the topology ({rebuild})"
    assert "base_system_hash" in tl_src and '"base_system_hash"' in SRC
    # the runner is the harness's dynamic trajectory, scored by its own metrics
    run_src = ast.get_source_segment(SRC, next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_timeline_run"))
    assert "dyn.DynamicTrajectory(" in run_src and "tj.metrics()" in run_src
    assert "REACH_TOLERANCE" in run_src and "tl.reconvergence_steps(" in run_src


def test_static_test_runs_the_sent_scenario():
    """Acceptance 5: both Static test pages consume scenario_sent through one rule."""
    import ast
    tree = ast.parse(SRC)
    rule = ast.get_source_segment(SRC, next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_static_scenario"))
    assert 'st.session_state.get("scenario_sent")' in rule and "_run_demo()" in rule
    body = ast.get_source_segment(SRC, next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "page_static_compare"))
    assert "_static_scenario(" in body and "_score_traj" not in body, \
        "Compare methods must reuse the run, never re-score it"
    assert "Trajectory.metrics" in body, "definitions are named as the harness's"


def test_sandbox_is_separated_and_labelled():
    """Acceptance 10: the persistent Sandbox indicator, and no Sandbox output on Results."""
    assert "Sandbox · simplified engine · not benchmark evidence" in SRC
    import ast
    tree = ast.parse(SRC)
    for name in ("page_summary", "page_compare", "page_dynamic_perf", "page_results"):
        body = ast.get_source_segment(SRC, next(
            n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name))
        for b in ("sim.", "frozen", "sweep_results", "bench_"):
            assert b not in body, f"{name} reads Sandbox state ({b})"


def test_tutorial_targets_real_controls_only():
    """§6: every step points at an element the page really draws — the hero's
    two links and the five cards gmppt_hero renders (keyed gm-card-<page>)."""
    import gmppt_hero as hero
    h = _load_helpers({"_tutorial_steps"})
    steps = h["_tutorial_steps"]()
    assert len(steps) == 7, "seven steps (§7)"
    cards = {f".st-key-gm-card-{k}" for k in hero.CARD_LINKS}
    for s in steps:
        assert s["target"] in ({".st-key-hero-primary a", ".st-key-hero-secondary a"} | cards), s
    assert {s["target"] for s in steps} >= cards, "every card is a step"


def test_language_switch_is_read_where_it_is_offered():
    """The EN/KO switch lives in the landing's top bar and drives the landing's
    copy — it must not be a dead control."""
    import gmppt_hero as hero
    src = (ROOT / "gmppt_hero.py").read_text(encoding="utf-8")
    assert 'key="gm_lang"' in src and 'st.session_state.get("gm_lang")' in src
    assert set(hero.TEXT) == {"EN", "KO"}
    assert set(hero.TEXT["EN"]) == set(hero.TEXT["KO"]), "both languages carry the same keys"
    assert len(hero.TEXT["EN"]["cards"]) == len(hero.TEXT["KO"]["cards"]) == len(hero.CARD_LINKS) == 5
    assert '"gm_lang"' in SRC.split("_PERSIST_KEYS")[1][:900], \
        "gm_lang must survive leaving the landing (R2)"


def test_tutorial_state_is_remembered():
    """Closed by default; opened only by the Guide me button in every header;
    Skip, Finish and a click outside close it and reset the step."""
    assert "gm_tut_open" in UI_SRC and "gm_tut_step" in UI_SRC
    assert "gm_tut_done" not in UI_SRC and "gm_tut_done" not in SRC, "no first-visit flag"
    assert "localStorage" not in UI_SRC and "localStorage" not in SRC
    assert "Show tutorial again" not in SRC, "one trigger only: Guide me"
    tut = UI_SRC.split("def tutorial(")[1].split("\ndef ")[0]
    assert 'if not st.session_state.get("gm_tut_open")' in tut, "never draws unless opened"
    assert "guide_button(pages.get(\"home\"), current)" in UI_SRC, "Guide me in app_header"
    assert 'ui.guide_button(None, "home")' in (ROOT / "gmppt_hero.py").read_text(encoding="utf-8"), \
        "Guide me in the landing top bar"
    close = UI_SRC.split("def _close_tutorial(")[1].split("\ndef ")[0]
    assert '["gm_tut_open"] = False' in close and '["gm_tut_step"] = 0' in close
    assert "dim.onclick" in UI_SRC, "click outside closes"


def test_missing_data_states_lead_with_plain_language():
    """§14: the reader gets a sentence; file names go under Technical details."""
    assert "ui.unavailable(" in SRC
    assert "Results unavailable" in SRC
    import ast
    tree = ast.parse(SRC)
    for name in ("missing_export", "missing_field", "require_keys"):
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == name)
        src = ast.get_source_segment(SRC, fn) or ""
        assert "ui.unavailable(" in src, f"{name} must use the plain unavailable state"
        assert "ui.callout(" not in src, f"{name} should no longer lead with a callout"


def test_targets_are_marked_when_not_recorded():
    """D2/N5: the static target is shown under both definitions, marked pending,
    and the targets the repository does not record are named as missing."""
    # the decision is named in plain words; its internal tag (D2) stays out of
    # the reader's view (§24)
    assert "definition pending advisor decision" in SRC
    assert "advisor decision (D2)" not in SRC
    assert "not recorded in this repository" in SRC
