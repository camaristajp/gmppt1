# CHANGELOG — dashboard revision

## Research-workflow navigation — Scenario · Static test · Dynamic test · Results · Data & validation · Sandbox (2026-09-25)

Information architecture and the pages that carry it. **Not changed:** PV/device physics, bypass and breakdown models, the tracker implementations, the proposed hybrid, the trained model, the scorer definitions, the benchmark scenario definitions, the split, the research metrics, and every validated export (`tests/test_app_smoke.py::test_T16_dashboard_never_writes_to_phase2` still hashes `results/phase2/` before and after).

### Navigation (`gmppt_ui.app_header`, `gmppt_app.STAGES`)
- The header is the six research sections, side by side, **no arrows**: SCENARIO · STATIC TEST · DYNAMIC TEST · RESULTS · DATA & VALIDATION, then SANDBOX behind a gap. Section keys are slugged to `[a-z0-9-]` for the container CSS class. The active sub-page gets a lighter treatment (2 px underline on a tint) than the section's filled pill. The old labels Understand / Inspect / Watch / Compare / Explore are gone from every user-facing string; the test suite scans for them.
- `STAGES` is the one table: `Scenario [panels, inside]`, `Static test [run, static_compare]`, `Dynamic test [timeline, tracker_response, energy]`, `Results [summary, compare, dynamic_perf, results]`, `Data & validation [benchset, validation, sources]`; `SANDBOX = [sim_setup, sim_saved, sim_sweep, sim_dataset]`. `ui.FLOW_STAGES` matches. No unbuilt page is offered: the planned "Whole system" page is removed (its content lives on Build system's Whole-system scope).
- Footer: the numbered journey is Build system → PV analysis → One run → Compare methods → Timeline → Tracker response → Energy → Research summary; the other Results, Data & validation and Sandbox pages get Previous / Next within their section, unnumbered.

### Scenario
- **Build system** (`page_panels`, `/panels`): unchanged in function; retitled; the legacy day-event editor under it is removed and replaced by a pointer to Dynamic test · Timeline.
- **PV analysis** (`page_inside`, `/panel`): reads `scenario_draft`, edits nothing. New top row: the handed panel's face with the shadow, each section's light and bypass state at the true peak (through the one `_diode_state` rule) with the generated sentence, and the shaded/unshaded P–V overlay; KPIs true peak / no shadow / lost to shade / peaks. Then the operating-point section, substring state, the A3 sweep and A4 ramp as before.

### Static test (the user's scenario — `Exploratory` chip)
- **One run** (`page_run`): retitled; links to Compare methods and to the validated Static performance.
- **Compare methods** (`page_static_compare`, new, `/compare-methods`): P&O, InC, PSO, Model only, Hybrid (bounded) · proposed, Hybrid (free), Perfect tracker on the same sent condition. Same landscape with every method's start (open circle), path (dotted) and stop; horizontal bars of steady-state efficiency; table GMPP reached · tracking efficiency · convergence (conditional on arrival) · readings/evaluations · power loss — all from `_run_scenario` / `_score_traj`, i.e. `gmppt.tracking.Trajectory.metrics`, never re-scored. One rule for which scenario runs: `_static_scenario` (the sent one; the example only while nothing is sent). CSV/JSON downloads.

### Dynamic test (the user's scenario — `Exploratory` chip) — `gmppt_timeline.py` (new, pure) + three pages
- **Timeline** (`page_timeline`, `/timeline`): inherits the PV SYSTEM from `scenario_sent` (`sent["system"]`, `sent["system_hash"]`); nothing about the topology is editable or rebuilt here. Adds G(t) = peak × clear-sky arc 06:00–18:00, T(t) = dawn → noon on the same arc, and shading events (shape from Scenario's own list, target panel or every panel for Cloud/Dirt, light left as a share of the sun at that moment, position, window, motion: fixed / drifts across the panel / deepens). Playhead slider; three-lane timeline figure (G, T, event lanes, condition changes dotted); the system at the playhead through `tl.state_at` — KPIs, tracked panel face, topology with shaded panels tinted, P–V now with the no-shadow reference. Writes `dynamic_scenario` (`base_system_hash`, tracked panel, sun, temperature, events, slices, hash). "Use an instant in the Sandbox": canonical-minute records (`time_minutes`, `start_minutes`, …) for the existing irradiance-only import.
- **Canonical time everywhere:** minutes after midnight (`gmppt_scenario.time_to_minutes` etc.). The 06:00–18:00 day-fraction mapping (`_day_event_state`, `_day_window_from_hour`, `t0/t1` fractions) is deleted; events restored from an older session are converted by `tl.migrate_legacy_events` and marked "converted from …". One shadow function: `tl.shadow_at` → `gmppt_scenario.shadow_pattern`, read by drawing and engine alike; two shadows on a panel combine as the darker, section by section.
- **Tracker response** (`page_tracker_response`, `/tracker-response`): `_timeline_run` builds one validated-engine curve per slice (48 × 8 control steps), a `gmppt.dynamic.DynamicTrajectory`, runs P&O, InC, PSO, Hybrid (bounded), Model only, and scores with the harness's `metrics()`. Per-slice G2 curve-integrity gate reported. One playhead drives the system view, the curve with each tracker's operating point, and the power-over-day chart (condition changes as dotted lines, re-convergence points as open diamonds). Table: dynamic efficiency, energy captured/lost (Wh), worst instant loss, re-converged k of n changes, median re-convergence steps (the harness's convergence rule applied per segment, `tl.reconvergence_steps`; dash = censored), readings, reseed/trigger ("none in this variant"). The seed's one temperature (dawn) is stated. A5/A6 playbacks replay this run. The EN 50530 ramp on the same handed panel (formerly Dynamic irradiance's live traces + A7) sits under an expander here.
- **Energy** (`page_energy`, `/energy`): captured Wh and share of available per method, the shaded loss area over the day for one method, lost-to-shading vs lost-to-tracking, CSV and run JSON.
- **System changed:** if `scenario_sent.system_hash != dynamic_scenario.base_system_hash`, Tracker response and Energy say so; Timeline reviews the events (drops those aimed at panels that no longer exist, keeps the rest) and rebinds to the new system.

### Results (validated exports only — `Benchmark result` chip, static figures)
- **Research summary** (`page_summary`, new): four cards (static arrival, dynamic efficiency, convergence, cost per cycle) and the P&O · InC · PSO · proposed table with the arrival-rate bar, all from `tracker_comparison_val`, `pso_comparison_val`, `dynamic_comparison_30-100_val`; generated "what the evidence supports" sentences; provenance.
- **Static performance** = the former Compare methods (`page_compare`), retitled. **Dynamic performance** (`page_dynamic_perf`): the p10 export for Seq 30-100 / 10-50 (KPIs, method table with shaded/uniform and s.e., the reseed negative result) plus the p12 relocation section (`_relocation_section`, the former Shading relocation page, unchanged in content). **Targets** = the former Results vs targets. The test suite asserts none of these functions touch `scenario_sent`, `dynamic_scenario`, a tracker run, or Sandbox state.

### Data & validation
- **Benchmark set** retitled. **PV model validation** (`page_validation_model`, new): the two engines, reference source and procedure (S2–S5 legs), what the model cannot claim, and app.py's validation record. **Experiment provenance** (`page_provenance`, replaces Where it comes from at `/sources`): one row per export — script, status, experiment, split, n, seed, version, method variants, written — plus the trained model file, the input sources and `config.provenance()`.

### Sandbox
- Persistent indicator on every page: `Sandbox · simplified engine · not benchmark evidence`. Pages: Simulator (the parametric-sweep tab moved out), Saved scenarios, **Sweep** (new page for `app.render_sweep`), **Dataset generator** (Make a dataset + the former Sandbox dataset view beneath it).

### Removed / migrated
- Removed dead code: `_event_pattern`, `_scenario`, `_set_draft`, `_dual_sel`, `_dual_num`, `_array_svg`, `_daytimeline_svg`, `_module_face_svg`, the whole `_day_*` block and `_day_run`, `_legacy_day_section`, `_your_day`, `page_system`, `page_moving`, `page_dataset`, `page_sources`. Session files: `day_events` are migrated on the first Timeline visit; `tl_events` and `dynamic_scenario` are saved and restored.
- Persisted keys: `tl_*`, `tr_time`, `tr_show`, `en_show`, `sc_show`, `dp_seq`; prefix `tlw_` for per-event widgets (buttons are `tl_*`, so no prefix reaches one).

### Verified
- `pytest tests/test_timeline.py tests/test_app_smoke.py tests/test_hero.py tests/test_layout.py tests/test_scenario_state.py tests/test_scenario_physics.py`: 129 passed, including the new acceptance tests (six sections, no arrows, no unbuilt page; Results reads exports only; Dynamic test inherits the sent system and runs the harness's DynamicTrajectory; Static test runs the sent scenario through one rule; Sandbox labelled and never read by Results) and `tests/test_timeline.py` (canonical minutes, sun/temperature arcs, `shadow_at` = Scenario's shadow, drift/deepen motions, state_at on a 3S × 2P system, darker-wins combination, change points, the re-convergence rule incl. censoring, hash sensitivity, legacy migration, canonical sample records, the figure).
- Headless, through `AppTest` (`tests/test_pages_render.py`, new): every one of the 18 navigation pages renders without an exception; then Build system → Send → One run → Compare methods → Timeline (+ event at the playhead, window edited to 09:00–11:30, playhead inside the event shows the active shadow) → Tracker response (table carries Hybrid (bounded) · proposed, re-convergence "k of 2") → Energy; a legacy `day_events` session converts to a drifting Pole 09:00–12:00; rebuilding the system to 2S and re-sending raises "System changed" on Tracker response and "timeline reviewed" on Timeline with the event kept; the Sandbox import lands with the "Irradiance from Dynamic test · Timeline" note.

## Layout revision — collapsible Scenario cards, equal-height sibling cards (2026-09-25)

UI only. No physics, state schema, hash, tracker or benchmark change; all 111 dashboard/device tests and the 48-check Scenario browser run are unchanged.

### The layout rule (design system, `gmppt_ui.py`)
- Documented beside the card styles: *sibling cards representing equivalent metrics or options in the same horizontal row stretch to the height of the tallest sibling; height equality is row-local and semantic.*
- `ui.sibling_row(weights)` — columns inside a keyed `gm-siblings-<n>` container whose CSS runs the flex stretch through every Streamlit wrapper between the column and the card (column → block → element → markdown → its inner wrapper → container → card). No per-card pixel heights anywhere. A container query stacks the siblings when the row is narrower than 300 px; stacked, the rule relaxes by itself.
- `ui.kpi_row(items, weights=None, equal_height=True)` uses it, so every KPI / metric row on every page follows the rule. The KPI card is now label (one line) / value (one line, shrinks below 150 px instead of wrapping) / note, so labels, values and the notes' first lines align across a row and the stretch aligns the bottoms.
- `ui.collapsible(title, key, summary, open_note, expanded)` — a styled keyed `st.expander` (the native, accessible control: real button, keyboard focus, `open` state, chevron at the right edge), with the state-derived summary in the header while collapsed and an optional muted note while open. Cards are independent; none closes another.

### Scenario
- Cards 1–3 are collapsible with keys `scenario_system_expanded`, `scenario_conditions_expanded`, `scenario_shading_expanded` (view state, in `_PERSIST_KEYS`, never in a record or hash). Collapsed summaries come from the live session values: "1 panel · 72-cell c-Si", "15:00 · 910 W/m² · 43 °C", "No shade" / "Pole · Panel 1 · 240 W/m²" / "shadow on N panels".
- What it makes: chart 230 → 260 px; the three KPIs are equal-width siblings.

### Verified (Chrome DevTools, 38/38)
Fresh load: all three open. Three KPI cards at identical 105 px with identical top, bottom, value and note offsets; no value overflow. Collapsing card 1 leaves both hashes and "● not sent yet" untouched; a Pole shadow then moves the scenario hash only and card 1 stays collapsed; card 3 reads "Pole · Panel 1 · 240 W/m²" when folded, card 2 "15:00 · 910 W/m² · 43 °C"; all three stay collapsed after Watch → Understand; the summary takes keyboard focus and Enter/Space reopens it. Light theme: equal heights. Compare methods: its sibling KPI rows are equal within 1 px. 820 px: no horizontal overflow, the KPI row stacks and no value is clipped.

## Scenario page — build the PV system once; static → dynamic contract (2026-09-25)

**Understand · The panels** is now **Understand · Scenario** (url slug `panels` kept). The page owns the PV system; the static tracker page consumes one frozen snapshot of it; the future dynamic timeline will inherit it unchanged and vary G(t), T(t), Shade(t).

### Engine (the one authorised change)
- `gmppt/device.py`: **`array_iv(mp, string_irradiances, T, n_substrings, bd, bp, blocking_diodes=True, n_points)`** appended. Strings in parallel on a common ascending voltage grid, each string from the unchanged `string_iv`, contributions clipped at zero (blocking diodes). A one-string array returns the string's own curve, exactly. `blocking_diodes=False` raises `NotImplementedError`: the engine has no forward-conduction branch above V_oc, so reverse current through an unprotected string cannot be computed without new physics — refused, not invented. Nothing existing was modified; `tests/test_s3_device.py` and `test_s5_array.py` unchanged and green.

### State (`gmppt_scenario.py`, new)
- **PV SYSTEM** `{module, n_series, n_parallel, optimisers_enabled, blocking_diodes, panels[{uid, display_id S<r>-M<p>, row, pos, shadow}]}` → `system_hash`. **STATIC CONDITION** `{time_minutes, temperature_c, base_irradiance, module_irradiances[row][module], shadow_metadata}` → `scenario_hash = f(system_hash, condition, geometry)`. Deterministic JSON, sorted keys, sha1[:12]. View state (selected panel, chart scope, Lab details, the drawing's click event) never enters either.
- Panels have uids; topology changes map by (row, pos): growing keeps every existing panel and its shadow and adds unshaded ones, shrinking drops only the vanished places. Shading is per panel (widgets keyed by uid: `shp_ / drk_ / pos_`, persisted).
- Shadow shapes (Pole, Tree, Leaf, Dirt, Cloud, None + how dark + where it falls) are presentation; the engine only sees `module_irradiances`, produced in exactly the form `module_iv` / `string_iv` accept (Leaf → the nested sub-substring entry). Scenario geometry = most complex present via the existing `geometry_of`.
- Time is minutes after midnight (`minutes_to_hhmm`, `hhmm_to_minutes`, `time_to_minutes`, `minutes_to_time`); 15:00 ↔ 900. No fractions anywhere in the new state.
- `scenario_draft` / `scenario_sent` keep the legacy keys (`module`, `temp`, `irr`, `label`, `hash`, …) so Inside a panel, Watch one run and the banner work unchanged; `irr` is the **handed panel**: the most shaded panel by rule (ties → topology order), never the one being looked at. The record also carries `schema_version: 2`, `system`, `system_hash`, `static_condition`, `focus_panel`.

### Page
- Left: 1 · Your PV system (panel type, panels in a row, rows, "Every panel has its own optimiser" shown only above one panel, "N panels" / lab `4S × 2P · 8 modules · 3 substrings/module`) · 2 · Conditions (Time, Sunlight 100–1000, Cell temperature) · 3 · Shading for the selected panel. Centre: the topology drawing (series links, DC bus; click a panel to select it; Prev / Select / Next; Reset inspected panel), the selected panel's face (6 × 10 cells, three sections, shadow, sun), section badges (working / bypassed / partly bypassed, from `_diode_state`) and a sentence generated from that state. Right: 4 · What it makes (This panel / The row / Whole system; row and system locked at one panel; dotted no-shadow reference; "the real peak" or lab "GMPP"; Making now / No shadow / Peaks from `analyse`) with, at Whole system, the per-panel-optimiser sum as Making now and "With one shared tracker instead — N W" (or the reverse when optimisers are off), labelled an instantaneous comparison; 5 · Hand it to the tracker (generated summary, lab hashes, ● not sent yet / sent / changed since sent, Send this setup → Send again, no navigation; the footer's Next navigates).
- Fresh session: 1S × 1P, 1 panel. Older sessions keep `gm_per` / `gm_rows`.
- The day-event editor stays below the new layout, verbatim and unconnected (pending migration to canonical minutes). `_event_pattern`, `_array_svg`, `_module_face_svg`, `_set_draft` are now unused and left in place.
- Copy: every "The panels" reference in Inside a panel, Watch one run, Sandbox, Dynamic irradiance, Sources, the banner and the Home card now says Scenario.

### Limitation surfaced, not worked around
- `string_iv` wraps each module pattern in `np.asarray(..., dtype=float)`, so a row cannot contain a nested (Leaf / sub-substring) entry: `ValueError: inhomogeneous shape`. The page offers Leaf on a single panel only, keeps a surviving Leaf when panels are added, and shows an explicit limit state for The row / Whole system while one is present. The fix is one line in a protected file and was not made.

### Verified
- `pytest tests/` (viz excluded): all green — 155 tests including `tests/test_scenario_physics.py` (T3 one-module string = module_iv with `array_equal` I and |ΔV| < 1e-9, three patterns; T4 one-string array = string to 1e-9 at the GMPP; T5 two identical strings: P and I ratio 2.000 ± 0.005, whole curve to 0.5 %; T6 `P_array ≥ P_healthy` and the array current above the weak string's V_oc equals the healthy string alone to 0.5 %; unprotected case raises; T12 unshaded 1×1, 2×1, 1×2, 3×2: shared / optimised = 1 ± 0.005) and `tests/test_scenario_state.py` (T1, T7, T8, T9, T10, T11, T13, patterns, focus rule, summary).
- Chrome DevTools, 48/48: fresh 1S × 1P; no optimiser box, views locked; Lab details shows `hash · system · handed panel`; 3S × 2P changes both hashes; Pole on S1-M01 changes the scenario hash only and hands S1-M01; Next → S1-M02 changes neither hash; Leaf hidden; Send → ● sent; selection keeps ● sent; Tree → ● changed since sent; Send again → ● sent; Whole system shows the comparison strip; a click on the drawing selects S2-M03 and keeps ● sent; Watch shows the sent scenario, not the example; back on Scenario the 3S × 2P survives and rows = 1 keeps S1-M01's Tree.

## Landing page — hero with a draggable before/after divider (2026-09-23)

Scope: Home only. `page_home` is now drawn by the new `gmppt_hero.py`; `gmppt_app.py` keeps the tutorial's step targets, the "Show tutorial again" button and the session save/restore expander.

### Structure (top to bottom)
1. **Top bar, landing only** — mark + wordmark, EN/KO, Light/Dark. No section or page tabs: `_wrapped` calls `hero.top_bar()` for `home` and `ui.app_header(...)` for every other page.
2. **Hero** — left column (max 480 px): amber eyebrow pill "AI Lab · Jeju National University × Nanum Energy", three-line heading with GMPPT teal / Bench amber, the lead, teal **Start exploring →** (The panels) and outline **▶ Watch a worked example** (Watch one run) as `st.page_link` in a wrapping row, and the restored fine print ("No account and no setup … 616 laboratory flash tests"). Right column: the figure card, then the restored `schematic` tag + "Illustrates the idea — not measured data."
3. **Figure** — `st.iframe` (fallback `st.components.v1.html`): two full-box SVG layers (unshaded under, shaded over, `clip-path: inset(0 0 0 p%)`), a third unclipped layer carrying both chips, a 3 px divider with a round handle, and a transparent full-size `<input type=range>` (aria-label, aria-valuetext, arrow keys, focus ring on the handle). Opens at 50 % on every load. Box sized by `aspect-ratio: 620/360` with `max-width: 620px`; the frame gets an explicit height and then follows the card's real height from inside, so there is no dead space at narrow widths. Both curves come from `app.module_iv(datasheet_to_ref(MODULE_PRESETS[DEFAULT_PRESET]))`, unshaded 1000/1000/1000 and shaded 1000/**250**/600 W/m² — three distinct levels are what give three peaks (middle strip alone at 250 gives two; one band across all three gives one). Colours are passed in from `ui.T()`; dark mode has its own cell colours and divider colour.
4. **What you can do here** — the five cards as before (Build the panel · Place the shadow · Read the curve · Run the trackers · Compare and export → Set up a panel, The panels, Inside a panel, Watch one run, Compare methods), keyed `gm-card-<page>` with `st.page_link` inside; the tutorial's seven steps now target the two hero links and these five cards.
5. **Footer** — one line: simulation note · "Where the numbers come from →" · department.

### The four defects
1. Chips cut off at the card edge → both chips live on their own SVG layer anchored to the same 620×360 box as the artwork and are never clipped by the wipe or the card. 2. Divider parked at the right → `value="50"` plus `set(50)` on load. 3. Panel off-centre → x = (620 − 210) / 2. 4. Rotated axis label → dropped; the captions say "power against voltage".

### EN/KO
`gm_lang` (in `_PERSIST_KEYS`) selects `gmppt_hero.TEXT["EN"|"KO"]` for every string on the landing, including inside the figure. The rest of the dashboard, and the tutorial popup, stay English. The old smoke test that banned `gm_lang` as a dead control is replaced by one that checks it is read.

### Verified
- `pytest tests/test_app_smoke.py tests/test_hero.py`: 72 passed (`tests/test_hero.py` is new: peaks 1 / 3 from the engine, preset change moves both curves, document invariants, dark and Korean variants, no header tabs on Home only, copy present, old content gone).
- Chrome DevTools, headless: 54/54 — no tabs on the landing; every string present; divider at 50 % on load and after reload; 620:360 kept; both chips inside the box and unwiped at 15 %; panel centred to 0.1 px; frame height = card height at 1440 / 1100 / 820 px; arrow keys move the range and the handle shows a focus ring; KO copy on the page and inside the figure; dark theme; Start exploring → `/panels` with the full Understand → Results strip; worked example → `/run`; card → `/simulator`; the tutorial still opens on first visit.

### Moving background (landing only) and dark default
- `gmppt_hero.backdrop()`: a fixed layer at `z-index: -1` under the page ground (the app's own grounds go transparent while Home is shown; html/body keep the page colour). Dark: a teal dawn glow that breathes, a faint 72 px cell lattice masked to the centre, teal and amber patches of light drifting left→right over 68–104 s, and a soft diagonal sweep every 46 s. Light: an amber sun, cloud shadows in the ink colour, the same lattice and sweep. Radial/linear gradients only, no blur filters; only `transform` and `opacity` animate. `prefers-reduced-motion` and the header's Animations-off switch park every shape at a composed position. Verified: present on Home only (The panels gets its ground back), animating, behind the hero frame and the cards, still under reduced motion and Animations off.
- Dark is now the default for every page: `gm_theme` defaults to `"Dark"` and `.streamlit/config.toml` carries the DARK tokens (`base = "dark"`), so the first paint and the widget accents are dark. Light remains the header's switch.

### Guided tour: opt-in only
- It auto-started because `ui.tutorial()` (gmppt_ui.py, the `if st.session_state.get("gm_tut_done") … return` guard) drew the tour whenever `gm_tut_done` was unset — i.e. on every fresh session — and `_wrapped` (gmppt_app.py) calls it on every Home render. The guard is now `if not st.session_state.get("gm_tut_open")`: nothing draws unless `open_tutorial()` ran. No first-visit flag, no localStorage; `gm_tut_done` is gone.
- One trigger: `ui.guide_button()` — a small "Guide me" in the landing top bar and in `ui.app_header` on every other page. On Home it opens the tour at step 1; elsewhere it goes to Home first (the steps point at Home's controls) and opens there. The "Show tutorial again" button on Home is removed.
- Skip, Finish (the final Next) and a click outside the card all run `_close_tutorial()`: closed, step reset to 1, overlay cleared, nothing else touched. The dim now takes pointer events, so an outside click only closes (it never reaches a link underneath); the spotlight hole is a clip-path, so the highlighted control stays clickable; wheel events on the dim are forwarded to the page's scroll container so the page still scrolls while the tour is open.
- Verified in Chrome (25/25): closed on load and after reload; Guide me on Home → step 1; Next → step 2; wheel scrolls; click on the dim closes without navigating; reopen → step 1; Skip → closed → reopen at step 1; seven Nexts → Finish on step 7 → closed, still on Home → reopen at step 1; Guide me on The panels → Home with the tour open at step 1. Tour content unchanged.

### Known
- Streamlit 1.63 logs that `st.components.v1.html` is deprecated ("will be removed after 2026-06-01") in favour of `st.iframe`; the figure uses `st.iframe` when present and falls back to `components.html`.
- The header mark (`ui._LOGO` via `st.html`) does not render on any page, the landing included; pre-existing, not touched.

## Phase UX-2 — copy + information architecture (master revision prompt §24–§27)

Method: a source sweep of every user-facing call (`callout`, `caption`, `legend_note`, `page_intro`, `unavailable`, `not_built`) for file names, module paths, script ids, schema keys, internal tags and app-mechanics words; then the rendered copy audit (widened with those patterns) over all 14 pages, excluding closed expanders; then every page rendered and read.

### Developer-facing text removed from the normal UI

| Where | Was | Now |
|---|---|---|
| Wrong-data-set guard | "Module split violation … resolves its modules through `dataset.module_split().val` — the same set `p7_tracker_comparison.py --split val` runs on" | "Wrong data set — … not validation data, so nothing is drawn" · machinery under Technical details |
| Watch one run, Dynamic irradiance | "needs the trained model (`results/phase3/c3_two_stage.pkl`) and scikit-learn" (×2) | "The trained model could not be loaded" · path under Technical details |
| Watch one run, A1 | "PSO evaluates 5 particles … (`gmppt/pso.py`) … particle k % 5 of iteration k // 5" | "every 5 dots are one iteration" · the loop arithmetic under Technical details |
| Watch one run, A1 | "already computed and cached" | "already computed for this scenario" |
| Compare methods | "Snapshot, not a live export" | "Snapshot, not the current result" |
| Results vs targets | "Targets are not carried in any export" | "were never written down in this project" |
| Shading relocation | "this export does not record the epsilon"; "Read from the export"; "uniform control (G5)"; "criteria p12 declared" | "the tolerance … was not recorded"; "What the numbers say"; "(G5)" and "p12" dropped |
| Shading relocation | "The triggered variants was not recorded" (grammar) | "The trigger rate of the triggered variants was not recorded" |
| Sources | engine "code" column: `gmppt.device + pvlib CEC parameters`, `app.py single-diode…` | a "model" column in words; module names under Technical details |
| Sources | `app.py`'s validation record (lists `v_l4_breakdown_sensitivity.csv` etc.) in the page body | under "Validation record → Technical details" (app.py untouched) |
| Set up a panel | "Explore and Testing use the validated research engine" · "benchmark figures under Testing" · a mono list `engine: single-diode + per-substring bypass (simplified) / reverse-bias avalanche: not modelled / …` | one plain sentence; the red card now says only what this engine cannot show |
| Set up a panel | "800-point current grid · 256-point export"; "modules in `MODULE_PRESETS`" | plain sentences |
| Dynamic irradiance | "needs a custom Streamlit component" | "a drag-and-drop control this dashboard does not have yet" |
| Sandbox dataset | "Generate one on Simulator → Make a dataset"; page titled "The dataset" under a tab called "Sandbox dataset" | one name, "Sandbox dataset"; "Make a dataset" |
| Benchmark set | near-tie file absent reported as a missing *field* ("shown as a dash") with no dash on the page | reported as not generated, which is what it is |
| Exceptions (day run, dynamic trace) | `Could not run the day (<exception>)` in the callout | plain sentence; the exception under Technical details |

### Duplicate explanations removed
- Set up a panel said "not the validated engine / not a benchmark" three times (Sandbox banner, intro banner, red card). The banner says it once; the intro says the engines never mix; the card says what the engine cannot show.
- Benchmark set's "Where it comes from →" and Sandbox dataset's "Where it comes from →" / "Make a dataset →" duplicated the footer navigation; Sources' "← The dataset" pointed a Results page back into the Sandbox. All four removed.

### Typography (§23)
`.gm-legend` (the note under every chart) was 0.72 rem developer mono. It is now body type at 0.82 rem. The provenance stamp and the animation budget line keep the mono face via `.gm-cite`, because those are citations.

### Retained on purpose
- `source: <file>.json · date · split=val · n=…` stamps under every figure (5 lines flagged by the audit): provenance the thesis needs.
- Technical details expanders keep: split sizes, nearest training module, `module_split()` provenance, file names, schema keys, re-run commands, exception text.
- The four failure states (not generated / could not be read / not in expected form / one field missing) stay distinct; only their visible sentences changed.

### Protected-file observations (not changed)
- `app.py` `render_dataset_section()` renders "🧪 Dataset" and then "🧪 Scenario Dataset Generator" (two headings for one thing) and "(CSV + NPZ + config)". Cosmetic; report only.
- `app.py` `page_validation()` lists result files by name; now behind Technical details on Sources.


## Phase UX-1 — workflow + visual architecture (master revision prompt §3–§23)

### One workflow table

| ID | What changed | Where | Verified |
|----|--------------|-------|----------|
| **§3** | `STAGES` is the single page→stage table. The header strip, the page eyebrow, the footer order, the Home stepper, the tutorial targets and the tests all derive from it. The old header sections ("Explore / Testing / The data") — a second vocabulary that produced `EXPLORE · INSIDE A PANEL` — are gone. | `STAGES`, `SANDBOX`, `JOURNEY`, `stage_of()` | `test_one_workflow_table_drives_everything`, `test_every_journey_page_eyebrow_names_its_stage` |
| **§4** | Inside a panel renders **INSPECT · INSIDE A PANEL**; every journey page's eyebrow is `Stage · Page`. Verified in the rendered DOM, not from the variable. | 12 `page_intro` calls | shots.py (eyebrow + header stage on 11 pages) |
| **§5** | The header's stage row **is** the workflow indicator: `UNDERSTAND → [INSPECT] → WATCH → COMPARE → EXPLORE → RESULTS │ SANDBOX`, mono, one line, current stage filled, others subdued, hover help per stage. The separate `.gm-flow` strip was a duplicate and is no longer rendered. Global controls moved to the second row so the strip never wraps around them; a media query keeps it on one line at 1100 px. | `ui.app_header(journey=, stage_help=)` | shots.py at 1440 and 1100 px |

### Navigation and Home

| ID | What changed | Where | Verified |
|----|--------------|-------|----------|
| **§13–14** | The five peer "Open →" cards are replaced by a **stepper**: one row per stage with done ✓ / current ● / next → / later ○, exactly one strong call to action (the next stage), quiet "open"/"revisit" links elsewhere, and no link at all on the current row. Visited stages are ticked from `gm_visited`. | `ui.stepper`, `_home_steps` | shots.py: one NEXT, one CTA, no "Open →" |
| **§20** | `_home_cards` and the card constants deleted; the Sandbox is one quiet link under the stepper. | `page_home` | copy audit |

### Interactive tutorial (§6–9)

| ID | What changed | Where | Verified |
|----|--------------|-------|----------|
| **§6** | `ui.tutorial(steps)` is now a real onboarding overlay: a fixed full-screen dim with a **cut-out hole** over the real control (CSS `clip-path` even-odd, so it works whatever stacking context the target sits in — a box-shadow spotlight on the target itself only dimmed its own block), a focus ring, and a compact popup placed beside the target (right → below → above → left, clamped to the viewport, repositioned on scroll/resize). Back / Skip / Next / Finish are ordinary buttons. Nothing is drawn to stand in for a control; the control stays usable under the overlay. | `ui.tutorial`, `_tut_script`, `_TUT_CLEAR` | shots.py: target = real element, popup never overlaps it, Back/Next/Skip/Finish/reopen all pass |
| **§7** | Seven steps on Home, each pointing at a real control: the Start button, then the six stepper rows. No navigation is forced. | `_tutorial_steps` | `test_tutorial_targets_real_controls_only` |
| **§9** | `gm_tut_done` / `gm_tut_step` as before; reopening resets only the step. | — | shots.py |

### Inside a panel (§15–19)

Rebuilt as sections in order: orientation → **Operating point** (slider, then Current and Power as identical peer cards) → **Panel response** (P–V and I–V side by side, same height, the operating point drawn the same way on both) → **Substring state** (three identical cells, no dataframe) → **Why the curve has steps** (three sentences, technical rule behind an expander) → **Next** (one primary "Watch the trackers →" that sends this scenario) → **Look further** (A3, A4 as sections, not bordered cards). Peak label given headroom so it is never clipped.

### Containers, balance, copy (§12, §20, §24)

- Bordered cards removed from every animation section (Watch one run, Inside a panel, Dynamic irradiance, Saved scenarios); `ui.section_head` + dividers instead.
- KPI rows: hero weight 1.6 → 1.25 so the verdict card is a peer; text values ("Across the strips") now set at word size so a phrase never makes one card twice the height of its neighbours (`.gm-kpi .v.text`).
- The panels: Previous/Next no longer truncate; both small P–V charts keep the peak label inside the plot (including when the taller unshaded reference is shown).
- Compare methods: scatter labels no longer overprint or clip; raw `arrival_separable_by_population =` moved under Technical details.
- Dynamic irradiance: raw `reseed_credited =` moved under Technical details; Streamlit's default spinner (`Running _dynamic_day(...)`) replaced with plain sentences on all three cached runs.
- Results: internal decision tag "(D2)" removed from the visible label. Relocation: "criteria p12 declared" → "acceptance criteria declared".
- Watch one run and Set up a panel gained the title + eyebrow every other page had.

### Glossary (§10)

`ui.GLOSSARY` + `term_tip()`: KPI labels get hover help automatically for GMPP, true peak, V_oc, substring, bypass diode, control step, dynamic/tracking efficiency, Sandbox, Validation data, Exploratory, s.e., near-tie, Animation. Visible labels stand on their own; tooltips are 1–2 sentences, no Python names.


## UI content cleanup + UX scaffolding (§5–§14)

### §8 — the reported block (CRITICAL)

| ID | What changed | Where | Verified | Residual risk |
|----|--------------|-------|----------|---------------|
| **§8** | The validation panel quoted in the report — split counts, "in training set / No", "closest module the model was trained on", the long "Validation module — not used to fit the model…" sentence and the model-file explanation — is **gone from the normal UI**. It was added in Phase C for U1.5 and read as a developer console. Replaced by one chip: **"Validation data — Used to compare tracking methods. Held-out test data is not shown."** | `_unseen_check`, `ui.data_chip` | uxtest §8 (9 phrases absent), phaseC (chip present, bookkeeping absent) | None. |
| **§8 (2nd site)** | The same copy also ran on **Watch one run**, inside the example-scenario callout (`_VAL_WORDING` plus "nearest training module … z-scored parameter distance of 0.17"). That page now uses the same `_unseen_check` chip, so both sites say it once and say it identically. `_VAL_WORDING` deleted. | `page_run` | phaseC (demo names its data set the same way) | None. |
| **§10 detail kept** | Nothing was deleted from the record. Split sizes (train 13,406 / validation 3,351 / test 4,189), the nearest training module and distance, and the note that membership resolves through `gmppt.dataset.module_split()` all moved into a collapsed **Technical details** expander. | `_unseen_check` | phaseC opens the expander and asserts all three facts | None — the check still runs; a training module still raises the **Wrong data set** limit callout. |

### §11–§14 — labels, empty states, page copy

| ID | What changed | Where | Verified |
|----|--------------|-------|----------|
| **§11** | 9 widget labels renamed out of implementation language — "Rows (strings)" → "Rows of panels", "Columns (per string)" → "Panels per row", "Shadow depth" → "How dark the shadow is", "Shadow width" → "How wide the shadow is", and so on. | `page_panels`, `page_sim_setup` | uxtest (no `(strings)` label survives) |
| **§14** | `missing_export`, `missing_field` and `require_keys` rewritten onto `ui.unavailable`. The reader gets one sentence naming what is not there and stating that nothing was estimated; file names, absent schema keys and the script to re-run moved into Technical details. The **four failure modes stay distinguishable** — "has not been generated yet" ≠ "could not be read" ≠ "not in the form it expects" ≠ one absent figure. | `missing_export`, `missing_field`, `require_keys` | phaseA 27/27, including that each mode keeps its own wording and its own detail |
| **§14 (gates)** | The relocation gate caveat led with `relocation_comparison_pole.json carries a single discarded total…`. It now leads with the finding — these results **cannot be described as gated** — in amber (`ui.unavailable(kind="limit")`), with the missing G1–G6 counts and the p12 re-run instruction underneath. | `page_relocation`, `ui.unavailable` | accept T9 (4 checks), `test_relocation_export_has_no_gate_counts` |
| **§12** | The Watch-one-run method box named `gmppt/fallback.py` in body copy. The fact a reader needs — **neither variant has a backup scan; nothing rescues a wrong seed** — is now the visible sentence; the file and the N1/D3 reasoning moved into Technical details. | `page_run` | copy audit (no longer flagged) |

**UI copy audit:** 42 → **6** flagged lines across all 14 pages. All six are intentional and stay: five `source: …json · date · split=val · n=…` provenance stamps (U7 requires every figure to name its export) and the Sources page naming the two engines, which is that page's subject.

### §5–§7 — navigation and orientation

| ID | What changed | Where | Verified |
|----|--------------|-------|----------|
| **§5** | Workflow indicator — `Understand → Inspect → Watch → Compare → Explore → Results` — above every journey page, with the current stage highlighted. Sandbox and the planned whole-system page carry **no** stage, because they are outside the benchmark journey. | `ui.flow_indicator`, `_FLOW_STAGE` | uxtest (6 pages highlight the right stage; Sandbox has none), `test_flow_stage_covers_the_journey_and_excludes_sandbox` |
| **§6** | First-visit tutorial on Home: 6 steps, Continue / Skip, remembered in `gm_tut_done`, reopenable via "Show tutorial again". | `ui.tutorial` | uxtest (shows, advances, skips, closes, reopens), `test_tutorial_state_is_remembered` |
| **§7** | `_PAGE_PURPOSE` gives each page a one-line statement of what it is for, used by the tutorial and the flow header. | `_PAGE_PURPOSE` | walk.py (all 15 pages render) |

**Suite after this work:** pytest **57/57** · walk 15/15 pages · uxtest **35/35** · accept **22/22** · phaseA **27/27** · phaseB **22/22** · phaseC **24/24** · a1test **33/33** · t12 **28/28** · nb3 **10/10**.

Three earlier failures were **stale tests**, not regressions — phaseA, phaseC and accept asserted the old copy verbatim. Each was rewritten to assert the new two-layer contract (plain sentence visible; the guaranteed fact still present once Technical details is opened), so the guarantee is still tested rather than dropped. nb3 failed only because it located a control by the label §11 renamed. A `cdp.tech()` helper was added to open expanders, since a closed `<details>` is absent from `innerText`.

**One anomaly investigated and cleared:** t12 reported one click adding two events at 17:00. `dblprobe.py` drives a single click with no retry and gets exactly one event each time — the duplicate is t12's own documented click-retry landing twice after a slow rerun, not an app defect.


## Workflow audit + Update 3 (animation layer, first tranche)

### Defects found by the §2 audit

| # | Defect | Where | Fix | Verified |
|---|--------|-------|-----|----------|
| 1 | **Loading a saved scenario crashed the page.** Phase B's R6 change widened the bench run signature to 7 fields, but `_bench_load` still wrote 4, so the unpack raised `ValueError: not enough values to unpack (expected 7, got 4)`. Two derivations of one quantity, in two places. | `_bench_load`, `page_sim_setup` | One builder, `_bench_sig()`, used by both writers; `_bench_ran()` discards a stale shape instead of raising, so a restored session degrades to the empty state. | `test_bench_run_signature_has_exactly_one_builder`, browser round trip |
| 2 | **`bench_save` (a button) was being pre-set from session state.** The persistence prefix `"bench_s"` matched `bench_save` and `bench_scen_name`. Streamlit raises `StreamlitValueAssignmentNotAllowedError` at *widget creation*, which the try/except inside `persist_widget_state` cannot catch. Masked by defect 1 until that was fixed. | `_PERSIST_PREFIXES` | The per-substring inputs are listed explicitly (`bench_s0…bench_s11`); the broad prefix is gone. | `test_persist_prefixes_never_match_a_button_key` |

Everything else in the §2 checklist passed. Three further audit failures were harness artifacts, confirmed separately: the divergence state does fire when the control change is verified; the Inside-a-panel slider **is** bounded to Voc (tick bar reads `0.00 41.30`); and Your day is badged and reads the day events.

### Update 3 — toolkit and A1

| Item | What | Verified |
|------|------|----------|
| Toolkit | `ui.trace_player`, `ui.curve_morph`, `ui.anim_badge`, `ui.snapshot_strip`, `ui.anim_exports`, `ui.anim_on`, `ui.downsample`, `ui.anim_budget_note`. Static background (curve, GMPP, bands) is drawn once and frames update only the marker/trail traces — that is what keeps the JSON small. | `test_toolkit_exists_with_the_specified_api`, T34 |
| §6 toggle | `gm_anim` (default On) in `ui.app_header` beside the theme control, persisted. Off builds **no** Plotly frames and renders the snapshot strip. | T33 (1 figure on → 4 off, 0 frames) |
| **A1** | Search replay on Watch one run. Replays `v_hist`/`p_hist` from `_run_scenario`; no tracker is re-run. Play/pause, 0.5×/1×/2×, step slider, per-method control-step and %-of-GMPP counters, trail, key frames, HTML/JSON export, generated text alternative. | T25, T26, T31, T33, T34, T35, T36 |

**A1 measured:** 60 frames · stride 1 · **0.238 MB** figure JSON · build **<0.01 s** (frames are list slicing over already-cached trajectories; the expensive `_run_scenario` is cached separately).

**PSO grouping (T26):** recoverable. `pso.py:183-187` is a fixed-order nest, `DEFAULT_POPULATION = 5`, so evaluation *k* is particle `k % 5` of iteration `k // 5`. `_pso_grouping()` re-checks the loop shape at runtime and falls back to "sequential evaluations — particle identity not recorded" if it ever changes.

**Not yet built:** A2–A9. See the report for what each needs.


## Phase A — Protect the data (consolidated update, Part 8)

| ID | What changed | Where | Verified | Residual risk |
|----|--------------|-------|----------|---------------|
| **§2.3 read-only** | Audited every write path in `gmppt_app.py` and `app.py`. Every `to_csv` / `savemat` / `writestr` is an in-memory download or zip buffer; nothing writes under `results/`. Asserted, not assumed. | — | T16, `test_T16_dashboard_never_writes_to_phase2` | None. |
| **§2.3 mirror** | The earlier revision deleted `_set_scenario` and with it the `current_scenario.json` mirror. Restored as `_mirror_scenario()`, writing to **`results/dashboard/`** so a dashboard artefact cannot sit beside a benchmark export. Written on Send only; failure is swallowed so losing the mirror cannot take a page down. | `_mirror_scenario`, `_send_scenario` | Phase A (mirror present, correct directory, carries the scenario) | Only the sent scenario is mirrored, not the draft — matching the original behaviour. |
| **§2.3 four failure modes** | `_load_json` returned `None` for everything. `_read_export` now distinguishes **not found / unreadable / malformed JSON / unexpected schema**, and `missing_export` re-probes the path so the message fits: a missing file gets "run it and reload", a truncated one gets "present but malformed JSON — the dashboard will not repair or regenerate it". | `_read_export`, `missing_export` | Phase A (all three fixtures), `test_export_reader_separates_missing_from_malformed` | None. |
| **§2.3 schema gate** | `require_keys()` added and wired into Compare, Dynamic, Relocation, Results and Benchmark set. A file that parses but has moved shape now says which top-level key is absent and that nothing is inferred from the fields that remain, instead of falling through to a KeyError or an empty table. | `require_keys` + 6 call sites | Phase A (unexpected-schema fixture), `test_pages_check_export_schema_before_reading_it` | Top-level keys only; nested schema drift still surfaces as `missing_field`. |
| **U7 experiment id** | `ui.provenance` now renders `experiment=…`. `_experiment_id()` prefers a real `experiment_id`/`run_id`/`uuid`; these exports carry none, so it falls back to the fields that do identify the run (`family`, `sequence`). It never synthesises one. | `ui.provenance`, `_experiment_id`, `_export_meta` | Phase A, `test_provenance_carries_an_experiment_id`, `test_experiment_id_is_read_not_invented` | **Protected-file request:** no export writes an explicit run id. The test fails loudly if one is added, so the better field gets used. |

**Phase A tests:** pytest 28/28 · Phase A browser suite 23/23 · prior suites 20/20 and 10/10 · all 14 pages render with exports present, absent, malformed and wrong-shaped.

## Phase C — Module sets and metrics (consolidated update, Part 8)

R11, R14+U8, R15 and R16 were already implemented and passing; Phase C adds U1 and U6.

| ID | What changed | Where | Verified | Residual risk |
|----|--------------|-------|----------|---------------|
| **U1.1 dropdown** | Already on `dataset.module_split().val`, with the original N_s/power-band/median selection applied to that set. Verified, not redone. | `_validation_modules` | T14 | None. |
| **U1.2 demo module** | The demo was the median-power 72-cell validation module. It is now the deterministic choice U1 specifies: among validation modules with `N_s == 72` and 340–380 W, the one whose **nearest training module is farthest away** in z-scored `V_mp_ref, I_mp_ref, V_oc_ref, I_sc_ref, N_s` over the full pool. Chosen: **`LG_Electronics_Inc__LG370S2W_A5`**, nearest training module `Auxin_Solar_AXN6M612T375` at z-distance **0.17**. Logged at startup and shown on Watch one run. Irradiance and temperature unchanged. | `_demo_module`, `_zmatrix`, `_nearest_train`, `_demo_startup_log` | T14 (6 checks incl. an independent re-computation) | The best available separation in that band is 0.17 — small, because the split is by module name and near-identical products straddle it. The number is shown rather than hidden. |
| **U1.3 load-time assertion** | `assert_val_modules()` gates the panel dropdown and the demo. A module in train or test renders a `limit` callout and **no results** on that page. | `assert_val_modules`, `page_panels`, `page_run` | T14, `test_T14_load_time_assertion_exists_and_blocks_rendering` | None. |
| **U1.4 test set unreachable** | No call to `split_modules()` and no `.test` read anywhere. Enforced on the **AST**, not by grep — the Sources page legitimately names `scenarios.split_modules(pool)[1]` in prose to explain what the test set is, and a text search cannot tell that from a call. | — | `test_T14_test_split_is_never_reached` | None. |
| **U1.5 unseen check** | Panel beside the dropdown: split summary (`train 13,406 · val 3,351 · test 4,189 (test not shown here)`), **In training set: No** from a live membership test, and **closest module the model was trained on** with its distance, computed live. | `_unseen_check`, `_split_counts`, `_nearest_train` | T14 | Verifies against the split function, not a training list in the model file — stated on screen and raised as a protected-file request. |
| **U1.6 wording** | `_VAL_WORDING` used wherever the dashboard describes these modules. "Held-out" now appears only where it names the **test** set; "never seen" appears nowhere. A test walks every non-comment line to keep it that way. | `_VAL_WORDING` and call sites | `test_T14_wording_never_calls_validation_modules_held_out` | None. |
| **U1.7 Sources** | "the held-out half of that pool (`split_modules`)" replaced by the three-way split with live counts, the function names, and an explicit line that the test set is reached only through `p3_final_comparison.py --confirm-test` and never here. | `page_sources` | T14 | None. |
| **U6 unknown variants** | `method_label` fell back to echoing the key, so an unrecognised export key would print as itself and read like a method name. It now returns **"Unknown variant — export schema needs review"**. Compare also *surfaces* unknown keys as their own rows plus a caveat naming them, rather than silently dropping rows the export contains. | `method_label`, `UNKNOWN_VARIANT`, `page_compare` | T15 (fixture injects `hybrid, experimental`) | The cost chart omits unknown rows by design — an unknown variant has no readings figure to place on a readings axis. |

**Phase C tests:** pytest 41/41 · Phase C browser 23/23.

**Protected-file requests (U1.8), reported not done:** (1) write each export's module list into the export JSON; (2) save `split.train` inside the model file. Until both exist, the unseen check verifies against the split function rather than against what the model was actually fitted on, and the panel says so.

## Phase B — State (consolidated update, Part 8)

R1–R10 and U9 were already implemented and passing (see the sections below); Phase B adds U3 and U4.

| ID | What changed | Where | Verified | Residual risk |
|----|--------------|-------|----------|---------------|
| **U3 panel navigation** | The drag/paint buttons were removed in the earlier pass, which also removed the only way to walk the array. Added **‹ Previous / Select panel / Next ›** with a **Panel B-03 of 15** counter, and turned the ✕ into a labelled **Reset inspected panel**. Stepping uses `on_click` callbacks writing `gm_sel`, so the keyed selectbox is in sync on the same run; they disable at the ends and do not wrap. Every control has a `help=`. | `page_panels` (`_step_panel`) | T13 (10 browser checks), `test_T13_*` | None. |
| **U3 state rule** | Changing the inspected panel updates `scenario_draft` — in this dashboard the draft *is* the inspected panel, since `sel_irr` depends on whether that panel is shaded. It writes nothing else: an AST test asserts `_step_panel` touches only `gm_sel`, and a browser test snapshots every other control across a step. | `_step_panel`, `_set_draft` | T13, `test_T13_panel_navigation_touches_only_the_inspected_panel` | The divergence warning still lives on Watch one run only (the banner was removed at the user's request). |
| **U4 record fields** | The sampled day record carried only `time_label`, `module_source`, `active_events`. It now also carries `source`, `time_hour`, `module_applied`, `scenario_hash`, and a per-event `events` list with `kind`, `uid`, `start_hour`, `end_hour`, `duration_hours`, `motion` — enough to reconstruct why the irradiance looks as it does. `active_events` alone could not tell two poles apart. | `_day_sample_scenarios` | `test_U4_day_record_carries_every_declared_field` | None. |
| **U4 display rule** | `_IMPORT_SENTENCE` is defined once and used twice: on the import message and inside the saved record (`config.imported_note`). A saved file can no longer outlive the explanation that the module did not come with the irradiance. | `_IMPORT_SENTENCE`, `page_sim_setup`, `_bench_record` | Phase B (U4 round trip), `test_U4_import_sentence_is_shared_by_message_and_record` | None. |
| **T12** | No code change — `_day_window_from_hour` already anchored events to the playhead and shifted left near 18:00. Now proven rather than assumed, at 08:00, 12:00, 15:00 and 17:00. | — | T12 (28 browser checks + unit) | None. |

**Phase B tests:** pytest 33/33 · T12 28/28 · Phase B browser 22/22.

**Note on T12 at 17:00.** The document lists 17:00 among the hours where "each new event starts at the selected hour", and separately requires that "near 18:00, the window shifts left and keeps its 1.5 h duration". With a 1.5 h duration those cannot both hold at 17:00 (17:00 + 1.5 h = 18:30). The implementation keeps the duration and shifts left, giving **16:30–18:00**, which still covers the 17:00 tick the user clicked. My first test encoded the other reading and failed; the test now encodes the exception.

**Disclosure:** the first run of the malformed/schema fixtures restored `tracker_comparison_val.json` with `write_bytes`, which preserved its **content** (SHA-256 verified identical, T16 passed) but reset its **mtime** to 2026-09-22 18:11. The provenance stamp for that one file therefore shows that date instead of its original 2026-09-16 10:14. No benchmark value changed. The harness now uses `shutil.copy2`, which preserves timestamps, and a re-run confirmed mtimes hold steady. If the original timestamp matters, re-run `phase2/p7_tracker_comparison.py --split val`.


One row per finding. "Verified" names the test that covers it: `T*` are the
acceptance tests (browser-driven unless marked *unit*), `pytest` means
`tests/test_app_smoke.py`.

Files changed: `gmppt_app.py`, `gmppt_ui.py` (additive helpers only),
`tests/test_app_smoke.py` (new). `app.py` and everything under `gmppt/` are
untouched.

---

## Critical fixes

| ID | What changed | Where | Verified | Residual risk |
|----|--------------|-------|----------|---------------|
| **R1** | Home cards and the footer "Where the numbers come from" link were raw `<a href=… target="_self">`, which is a full browser navigation: it starts a new Streamlit session and drops `scenario`, `frozen`, `dataset` and `day_events`. All are now `st.page_link` inside the same keyed containers; the card body stays HTML and the action is a real link pinned to the card's bottom by CSS. | `_home_cards`, `page_home` | T2, pytest (`href=` grep clean) | None. Typing a URL by hand still starts a new session — that is Streamlit, not the app. |
| **R2** | Streamlit deletes a widget's session key on any run that does not render it, i.e. every run spent on another page. `ui.persist_widget_state(keys, prefixes)` re-assigns each key to itself once per run, before `nav.run()`. Covers all `gm_*`, `run_*`, `mv_*`, `saved_pick`, `day_time`, `bench_*` keys and the `bench_s`, `day_win_`, `day_mot_`, `swp_` prefixes. | `gmppt_ui.persist_widget_state`, `_PERSIST_KEYS` | T1 | A key added later must be added to the list; the prefix entries cover the generated families. |
| **R11** | `_RUN_READINGS` hardcoded `{Model only: 6, Hybrid: 6, PSO: 100}` and the cost KPI divided by a literal `6.0`. Readings now come from `gmppt.hybrid.SEED_PROBE_COST` (= 5) and, for PSO, from the export's `sequential_steps`. P&O and InC show `—` because no export reports a separate probe budget for them. | `_READINGS_FIXED`, `_pso_readings` | T5, pytest | The PSO row is the best-arrival row of the sweep; if the sweep changes, so does the number (by design). |
| **R12 / N4** | The panel dropdown and both demo scenarios were built from `scenarios.split_modules(pool)[1]` — the **held-out TEST set**, which `dataset.py` reserves for one ledgered opening. They now resolve through `dataset.module_split().val`, the same call `p7 --split val` makes. `SPLIT_NAME` travels with every scenario. | `_val_module_names`, `_validation_modules`, `_demo_module` | T11, pytest, T4 (banner shows `split=val`) | None. See D1. |
| **R12 (demo)** | The demo module `LG_Electronics_Inc__LG375N2K_G4` is a **training** module — one the model was fitted on. Replaced at load time with the median-power 72-cell validation module, and the substitution is stated on screen. | `_demo_module` | T4, T7 | If the pool changes, a different module is picked; the note says which. |
| **R4** | Day-event widgets were keyed by list index, so deleting an event shifted every later event's window and motion onto its neighbour. Each event now carries a `uid`; widgets are `day_win_{uid}` / `day_mot_{uid}`; delete pops that event's keys; events restored from a session file are migrated. | `_day_uid`, `_day_migrate`, `_day_drop` | T3 | None. |
| **crash guards** | `f"{hyb:.3f}"` on the dynamic page and `g("hybrid, bounded")` on Compare raised when a variant was absent. Every export read now goes through `_load_json` + guarded `.get`, with `missing_export` / `missing_field` callouts naming the file and the script that writes it, and `_fmt` rendering `—` for `None`/`NaN`. | `missing_export`, `missing_field`, `_fmt` | T6 | None — T6 runs every page with `results/phase2` removed. |

## State architecture

| ID | What changed | Where | Verified | Residual risk |
|----|--------------|-------|----------|---------------|
| **R3** | `gm_last` / `scenario` replaced by `scenario_draft` (rewritten on every render of The panels) and `scenario_sent` (written only by "Send this panel to the trackers"). Both carry `module, temp, irr, label, geometry, geometry_label, pattern, split, engine, created_at, hash`. | `_scenario`, `_set_draft`, `_send_scenario` | T4 | None. |
| **R3 (banner)** | ~~`ui.scenario_banner` under the header on every Explore/Testing page.~~ **Removed at the user's request** after review: it was an always-on status line repeating what the page already showed. The one part of it that was load-bearing survives as `_resend_notice()` on Watch one run — an "Edited since sent" caveat plus **Resend**, shown *only* when the draft has actually diverged from the scenario being run. `ui.scenario_banner` and `.gm-scenbar` remain in the design system, now unused. | `_resend_notice`, `page_run` | nb3 (10/10) | Explore pages no longer state the split on screen; it is still in the session and on the Sources page. |
| **R10** | `Scenario(...)` was constructed with a literal `"whole_substring"` on both the static and dynamic paths, mislabelling every sub-substring pattern. `geometry_of()` derives it; `geometry_label()` additionally names the dashboard's own "across the strips" case as **sub-substring (all strips)**, since it shades a group on *every* substring, unlike `scenarios.py`'s single-substring case. | `geometry_of`, `geometry_label` | T4, pytest | None. |
| **R5** | `bench_import_meta` survived manual edits, so an imported-day label could describe numbers the user had since changed. The import records a signature; any edit to the substring irradiance, base G or T clears the label, as does "Reset". An explicit **Clear import** button was added. `day_scenario_samples` and `day_ran` are cleared whenever the events change. | `_bench_apply_preset`, bench import block, day editor | manual | The signature covers irradiance/base/T, not the datasheet fields individually (Reset covers those). |
| **R6** | `_bench_save` and the "array (scaled)" KPI read the *current* `base_G`, `m_str`, `p_str` while the curve came from the last run. All three are now in the `bench_ran` signature and the record is built from the ran values. | `cur_sig`, `_bench_save` | manual | None. |
| **R7** | `gm_vop` could hold a value outside `[0, voc]` after the scenario changed, which makes `st.slider` raise. Clamped before rendering. | `page_inside` | T7 walk | None. |
| **R8** | The "Mounting" control only picked the default index of "Runs" and then did nothing. Removed. | `page_panels` | walk | Removed rather than wired; see "not done". |
| **R9** | The 12-scenario cap dropped the oldest silently. It now names what went, in a toast. | `_bench_save` | manual | None. |

## Navigation and presentation

| ID | What changed | Where | Verified | Residual risk |
|----|--------------|-------|----------|---------------|
| **N3** | `render_header()` and four hand-rolled tab rows (`benchtabs`, `runtabs`, `mvtabs`, the Simulator sub-links) deleted. `ui.app_header` — which already implements the active section, page tabs and greyed "· coming" tabs — is called once from a single page wrapper. The KO language toggle is gone (`gm_lang` was read nowhere). | `_make_page`, `SECTION_KEYS` | T1, T2, walk | "Whole system" renders its tab as `system · coming` (the key, not the title) because `app_header` formats `None` pages that way; changing it would alter a helper's behaviour. |
| **§5** | `ui.footer_nav(prev, next, step, total, rationale)` replaces every `ui.next_step`. Explore → Testing → The data is one 9-step flow; the Sandbox is a separate 4-step flow, deliberately outside the count. | `ui.footer_nav`, `_FLOW` | walk | None. |
| **§5** | Session save/restore: **Download session (JSON)** carries the two scenarios, `frozen`, `day_events` and the export filenames with their mtimes; **Load session (JSON)** on Home restores them. | `_session_io`, `_session_blob` | manual | None. |
| **§7.1 / R13 / N1** | One `_METHOD_LABELS` table. The bare word "Hybrid" no longer appears: `hybrid.py` builds four functions and the exports carry five hybrid keys. Both `Hybrid (bounded)` and `Hybrid (free)` are run and shown. | `_METHOD_LABELS`, `method_label` | T5, walk | None. |
| **§7.2** | `_RUN_COLORS` and `_MV_COLORS` deleted. `ui.method_style(label)` returns colour (from `METHOD_COLORS`, by base name) and dash (by variant). `Oracle` added to `METHOD_COLORS`. | `ui.method_style` | pytest | None. |
| **§7.3** | `ui.provenance(exports)` under every export-backed figure: filename, mtime, split, n, seed/version where present. | `ui.provenance` | walk | Exports carry no `seed` or `version` field today, so those are simply absent. |
| **§7.4** | Every `st.plotly_chart` replaced by `ui.show_chart` (11 call sites). | throughout | pytest | None. |
| **R15** | `_score_traj` had its own arrival/steps definitions with two defects: convergence measured against the method's **own** final power (so a firmly-trapped tracker scored as converged) and `steps = 0` printed for "never settled". It now delegates to the harness's `Trajectory.metrics()` — the same code p7 summarises. Steps show `—` when the method did not arrive. | `_score_traj` | T5, walk | None. |
| **R16** | The unshaded reference on the dynamic page ran at 1000 W/m² while the shaded demo ran at 910, so part of the gap labelled "shading" was a brightness difference. Both now use `max(shaded_irr)`. | `_dynamic_day` | walk | None. |
| **R17** | `int(f * n_sub)` snapped a drifting shadow from one strip to the next between slices — a teleport. Replaced by a continuous edge sweep: a `DRIFT_WIDTH`-wide shadow whose leading edge crosses the module once per window, with per-substring coverage interpolated. | `_day_event_state`, `DRIFT_WIDTH` | manual | The sweep rate is declared by `DRIFT_WIDTH`, not measured against a sun model. |
| **R14** | Hardcoded relocation prose ("~64% lost", "One shift at step 40", "all data-validation gates passed") deleted. Every number is read from the export; the jump step is `settle_steps` (200, not 40). | `page_relocation` | T9, pytest | None. |

## Page restructure

| Area | What changed | Verified |
|------|--------------|----------|
| **Home** | Cards follow the real journey — panels → inside → run → compare → results. The Sandbox card is on its own row under "A separate engine". Card 2 text now matches what *Inside a panel* shows. | T2 |
| **The panels** | "Refresh analysis" (cosmetic), the disabled drag/paint buttons and the day **tracker run** removed. The event editor and scenario-sampling stay. KPI relabelled **Array upper bound (every optimizer at its GMPP)**. A scoped "Reset shadow" added. Width and Runs are disabled for cloud/soiling, where `_event_pattern` ignores them. | T1, T4 |
| **Inside a panel** | Reads `scenario_draft` and says so. A P–V subplot with `ui.mark_gmpp` / `ui.mark_local_peaks` was added above the I–V, so the Home card's promise is met. | walk |
| **Watch one run** | Harness scorer; `ui.add_strip_bands` for the region window, labelled "Bounded P&O cannot leave this window" or "Seed's predicted region (start only)"; the method card's step 5 (which described `fallback.py`, never run here) removed; the "Control" callout shown only when P&O actually failed; probe label from `SEED_PROBE_COST`; "Discard sent scenario"; the mid-run block moved to its own page. | T5, T7 |
| **Compare methods** | Cost KPI first (readings, Hybrid vs PSO, at equal arrival), then arrival, then worst case. The 78%-baseline progress column and its "so the top methods are separable" note are gone. PSO labelled "best of sweep, selected on val" with its steps and worst case from the export. CSV and JSON exports with the provenance stamp. | T5, T6 |
| **Dynamic irradiance** | s.e. shown for PSO and P&O as well as the hybrid; the "reseed each block" negative result surfaced with `reseed_credited`; unshaded reference fixed (R16); **Your day** added as a collapsible, badged *exploratory — not a benchmark, not gated*, with the per-slice G2 curve-integrity count and a "Hybrid unavailable" callout when the model is missing. | T6, T7 |
| **Shading relocation** (new) | Gate panel that says plainly *"Gate counts are not in this export — the result cannot be presented as gated"*, since the export carries only `discarded` and `c1`–`c4`. `reconv_frac` shown as a number, not a yes/no against an invented 0.5 threshold. All prose generated from the numbers. Planned families listed via `ui.not_built`. | T9 |
| **Results vs targets** (new) | Three target rows computed from exports only, with PASS / NOT MET, ± s.e., n and split. The static target is shown under **both** definitions, marked "definition pending advisor decision (D2)". The mandatory caveat block and CSV/JSON export are present. | T10 |
| **Benchmark scenario set** (new) | n per subset, geometry mix, split, seed source, temperature and irradiance ranges — all from export metadata or `scenarios.py` constants, with `—` plus a named callout for anything absent. | T6 |
| **Sandbox** | Renamed from "Simulator", with a tinted "Sandbox · simplified engine" bar. The Parametric sweep tab now calls `sim.render_sweep()` (N6) with a note that it sweeps `MODULE_PRESETS`, not the typed datasheet. The dead "Figure SVG" button is replaced by a one-line roadmap note. | walk |
