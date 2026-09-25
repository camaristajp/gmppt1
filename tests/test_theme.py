"""Global theme: Dark by default, the user's explicit choice authoritative
thereafter, one source for every page, and nothing else able to change it.

Run:  python -m pytest tests/test_theme.py -q
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APP_SRC = (ROOT / "gmppt_app.py").read_text(encoding="utf-8")
UI_SRC = (ROOT / "gmppt_ui.py").read_text(encoding="utf-8")
HERO_SRC = (ROOT / "gmppt_hero.py").read_text(encoding="utf-8")


def _fn(name, src):
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
    return ast.get_source_segment(src, fn)


def test_one_theme_key_and_a_dark_default_that_is_never_rewritten():
    head = APP_SRC.split("ui.setup(")[0]
    assert 'st.session_state.get("gm_theme_pref", "Dark")' in head
    assert 'if st.session_state.get("gm_theme") not in ("Light", "Dark"):' in head
    assert 'st.session_state.setdefault("gm_theme"' not in APP_SRC
    assert 'st.session_state["gm_theme"] = "Light"' not in APP_SRC
    # every theme control uses the same key
    assert 'key="gm_theme"' in HERO_SRC and 'theme_key: str = "gm_theme"' in UI_SRC
    assert APP_SRC.count('"gm_theme"') >= 2 and "gm_theme_light" not in APP_SRC
    # the CSS/palette is applied from the persisted value on every run
    assert "ui.setup(st.session_state.gm_theme)" in APP_SRC


def test_palette_is_per_session_not_a_process_global():
    t = _fn("T", UI_SRC)
    assert "_session_theme_name()" in t
    s = _fn("setup", UI_SRC)
    assert 'st.session_state["_gm_theme_name"] = _theme_name' in s
    # collapsibles never touch the theme
    col = _fn("collapsible", UI_SRC)
    assert "theme" not in col.lower().split('"""')[-1]


@pytest.fixture(scope="module")
def app():
    from streamlit.testing.v1 import AppTest
    a = AppTest.from_file(str(ROOT / "gmppt_app.py"), default_timeout=900)
    a.run()
    return a


def test_T8_fresh_session_is_dark(app):
    assert app.session_state["gm_theme"] == "Dark"
    assert app.session_state["gm_theme_pref"] == "Dark"
    assert app.session_state["_gm_theme_name"] == "dark"


def test_deselecting_the_control_restores_the_previous_choice(app):
    app.session_state["gm_theme"] = None            # a click on the active pill
    app.run()
    assert app.session_state["gm_theme"] == "Dark" and app.session_state["_gm_theme_name"] == "dark"


def test_T12_T13_explicit_choice_persists_across_reruns(app):
    app.session_state["gm_theme"] = "Light"          # the user's explicit choice
    app.run()
    assert app.session_state["gm_theme_pref"] == "Light" and app.session_state["_gm_theme_name"] == "light"
    app.run()                                        # any rerun (expander, slider, navigation)
    assert app.session_state["gm_theme"] == "Light" and app.session_state["_gm_theme_name"] == "light"
    app.session_state["gm_theme"] = None             # deselect while Light: Light stays
    app.run()
    assert app.session_state["gm_theme"] == "Light"
    app.session_state["gm_theme"] = "Dark"           # back to Dark, explicitly
    app.run()
    app.run()
    assert app.session_state["gm_theme"] == "Dark" and app.session_state["_gm_theme_name"] == "dark"
