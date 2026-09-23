# CHANGELOG — dashboard revision

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
