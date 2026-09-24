"""The landing page's before/after figure and top bar.

Run:  python -m pytest tests/test_hero.py -q
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import app as sim                # noqa: E402
import gmppt_hero as hero        # noqa: E402
import gmppt_ui as ui            # noqa: E402

APP_SRC = (ROOT / "gmppt_app.py").read_text(encoding="utf-8")
HERO_SRC = (ROOT / "gmppt_hero.py").read_text(encoding="utf-8")


def _cv(preset=None):
    ds = dict(sim.MODULE_PRESETS[preset or sim.DEFAULT_PRESET])
    return hero.compute_curves(ds)


def test_curves_come_from_module_iv_and_have_one_and_three_peaks():
    cv = _cv()
    assert cv["unshaded"]["irr"] == [1000.0, 1000.0, 1000.0]
    assert cv["shaded"]["irr"][1] == 250.0, "the middle strip is the ~250 W/m² one"
    assert len(cv["unshaded"]["lmpps"]) == 0, "one peak unshaded"
    assert len(cv["shaded"]["lmpps"]) == 2, "three peaks shaded (global + two local)"
    # the figure's global peak is the engine's
    ref = sim.datasheet_to_ref(sim.MODULE_PRESETS[sim.DEFAULT_PRESET])
    r = sim.module_iv(list(hero.SHADED_IRR), hero.T_CELL,
                      sim.MODULE_PRESETS[sim.DEFAULT_PRESET]["Ns"] // 3, ref)
    assert abs(cv["shaded"]["gmpp"][1] - r["gmpp"][2]) < 0.01
    assert "module_iv(" in HERO_SRC and "datasheet_to_ref(" in HERO_SRC
    assert "polyline points=" in HERO_SRC, "the path is generated, never hand-drawn"


def test_changing_the_preset_changes_both_curves():
    a = _cv("Generic 60-cell mono 300 W")
    b = _cv("JinkoSolar JKM400M-72")
    assert a["unshaded"]["gmpp"] != b["unshaded"]["gmpp"]
    assert a["shaded"]["gmpp"] != b["shaded"]["gmpp"]


def _html(dark=False, lang="EN"):
    cv = _cv()
    return hero.figure_html(cv, ui.DARK if dark else ui.LIGHT, hero.TEXT[lang], dark)


def test_figure_document():
    doc = _html()
    assert doc.count("<svg") == 3, "two artwork layers plus the unclipped chip layer, one box"
    assert doc.count('rx="11"') == 2 and 'id="chips"' in doc, "both chips ride above the wipe"
    assert 'viewBox="0 0 620 360"' in doc
    assert "aspect-ratio:620 / 360" in doc, "sized by aspect ratio, not a fixed pixel height"
    assert 'value="50"' in doc and "r.value=50;set(50);" in doc, "opens centred every load"
    assert "clip-path:inset(0 0 0 50%)" in doc, "the top layer is clipped from the left"
    assert 'type="range"' in doc and 'aria-label="' in doc and "aria-valuetext" in doc
    for label in ("UNSHADED", "SHADOW ACROSS THE STRIPS", "One peak. Any tracker finds it.",
                  "Three peaks. Only one is the real maximum.", "the other two are traps",
                  "power against voltage", "Drag the divider."):
        assert label in doc, label
    assert "rotate(" not in doc, "no rotated axis label"
    # chips are anchored to the artwork box, inside the SVG, not to the card
    i_svg = doc.index("<svg")
    assert doc.index("UNSHADED") > i_svg and doc.index("SHADOW ACROSS") > i_svg
    assert "frameElement.style.height" in doc, "the frame follows its content"
    assert ui.FONT_IMPORT in doc


def test_panel_is_centred_in_the_box():
    assert hero._PX * 2 + hero._PW == hero._W


def test_dark_and_korean_variants():
    d = _html(dark=True)
    assert ui.DARK["surface"] in d and ui.DARK["amber_tint"] in d and ui.DARK["bg"] in d
    k = _html(lang="KO")
    assert hero.TEXT["KO"]["chip_u"] in k and hero.TEXT["KO"]["caption"] in k
    assert 'lang="ko"' in k


def test_home_has_no_section_or_page_tabs_but_other_pages_keep_them():
    tree = ast.parse(APP_SRC)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_wrapped")
    body = ast.get_source_segment(APP_SRC, fn)
    assert 'if key == "home":' in body and "hero.top_bar()" in body
    assert "ui.app_header(" in body.split("else:")[1]
    bar = ast.get_source_segment(HERO_SRC, next(
        n for n in ast.walk(ast.parse(HERO_SRC))
        if isinstance(n, ast.FunctionDef) and n.name == "top_bar"))
    assert "page_link" not in bar and "gm-sec-" not in bar and "gm-tab-" not in bar
    for ctl in ('key="gm_lang"', 'key="gm_theme"', "_LOGO", "GMPPT Bench"):
        assert ctl in bar


def test_hero_copy_and_notes_present():
    en = hero.TEXT["EN"]
    assert en["fine"].startswith("No account and no setup.") and "616" in en["fine"]
    assert en["schematic"] == "Illustrates the idea — not measured data."
    assert en["eyebrow"] == "AI Lab · Jeju National University × Nanum Energy"
    assert [t for t, _ in en["cards"]] == ["Build the panel", "Place the shadow", "Read the curve",
                                           "Run the trackers", "Compare and export"]
    assert hero.CARD_LINKS == ["sim_setup", "panels", "inside", "run", "compare"]
    src = ast.get_source_segment(HERO_SRC, next(
        n for n in ast.walk(ast.parse(HERO_SRC))
        if isinstance(n, ast.FunctionDef) and n.name == "render_hero"))
    assert 'P["panels"]' in src and 'P["run"]' in src, "both buttons are st.page_link, outside the frame"
    assert "_frame(" in src and "FIGURE_HEIGHT" in src
    fr = ast.get_source_segment(HERO_SRC, next(
        n for n in ast.walk(ast.parse(HERO_SRC))
        if isinstance(n, ast.FunctionDef) and n.name == "_frame"))
    assert "components.html(" in fr and "st.iframe(" in fr and "height=height" in fr, \
        "explicit height through either frame API"


def test_backdrop_is_landing_only_and_respects_motion_settings():
    """The moving background: drawn by render_hero (Home only), pure CSS with
    only transform/opacity animated, still under prefers-reduced-motion and
    under the header's Animations-off switch, both themes."""
    tree = ast.parse(HERO_SRC)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "backdrop")
    src = ast.get_source_segment(HERO_SRC, fn)
    hero_src = ast.get_source_segment(HERO_SRC, next(
        n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "render_hero"))
    assert "backdrop()" in hero_src
    assert "backdrop(" not in APP_SRC, "only the landing draws it"
    assert "prefers-reduced-motion" in src and "ui.anim_on()" in src
    assert '"on" if on else "still"' in src
    assert "z-index:-1" in src and "pointer-events:none" in src
    assert "filter:" not in src, "no blur filters — gradients only"
    import re
    frames = re.findall(r"@keyframes [\w-]+\{(.*?)\}\"", src)
    assert len(frames) == 3, frames
    for body in frames:
        props = set(re.findall(r"(?:^|[{;])\s*([a-z-]+)\s*:", body))
        assert props <= {"transform", "opacity"}, f"keyframes animate {props}"
    assert "c is ui.DARK" in src, "a dark variant"


def test_dark_is_the_default_everywhere():
    assert 'st.session_state.setdefault("gm_theme", "Dark")' in APP_SRC
    cfg = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'base = "dark"' in cfg
    assert ui.DARK["bg"] in cfg and ui.DARK["teal"] in cfg


def test_home_in_app_is_thin_and_keeps_session_and_tutorial():
    tree = ast.parse(APP_SRC)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "page_home")
    body = ast.get_source_segment(APP_SRC, fn)
    for call in ("hero.render_hero(P)", "hero.render_cards(P)", "hero.render_footer(P)",
                 "_session_io()"):
        assert call in body, call
    for gone in ("_HERO_SVG", "_CARD_TEXT", "_home_steps", "ui.stepper("):
        assert gone not in APP_SRC, gone
