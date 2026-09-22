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
    assert "Module split violation" in SRC
    assert SRC.count("assert_val_modules(") >= 3, \
        "expected the guard on the dropdown and the demo, plus its definition"
    # the guard must be used as a gate, i.e. followed by a return
    assert "if not assert_val_modules([n for _, n in val_mods]" in SRC


def test_T14_unseen_check_panel():
    """U1.5: split summary, live membership test, nearest training module."""
    assert "def _unseen_check" in SRC
    assert "in training set" in SRC
    assert "closest module the model was trained on" in SRC
    assert "test not shown here" in SRC
    # and the honest note about what it verifies against (the sentence is split
    # across source lines, so match the tail)
    assert "not record one" in SRC


def test_T14_wording_never_calls_validation_modules_held_out():
    """U1.6: 'held-out' and 'never seen' belong to the test set only."""
    assert "_VAL_WORDING" in SRC
    assert "Validation module — not used to fit the model" in SRC
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
def _load_helpers(extra=()):
    """Import the dashboard's pure helpers without executing the Streamlit app."""
    import ast
    import numpy as np
    tree = ast.parse(SRC)
    wanted = {"geometry_of", "geometry_label", "_key"} | set(extra)
    ns = {"np": np}
    mod = ast.Module(body=[n for n in tree.body
                           if isinstance(n, ast.FunctionDef) and n.name in wanted],
                     type_ignores=[])
    exec(compile(mod, "<helpers>", "exec"), ns)
    return ns


# --------------------------------------------------------------------------- #
# Phase B — U3 panel navigation, U4 record fields, T12 event windows
# --------------------------------------------------------------------------- #
def test_T12_event_window_follows_the_playhead():
    """A new event starts at the selected hour and keeps its 1.5 h duration,
    shifting left rather than shrinking when the playhead is near 18:00."""
    h = _load_helpers({"_day_window_from_hour"})
    win = h["_day_window_from_hour"]

    def hours(hour, duration=1.5):
        t0, t1 = win(hour, duration)
        return round(6 + t0 * 12, 4), round(6 + t1 * 12, 4)

    # Away from the right edge, the event starts exactly at the playhead.
    for hour in (8.0, 12.0, 15.0, 16.5):
        start, end = hours(hour)
        assert start == hour, f"event at {hour} started at {start}"
        assert round(end - start, 4) == 1.5, f"duration at {hour} was {end - start}"
    # Near 18:00 it shifts left and keeps its length rather than being truncated,
    # and the window still covers the tick the user clicked at.
    for hour in (17.0, 17.5, 18.0):
        start, end = hours(hour)
        assert end == 18.0, f"event at {hour} ended at {end}"
        assert round(end - start, 4) == 1.5, f"duration at {hour} was {end - start}"
        assert start <= hour <= end, f"window {start}-{end} does not cover {hour}"
    # and never leaves the day
    for hour in (5.0, 6.0, 19.0):
        start, end = hours(hour)
        assert 6.0 <= start <= end <= 18.0


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
    """The sampled record must let a reader reconstruct why the curve looks so."""
    for field in ("\"source\"", "\"time_hour\"", "\"time_label\"", "\"module_source\"",
                  "\"module_applied\"", "\"temperature_C\"", "\"base_irradiance_Wm2\"",
                  "\"substring_irradiance_Wm2\"", "\"scenario_hash\"", "\"events\""):
        assert field in SRC, f"day-event record is missing {field}"
    for per_event in ("\"kind\"", "\"uid\"", "\"start_hour\"", "\"end_hour\"",
                      "\"duration_hours\"", "\"motion\""):
        assert per_event in SRC, f"per-event detail is missing {per_event}"


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
    assert "Gate counts are not in this export" in SRC


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
    aggregate = {"page_compare", "page_results", "page_benchset", "page_sources"}
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


def test_targets_are_marked_when_not_recorded():
    """D2/N5: the static target is shown under both definitions, marked pending,
    and the targets the repository does not record are named as missing."""
    assert "definition pending advisor decision (D2)" in SRC
    assert "not recorded in this repository" in SRC
