# CHANGELOG — dashboard revision

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
