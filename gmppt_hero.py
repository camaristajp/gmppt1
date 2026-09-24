"""
gmppt_hero.py — the landing page (Home) of the GMPPT Bench dashboard.

Top bar (mark, wordmark, EN/KO, Light/Dark — no section or page tabs), the
two-column hero, the draggable before/after figure, the five "what you can do
here" cards and the one-line footer. gmppt_app.page_home() calls the render_*
functions in order and keeps only what its tests and the tutorial need to see.

The figure's two curves are computed by app.module_iv on the default preset in
app.MODULE_PRESETS, never hand-drawn. It is a schematic: it illustrates the idea
and is labelled so; it never reports a result. The figure is a
st.components.v1.html frame (inline SVG + a range input + a few lines of JS),
so the colours are passed in from ui.T() — the frame does not inherit CSS.
"""
from __future__ import annotations

import numpy as np
import streamlit as st
import streamlit.components.v1 as components

import app as sim
import gmppt_ui as ui

_e = ui._e

# --------------------------------------------------------------------------- #
# Copy — one dict per language, same keys. The EN/KO switch in the top bar
# picks the dict; it is read here and nowhere else (the rest of the app is
# English only).
# --------------------------------------------------------------------------- #
TEXT = {
    "EN": dict(
        eyebrow="AI Lab · Jeju National University × Nanum Energy",
        head_pre="Welcome to the", head_post="Dashboard",
        lead=("Put a shadow anywhere on a solar panel, watch the power curve change "
              "shape, and see which tracking method still finds the true peak."),
        primary="Start exploring  →",
        secondary="▶  Watch a worked example",
        fine=("No account and no setup. Every panel here is simulated on a model "
              "matched to within about one per cent of 616 laboratory flash tests."),
        chip_u="UNSHADED", chip_s="SHADOW ACROSS THE STRIPS",
        cap_u="One peak. Any tracker finds it.", cap_u2="power against voltage",
        cap_s="Three peaks. Only one is the real maximum.", cap_s2="the other two are traps",
        caption=("The same panel on the same afternoon, with and without partial "
                 "shading. Drag the divider."),
        slider="Divider between the unshaded and the shaded panel. Arrow keys move it.",
        schematic_tag="schematic", schematic="Illustrates the idea — not measured data.",
        what="What you can do here", open="Open →",
        cards=[
            ("Build the panel",
             "Pick a 60- or 72-cell module, set the sunlight and the cell temperature, "
             "and start from a clean unshaded curve."),
            ("Place the shadow",
             "Drag a band along the cell strips or across them, choose how dark it is, "
             "and watch which bypass diodes switch on."),
            ("Read the curve",
             "The current and power curves redraw as you go, with the step, every peak, "
             "and the true maximum marked."),
            ("Run the trackers",
             "Send your scenario to the classic algorithms and to the model, and watch "
             "each one search the same curve step by step."),
            ("Compare and export",
             "See how much power each method actually captured, how long it took, and "
             "take the table and figures away as files."),
        ],
        foot_note="Simulated modules only — no field measurements behind these figures yet.",
        foot_link="Where the numbers come from →",
        foot_dept="Dept. of Computer Engineering, Jeju National University",
        lang_help="Language of this page. The rest of the dashboard is in English.",
    ),
    "KO": dict(
        eyebrow="AI Lab · 제주대학교 × Nanum Energy",
        head_pre="", head_post="대시보드에<br>오신 것을 환영합니다",
        lead=("태양광 패널 어디에나 그림자를 드리워 보고, "
              "전력 공선의 모양이 어떻게 바뀜는지, "
              "그리고 어떤 추적 방법이 여전히 진짜 최고점을 "
              "찾아내는지 확인해 보세요."),
        primary="탐색 시작  →",
        secondary="▶  예시 실행 보기",
        fine=("계정도 설정도 필요 없습니다. 이곳의 모든 패널은 "
              "616회의 실험실 플래시 테스트와 약 1% 이내로 "
              "일치하는 모델로 시뮬레이션됩니다."),
        chip_u="그늘 없음", chip_s="스트립을 가로지르는 그림자",
        cap_u="봉우리 하나. 어떤 추적기든 찾습니다.",
        cap_u2="전압 대 전력",
        cap_s="봉우리 셈. 진짜 최대점은 하나뿐입니다.",
        cap_s2="나머지 둘은 함정입니다",
        caption=("같은 오후, 같은 패널 — 부분 음영이 있을 때와 "
                 "없을 때. 구분선을 드래그해 보세요."),
        slider="그늘 없음과 그늘 있음 사이의 구분선. 방향키로 움직입니다.",
        schematic_tag="schematic",
        schematic="개념을 설명하는 그림입니다 — 측정 데이터가 아닙니다.",
        what="여기서 할 수 있는 것", open="열기 →",
        cards=[
            ("패널 구성",
             "60셀 또는 72셀 모듈을 고르고 일사량과 셀 온도를 "
             "설정한 뒤, 그늘이 없는 깨끗한 공선에서 시작합니다."),
            ("그림자 배치",
             "셀 스트립을 따라 또는 가로질러 띄를 놓고 어둡기를 "
             "정한 뒤, 어떤 바이패스 다이오드가 켜지는지 확인합니다."),
            ("공선 읽기",
             "조작할 때마다 전류·전력 공선이 다시 그려지고, "
             "계단과 모든 봉우리, 진짜 최대점이 표시됩니다."),
            ("추적기 실행",
             "시나리오를 고전 알고리즘과 모델에 보내고, 각각이 "
             "같은 공선을 한 단계씩 탐색하는 과정을 지켜봅니다."),
            ("비교와 내보내기",
             "각 방법이 실제로 얼마나 전력을 확보했고 얼마나 "
             "걸렸는지 보고, 표와 그림을 파일로 가져갑니다."),
        ],
        foot_note="시뮬레이션 모듈만 사용 — 아직 이 수치 뒤에 현장 측정은 없습니다.",
        foot_link="수치의 출처 →",
        foot_dept="제주대학교 컴퓨터공학과",
        lang_help="이 페이지의 언어입니다. 대시보드의 나머지는 영어입니다.",
    ),
}

# The page each card opens, in the order of TEXT[lang]["cards"].
CARD_LINKS = ["sim_setup", "panels", "inside", "run", "compare"]
_CARD_ICONS = [
    '<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="2" width="14" height="14" rx="1.5" fill="none" stroke="%(teal)s" stroke-width="1.4"></rect><path d="M6.7 2v14M11.3 2v14" stroke="%(teal)s" stroke-width="1.4"></path></svg>',
    '<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><rect x="2" y="2" width="14" height="14" rx="1.5" fill="none" stroke="%(teal)s" stroke-width="1.4"></rect><path d="M2 11l7-7M5 15l10-10M10 16l6-6" stroke="%(amber)s" stroke-width="1.3"></path></svg>',
    '<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 15c3 0 3-9 6.5-9S12 13 16 3" fill="none" stroke="%(teal)s" stroke-width="1.5" stroke-linecap="round"></path></svg>',
    '<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><path d="M4 3l8 6-8 6z" fill="none" stroke="%(teal)s" stroke-width="1.4" stroke-linejoin="round"></path></svg>',
    '<svg width="17" height="17" viewBox="0 0 18 18" aria-hidden="true"><path d="M3 15V9M8 15V4M13 15v-4" stroke="%(teal)s" stroke-width="1.6" stroke-linecap="round"></path></svg>',
]


def lang() -> str:
    """The landing language: EN unless the top bar's switch says KO."""
    return "KO" if st.session_state.get("gm_lang") == "KO" else "EN"


def text() -> dict:
    return TEXT[lang()]


# --------------------------------------------------------------------------- #
# Physics — app.module_iv on the default preset. Three strips: the unshaded
# panel has every strip at 1000 W/m²; the shaded one has the middle strip at
# 250 and the third at 600. Two shaded levels are needed for THREE peaks — a
# band of one depth across all three strips gives one lower peak, and shading
# the middle strip alone gives two; the brief's three-peak figure needs three
# distinct light levels, so the third strip is lightly shaded as well.
# --------------------------------------------------------------------------- #
UNSHADED_IRR = (1000.0, 1000.0, 1000.0)
SHADED_IRR = (1000.0, 250.0, 600.0)
T_CELL = 25.0
_N_DRAW = 160          # points per curve handed to the browser


def compute_curves(ds: dict, T_c: float = T_CELL) -> dict:
    """Both curves from app.module_iv, thinned for drawing. Pure; see curves()."""
    ref = sim.datasheet_to_ref(ds)
    cps = max(1, int(ds["Ns"]) // 3)
    out = {}
    for name, irr in (("unshaded", UNSHADED_IRR), ("shaded", SHADED_IRR)):
        r = sim.module_iv(list(irr), float(T_c), cps, ref)
        V, P = np.asarray(r["V"], float), np.asarray(r["P"], float)
        idx = np.unique(np.linspace(0, len(V) - 1, _N_DRAW).astype(int))
        out[name] = dict(
            V=[round(float(x), 3) for x in V[idx]],
            P=[round(float(x), 2) for x in P[idx]],
            gmpp=(round(float(r["gmpp"][0]), 3), round(float(r["gmpp"][2]), 2)),
            lmpps=[(round(float(v), 3), round(float(p), 2)) for v, _i, p in r["lmpps"]],
            irr=list(irr), Voc=round(float(r["Voc"]), 3),
        )
    out["vmax"] = max(out["unshaded"]["Voc"], out["shaded"]["Voc"])
    out["pmax"] = max(max(out["unshaded"]["P"]), max(out["shaded"]["P"]))
    return out


@st.cache_data(show_spinner=False)
def curves(ds: dict, T_c: float = T_CELL) -> dict:
    """compute_curves, cached on the datasheet values — edit MODULE_PRESETS and
    the figure follows."""
    return compute_curves(ds, T_c)


# --------------------------------------------------------------------------- #
# The figure: two SVG layers in one box, the top one clipped by the divider
# --------------------------------------------------------------------------- #
_W, _H = 620, 360                       # the artwork's box; everything is anchored to it
_PX, _PY, _PW, _PH = 205, 26, 210, 96   # the panel, centred: (620 - 210) / 2 = 205
_X0, _X1, _Y0, _Y1 = 30, 590, 300, 150  # the plot area: baseline at 300, top at 150


def _chip(x: float, y: float, label: str, fill: str, color: str, anchor_end: bool) -> str:
    w = 7.4 * len(label) + 22
    rx = x - w if anchor_end else x
    tx = x - 11 if anchor_end else x + 11
    return (f'<rect x="{rx:.1f}" y="{y}" width="{w:.1f}" height="22" rx="11" fill="{fill}"></rect>'
            f'<text x="{tx:.1f}" y="{y + 15}" font-family="IBM Plex Mono, monospace" font-size="11.5" '
            f'letter-spacing=".06em" fill="{color}" text-anchor="{"end" if anchor_end else "start"}">'
            f'{_e(label)}</text>')


def _panel(irr, c: dict, dark: bool) -> str:
    cell, line = ("#33556A", "#4A7089") if dark else ("#DCE8E8", "#A8C0C1")
    s = _PW / 3
    out = [f'<rect x="{_PX}" y="{_PY}" width="{_PW}" height="{_PH}" rx="2" fill="{cell}" stroke="{line}"></rect>']
    for k in (1, 2):
        out.append(f'<line x1="{_PX + k * s:.1f}" y1="{_PY}" x2="{_PX + k * s:.1f}" y2="{_PY + _PH}" stroke="{line}"></line>')
    g_max = max(irr)
    band_y, band_h = _PY + 54, 30
    for k, g in enumerate(irr):
        dark_frac = 1.0 - float(g) / g_max
        if dark_frac <= 0.001:
            continue
        out.append(f'<rect x="{_PX + k * s:.1f}" y="{band_y}" width="{s:.1f}" height="{band_h}" '
                   f'fill="{c["amber"]}" opacity="{0.22 + 0.5 * dark_frac:.2f}"></rect>')
    return "".join(out)


def _curve(cv: dict, key: str, c: dict) -> str:
    st_ = cv[key]
    vmax, pmax = float(cv["vmax"]), float(cv["pmax"]) * 1.05

    def X(v):
        return _X0 + float(v) / vmax * (_X1 - _X0)

    def Y(p):
        return _Y0 - float(p) / pmax * (_Y0 - _Y1)

    pts = " ".join(f"{X(v):.1f},{Y(p):.1f}" for v, p in zip(st_["V"], st_["P"]))
    out = [f'<line x1="{_X0}" y1="{_Y0}" x2="{_X1}" y2="{_Y0}" stroke="{c["border_strong"]}"></line>',
           f'<polyline points="{pts}" fill="none" stroke="{c["teal"]}" stroke-width="2.5" '
           f'stroke-linejoin="round" stroke-linecap="round"></polyline>']
    for v, p in st_["lmpps"]:
        out.append(f'<circle cx="{X(v):.1f}" cy="{Y(p):.1f}" r="4.5" fill="none" '
                   f'stroke="{ui.PEAK_COLORS["local"]}" stroke-width="1.6"></circle>')
    gv, gp = st_["gmpp"]
    out.append(f'<circle cx="{X(gv):.1f}" cy="{Y(gp):.1f}" r="6" fill="{c["amber"]}"></circle>')
    return "".join(out)


def _layer(key: str, cv: dict, c: dict, t: dict, dark: bool) -> str:
    shaded = key == "shaded"
    bg = c["amber_tint"] if shaded else c["bg"]
    body = [f'<rect x="0" y="0" width="{_W}" height="{_H}" rx="10" fill="{bg}"></rect>',
            _panel(cv[key]["irr"], c, dark), _curve(cv, key, c)]
    if shaded:
        body.append(f'<text x="{_W - 22}" y="328" text-anchor="end" font-family="IBM Plex Sans, sans-serif" '
                    f'font-size="13" fill="{c["text_body"]}">{_e(t["cap_s"])}</text>'
                    f'<text x="{_W - 22}" y="347" text-anchor="end" font-family="IBM Plex Mono, monospace" '
                    f'font-size="11" fill="{c["amber_text"]}">{_e(t["cap_s2"])}</text>')
        label = t["cap_s"]
    else:
        body.append(f'<text x="22" y="328" font-family="IBM Plex Sans, sans-serif" font-size="13" '
                    f'fill="{c["text_body"]}">{_e(t["cap_u"])}</text>'
                    f'<text x="22" y="347" font-family="IBM Plex Mono, monospace" font-size="11" '
                    f'fill="{c["text_muted"]}">{_e(t["cap_u2"])}</text>')
        label = t["cap_u"]
    return (f'<svg viewBox="0 0 {_W} {_H}" preserveAspectRatio="xMidYMid meet" role="img" '
            f'aria-label="{_e(label)}">{"".join(body)}</svg>')


def _chips_layer(c: dict, t: dict) -> str:
    """Both chips on one unclipped layer over the wipe, anchored to the same
    620×360 box as the artwork: fully visible at every divider position and
    never cut by the card edge."""
    return (f'<svg viewBox="0 0 {_W} {_H}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">'
            f'{_chip(14, 14, t["chip_u"], c["surface"], c["teal"], False)}'
            f'{_chip(_W - 14, 14, t["chip_s"], c["surface"], c["amber_text"], True)}</svg>')


FIGURE_HEIGHT = _H + 14 * 2 + 30 + 2    # card padding, caption, border — the frame's explicit height


def figure_html(cv: dict, c: dict, t: dict, dark: bool) -> str:
    divider = c["text"] if dark else "#FFFFFF"
    return f"""<!doctype html><html lang="{'ko' if t is TEXT['KO'] else 'en'}"><head><meta charset="utf-8">
<link rel="stylesheet" href="{ui.FONT_IMPORT}">
<style>
html,body{{margin:0;padding:0;background:transparent;font-family:{ui.FONTS['body']};}}
.card{{background:{c['surface']};border:1px solid {c['border']};border-radius:16px;padding:14px;box-sizing:border-box;}}
.fig{{position:relative;width:100%;max-width:{_W}px;aspect-ratio:{_W} / {_H};margin:0 auto;border-radius:10px;overflow:hidden;}}
.layer{{position:absolute;inset:0;}}
.layer svg{{display:block;width:100%;height:100%;}}
#top{{clip-path:inset(0 0 0 50%);}}
#chips{{pointer-events:none;}}
.line{{position:absolute;top:0;bottom:0;left:50%;width:3px;margin-left:-1.5px;background:{divider};pointer-events:none;}}
.knob{{position:absolute;top:50%;left:50%;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;
background:{divider};box-shadow:0 1px 6px rgba(0,0,0,.28);display:flex;align-items:center;justify-content:center;
pointer-events:none;color:{'#0F1A22' if dark else c['text']};font:600 13px {ui.FONTS['mono']};letter-spacing:-.05em;}}
.fig.kb .knob{{outline:2px solid {c['amber']};outline-offset:3px;}}
input[type=range]{{position:absolute;inset:0;width:100%;height:100%;margin:0;opacity:0;cursor:ew-resize;
-webkit-appearance:none;appearance:none;background:transparent;}}
input[type=range]::-webkit-slider-thumb{{-webkit-appearance:none;width:44px;height:100%;}}
input[type=range]::-moz-range-thumb{{width:44px;height:100%;border:0;}}
.cap{{margin:10px 0 0 0;text-align:center;font-size:12.5px;line-height:1.5;color:{c['text_muted']};}}
</style></head><body>
<div class="card"><div class="fig" id="fig">
<div class="layer" id="bottom">{_layer("unshaded", cv, c, t, dark)}</div>
<div class="layer" id="top">{_layer("shaded", cv, c, t, dark)}</div>
<div class="layer" id="chips">{_chips_layer(c, t)}</div>
<div class="line" id="line"></div><div class="knob" id="knob" aria-hidden="true">&#8249;&#8250;</div>
<input type="range" id="r" min="0" max="100" step="0.5" value="50" aria-label="{_e(t['slider'])}" aria-valuetext="50%">
</div><p class="cap">{_e(t['caption'])}</p></div>
<script>
(function(){{
var r=document.getElementById('r'),top=document.getElementById('top'),line=document.getElementById('line'),
knob=document.getElementById('knob'),fig=document.getElementById('fig');
function set(v){{v=Math.max(0,Math.min(100,v));top.style.clipPath='inset(0 0 0 '+v+'%)';
line.style.left=v+'%';knob.style.left=v+'%';r.setAttribute('aria-valuetext',Math.round(v)+'%');}}
r.value=50;set(50);                                   /* opens centred on every load */
r.addEventListener('input',function(){{set(parseFloat(r.value));}});
r.addEventListener('focus',function(){{try{{if(r.matches(':focus-visible'))fig.classList.add('kb');}}catch(e){{}}}});
r.addEventListener('blur',function(){{fig.classList.remove('kb');}});
/* the card's own height, not scrollHeight (which never reports less than the frame) */
function fit(){{try{{var h=Math.ceil(document.body.getBoundingClientRect().height);
if(h>40)window.frameElement.style.height=h+'px';}}catch(e){{}}}}
fit();window.addEventListener('resize',fit);
if(window.ResizeObserver){{new ResizeObserver(fit).observe(document.body);}}
}})();
</script></body></html>"""


def _frame(html: str, height: int) -> None:
    """The figure's frame. `st.components.v1.html` is what the brief asked for
    and it still works, but Streamlit 1.63 logs on every render that it is
    deprecated in favour of `st.iframe`, which embeds the same string the same
    way (same-origin srcdoc, scripts allowed). So: st.iframe where it exists,
    components.html where it does not. Either way the height is explicit."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=height)
    else:
        components.html(html, height=height)


# --------------------------------------------------------------------------- #
# Page pieces
# --------------------------------------------------------------------------- #
def home_css(c: dict) -> None:
    st.markdown(
        ("<style>"
         # the landing's top bar: the same card as the app header, without the tabs row
         ".st-key-gm-hdr{padding-bottom:10px!important;}"
         ".gm-home-wordmark{font-family:%(disp)s;font-weight:700;font-size:1.06rem;"
         "color:%(text)s;letter-spacing:-.01em;}"
         ".gm-home-left{max-width:480px;}"
         ".gm-eyebrow-pill{display:inline-flex;align-items:center;gap:8px;padding:7px 14px;"
         "border:1px solid %(amber_border)s;border-radius:999px;background:%(amber_tint)s;"
         "font-family:%(mono)s;font-size:11px;letter-spacing:.07em;text-transform:uppercase;"
         "color:%(amber_text)s;}"
         ".gm-home-h1{margin:16px 0 0 0;font-family:%(disp)s;font-size:54px;font-weight:800;"
         "line-height:1.04;letter-spacing:-.035em;color:%(text)s;}"
         ".gm-home-h1 .t{color:%(teal)s;} .gm-home-h1 .a{color:%(amber)s;}"
         ".gm-home-lead{margin:16px 0 6px 0;font-size:17px;line-height:1.55;color:%(text_body)s;}"
         ".gm-home-fine{margin:14px 0 0 0;font-size:13px;line-height:1.5;color:%(text_muted)s;}"
         "@media (max-width:1100px){.gm-home-h1{font-size:44px;}}"
         ".st-key-hero-primary a{height:52px;padding:0 26px;background:%(teal)s;"
         "color:#fff!important;border:1px solid %(teal)s;border-radius:10px;font-size:15px;"
         "font-weight:600;display:flex;align-items:center;justify-content:center;gap:10px;"
         "text-decoration:none;}"
         ".st-key-hero-primary a:hover{background:%(teal_dark)s;border-color:%(teal_dark)s;}"
         ".st-key-hero-primary a p{color:#fff!important;margin:0;font-weight:600;}"
         ".st-key-hero-secondary a{height:52px;padding:0 22px;background:%(surface)s;"
         "color:%(text)s!important;border:1px solid %(border_strong)s;border-radius:10px;"
         "font-size:15px;font-weight:500;display:flex;align-items:center;justify-content:center;"
         "gap:10px;text-decoration:none;}"
         ".st-key-hero-secondary a:hover{border-color:%(text_muted)s;}"
         ".st-key-hero-secondary a p{color:%(text)s!important;margin:0;}"
         ".st-key-hero-primary a>svg,.st-key-hero-secondary a>svg{display:none;}"
         ".st-key-hero-primary a:focus-visible,.st-key-hero-secondary a:focus-visible{"
         "outline:2px solid %(amber)s;outline-offset:2px;}"
         # the frame sits directly on the page; the card is drawn inside it
         ".st-key-gm-hero-fig iframe{display:block;}"
         ".gm-home-what{margin-top:28px;text-align:center;font-family:%(mono)s;font-size:12px;"
         "letter-spacing:.14em;text-transform:uppercase;color:%(text_muted)s;}"
         "div[class*=\"st-key-gmcards\"]{margin-top:14px;}"
         "div[class*=\"st-key-gmcards\"] div[data-testid=\"stColumn\"]{display:flex;"
         "flex-direction:column;}"
         "div[class*=\"st-key-gmcards\"] div[data-testid=\"stColumn\"]>div{width:100%%;"
         "height:100%%;}"
         "div[class*=\"st-key-gm-card-\"]{box-sizing:border-box;display:flex;flex-direction:column;"
         "height:100%%;min-height:212px;gap:0!important;background:%(surface)s;"
         "border:1px solid %(border)s;border-radius:14px;padding:18px;"
         "transition:border-color .12s ease;}"
         "div[class*=\"st-key-gm-card-\"]>div{flex:0 0 auto;width:100%%;min-height:0;}"
         "div[class*=\"st-key-gm-card-\"]:hover{border-color:%(border_strong)s;}"
         ".gm-ico{width:34px;height:34px;display:flex;align-items:center;"
         "justify-content:center;border:1px solid %(border)s;border-radius:9px;}"
         ".gm-title{margin-top:12px;font-size:15px;font-weight:600;color:%(text)s;}"
         ".gm-desc{margin:6px 0 0 0;font-size:13px;line-height:1.5;color:%(text_body)s;}"
         "div[class*=\"st-key-gm-go-\"]{margin-top:auto!important;padding-top:16px;}"
         "div[class*=\"st-key-gm-go-\"] a{display:inline-flex;align-items:center;"
         "justify-content:center;height:36px;padding:0 16px;border-radius:8px;"
         "background:%(teal)s;color:#fff!important;font-weight:600;font-size:13px;"
         "text-decoration:none;}"
         "div[class*=\"st-key-gm-go-\"] a:hover{background:%(teal_dark)s;}"
         "div[class*=\"st-key-gm-go-\"] a p{margin:0;color:#fff!important;font-weight:600;}"
         "div[class*=\"st-key-gm-go-\"] a>svg{display:none;}"
         ".gm-home-foot{margin-top:28px;padding-top:18px;border-top:1px solid %(border)s;"
         "font-size:12.5px;color:%(text_muted)s;}"
         ".st-key-gm-home-foot{align-items:center;}"
         ".st-key-home-sources a{color:%(teal)s!important;font-weight:600;text-decoration:none;}"
         ".st-key-home-sources a p{margin:0;font-weight:600;font-size:12.5px;}"
         ".st-key-home-sources a>svg{display:none;}"
         ".gm-home-dept{font-family:%(mono)s;font-size:12.5px;color:%(text_muted)s;}"
         "</style>") % {"teal": c["teal"], "teal_dark": c["teal_dark"], "amber": c["amber"],
                        "amber_text": c["amber_text"], "amber_tint": c["amber_tint"],
                        "amber_border": c["amber_border"], "surface": c["surface"],
                        "text": c["text"], "text_body": c["text_body"],
                        "text_muted": c["text_muted"], "border": c["border"],
                        "border_strong": c["border_strong"],
                        "disp": ui.FONTS["display"], "mono": ui.FONTS["mono"]},
        unsafe_allow_html=True)


def backdrop() -> None:
    """Landing only: cloud shadows drifting slowly across a sunlit page.

    The page ground is what the shadows fall on — the cards and the figure stay
    opaque above it. Pure CSS: a faint sun glow (amber; teal in the dark theme)
    that breathes, and three soft shadow blobs (the text colour at 6–8 %; faint
    light patches in the dark theme) that drift left to right over 70–110 s.
    Nothing is blurred with a filter — every shape is a radial gradient and only
    `transform` and `opacity` are animated, so it costs the GPU almost nothing.
    Under prefers-reduced-motion, or with Animations off in the header, the
    shapes stand still at a composed position. Drawn only while Home is the
    page; leaving it takes the styles with it.
    """
    c = ui.T()
    dark = c is ui.DARK
    if dark:
        # night: a teal glow where the sun will rise, a faint cell lattice, and
        # patches of teal and amber light moving over it like light through cloud
        sun = "rgba(47,163,174,.34)"
        c1, c2, c3 = "rgba(47,163,174,.20)", "rgba(224,145,63,.13)", "rgba(47,163,174,.15)"
        lattice = "rgba(242,244,245,.05)"
        sweep = "rgba(242,244,245,.045)"
    else:
        # day: an amber sun, cloud shadows in the ink colour drifting across the paper
        sun = "rgba(181,100,26,.24)"
        c1, c2, c3 = "rgba(21,24,27,.11)", "rgba(21,24,27,.085)", "rgba(21,24,27,.10)"
        lattice = "rgba(21,24,27,.055)"
        sweep = "rgba(181,100,26,.07)"
    on = ui.anim_on()
    st.markdown(
        ("<style>"
         # the app's own grounds go clear so the fixed layer beneath shows through;
         # html/body keep the page colour, so nothing ever flashes white.
         "html,body{background:%(bg)s!important;}"
         ".stApp,[data-testid=\"stAppViewContainer\"],section.stMain,[data-testid=\"stMain\"]"
         "{background:transparent!important;}"
         ".gm-sky{position:fixed;inset:0;z-index:-1;pointer-events:none;overflow:hidden;}"
         # the cell lattice: the ground is a panel
         ".gm-sky .lattice{position:absolute;inset:0;background-image:"
         "linear-gradient(%(lattice)s 1px,transparent 1px),"
         "linear-gradient(90deg,%(lattice)s 1px,transparent 1px);background-size:72px 72px;"
         "-webkit-mask-image:radial-gradient(ellipse at 50%% 40%%,#000 30%%,transparent 85%%);"
         "mask-image:radial-gradient(ellipse at 50%% 40%%,#000 30%%,transparent 85%%);}"
         ".gm-sky .sun{position:absolute;width:70vmax;height:70vmax;right:-24vmax;top:-34vmax;"
         "border-radius:50%%;background:radial-gradient(circle at center,%(sun)s 0%%,"
         "transparent 60%%);will-change:transform,opacity;}"
         ".gm-sky .cloud{position:absolute;left:-70vw;width:64vw;height:56vh;border-radius:50%%;"
         "will-change:transform;}"
         ".gm-sky .c1{top:2%%;background:radial-gradient(ellipse at center,%(c1)s 0%%,transparent 62%%);}"
         ".gm-sky .c2{top:34%%;width:80vw;height:50vh;"
         "background:radial-gradient(ellipse at center,%(c2)s 0%%,transparent 62%%);}"
         ".gm-sky .c3{top:60%%;width:52vw;height:44vh;"
         "background:radial-gradient(ellipse at center,%(c3)s 0%%,transparent 62%%);}"
         # a wide soft band of light sweeping diagonally over the lattice
         ".gm-sky .sweep{position:absolute;top:-60vh;left:-90vw;width:38vw;height:220vh;"
         "transform:rotate(22deg);background:linear-gradient(90deg,transparent,%(sweep)s,transparent);"
         "will-change:transform;}"
         "@keyframes gm-drift{from{transform:translateX(0);}to{transform:translateX(180vw);}}"
         "@keyframes gm-breathe{from{opacity:.6;transform:scale(1);}"
         "to{opacity:1;transform:scale(1.08);}}"
         "@keyframes gm-sweep{from{transform:translateX(0) rotate(22deg);}"
         "to{transform:translateX(230vw) rotate(22deg);}}"
         ".gm-sky.on .sun{animation:gm-breathe 14s ease-in-out infinite alternate;}"
         ".gm-sky.on .cloud{animation:gm-drift 80s linear infinite;}"
         ".gm-sky.on .c1{animation-delay:-16s;}"
         ".gm-sky.on .c2{animation-duration:104s;animation-delay:-58s;}"
         ".gm-sky.on .c3{animation-duration:68s;animation-delay:-37s;}"
         ".gm-sky.on .sweep{animation:gm-sweep 46s linear infinite;animation-delay:-12s;}"
         # still: the same shapes, parked where a frame of the animation would put them
         ".gm-sky:not(.on) .c1{transform:translateX(52vw);}"
         ".gm-sky:not(.on) .c2{transform:translateX(96vw);}"
         ".gm-sky:not(.on) .c3{transform:translateX(24vw);}"
         ".gm-sky:not(.on) .sweep{transform:translateX(120vw) rotate(22deg);}"
         "@media (prefers-reduced-motion: reduce){"
         ".gm-sky .sun,.gm-sky .cloud,.gm-sky .sweep{animation:none!important;}"
         ".gm-sky .c1{transform:translateX(52vw);}.gm-sky .c2{transform:translateX(96vw);}"
         ".gm-sky .c3{transform:translateX(24vw);}.gm-sky .sweep{transform:translateX(120vw) rotate(22deg);}}"
         "</style>"
         '<div class="gm-sky %(cls)s" aria-hidden="true"><div class="lattice"></div><div class="sun"></div>'
         '<div class="cloud c1"></div><div class="cloud c2"></div><div class="cloud c3"></div>'
         '<div class="sweep"></div></div>')
        % {"bg": c["bg"], "sun": sun, "c1": c1, "c2": c2, "c3": c3, "lattice": lattice,
           "sweep": sweep, "cls": "on" if on else "still"},
        unsafe_allow_html=True)


def top_bar() -> None:
    """Landing only: mark + wordmark, EN/KO, Light/Dark. No section or page tabs."""
    t = text()
    with st.container(key="gm-hdr"):
        with st.container(horizontal=True, vertical_alignment="center", gap="small",
                          key="gm-hdr-top"):
            st.html(ui._LOGO, width="content")
            st.html('<span class="gm-home-wordmark">GMPPT Bench</span>', width="content")
            st.space("stretch")
            ui.guide_button(None, "home")
            st.segmented_control("Language", ["EN", "KO"], key="gm_lang",
                                 label_visibility="collapsed", help=t["lang_help"])
            st.segmented_control("Theme", ["Light", "Dark"], key="gm_theme",
                                 label_visibility="collapsed")


def render_hero(P: dict) -> None:
    c, t = ui.T(), text()
    dark = c is ui.DARK
    home_css(c)
    backdrop()
    left, right = st.columns([0.46, 0.54], gap="large", vertical_alignment="center")
    with left:
        pre = f'{_e(t["head_pre"])}<br>' if t["head_pre"] else ""
        st.markdown(
            f'<div class="gm-home-left"><span class="gm-eyebrow-pill">'
            f'<svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">'
            f'<circle cx="5" cy="5" r="4" fill="{c["amber"]}"></circle></svg>{_e(t["eyebrow"])}</span>'
            f'<h1 class="gm-home-h1">{pre}<span class="t">GMPPT</span> <span class="a">Bench</span>'
            f'<br>{t["head_post"]}</h1>'
            f'<p class="gm-home-lead">{_e(t["lead"])}</p></div>', unsafe_allow_html=True)
        # A wrapping row, not fixed-ratio columns: in a narrow column the second
        # button drops to the next line instead of clipping the first's label.
        with st.container(horizontal=True, gap="small", key="gm-hero-buttons"):
            with st.container(key="hero-primary", width="content"):
                st.page_link(P["panels"], label=t["primary"])
            with st.container(key="hero-secondary", width="content"):
                st.page_link(P["run"], label=t["secondary"])
        st.markdown(f'<div class="gm-home-left"><p class="gm-home-fine">{_e(t["fine"])}</p></div>',
                    unsafe_allow_html=True)
    with right:
        cv = curves(dict(sim.MODULE_PRESETS[sim.DEFAULT_PRESET]))
        with st.container(key="gm-hero-fig"):
            _frame(figure_html(cv, c, t, dark), FIGURE_HEIGHT)
        st.markdown(
            f'<div class="gm-animbadge mute"><b>{_e(t["schematic_tag"])}</b>'
            f'<span>{_e(t["schematic"])}</span></div>', unsafe_allow_html=True)


def render_cards(P: dict) -> None:
    c, t = ui.T(), text()
    st.markdown(f'<div class="gm-home-what">{_e(t["what"])}</div>', unsafe_allow_html=True)
    with st.container(key="gmcards"):
        cols = st.columns(5, gap="small")
        for col, (title, desc), icon, key in zip(cols, t["cards"], _CARD_ICONS, CARD_LINKS):
            with col:
                with st.container(key=f"gm-card-{key}"):
                    st.markdown(
                        f'<span class="gm-ico">{icon % {"teal": c["teal"], "amber": c["amber"]}}</span>'
                        f'<div class="gm-title">{_e(title)}</div>'
                        f'<p class="gm-desc">{_e(desc)}</p>', unsafe_allow_html=True)
                    with st.container(key=f"gm-go-{key}"):
                        st.page_link(P[key], label=t["open"])


def render_footer(P: dict) -> None:
    t = text()
    st.markdown('<div class="gm-home-foot"></div>', unsafe_allow_html=True)
    with st.container(horizontal=True, vertical_alignment="center", gap="medium",
                      key="gm-home-foot"):
        st.html(f'<span class="gm-home-dept" style="font-family:inherit">{_e(t["foot_note"])}</span>',
                width="content")
        with st.container(key="home-sources", width="content"):
            st.page_link(P["sources"], label=t["foot_link"])
        st.space("stretch")
        st.html(f'<span class="gm-home-dept">{_e(t["foot_dept"])}</span>', width="content")
