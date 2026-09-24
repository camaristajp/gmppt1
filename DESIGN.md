# GMPPT Bench — design and concept

The design spec behind the wireframes, written so it can be applied to the existing Streamlit simulator (`app.py`). Four files come with it, plus this document:

| File | What it is |
|---|---|
| `gmppt_ui.py` | The design system as code: tokens, CSS, Plotly template, components, chart helpers. |
| `gmppt_app.py` | A new entry point that wraps your `app.py` in the new navigation. Your existing file is imported, not edited. |
| `gmppt_scene.py` | The panels, the shadows and the day: layout, ten shading-event types, per-cell light → per-strip irradiance, and the array / panel-face / timeline figures. |
| `.streamlit/config.toml` | Streamlit theme: widget accent colours, fonts, radius. Streamlit reads this, not CSS, for sliders, pills and chips. |
| `DESIGN.md` | This document: the concept, the rules, and how each page should behave. |

**Five-minute start:** put the files (and the `.streamlit` folder) next to `app.py`, then `streamlit run gmppt_app.py`. Every page renders; the pages that need data you do not produce yet show a labelled "coming" placeholder. Verified headlessly on Streamlit 1.63.0 — all twelve pages render without errors. Requires 1.46 or newer for the top navigation bar; older versions fall back to the sidebar automatically.

---

## 1. The concept

### The story

The dashboard answers four questions, in order. Each section of the navigation is one question.

| Section | The question | Who it is mostly for |
|---|---|---|
| **Explore** | What actually happens when a shadow falls on a panel? | A visitor, a partner engineer, the professor |
| **Simulator** | What are the exact numbers for this panel and this shadow? | The researcher — you |
| **Testing** | Which tracking method copes best, and at what cost? | Supervisor, reviewers, Nanum |
| **The data** | Why should anyone believe these numbers? | Anyone about to quote them |

A first-time visitor reads left to right. An expert jumps straight to the section they need. The story works both ways because every page states its own question in its title and lead sentence.

### The one-sentence version

> A shadow gives a panel's power curve several peaks; ordinary trackers climb the nearest one and stop; our method predicts which peak is tallest from six readings, then lets the ordinary tracker finish — the accuracy of a full search at the cost of a guess.

Every page should be traceable to one clause of that sentence. If a panel on a page supports none of them, it belongs in the research view or nowhere.

### Five design rules

1. **One teal button per page, and it means "next step".** Dark buttons compute something on this page. Outline buttons are secondary. If a page has two teal buttons, one of them is really an export.
2. **A route changes what you look at; a switch changes how.** Shaded versus unshaded is a view switch (a pill), not a page. This rule is what keeps the app at twelve pages instead of thirty.
3. **The caveat sits beside the claim.** A limitation printed on a separate "limitations" page is a limitation nobody reads. Put the amber callout next to the number it qualifies.
4. **Every curve states which engine drew it.** The simplified engine in `app.py` cannot represent part-of-a-strip shading; the validated thesis engine can. The engine badge makes that visible on every page that plots a curve.
5. **Planned features are visible, never hidden and never faked.** A greyed "coming" card with one sentence about what it will do is honest. Empty charts with invented numbers are not.

---

## 2. Information architecture

| Section | Page | Answers | URL | Status | Built from |
|---|---|---|---|---|---|
| — | Home | What is this? | `/home` | Ready | new |
| Explore | The panels | What does a shadow do to the curve? | `/panels` | Ready (single panel) | `module_iv`, `object_to_sub_irr`, `what_happened` |
| Explore | Inside a panel | Why does the curve get extra peaks? | `/panel` | Ready | `module_iv` → `sub_curves` |
| Explore | Whole system | How much electricity reaches the grid? | `/system` | Coming | needs a string + inverter model |
| Simulator | Set up a panel | Exact numbers for this panel | `/simulator` | Ready | `render_simulator` (yours) |
| Simulator | Saved scenarios | Reload and compare saved cases | `/saved` | Ready | `render_scenarios_section` (yours) |
| Simulator | Make a dataset | Thousands of cases, with a seed | `/make-dataset` | Ready | `render_dataset_section` (yours) |
| Testing | Watch one run | What does each method do on one curve? | `/run` | Coming | needs per-step traces from p7/p9 |
| Testing | Compare methods | Which method is best, and what does it cost? | `/compare` | Snapshot | report numbers; replace with harness export |
| Testing | Moving light | Does it hold through a day? | `/moving-light` | Snapshot + coming | needs per-step logging from p10 |
| The data | The dataset | What is in the scenario set? | `/data` | Ready when a dataset exists | `generate_dataset` dataframe |
| The data | Where it comes from | How was this validated, and what can it not say? | `/sources` | Ready | `page_validation` (yours) |

Nothing in your existing app is thrown away. Its six sections all have a home: Home → Home, Simulator → Set up a panel, Analysis → the simulator's own tabs, Dataset → Make a dataset, Scenarios → Saved scenarios, Validation → Where it comes from. The existing app becomes the **Simulator** section; **Explore** and **Testing** are what is new.

### Navigation

Two levels, never three. Section tabs across the top (Explore · Simulator · Testing · The data), page links inside each section. View switches live inside a page as pills. The wordmark always returns home.

---

## 3. The flow

Each page ends with exactly one "Next" bar that says *why* you would go on, then links there:

```
Home ──► The panels ──► Inside a panel ──► Watch one run ──► Compare methods ──► Moving light ──► The dataset
                                                  ▲
Whole system ────────────────────────────────────┘ (to Compare methods)
Simulator pages ──► "Send to the trackers" (Watch one run)
```

| From | Next-step sentence | To |
|---|---|---|
| The panels | You have seen the curve grow extra peaks. Now look at why. | Inside a panel |
| Inside a panel | You know why there are several peaks. Now watch each method try to find the tallest. | Watch one run |
| Whole system | The energy figures rest on the tracking result. See how it was measured. | Compare methods |
| Watch one run | One curve proves nothing on its own. See every method on every shaded case. | Compare methods |
| Compare methods | Now see whether it holds when the light moves. | Moving light |
| Moving light | Every number so far rests on a dataset. See what is in it. | The dataset |

---

## 4. Design tokens

All tokens live in `gmppt_ui.LIGHT` / `gmppt_ui.DARK`. Use the token name in code, never the hex.

### Colour

| Token | Light | Dark | Use |
|---|---|---|---|
| `bg` | `#F7F6F1` | `#0F1A22` | Page ground — warm paper, not pure white |
| `surface` | `#FFFFFF` | `#15232D` | Cards, charts |
| `surface_alt` | `#FCFBF8` | `#1A2B36` | Inputs, inset panels |
| `border` | `#E3DFD4` | `#27404F` | Card edges, dividers |
| `text` | `#15181B` | `#F2F4F5` | Headings, values |
| `text_body` | `#2B3238` | `#D5DCE0` | Paragraphs |
| `text_muted` | `#6A7177` | `#9AA7B0` | Labels, captions |
| `teal` | `#16616B` | `#2FA3AE` | Brand, next-step button, our method |
| `amber` | `#B5641A` | `#E0913F` | The true peak (GMPP); caveats |
| `red` | `#A32B24` | `#E0645B` | Trapped / failed; hard limits |
| `ink` | `#15181B` | `#E9EEF1` | "Run / compute" buttons |

**Fixed-meaning colours** (same on every chart, every page):

| Thing | Colour | Style |
|---|---|---|
| Hybrid (our method) | teal `#16616B` | solid, 2.5–3 px |
| Model only | `#9BBDBF` | solid |
| PSO | `#7FA5A8` | solid |
| P&O | red `#A32B24` | solid |
| InC | `#8A9098` | solid |
| Perfect tracker | `#C9C4B7` | solid, grey |
| True peak (GMPP) | amber `#B5641A` | filled dot |
| Lower peaks | `#8A9098` | hollow ring |
| Operating point | `#2F8F63` | filled dot / dashed line |
| "If nothing were shading it" | amber | dotted |
| "Power available at the true peak" | `#2B3238` | solid dark |

Shading events on the day timeline have their own palette in `EVENT_COLORS` (row in front blue, pole amber, tree green, cloud grey, soiling coral, and so on).

### Typography

| Role | Family | Weight | Size |
|---|---|---|---|
| Page title (h1) | Plus Jakarta Sans | 800 | 44–54 px, letter-spacing −0.035em |
| Section / card title | Plus Jakarta Sans | 700 | 16–18 px |
| Body | IBM Plex Sans | 400 | 14–16 px, line-height 1.55 |
| Labels (small caps) | IBM Plex Sans | 600 | 11–12 px, uppercase, +0.06em |
| Numbers, units, routes | IBM Plex Mono | 400–500 | 12–26 px |

Numbers are always in the mono face, so digits line up in tables and a reader can tell a measured value from prose at a glance. Plus Jakarta Sans was matched by eye to the lab's PI-Solar landing page; if their CSS names a different family, change `FONTS["display"]` and `FONT_IMPORT` and nothing else.

### Space and shape

Spacing steps: 4 · 8 · 12 · 16 · 24 · 32 px. Radii: 8 (inputs), 10 (buttons), 14 (cards), pill (switches). No drop shadows — cards separate by border and ground colour only. Minimum touch target 44 px.

---

## 5. Components

| Component | Call | Use it for | Rule |
|---|---|---|---|
| Page intro | `ui.page_intro(title, lead, eyebrow)` | Top of every page | One sentence lead, stating the page's question |
| Section label | `ui.section_label("1 · The panel")` | Above a group of controls | Number the groups when order matters |
| KPI card | `ui.kpi(label, value, note, tone)` | One headline number | `tone="hero"` at most once per page — it is the verdict |
| KPI row | `ui.kpi_row([...], weights)` | Three or four numbers together | Hero first, widest |
| Callout | `ui.callout(body, title, kind)` | `caveat` amber: read beside the claim · `limit` red: cannot be claimed · `info`: how to read | Place directly under the figure it qualifies |
| Engine badge | `ui.engine_badge("simplified")` | Any page that plots a simulated curve | Always visible; switch to `"validated"` once the thesis engine is wired in |
| Not built | `ui.not_built(name, what_it_will_do)` | Planned features | Greyed and labelled "coming"; never an empty chart |
| Next step | `ui.next_step(text, page, label, key)` | Last element on every page | The page's only teal action |
| Run button | `ui.run_button(label, key)` | Run, Simulate, Generate | Dark, never teal |
| View switch | `st.segmented_control(...)` | Shaded / Unshaded / Both, Power / Efficiency | A pill changes the view, never triggers work |
| Legend note | `ui.legend_note(text)` | Under a chart: axis choices, n, units | "Bars start at 78%, not 0 — …" |

### Button states

| Button | Default | Hover | Disabled |
|---|---|---|---|
| Next step (teal) | teal fill, white text | `teal_dark` | not used — if the next step is unavailable, show the not-built card instead |
| Run (dark) | ink fill, white text | 85% opacity | `st.button(disabled=True)` with a caption saying what is missing |
| Secondary (outline) | surface fill, strong border | border darkens | greyed |

---

## 6. Page specs

### 6.1 Home

Dark is the default theme on every page; Light is the switch. Behind the landing only, a slow moving ground (`gmppt_hero.backdrop`): a dawn glow, a faint cell lattice and patches of light drifting across it like light through cloud (cloud shadows on the paper in Light), parked under reduced motion or Animations off. Landing-only top bar (mark, wordmark, EN/KO, Light/Dark — no section or page tabs; every other page keeps `ui.app_header`). Hero on the left (eyebrow pill, three-line title with GMPPT teal / Bench amber, one-sentence lead, **Start exploring →** teal link to The panels, **▶ Watch a worked example** outline link to Watch one run, the "no account and no setup … 616 flash tests" fine print). On the right, the landing figure in a white card: the same panel unshaded and shaded as two layers with a draggable divider (opens at 50 %), chips `UNSHADED` / `SHADOW ACROSS THE STRIPS`, one amber dot on the true peak and hollow grey rings on the traps, captions inside the figure, "Drag the divider" under it, and a `schematic` note under the card — both curves drawn live by `app.module_iv` (1000/1000/1000 and 1000/250/600 W/m²), never an image. Built in `gmppt_hero.py` as an `st.iframe` document (inline SVG + range input); colours are passed in from `ui.T()`. Below: "What you can do here", five cards, each linking to its page; then the one-line footer.

### 6.2 Explore · The panels

*Question: what does a shadow do to the curve?* **Built** — see `page_panels` and `gmppt_scene.py`.

Three columns and a full-width timeline. Left: **1 · The panels** (model, rows, per row, portrait/landscape, cell strips), **2 · Shading events** (an editable table: event, from, to, dark %, size %), **3 · Conditions** (collapsed: sunlight, temperature). Centre: a time-of-day slider, "Your panels at 11:00", the array drawn top-down with the shadows on it — click a panel to inspect it — and three readouts (all panels right now as the hero, shaded panels, shadow type). Right: the selected panel's face cell by cell, each strip's light and diode state, its P-V curve with the strip bands and a Shaded / Unshaded / Both switch, a plain link to send it to the trackers, then *What happened*, *What the algorithm gets to see*, and the engine badge. Below: the palette of ten events, the day timeline with the playhead, and a strip counting the selected panel's peaks through the day. Next: Inside a panel.

How a shadow becomes an input: each event is a shape (band, blob, half-plane, or the whole array for a cloud) that can move between its start and end. A cell's light is the product over active events of (1 − dark%·inside). A strip's irradiance is its **darkest** cell, because cells in series pass only what the weakest allows. The engine then takes one value per strip. Consequence worth knowing: in portrait, a row-in-front shadow darkens all three strips equally, so this engine shows a dimmer single-peak curve; the real panel would show a step from reverse-bias conduction that only the validated engine models. In landscape the same shadow covers one strip and the extra peaks appear — which is exactly the orientation lesson the page should teach.

*(Original wireframe notes follow.)*
Left column, three numbered cards: **1 · The panel** (model preset, number of cell strips — only divisors of the cell count are offered), **2 · The shadow** (what casts it, how dark, which strips; strips disable for cloud and soiling since those cover everything), **3 · Conditions** (sunlight, temperature). Right: KPI row (power at the true peak as hero, power with no shadow, % lost to the shadow, number of peaks), a Shaded / Unshaded / Both switch, the P-V chart, then `what_happened()` as an info callout beside the engine badge. Next: Inside a panel.

**Coming — the array and the day.** In the wireframe this page shows 15 panels in three strings, draggable shadows, and a day timeline with four lanes (row in front, pole or vent, cloud, soiling) and a playhead. To build it the scenario must become *a list of events plus a clock*:

```python
event = dict(kind="Pole or vent", start="09:20", end="12:40",
             depth=0.74, width=0.55, runs="across", edge="soft", motion="drifts")
def sub_irr_at(t, events, base_G, n_sub) -> list[float]: ...
# then module_iv(sub_irr_at(t, ...), T(t), cells, ref) for each timestep
```

Ten-minute steps (144 per day) are cheap at `n_grid=400`; cloud events need a finer step inside their own window only. Precompute the whole day once and let the playhead index into it — scrubbing then never waits.

### 6.3 Explore · Inside a panel

*Question: why does the curve get extra peaks?*
A terminal-voltage slider (starts at the true peak). From it: current at that point, and a per-strip table — light, whether the bypass diode is on ("on — current goes around"), and the volts each strip adds (−0.7 V when bypassed). Beside it, the I-V curve with the operating point as a dashed line. Info callout: "A bypass diode is a switch, not a dimmer." The "diodes removed" view is coming — it needs the reverse-bias term. Next: Watch one run.

Note: `app.py` computes `bypassed` only at the true peak. This page recomputes it at any point from `sub_curves`: a strip is bypassed wherever its voltage equals −`V_BYPASS`.

### 6.4 Explore · Whole system (coming)

Flow from light on the panels → at the true peaks → after tracking → after DC/DC → after the inverter → AC to grid, with the no-optimizer case beside it. Then hourly generation bars, and a **"Who recovered what"** split: optimizer hardware (Nanum's) versus the algorithm (ours). Assumptions (inverter 97%, DC/DC 98.5%, no clipping) are printed on this page beside the headline, because this is the only page that makes an energy claim.

### 6.5 Simulator pages

Your existing pages, called unchanged, with a `page_intro` added above each. The wireframe's "Set up a panel" adds two things worth porting into `render_simulator` later: the **engine badge** under the result, and a **"Do something with it"** card with *Send to the trackers* (teal), *Save to the scenario library*, *See the circuit behind this curve*, *Generate 5 000 like it*.

### 6.6 Testing · Watch one run (coming)

One curve, every method overlaid: where each starts, the six readings the model takes (numbered p1–p6), the predicted strip shaded, the path P&O climbs to a lower peak in red, the hybrid landing on the amber peak. Right rail: "How the model picks a starting point" in five plain steps — *take six readings, pick a strip, place the starting point, hand over to P&O, safety check*. Below: **Change the shading mid-run** (no change · one shift at step 40 · pole drifts · cloud passes) with a recovery table that stays empty until the pattern-transition experiment runs. Needs per-step `(V, P)` traces from the p7/p9 runners.

### 6.7 Testing · Compare methods

A verdict first (hero: "Hybrid — kept 99.88% of the available power"), two deltas beside it (+20.4 pt vs P&O; 20× fewer readings than PSO). Then one leaderboard, methods as rows, sorted by energy captured, with the perfect tracker as a grey reference row; energy-captured bars start at 78% and say so. Beside it, **What the accuracy costs**: energy lost against readings per cycle, both log scale — the hybrid sits at PSO's loss at a twentieth of the cost. Caveat: hybrid and PSO are tied on energy; the win is cost. A **Research view** toggle (off by default) reveals the funded-target scorecard, the published starting-point methods, the best-possible ceilings and the per-geometry breakdown.

The table in `gmppt_app.py` is a snapshot of the validation report. Replace it with the harness export; the dashboard must never compute headline numbers itself.

### 6.8 Testing · Moving light

Run selector: **My day** (from the panels page) or the EN 50530 sequences. Method chips toggle traces on and off. Top chart: power through the day with the two reference lines (dotted = unshaded potential; dark = available at the true peak). The gap to the dotted line is shading; the gap to the dark line is tracking — only the second is ours. Second chart: power lost to tracking. Under it, a strip of marks for every step a method sat on a lower peak. Metric cards at the bottom. Caveat: the standard profile barely moves the peak, so the margin over P&O is inherited from static trapping.

### 6.9 The data · The dataset

Filter by split and shading type. KPIs (scenarios, how many have more than one peak, largest loss). Charts: where the tallest peak sits (histogram), loss against how dark the shadow is (scatter by shading object). A hand-written "What the graphs say" column sits beside the charts, not under them.

### 6.10 The data · Where it comes from

Your `page_validation`. The wireframe version adds: the chain *laboratory measurement → simulator → scenarios → splitting → scoring*, the untouched test set (opened once), the worst-case guarantee status, **What these numbers cannot tell you**, and **How this run was made** (commit, config hash, split, timestamp).

---

## 7. Charts

- **Power curves:** voltage on x, power on y. True peak = amber filled dot with its value; lower peaks = hollow grey rings. Never colour the curve by method on a single-scenario plot — colour belongs to methods.
- **Over time:** always both reference lines (`ui.add_reference_lines`). Method traces use `ui.method_trace(name, …)` so colours never drift.
- **Axis honesty:** if an axis does not start at zero, say so in a legend note under the chart. Use log scale for losses that span orders of magnitude, and label it.
- **Legends** sit above the plot, horizontal. Hover text in the mono face.
- **One idea per chart.** If a chart needs a paragraph to read, it is two charts.

---

## 8. Words

The rule: a term stays if a semi-formal reader in this field would use it (P&O, PSO, EN 50530, performance ratio, bypass diode); it goes if only the thesis uses it.

| Instead of | Say |
|---|---|
| array | the panels (keep "array" once, as a gloss) |
| module (in body text) | panel — but keep **module optimizer**, the product name |
| seed | the model / starting point |
| probe | reading |
| oracle | perfect tracker |
| GMPP arrival | found the true peak |
| steady-state efficiency | energy captured |
| whole-substring / sub-substring | shadow along the strips / across the strips |
| region error | wrong strip |
| held-out ledger | the untouched test set |
| generalisation gap | gap on unseen panels |
| provenance and limits | where it comes from |
| limits register | what these numbers cannot tell you |
| run stamp | how this run was made |

Sentences: short, active, present tense. Titles are questions or plain nouns, never slogans. Numbers carry their unit and, where it matters, their *n*.

---

## 9. States

| State | Show |
|---|---|
| Empty (nothing to show yet) | Info callout saying what to do first, plus a link to the page that does it |
| Not built | `ui.not_built(...)` — greyed, labelled "coming", one sentence of what it will do |
| Loading (dataset generation, day precompute) | `st.progress` with a count ("1 200 of 5 000"), never a bare spinner for anything over two seconds |
| Error / invalid input | Your existing `validate_datasheet` warnings, shown in place above the inputs, not as a popup |
| Snapshot data | Legend note naming the source run ("snapshot from p7, validation, n = 632") |

---

## 10. Accessibility

Text contrast at least 4.5:1 (the muted grey `#6A7177` on the paper ground passes; do not go lighter). Touch targets at least 44 px. Never rely on colour alone: P&O's failure is red *and* labelled; the true peak is amber *and* has its value written beside it. Every chart has a title that says what it shows. Icon-only buttons get an `aria-label` / `help=`.

---

## 11. Applying it to `app.py`

`gmppt_app.py` already does steps 1–4 without editing your file. Steps 5–8 are the clean-up you do inside `app.py` when convenient.

1. **Entry point.** Run `gmppt_app.py` instead of `app.py`. Your `main()`, `render_topbar()` and `NAV` are no longer called.
2. **Theme.** `ui.setup(theme)` replaces `apply_theme_css`. Keep `sim.TH` in step (already done in `gmppt_app.py`) so your existing Plotly figures still style correctly.
3. **Navigation.** `st.navigation` with sections replaces the segmented-control nav. URLs now work, so a figure in the thesis can carry the link that reproduces it.
4. **Pages.** Your render functions are called unchanged under the Simulator and The data sections.
5. **Internal jumps.** Replace every `st.session_state.section = "…"; st.rerun()` with `st.switch_page(...)` (lines ~1090, 1146, 1373, 1823, 1877). `gmppt_app.go_to("sim_setup")` shows the pattern.
6. **Emoji in labels.** Remove them from headings and nav (`"🔆 Simulator"` → `"Set up a panel"`). Icons, where needed, are stroke icons, not emoji.
7. **Fonts and figures.** Delete the Inter font references; `_style(fig)` can become `ui.style_fig(fig)`. Replace `use_container_width=True` with `width="stretch"` — Streamlit is removing the old argument.
8. **One shading vocabulary.** `preset_sub_irradiance`, `SHADING_OBJECTS` and `REALWORLD_PRESETS` overlap. Keep `SHADING_OBJECTS` + `object_to_sub_irr` (they match the design's shadow palette) and retire the other two before the dashboard binds to them.

---

## 12. Streamlit rules that make the design actually appear

These are the four things that make a Streamlit page look like the wireframe instead of like Streamlit:

1. **Hide Streamlit's navigation and draw your own.** `st.navigation(..., position="hidden")`, then `ui.app_header(...)` before `nav.run()`. Streamlit's top bar cannot show the wordmark, the two levels, or the greyed "coming" tabs.
2. **Never call `st.plotly_chart` directly — use `ui.show_chart`.** By default Streamlit re-themes every Plotly figure (grey plot area, its own fonts and colours). `theme=None` is what lets the GMPPT template through.
3. **Widget colours live in `.streamlit/config.toml`, not CSS.** Slider handles, selected pills and multiselect chips take `primaryColor` from the config; CSS cannot reach all of them reliably.
4. **Style by key, not by position.** `st.container(key="next-…")`, `key="run-…"`, `key="gm-tab-…"` give each element a stable CSS class (`st-key-…`). Selectors based on Streamlit's internal element order break on every upgrade.

## 13. Known gaps (say them before someone else does)

| Gap | Consequence | Fix |
|---|---|---|
| The simplified engine stores one irradiance per strip | Part-of-a-strip shading — 41% of the thesis dataset and the core argument — cannot be shown | Swap `module_iv` for the validated thesis engine; flip the engine badge to `"validated"` |
| No reverse-bias term | "Diodes removed" view cannot be drawn | Comes with the validated engine |
| Tracker runners *keep* the trace but do not export it | Watch one run and Moving light charts have no data to read | Smaller than it looks: `Trajectory` already records `v_hist` / `p_hist` per step (`gmppt/tracking.py`), and p7 says so itself ("No new instrumentation is needed"). The fix is an `--emit` flag in p7/p9/p10 that writes those arrays out as `(t, V, P, method)` — an export, not instrumentation |
| No clock in the scenario | The day timeline cannot run | Events + clock (§6.2) |
| No string or inverter model | Whole system is a placeholder | Declared assumptions first; measured values from Nanum later |
