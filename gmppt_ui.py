"""
gmppt_ui.py — the GMPPT Bench design system, as a drop-in Streamlit module.

What this gives you
    setup(theme)            inject fonts + CSS and register the Plotly template (call once, first)
    TOKENS / LIGHT / DARK   every colour, font, radius and spacing value in one place
    METHOD_COLORS etc.      fixed colours per tracker, reference line and shading event
    Components              page_intro, section_label, kpi, kpi_row, callout, engine_badge,
                            not_built, next_step, run_button, legend_note
    Chart helpers           style_fig, add_reference_lines, mark_gmpp, mark_local_peaks

Design rules this module enforces (see DESIGN.md for the reasoning)
    1. One teal button per page, and it always means "go to the next step".
       Dark buttons compute something here. Outline buttons are secondary.
    2. A pill (segmented control) is a view switch, never an action.
    3. A caveat sits beside the claim it limits, not on a separate page.
    4. Every page that draws a curve states which engine drew it.
    5. Not-built features are shown greyed and labelled, never hidden.

Requires Streamlit >= 1.63 (app_header uses st.container(horizontal=..., width=...),
st.html(width=...) and st.space; plus st.container(key=...), st.segmented_control,
st.navigation).
"""
from __future__ import annotations

import datetime as _dt
import html
import os
from typing import Iterable, Mapping, Sequence

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# --------------------------------------------------------------------------- #
# Tokens
# --------------------------------------------------------------------------- #
LIGHT = dict(
    bg="#F7F6F1",          # page ground — warm paper, not white
    surface="#FFFFFF",     # cards
    surface_alt="#FCFBF8", # inputs, inset panels
    muted_fill="#F0EDE4",  # tracks, inactive pills
    border="#E3DFD4",
    border_strong="#D9D4C7",
    text="#15181B",
    text_body="#2B3238",
    text_muted="#6A7177",
    text_faint="#8A9098",
    teal="#16616B",        # brand + "next step"
    teal_dark="#0E434A",
    teal_tint="#E7EFEF",
    amber="#B5641A",       # the true peak (GMPP), highlights
    amber_text="#9A5314",
    amber_tint="#FBF4EC",
    amber_border="#E0C49F",
    red="#A32B24",         # failure / trapped / limits
    red_tint="#FBEFEE",
    red_border="#E0A9A4",
    ink="#15181B",         # "run" buttons
    panel="#26404F",       # solar panel fill in diagrams
)

DARK = dict(
    bg="#0F1A22",
    surface="#15232D",
    surface_alt="#1A2B36",
    muted_fill="#223544",
    border="#27404F",
    border_strong="#335063",
    text="#F2F4F5",
    text_body="#D5DCE0",
    text_muted="#9AA7B0",
    text_faint="#7C8A94",
    teal="#2FA3AE",
    teal_dark="#5CC3CC",
    teal_tint="#16343A",
    amber="#E0913F",
    amber_text="#F0B06E",
    amber_tint="#2E2417",
    amber_border="#5C4424",
    red="#E0645B",
    red_tint="#2E1A1A",
    red_border="#5C2E2B",
    ink="#E9EEF1",
    panel="#3E6076",
)

FONTS = dict(
    display="'Plus Jakarta Sans', 'IBM Plex Sans', system-ui, sans-serif",
    body="'IBM Plex Sans', system-ui, sans-serif",
    mono="'IBM Plex Mono', ui-monospace, 'SFMono-Regular', monospace",
)
FONT_IMPORT = (
    "https://fonts.googleapis.com/css2?"
    "family=Plus+Jakarta+Sans:wght@500;600;700;800"
    "&family=IBM+Plex+Sans:wght@400;500;600"
    "&family=IBM+Plex+Mono:wght@400;500&display=swap"
)

RADIUS = dict(sm="8px", md="10px", lg="14px", pill="999px")
SPACE = dict(xs="4px", sm="8px", md="12px", lg="16px", xl="24px", xxl="32px")

TOKENS = dict(light=LIGHT, dark=DARK, fonts=FONTS, radius=RADIUS, space=SPACE)

# Fixed meaning colours — the same method is the same colour on every page.
METHOD_COLORS = {
    "Hybrid": "#16616B",
    "Model only": "#9BBDBF",
    "PSO": "#7FA5A8",
    "P&O": "#A32B24",
    "InC": "#8A9098",
    "Perfect tracker": "#C9C4B7",
    "Oracle": "#C9C4B7",
}
REF_COLORS = {
    "unshaded": "#B5641A",    # dotted: what the panel would make with nothing shading it
    "available": "#2B3238",   # solid dark: power available at the true peak
}
EVENT_COLORS = {              # shading events on the day timeline
    "Row in front": "#AFC9E3",
    "Pole or vent": "#F0C68A",
    "Tree branch": "#A9C79F",
    "Cloud": "#C2BFB6",
    "Soiling": "#E9A08C",
    "Bird dropping": "#BEB8D4",
    "Leaf": "#8FA0A6",
    "Snow band": "#DCE3E8",
    "Building edge": "#9FA7AE",
}
PEAK_COLORS = {"gmpp": "#B5641A", "local": "#8A9098", "operating": "#2F8F63"}

# Variants share their base method's colour and differ only by dash style, so a
# reader never has to learn two colours for one algorithm.
VARIANT_DASH = {
    "bounded": "solid", "free": "dash", "no reseed": "solid",
    "triggered reseed": "dash", "never reseed": "dot",
    "reseed each block": "dashdot", "best of sweep": "solid",
}


def method_style(label: str) -> dict:
    """(colour, dash) for a method label like 'Hybrid (bounded)'.

    The base name before the bracket picks the colour from METHOD_COLORS; the
    bracketed variant picks the dash. Unknown names fall back to the neutral
    'InC' grey rather than inventing a colour in the calling module.
    """
    base = str(label).split(" (")[0].strip()
    variant = str(label).split(" (")[1].rstrip(")").strip() if " (" in str(label) else ""
    return {"color": METHOD_COLORS.get(base, METHOD_COLORS["InC"]),
            "dash": VARIANT_DASH.get(variant, "solid")}

_theme_name = "light"


def T() -> dict:
    """The active palette."""
    return DARK if _theme_name == "dark" else LIGHT


# --------------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------------- #
def setup(theme: str = "light") -> None:
    """Call once at the top of the entry script, after st.set_page_config."""
    global _theme_name
    _theme_name = "dark" if str(theme).lower().startswith("d") else "light"
    _inject_css(T())
    _register_plotly(T())


def _inject_css(c: dict) -> None:
    css = f"""
    @import url('{FONT_IMPORT}');

    html, body, .stApp, [data-testid="stAppViewContainer"] {{
        background: {c['bg']};
        color: {c['text']};
        font-family: {FONTS['body']};
    }}
    header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none !important; }}
    .block-container {{ padding-top: 1rem; padding-bottom: 2.5rem; max-width: 1440px; }}

    /* ---------- our header (replaces Streamlit's top nav) ---------- */
    .st-key-gm-hdr {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: {RADIUS['lg']};
        padding: 10px 16px 0 16px; margin-bottom: 18px; gap: 4px; }}
    .st-key-gm-hdr a, .st-key-gm-hdr a:hover {{ text-decoration: none !important; background: transparent !important; }}
    .st-key-gm-hdr a p {{ margin: 0; }}
    .st-key-gm-wordmark a p {{ font-family: {FONTS['display']} !important; font-weight: 700; font-size: 1.06rem;
        color: {c['text']} !important; letter-spacing: -0.01em; }}
    [class*="st-key-gm-sec-"] a {{ padding: 6px 12px !important; border-radius: {RADIUS['sm']} !important; }}
    [class*="st-key-gm-sec-"] a p {{ font-size: 0.9rem; color: {c['text_body']} !important; }}
    [class*="st-key-gm-sec-"] a:hover {{ background: {c['muted_fill']} !important; }}
    .gm-sec-on {{ display: inline-block; padding: 7px 13px; border-radius: {RADIUS['sm']}; background: {c['teal_tint']};
        color: {c['teal']}; font-weight: 600; font-size: 0.9rem; font-family: {FONTS['body']}; }}
    .st-key-gm-hdr-tabs {{ border-top: 1px solid {c['muted_fill']}; margin-top: 6px; gap: 2px !important; }}
    [class*="st-key-gm-tab-"] a {{ padding: 10px 14px 9px 14px !important; border-radius: 0 !important;
        border-bottom: 3px solid transparent; }}
    [class*="st-key-gm-tab-"] a p {{ font-size: 0.92rem; color: {c['text_body']} !important; }}
    [class*="st-key-gm-tab-"] a:hover {{ border-bottom-color: {c['border_strong']}; }}
    .gm-tab-on {{ display: inline-block; padding: 10px 14px 9px 14px; border-bottom: 3px solid {c['teal']};
        font-weight: 600; font-size: 0.92rem; color: {c['text']}; font-family: {FONTS['body']}; }}
    .gm-tab-off {{ display: inline-block; padding: 10px 14px 9px 14px; font-size: 0.92rem;
        color: {c['text_faint']}; font-family: {FONTS['body']}; }}
    .gm-route {{ font-family: {FONTS['mono']}; font-size: 0.74rem; color: {c['text_muted']}; }}

    /* charts sit on cards, not on the page ground */
    [data-testid="stPlotlyChart"] {{ background: {c['surface']}; border-radius: {RADIUS['md']}; }}
    h1, h2, h3, h4, [data-testid="stHeading"] * {{
        font-family: {FONTS['display']} !important;
        color: {c['text']} !important;
        letter-spacing: -0.015em;
    }}
    h1 {{ font-weight: 800 !important; letter-spacing: -0.035em; }}
    h2, h3 {{ font-weight: 700 !important; }}
    p, li, label, span {{ font-family: {FONTS['body']}; }}
    code, pre, [data-testid="stMetricValue"] {{ font-family: {FONTS['mono']} !important; }}
    [data-testid="stCaptionContainer"], small {{ color: {c['text_muted']} !important; }}

    /* ---------- buttons: one meaning each ---------- */
    /* teal = next step (type="primary") */
    button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
        background: {c['teal']} !important; border: 1px solid {c['teal']} !important;
        color: #FFFFFF !important; border-radius: {RADIUS['md']} !important;
        font-weight: 600 !important; min-height: 44px;
    }}
    button[kind="primary"]:hover, button[data-testid="stBaseButton-primary"]:hover {{
        background: {c['teal_dark']} !important; border-color: {c['teal_dark']} !important;
    }}
    /* outline = secondary (default st.button) */
    button[kind="secondary"], button[data-testid="stBaseButton-secondary"] {{
        background: {c['surface']} !important; border: 1px solid {c['border_strong']} !important;
        color: {c['text_body']} !important; border-radius: {RADIUS['md']} !important; min-height: 44px;
    }}
    /* dark = compute something here — wrap the button in run_button() */
    [class*="st-key-run-"] button {{
        background: {c['ink']} !important; border-color: {c['ink']} !important;
        color: {c['bg'] if _theme_name == 'dark' else '#FFFFFF'} !important; font-weight: 600 !important;
    }}
    /* next-step page links — wrapped by next_step() */
    [class*="st-key-next-"] a {{
        display: inline-flex; align-items: center; min-height: 44px; padding: 0 18px;
        background: {c['teal']}; color: #FFFFFF !important; border-radius: {RADIUS['md']};
        font-weight: 600; text-decoration: none;
    }}
    [class*="st-key-next-"] a:hover {{ background: {c['teal_dark']}; }}
    [class*="st-key-next-"] a p {{ color: #FFFFFF !important; }}

    /* ---------- tabs: underline, not boxes ---------- */
    .stTabs [data-baseweb="tab-list"] {{ gap: 4px; border-bottom: 1px solid {c['border']}; }}
    .stTabs [data-baseweb="tab"] {{ font-family: {FONTS['body']}; color: {c['text_muted']}; }}
    .stTabs [aria-selected="true"] {{ color: {c['text']} !important; font-weight: 600; }}
    .stTabs [data-baseweb="tab-highlight"] {{ background: {c['teal']} !important; height: 3px; }}

    /* ---------- metrics and containers as cards ---------- */
    div[data-testid="stMetric"] {{
        background: {c['surface']}; border: 1px solid {c['border']};
        border-radius: {RADIUS['lg']}; padding: 14px 16px;
    }}
    div[data-testid="stMetricLabel"] p {{
        font-family: {FONTS['mono']}; font-size: 0.72rem; letter-spacing: 0.07em;
        text-transform: uppercase; color: {c['text_muted']} !important;
    }}
    [data-testid="stVerticalBlockBorderWrapper"] {{
        border-color: {c['border']} !important; border-radius: {RADIUS['lg']} !important;
        background: {c['surface']};
    }}
    [data-testid="stSidebar"] {{ background: {c['surface']}; border-right: 1px solid {c['border']}; }}

    /* ---------- components from this module ---------- */
    .gm-eyebrow {{ font-family: {FONTS['mono']}; font-size: 0.74rem; letter-spacing: 0.08em;
        text-transform: uppercase; color: {c['text_muted']}; margin-bottom: 6px; }}
    .gm-lead {{ font-size: 1.02rem; line-height: 1.55; color: {c['text_body']}; max-width: 820px; margin: 4px 0 0 0; }}
    .gm-label {{ font-size: 0.74rem; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase;
        color: {c['text_muted']}; margin: 6px 0 4px 0; }}
    .gm-kpi {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: {RADIUS['lg']};
        padding: 14px 18px; min-height: 122px; box-sizing: border-box; }}
    .gm-kpi .k {{ font-family: {FONTS['mono']}; font-size: 0.7rem; letter-spacing: 0.07em;
        text-transform: uppercase; color: {c['text_muted']}; }}
    .gm-kpi .v {{ font-family: {FONTS['mono']}; font-size: 1.6rem; margin-top: 4px; color: {c['text']}; }}
    .gm-kpi .n {{ font-size: 0.8rem; color: {c['text_muted']}; margin-top: 2px; }}
    .gm-kpi.good .v {{ color: {c['teal']}; }} .gm-kpi.bad .v {{ color: {c['red']}; }}
    .gm-kpi.hero {{ background: {c['teal']}; border-color: {c['teal']}; }}
    .gm-kpi.hero .k, .gm-kpi.hero .n {{ color: rgba(255,255,255,0.82); }}
    .gm-kpi.hero .v {{ color: #FFFFFF; }}
    .gm-callout {{ border-radius: {RADIUS['lg']}; padding: 13px 16px; font-size: 0.88rem;
        line-height: 1.55; color: {c['text_body']}; margin: 6px 0; }}
    .gm-callout b.t {{ display: block; margin-bottom: 3px; }}
    .gm-callout.caveat {{ background: {c['amber_tint']}; border: 1px solid {c['amber_border']}; }}
    .gm-callout.caveat b.t {{ color: {c['amber_text']}; }}
    .gm-callout.limit {{ background: {c['red_tint']}; border: 1px solid {c['red_border']}; }}
    .gm-callout.limit b.t {{ color: {c['red']}; }}
    .gm-callout.info {{ background: {c['surface_alt']}; border: 1px solid {c['border']}; }}
    .gm-badge {{ font-family: {FONTS['mono']}; font-size: 0.74rem; line-height: 1.6;
        background: {c['red_tint']}; border: 1px solid {c['red_border']}; border-radius: {RADIUS['md']};
        padding: 10px 12px; color: {c['text_body']}; }}
    .gm-badge .bad {{ color: {c['red']}; }}
    .gm-badge.ok {{ background: {c['teal_tint']}; border-color: {c['teal']}; }}
    .gm-scenbar {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
        padding: 8px 12px; border: 1px solid {c['border']}; border-radius: {RADIUS['md']};
        background: {c['surface_alt']}; font-size: 0.82rem; color: {c['text_body']}; }}
    .gm-scenbar .chip {{ font-family: {FONTS['mono']}; font-size: 0.68rem; letter-spacing: 0.06em;
        text-transform: uppercase; padding: 3px 9px; border-radius: {RADIUS['pill']}; }}
    .gm-scenbar .chip.ok {{ background: {c['teal_tint']}; color: {c['teal']}; }}
    .gm-scenbar .chip.warn {{ background: {c['amber_tint']}; color: {c['amber_text']}; }}
    .gm-scenbar .chip.mute {{ background: {c['muted_fill']}; color: {c['text_muted']}; }}
    .gm-scenbar .body {{ font-family: {FONTS['mono']}; font-size: 0.76rem; }}
    .gm-step {{ font-family: {FONTS['mono']}; font-size: 0.72rem; letter-spacing: 0.06em;
        text-transform: uppercase; color: {c['text_muted']}; text-align: center; }}
    .gm-next-why {{ font-size: 0.8rem; line-height: 1.45; color: {c['text_muted']};
        margin-bottom: 6px; }}
    div[class*="st-key-gm-next"] a {{ display: flex; align-items: center; justify-content: center;
        height: 42px; border-radius: {RADIUS['sm']}; background: {c['teal']};
        color: #fff !important; font-weight: 600; text-decoration: none; }}
    div[class*="st-key-gm-next"] a p {{ margin: 0; color: #fff !important; font-weight: 600; }}
    div[class*="st-key-gm-next"] a > svg, div[class*="st-key-gm-prev"] a > svg {{ display: none; }}
    div[class*="st-key-gm-prev"] a {{ display: flex; align-items: center; height: 42px;
        color: {c['text_body']} !important; text-decoration: none; }}
    div[class*="st-key-gm-prev"] a p {{ margin: 0; }}
    .gm-sandbox {{ display: flex; align-items: center; gap: 10px; padding: 7px 12px;
        border-radius: {RADIUS['md']}; background: {c['amber_tint']};
        border: 1px solid {c['amber_border']}; color: {c['amber_text']};
        font-size: 0.82rem; margin-bottom: 10px; }}
    .gm-sandbox b {{ font-family: {FONTS['mono']}; font-size: 0.68rem; letter-spacing: 0.06em;
        text-transform: uppercase; }}
    .gm-animbadge {{ display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap;
        padding: 6px 11px; border-radius: {RADIUS['md']}; font-size: 0.78rem;
        margin-bottom: 8px; border: 1px solid {c['border']}; background: {c['surface_alt']};
        color: {c['text_body']}; }}
    .gm-animbadge b {{ font-family: {FONTS['mono']}; font-size: 0.66rem; letter-spacing: 0.06em;
        text-transform: uppercase; padding: 2px 8px; border-radius: {RADIUS['pill']}; }}
    .gm-animbadge.ok b {{ background: {c['teal_tint']}; color: {c['teal']}; }}
    .gm-animbadge.warn b {{ background: {c['amber_tint']}; color: {c['amber_text']}; }}
    .gm-animbadge.mute b {{ background: {c['muted_fill']}; color: {c['text_muted']}; }}
    .gm-animbadge .detail {{ font-family: {FONTS['mono']}; font-size: 0.7rem;
        color: {c['text_muted']}; }}
    /* Plotly's own play/pause and slider must stay visible and keyboard-reachable */
    .js-plotly-plot .updatemenu-container, .js-plotly-plot .slider-container {{
        display: block !important; }}
    @media (prefers-reduced-motion: reduce) {{
        .gm-hero-anim, .gm-hero-anim * {{ animation: none !important; }}
    }}
    .gm-notbuilt {{ border: 1px dashed {c['border_strong']}; border-radius: {RADIUS['lg']};
        padding: 16px 18px; color: {c['text_muted']}; background: {c['surface_alt']}; }}
    .gm-notbuilt b {{ color: {c['text_body']}; }}
    .gm-next {{ display: flex; align-items: center; gap: 12px; }}
    .gm-next .tag {{ font-family: {FONTS['mono']}; font-size: 0.7rem; letter-spacing: 0.07em;
        text-transform: uppercase; color: {c['text_muted']}; }}
    .gm-legend {{ font-family: {FONTS['mono']}; font-size: 0.72rem; color: {c['text_faint']}; }}
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def _register_plotly(c: dict) -> None:
    grid = c["muted_fill"]
    tpl = go.layout.Template(
        layout=dict(
            font=dict(family="IBM Plex Sans, sans-serif", color=c["text_body"], size=13),
            title=dict(font=dict(family="Plus Jakarta Sans, sans-serif", size=16, color=c["text"])),
            paper_bgcolor=c["surface"],
            plot_bgcolor=c["surface"],
            colorway=list(METHOD_COLORS.values()),
            margin=dict(l=56, r=20, t=40, b=48),
            hoverlabel=dict(font=dict(family="IBM Plex Mono, monospace", size=12)),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                        font=dict(size=12), bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(gridcolor=grid, linecolor=c["border_strong"], zeroline=False,
                       ticks="outside", tickcolor=c["border_strong"],
                       tickfont=dict(family="IBM Plex Mono, monospace", size=11)),
            yaxis=dict(gridcolor=grid, linecolor=c["border_strong"], zeroline=False,
                       ticks="outside", tickcolor=c["border_strong"],
                       tickfont=dict(family="IBM Plex Mono, monospace", size=11)),
        )
    )
    pio.templates["gmppt"] = tpl
    pio.templates.default = "plotly_white+gmppt"


# --------------------------------------------------------------------------- #
# Components
# --------------------------------------------------------------------------- #
def _e(s) -> str:
    return html.escape(str(s))


def page_intro(title: str, lead: str = "", eyebrow: str = "") -> None:
    """Page title with an optional one-sentence lead. One per page, at the top."""
    if eyebrow:
        st.markdown(f'<div class="gm-eyebrow">{_e(eyebrow)}</div>', unsafe_allow_html=True)
    st.markdown(f"# {title}")
    if lead:
        st.markdown(f'<p class="gm-lead">{_e(lead)}</p>', unsafe_allow_html=True)


def section_label(text: str) -> None:
    """Small uppercase label above a group of controls."""
    st.markdown(f'<div class="gm-label">{_e(text)}</div>', unsafe_allow_html=True)


def kpi(label: str, value: str, note: str = "", tone: str = "neutral") -> None:
    """A metric card. tone: neutral | good | bad | hero (hero = the page's verdict, one per page)."""
    tone = tone if tone in ("neutral", "good", "bad", "hero") else "neutral"
    st.markdown(
        f'<div class="gm-kpi {tone}"><div class="k">{_e(label)}</div>'
        f'<div class="v">{_e(value)}</div>'
        + (f'<div class="n">{_e(note)}</div>' if note else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def kpi_row(items: Sequence[tuple], weights: Sequence[float] | None = None) -> None:
    """items: [(label, value, note, tone), ...] — note and tone optional."""
    cols = st.columns(weights or [1] * len(items))
    for col, it in zip(cols, items):
        label, value, *rest = it
        note = rest[0] if len(rest) > 0 else ""
        tone = rest[1] if len(rest) > 1 else "neutral"
        with col:
            kpi(label, value, note, tone)


def callout(body: str, title: str = "", kind: str = "caveat") -> None:
    """kind: caveat (amber — read this beside the claim) | limit (red — this cannot be claimed)
    | info (neutral — how to read the chart). Put it next to the figure it qualifies."""
    kind = kind if kind in ("caveat", "limit", "info") else "info"
    t = f'<b class="t">{_e(title)}</b>' if title else ""
    st.markdown(f'<div class="gm-callout {kind}">{t}{_e(body)}</div>', unsafe_allow_html=True)


def engine_badge(engine: str = "simplified", sub_substring: bool = False) -> None:
    """Always shown on any page that draws a simulated curve.
    engine: 'simplified' (app.py NumPy model) | 'validated' (thesis pvlib + Bishop engine)."""
    if engine == "validated":
        st.markdown(
            '<div class="gm-badge ok"><b>validated engine</b> — used for research and '
            'benchmark analysis<br>'
            'single-diode + bypass + reverse bias<br>'
            'matched to ~1% against 616 laboratory flash tests</div>',
            unsafe_allow_html=True,
        )
        return
    warn = ('<br><span class="bad">part-of-a-strip shading: this engine cannot show it</span>'
            if not sub_substring else "")
    st.markdown(
        '<div class="gm-badge"><b>interactive simulator</b> — exploratory configuration and '
        'visualisation, not a benchmark result<br>'
        'single-diode + per-substring bypass (simplified)<br>'
        'reverse-bias avalanche: not modelled<br>'
        'shading detail: one value per substring' + warn + "</div>",
        unsafe_allow_html=True,
    )


def not_built(name: str, what_it_will_do: str) -> None:
    """Greyed, labelled placeholder. Never hide a planned feature, never fake its output."""
    st.markdown(
        f'<div class="gm-notbuilt"><b>{_e(name)} · coming</b><br>{_e(what_it_will_do)}</div>',
        unsafe_allow_html=True,
    )


def next_step(text: str, page, label: str, key: str) -> None:
    """The page's single teal action: a sentence saying why, and a link to the next page.
    page: an st.Page object (or a path string accepted by st.page_link)."""
    with st.container(border=True):
        c1, c2 = st.columns([5, 2], vertical_alignment="center")
        c1.markdown(
            f'<div class="gm-next"><span class="tag">Next</span><span>{_e(text)}</span></div>',
            unsafe_allow_html=True,
        )
        with c2:
            with st.container(key=f"next-{key}"):
                st.page_link(page, label=label)


def run_button(label: str, key: str, **kwargs) -> bool:
    """A dark 'compute something here' button. Use for Run / Simulate / Generate."""
    with st.container(key=f"run-{key}"):
        return st.button(label, key=key, **kwargs)


def legend_note(text: str) -> None:
    """Small mono note under a chart — axis choices, n, units."""
    st.markdown(f'<div class="gm-legend">{_e(text)}</div>', unsafe_allow_html=True)


_LOGO = ('<svg width="28" height="28" viewBox="0 0 30 30" role="img" aria-label="GMPPT Bench">'
         '<circle cx="10" cy="10" r="5" fill="#B5641A"></circle>'
         '<path d="M2 25 C 8 25, 9 13, 15 13 C 21 13, 20 21, 28 21" fill="none" stroke="#16616B" '
         'stroke-width="2.4" stroke-linecap="round"></path></svg>')


def app_header(pages: dict, sections: dict, current: str, routes: dict | None = None,
               theme_key: str = "gm_theme") -> None:
    """The two-level header from the wireframe: wordmark, section tabs, page tabs.

    pages    {key: st.Page or None}   None = not built yet (shown greyed, "coming")
    sections {"Explore": ["panels", "inside", "system"], ...}  first key = section landing
    current  key of the page being shown
    Use together with st.navigation(..., position="hidden")."""
    cur_sec = next((sec for sec, ks in sections.items() if current in ks), None)
    with st.container(key="gm-hdr"):
        with st.container(horizontal=True, vertical_alignment="center", gap="small", key="gm-hdr-top"):
            st.html(_LOGO, width="content")
            with st.container(key="gm-wordmark", width="content"):
                st.page_link(pages["home"], label="GMPPT Bench")
            st.html('<span style="display:inline-block;width:14px"></span>', width="content")
            for sec, keys in sections.items():
                slug = sec.lower().replace(" ", "-")
                if sec == cur_sec:
                    st.html(f'<span class="gm-sec-on">{_e(sec)}</span>', width="content")
                else:
                    with st.container(key=f"gm-sec-{slug}", width="content"):
                        st.page_link(pages[keys[0]], label=sec)
            st.space("stretch")
            if routes and current in routes:
                st.html(f'<span class="gm-route">{_e(routes[current])}</span>', width="content")
            # Animations On/Off sits beside the theme control (§6). Off is a real
            # setting, not a preference hint: the pages build no Plotly frames at
            # all and fall back to their snapshot strips.
            st.html('<span class="gm-route" style="padding-right:6px">Animations</span>',
                    width="content")
            st.segmented_control("Animations", ["On", "Off"], key="gm_anim",
                                 label_visibility="collapsed")
            st.segmented_control("Theme", ["Light", "Dark"], key=theme_key, label_visibility="collapsed")
        if cur_sec:
            with st.container(horizontal=True, gap=None, key="gm-hdr-tabs"):
                for k in sections[cur_sec]:
                    page = pages.get(k)
                    title = page.title if page is not None else k
                    if k == current:
                        st.html(f'<span class="gm-tab-on">{_e(title)}</span>', width="content")
                    elif page is None:
                        st.html(f'<span class="gm-tab-off">{_e(k)} · coming</span>', width="content")
                    else:
                        with st.container(key=f"gm-tab-{k}", width="content"):
                            st.page_link(page, label=title)


def persist_widget_state(keys: Iterable[str] = (), prefixes: Iterable[str] = ()) -> None:
    """Keep widget-bound session keys alive across page changes.

    Streamlit drops a widget's session key on any run in which that widget is not
    rendered — which, in a multipage app, is every run the user spends on another
    page. Re-assigning each key to itself marks it as "set by the app", which
    survives the cleanup pass. Call once per run, before the page body.
    """
    keys = set(keys)
    prefixes = tuple(prefixes)
    for k in list(st.session_state.keys()):
        name = str(k)
        if name in keys or (prefixes and name.startswith(prefixes)):
            try:
                st.session_state[k] = st.session_state[k]
            except Exception:
                pass          # a key Streamlit refuses to re-set is not worth a crash


def provenance(exports: Mapping[str, Mapping]) -> None:
    """Stamp under every figure that came from a harness export.

    exports: {filename: {"path": str|Path|None, "experiment":…, "split":…,
                         "n":…, "seed":…, "version":…}}. Missing fields are
    simply not shown — never filled in with a guess.
    """
    if not exports:
        return
    rows = []
    for fname, meta in exports.items():
        meta = meta or {}
        bits = [_e(str(fname))]
        path = meta.get("path")
        try:
            if path and os.path.exists(path):
                ts = _dt.datetime.fromtimestamp(os.path.getmtime(path))
                bits.append(ts.strftime("%Y-%m-%d %H:%M"))
        except Exception:
            pass
        for label, key in (("experiment", "experiment"), ("split", "split"), ("n", "n"),
                           ("seed", "seed"), ("version", "version")):
            v = meta.get(key)
            if v not in (None, ""):
                bits.append(f"{label}={_e(str(v))}")
        rows.append(" · ".join(bits))
    st.markdown('<div class="gm-legend">source: ' + "<br>source: ".join(rows) + "</div>",
                unsafe_allow_html=True)


_BANNER_CHIP = {
    "sent": ("ok", "sent"),
    "edited": ("warn", "edited since sent"),
    "example": ("warn", "example scenario"),
    "aggregate": ("mute", "aggregate page — not your scenario"),
    "fixed_demo": ("warn", "fixed demo module — not your scenario"),
    "none": ("mute", "no scenario yet"),
}


def scenario_banner(draft: dict | None, sent: dict | None, page_kind: str) -> bool:
    """The strip under the header saying which scenario the page is showing.

    page_kind: 'explore'    reads the draft
               'testing'    reads the sent scenario
               'aggregate'  neither (Compare, Results)
               'fixed_demo' a hardcoded demo module (Dynamic, Relocation)
    Returns True when the user pressed Resend, so the caller can copy draft→sent.
    """
    if page_kind == "aggregate":
        state, shown = "aggregate", None
    elif page_kind == "fixed_demo":
        state, shown = "fixed_demo", None
    elif page_kind == "explore":
        state, shown = ("none", None) if not draft else ("sent", draft)
        if draft and sent and draft.get("hash") != sent.get("hash"):
            state = "edited"
    else:                                              # testing
        if not sent:
            state, shown = "example", None
        else:
            shown = sent
            state = "edited" if (draft and draft.get("hash") != sent.get("hash")) else "sent"

    tone, chip = _BANNER_CHIP[state]
    bits = []
    if shown:
        bits = [shown.get("module", "—"), f"{float(shown.get('temp', 0)):.0f} °C",
                shown.get("pattern", ""), shown.get("geometry_label", ""),
                f"split={shown.get('split', '—')}", f"engine={shown.get('engine', '—')}"]
        bits = [b for b in bits if b]
    body = " · ".join(_e(str(b)) for b in bits) or {
        "aggregate": "Aggregate results over the whole scenario set.",
        "fixed_demo": "This trace runs a fixed demo module, not your scenario.",
        "example": "No scenario sent from Explore — showing the built-in example.",
        "none": "Build a scenario on The panels.",
    }.get(state, "")

    resend = False
    with st.container(key=f"gm-scen-{page_kind}"):
        left, right = st.columns([6, 1.3], vertical_alignment="center")
        left.markdown(
            f'<div class="gm-scenbar"><span class="chip {tone}">{_e(chip)}</span>'
            f'<span class="body">{body}</span></div>', unsafe_allow_html=True)
        if state == "edited" and page_kind == "testing":
            resend = right.button("Resend", key=f"gm-resend-{page_kind}",
                                  use_container_width=True,
                                  help="Copy the scenario you are editing on The panels "
                                       "over the one Testing is running.")
    return bool(resend)


def footer_nav(prev_page, next_page, step: int | None, total: int | None,
               rationale: str = "") -> None:
    """Previous / step counter / Next, at the foot of every page in a section."""
    with st.container(border=True, key="gm-footer"):
        a, b, d = st.columns([2, 1.4, 2.4], vertical_alignment="center")
        with a:
            if prev_page is not None:
                with st.container(key="gm-prev"):
                    st.page_link(prev_page, label=f"← Previous: {_prev_title(prev_page)}")
        if step and total:
            b.markdown(f'<div class="gm-step">Step {int(step)} of {int(total)}</div>',
                       unsafe_allow_html=True)
        with d:
            if rationale:
                st.markdown(f'<div class="gm-next-why">{_e(rationale)}</div>',
                            unsafe_allow_html=True)
            if next_page is not None:
                with st.container(key="gm-next"):
                    st.page_link(next_page, label=f"Next: {_prev_title(next_page)} →")


def _prev_title(page) -> str:
    return getattr(page, "title", str(page))


# --------------------------------------------------------------------------- #
# Animation toolkit (Update 3 §5.2)
#
# One player, used by every animation. The rules it enforces so callers cannot
# break them: a badge always states what kind of thing the animation is; motion
# is Plotly `frames` driven in the browser, never st.rerun; and when animations
# are off the caller gets a static snapshot strip with the same information.
# --------------------------------------------------------------------------- #
ANIM_MAX_FRAMES = 300
ANIM_MAX_JSON_MB = 5.0

_BADGE_TEXT = {
    "recorded": "Recorded playback — harness export. Nothing here is re-run.",
    "live": ("Live illustration — one scenario on the validated engine. Explains "
             "behaviour; not a benchmark result."),
    "schematic": "Schematic — illustrates the idea; not measured data.",
    "sandbox": "Sandbox — simplified engine. Not a benchmark result.",
}
_BADGE_TONE = {"recorded": "ok", "live": "warn", "schematic": "mute", "sandbox": "warn"}


def anim_on() -> bool:
    """The global Animations On/Off switch (§5.2.4). Off => snapshot strips only."""
    return str(st.session_state.get("gm_anim", "On")) == "On"


def anim_badge(kind: str, detail: str = "") -> None:
    """Exactly one of these sits above every animation, saying what it is."""
    kind = kind if kind in _BADGE_TEXT else "schematic"
    tone = _BADGE_TONE[kind]
    extra = f' <span class="detail">{_e(detail)}</span>' if detail else ""
    st.markdown(
        f'<div class="gm-animbadge {tone}"><b>{_e(kind)}</b>'
        f'<span>{_e(_BADGE_TEXT[kind])}</span>{extra}</div>', unsafe_allow_html=True)


def downsample(n: int, key_frames: Iterable[int] = (), max_frames: int = ANIM_MAX_FRAMES):
    """Indices to keep, and the stride used. Key frames are always kept (§5.0.5).

    Integer arithmetic only — this runs before any figure is built and must not
    depend on numpy being importable in the caller's context.
    """
    if n <= max_frames:
        return list(range(n)), 1
    stride = max(1, -(-n // max_frames))          # ceil(n / max_frames)
    keep = set(range(0, n, stride)) | {n - 1} | {int(k) for k in key_frames if 0 <= k < n}
    return sorted(keep), stride


def _speed_buttons(base_ms: int):
    """0.5x / 1x / 2x, plus play and pause, as Plotly layout controls."""
    def play(ms):
        return dict(label=f"{base_ms / ms:.1f}×".replace(".0×", "×"), method="animate",
                    args=[None, {"frame": {"duration": ms, "redraw": True},
                                 "fromcurrent": True,
                                 "transition": {"duration": 0}}])
    return [dict(
        type="buttons", direction="left", x=0, y=1.14, xanchor="left", yanchor="top",
        showactive=False, pad=dict(r=6, t=4),
        buttons=[
            dict(label="▶ Play", method="animate",
                 args=[None, {"frame": {"duration": base_ms, "redraw": True},
                              "fromcurrent": True, "transition": {"duration": 0}}]),
            dict(label="❚❚ Pause", method="animate",
                 args=[[None], {"frame": {"duration": 0, "redraw": False},
                                "mode": "immediate",
                                "transition": {"duration": 0}}]),
            play(base_ms * 2), play(base_ms), play(max(1, base_ms // 2)),
        ])]


def trace_player(frames: Sequence[dict], series: Mapping[str, Mapping], *,
                 curve_panel: bool = True, face_panel: bool = False,
                 timeline: Mapping | None = None, key_frames: Sequence[int] = (),
                 height: int = 620, view: str = "together",
                 x_title: str = "terminal voltage  V", y_title: str = "power  W",
                 static_traces: Sequence = (), frame_ms: int = 120) -> go.Figure:
    """The one shared player. Returns a figure; the caller renders it.

    Static background (the curve, the GMPP, the substring bands) is drawn ONCE in
    `static_traces`; frames update only the per-series marker and trail traces.
    That is what keeps the JSON inside budget — re-embedding an 800-point curve
    in every frame is what blows it.

    `frames` follows the Update 3 schema; fields a frame omits are not drawn.
    """
    fig = go.Figure()
    for t in static_traces:
        fig.add_trace(t)
    n_static = len(fig.data)

    names = list(series)
    # one marker + one trail trace per series, seeded from the first frame
    first = frames[0] if frames else {}
    idx = {}
    for nm in names:
        spec = series[nm]
        trail = (first.get("trails") or {}).get(nm) or []
        fig.add_trace(go.Scatter(
            x=[p[0] for p in trail], y=[p[1] for p in trail], mode="lines",
            line=dict(color=spec.get("color", "#888"), width=1.4, dash="dot"),
            opacity=0.55, showlegend=False, hoverinfo="skip", name=f"{nm} trail"))
        mk = (first.get("markers") or {}).get(nm)
        fig.add_trace(go.Scatter(
            x=[mk["V"]] if mk else [], y=[mk["P"]] if mk else [], mode="markers",
            marker=dict(color=spec.get("color", "#888"), size=12,
                        symbol=spec.get("symbol", "circle"),
                        line=dict(color="#ffffff", width=1)),
            name=nm))
        idx[nm] = (n_static + len(idx) * 2, n_static + len(idx) * 2 + 1)

    order = [i for pair in idx.values() for i in pair]
    plotly_frames = []
    for f in frames:
        data = []
        for nm in names:
            trail = (f.get("trails") or {}).get(nm) or []
            mk = (f.get("markers") or {}).get(nm)
            data.append(go.Scatter(x=[p[0] for p in trail], y=[p[1] for p in trail]))
            data.append(go.Scatter(x=[mk["V"]] if mk else [],
                                   y=[mk["P"]] if mk else []))
        plotly_frames.append(go.Frame(name=str(f.get("step")), data=data, traces=order))
    fig.frames = plotly_frames

    steps = [dict(method="animate", label=str(f.get("step")),
                  args=[[str(f.get("step"))],
                        {"frame": {"duration": 0, "redraw": True},
                         "mode": "immediate", "transition": {"duration": 0}}])
             for f in frames]
    fig.update_layout(
        updatemenus=_speed_buttons(frame_ms),
        sliders=[dict(active=0, x=0, y=-0.02, len=1.0, pad=dict(t=34, b=8),
                      currentvalue=dict(prefix="control step ", font=dict(size=12)),
                      steps=steps)])
    style_fig(fig, height=height, x_title=x_title, y_title=y_title)
    fig.update_layout(legend=dict(orientation="h", y=1.02, x=0.42))
    return fig


def curve_morph(curves: Sequence[Mapping], labels: Sequence[str], *,
                marks: bool = True, key_frames: Sequence[int] = (),
                height: int = 420, frame_ms: int = 220) -> go.Figure:
    """Frames that change the CURVE rather than a marker on it (A4, A5, A9)."""
    fig = go.Figure()
    c0 = curves[0]
    fig.add_trace(go.Scatter(x=c0["V"], y=c0["P"], mode="lines",
                             line=dict(color=LIGHT["teal"], width=3), name="P–V"))
    if marks:
        g = c0.get("gmpp") or {}
        fig.add_trace(go.Scatter(x=[g.get("V")], y=[g.get("P")], mode="markers",
                                 name="true peak",
                                 marker=dict(symbol="star", size=15,
                                             color=PEAK_COLORS["gmpp"])))
    frames = []
    for i, cur in enumerate(curves):
        data = [go.Scatter(x=cur["V"], y=cur["P"])]
        if marks:
            g = cur.get("gmpp") or {}
            data.append(go.Scatter(x=[g.get("V")], y=[g.get("P")]))
        frames.append(go.Frame(name=str(i), data=data,
                               traces=list(range(len(data))),
                               layout=dict(title=dict(text=str(labels[i])
                                                      if i < len(labels) else ""))))
    fig.frames = frames
    fig.update_layout(
        updatemenus=_speed_buttons(frame_ms),
        sliders=[dict(active=0, x=0, y=-0.02, len=1.0, pad=dict(t=34, b=8),
                      currentvalue=dict(prefix="frame ", font=dict(size=12)),
                      steps=[dict(method="animate", label=str(i),
                                  args=[[str(i)], {"frame": {"duration": 0, "redraw": True},
                                                   "mode": "immediate",
                                                   "transition": {"duration": 0}}])
                             for i in range(len(curves))])])
    style_fig(fig, height=height, x_title="terminal voltage  V", y_title="power  W")
    return fig


def snapshot_strip(frames: Sequence[dict], key_frames: Sequence[int],
                   captions: Sequence[str] = (), *, static_traces: Sequence = (),
                   series: Mapping[str, Mapping] | None = None,
                   height: int = 240, key: str | None = None) -> None:
    """Static small multiples of the key frames — the reduced-motion fallback.

    Shown whenever animations are off, and always available under every
    animation so a still can be lifted straight into a thesis figure.
    """
    picks = [k for k in key_frames if 0 <= k < len(frames)] or list(
        range(0, len(frames), max(1, len(frames) // 3)))[:4]
    if not picks:
        return
    cols = st.columns(len(picks), gap="small")
    for col, k in zip(cols, picks):
        f = frames[k]
        fig = go.Figure()
        for t in static_traces:
            fig.add_trace(t)
        for nm, spec in (series or {}).items():
            mk = (f.get("markers") or {}).get(nm)
            if mk:
                fig.add_trace(go.Scatter(
                    x=[mk["V"]], y=[mk["P"]], mode="markers", name=nm,
                    marker=dict(color=spec.get("color", "#888"), size=11,
                                symbol=spec.get("symbol", "circle"))))
        style_fig(fig, height=height, x_title="", y_title="")
        fig.update_layout(showlegend=False, margin=dict(l=30, r=8, t=26, b=26),
                          title=dict(text=f"step {f.get('step')}", font=dict(size=11)))
        with col:
            show_chart(fig, key=f"{key or 'snap'}-{k}")
            cap = captions[picks.index(k)] if picks.index(k) < len(captions) else ""
            if cap:
                st.markdown(f'<div class="gm-legend">{_e(cap)}</div>',
                            unsafe_allow_html=True)


def anim_exports(fig: go.Figure, frames: Sequence[dict], meta: Mapping,
                 *, key: str, name: str = "animation") -> dict:
    """HTML + JSON downloads for an animation, and its measured budget (§5.2.6).

    Neither download needs kaleido. Returns the measurement dict so the caller
    can log frame count, stride, JSON size and build time.
    """
    import json as _json
    payload = {"provenance": dict(meta), "frames": list(frames)}
    js = _json.dumps(payload, default=str)
    try:
        html = fig.to_html(include_plotlyjs="cdn", full_html=True)
        head = (f"<p style='font-family:sans-serif;font-size:13px'>"
                f"{_e(str(meta.get('badge', '')))} — {_e(str(meta.get('detail', '')))}</p>")
        html = html.replace("<body>", "<body>" + head, 1)
    except Exception as e:                                  # pragma: no cover
        html = f"<html><body>could not serialise the figure: {_e(str(e))}</body></html>"
    fig_bytes = len(_json.dumps(fig.to_plotly_json(), default=str).encode())
    a, b = st.columns(2)
    a.download_button("Download animation (HTML)", html, f"{name}.html", "text/html",
                      use_container_width=True, key=f"{key}-html")
    b.download_button("Download frames (JSON)", js, f"{name}.json", "application/json",
                      use_container_width=True, key=f"{key}-json")
    return {"frames": len(frames), "figure_json_bytes": fig_bytes,
            "figure_json_mb": round(fig_bytes / 1e6, 3)}


def anim_budget_note(measured: Mapping, stride: int = 1, build_s: float | None = None):
    """One mono line under every animation stating what it actually cost."""
    bits = [f"{measured.get('frames', '—')} frames"]
    if stride and stride > 1:
        bits.append(f"showing every {stride}{'nd' if stride == 2 else 'rd' if stride == 3 else 'th'} step")
    bits.append(f"{measured.get('figure_json_mb', '—')} MB figure JSON")
    if build_s is not None:
        bits.append(f"built in {build_s:.2f} s")
    st.markdown(f'<div class="gm-legend">{_e(" · ".join(bits))}</div>',
                unsafe_allow_html=True)


def show_chart(fig: go.Figure, key: str | None = None, **kwargs):
    """Always use this instead of st.plotly_chart: theme=None stops Streamlit from
    overriding the GMPPT template (the cause of grey plot areas and wrong fonts)."""
    return st.plotly_chart(fig, theme=None, width="stretch", key=key,
                           config={"displayModeBar": False}, **kwargs)


def add_strip_bands(fig: go.Figure, voc: float, n_sub: int, highlight: int | None = None) -> go.Figure:
    """Shade the voltage range each cell strip can own a peak in (k·V_oc/n), as in the wireframe."""
    c = T()
    for k in range(n_sub):
        x0, x1 = voc * k / n_sub, voc * (k + 1) / n_sub
        fill = c["teal_tint"] if k == highlight else (c["surface_alt"] if k % 2 == 0 else c["surface"])
        fig.add_vrect(x0=x0, x1=x1, fillcolor=fill, opacity=1, layer="below", line_width=0)
        fig.add_annotation(x=(x0 + x1) / 2, y=1.0, yref="paper", yanchor="bottom", showarrow=False,
                           text=f"S{k + 1}", font=dict(family="IBM Plex Mono, monospace", size=11,
                                                        color=c["teal"] if k == highlight else c["text_muted"]))
        if k:
            fig.add_vline(x=x0, line=dict(color=c["border_strong"], width=1, dash="dot"), layer="below")
    return fig


# --------------------------------------------------------------------------- #
# Chart helpers
# --------------------------------------------------------------------------- #
def style_fig(fig: go.Figure, height: int | None = None, y_title: str = "", x_title: str = "") -> go.Figure:
    fig.update_layout(template="plotly_white+gmppt")
    if height:
        fig.update_layout(height=height)
    if y_title:
        fig.update_yaxes(title_text=y_title)
    if x_title:
        fig.update_xaxes(title_text=x_title)
    return fig


def add_reference_lines(fig: go.Figure, x: Iterable, unshaded: Iterable | None = None,
                        available: Iterable | None = None) -> go.Figure:
    """The two reference lines used on every power-over-time chart.
    Gap to the dotted line = shading (hardware's problem).
    Gap to the dark line = tracking (the algorithm's problem)."""
    x = list(x)
    if unshaded is not None:
        fig.add_trace(go.Scatter(x=x, y=list(unshaded), name="If nothing were shading it",
                                 mode="lines", line=dict(color=REF_COLORS["unshaded"], width=2, dash="dot")))
    if available is not None:
        fig.add_trace(go.Scatter(x=x, y=list(available), name="Power available (true peak)",
                                 mode="lines", line=dict(color=REF_COLORS["available"], width=2.5)))
    return fig


def mark_gmpp(fig: go.Figure, v: float, p: float, label: str = "true peak") -> go.Figure:
    fig.add_trace(go.Scatter(x=[v], y=[p], mode="markers+text", name=label,
                             marker=dict(color=PEAK_COLORS["gmpp"], size=12),
                             text=[f"{label} · {p:.1f} W"], textposition="top right",
                             textfont=dict(family="IBM Plex Mono, monospace", color=PEAK_COLORS["gmpp"])))
    return fig


def mark_local_peaks(fig: go.Figure, peaks: Iterable[tuple]) -> go.Figure:
    """peaks: [(v, i, p), ...] as returned in res['lmpps'] by app.module_iv."""
    peaks = list(peaks)
    if peaks:
        fig.add_trace(go.Scatter(x=[pk[0] for pk in peaks], y=[pk[2] for pk in peaks],
                                 mode="markers", name="lower peak",
                                 marker=dict(color="rgba(0,0,0,0)", size=10,
                                             line=dict(color=PEAK_COLORS["local"], width=2))))
    return fig


def method_trace(name: str, x, y, **line) -> go.Scatter:
    """A tracker trace in its fixed colour. name must be a key of METHOD_COLORS."""
    return go.Scatter(x=list(x), y=list(y), name=name, mode="lines",
                      line=dict(color=METHOD_COLORS.get(name, "#6A7177"), width=2.5, **line))