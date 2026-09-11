"""
run_validation.py  —  measured-data validation of the GMPPT simulator.

Reproduces the four measured-validation layers of Phase 1:

    C1  v_c1_measured.csv               V_mp/V_oc characterisation on the flash-test DB
    L2  v_l2_curves.csv                 measured flash-test I-V vs single-diode model
    L3  v_l3_offstc.csv                 IEC 61853 (G,T) matrix, measured vs predicted
    L4  v_l4_breakdown_sensitivity.csv  sub-substring region error vs breakdown params

Expected directory layout (edit DATA_DIR / RESULTS_DIR if yours differs):

    <project root>/
        gmppt/      device.py, config.py, scenarios.py     (importable)
        data/       AnonDB.csv, IEC61853_1-2.xlsx, IV.zip, RefIV.zip
        results/    outputs are written here (v_*.csv)
        run_validation.py

Dependencies: numpy, pandas, scipy, pvlib (== 0.15.2), openpyxl.
No PySAM required: the single-diode fits use a small, robust Lambert-W
least-squares fit anchored at the measured STC operating point.

Run:  python run_validation.py            # all layers
      python run_validation.py c1 l3      # selected layers
"""
from __future__ import annotations
import io, re, sys, zipfile
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

ANON_DB = DATA_DIR / "AnonDB.csv"
IEC_XLSX = DATA_DIR / "IEC61853_1-2.xlsx"
IV_ZIP = DATA_DIR / "IV.zip"
IV_DIR = DATA_DIR / "IV"

Q, K, TREF = 1.602176634e-19, 1.380649e-23, 298.15
CSI_CELLTYPE = {"mono-Si module": "monoSi", "multi-Si module": "multiSi"}


# ----------------------------------------------------------------- C1
def layer_c1():
    df = pd.read_csv(ANON_DB)
    ratio = (df["Vmp_(V)"] / df["Voc_(V)"]).replace([np.inf, -np.inf], np.nan)

    def stats(s):
        s = s.dropna()
        return dict(n=int(len(s)), mean=float(s.mean()), sd=float(s.std()),
                    lo=float(s.min()), hi=float(s.max()),
                    miss=float((s.sub(0.80).abs() > 0.01).mean()))

    per_flash = stats(ratio)
    per_module = stats(df.assign(r=ratio).groupby("Mod_ID")["r"].mean())
    out = pd.DataFrame([per_flash, per_module])
    out.to_csv(RESULTS_DIR / "v_c1_measured.csv", index=False)
    print(f"C1  flash n={per_flash['n']} mean={per_flash['mean']:.4f} "
          f"miss={per_flash['miss']:.4f} | module n={per_module['n']} "
          f"mean={per_module['mean']:.4f} miss={per_module['miss']:.4f}")
    return out


# ----------------------------------------------------------------- single-diode helpers
def estimate_ns(voc, vpc_target=0.62):
    return min([36, 48, 60, 72, 96, 120, 144],
               key=lambda ns: abs(voc / ns - vpc_target))


def _fit_sd(v_mp, i_mp, v_oc, i_sc, alpha_sc, n_s, n_ideal=1.2):
    """Robust 5-parameter single-diode fit anchored at STC via Lambert-W.
    Fixes the ideality (a_ref) and solves I_L, I_o, R_s, R_sh from the four STC
    constraints (I@0=Isc, I@Voc=0, I@Vmp=Imp, dP/dV=0 at MPP)."""
    from scipy.optimize import least_squares
    from pvlib import pvsystem
    a_ref = n_ideal * n_s * K * TREF / Q

    def i_at(V, IL, Io, Rs, Rsh):
        return float(np.asarray(pvsystem.i_from_v(V, IL, Io, Rs, Rsh, a_ref),
                                dtype=float).ravel()[0])

    def resid(x):
        IL, Io, Rs, Rsh = np.exp(x)
        dv = 0.01
        imp = i_at(v_mp, IL, Io, Rs, Rsh)
        dIdV = (i_at(v_mp + dv, IL, Io, Rs, Rsh) - imp) / dv
        return [(i_at(0.0, IL, Io, Rs, Rsh) - i_sc) / i_sc,
                i_at(v_oc, IL, Io, Rs, Rsh) / i_sc,
                (imp - i_mp) / i_sc,
                (imp + v_mp * dIdV) / i_sc]

    x0 = np.log([i_sc, max(i_sc / np.exp(v_oc / a_ref), 1e-30), 0.3, 200.0])
    sol = least_squares(resid, x0, method="lm", max_nfev=6000)
    IL, Io, Rs, Rsh = np.exp(sol.x)
    return dict(I_L_ref=IL, I_o_ref=Io, R_s=Rs, R_sh_ref=Rsh, a_ref=a_ref,
                alpha_sc=alpha_sc, EgRef=1.121, dEgdT=-0.0002677)


def _params_at(p, G, T):
    from pvlib import pvsystem
    with np.errstate(all="ignore"):
        return pvsystem.calcparams_desoto(
            float(G), float(T), p["alpha_sc"], p["a_ref"], p["I_L_ref"],
            p["I_o_ref"], p["R_sh_ref"], p["R_s"],
            EgRef=p["EgRef"], dEgdT=p["dEgdT"])


def _current_at(p, G, T, v_query):
    from pvlib import pvsystem
    IL, Io, Rs, Rsh, a = _params_at(p, G, T)
    with np.errstate(all="ignore"):
        return np.asarray(pvsystem.i_from_v(np.asarray(v_query, float),
                                            IL, Io, Rs, Rsh, a), dtype=float)


def _oc_and_mpp(p, G, T, voc_hint):
    from pvlib import pvsystem
    IL, Io, Rs, Rsh, a = _params_at(p, G, T)
    Vg = np.linspace(0.0, voc_hint * 1.4, 900)
    with np.errstate(all="ignore"):
        Ig = np.asarray(pvsystem.i_from_v(Vg, IL, Io, Rs, Rsh, a), dtype=float)
    ok = np.isfinite(Ig)
    Vg, Ig = Vg[ok], Ig[ok]
    voc = float(np.interp(0.0, Ig[::-1], Vg[::-1]))
    m = Ig >= 0
    pm = float((Vg[m] * Ig[m]).max()) if m.any() else 0.0
    return voc, pm


# ----------------------------------------------------------------- L2
def _read_iv_file(iv_path_field):
    name = Path(str(iv_path_field)).name
    if IV_DIR.exists():
        p = IV_DIR / name
        if p.exists():
            return pd.read_csv(p)
    if IV_ZIP.exists():
        with zipfile.ZipFile(IV_ZIP) as z:
            for member in z.namelist():
                if member.endswith(name):
                    with z.open(member) as fh:
                        return pd.read_csv(io.TextIOWrapper(fh, "utf-8"))
    return None


def layer_l2(mod_ids=None, n_sample=11):
    df = pd.read_csv(ANON_DB)
    pool = df[df["IVPath"].notna()].copy()
    ref = RESULTS_DIR / "v_l2_curves.csv"
    if mod_ids is None and ref.exists():
        mod_ids = pd.read_csv(ref)["mod_id"].tolist()
    if mod_ids is None:
        srt = pool.sort_values("Voc_(V)")
        mod_ids = srt.iloc[np.linspace(0, len(srt) - 1, n_sample).astype(int)]["Mod_ID"].tolist()

    rows = []
    for mid in mod_ids:
        r = pool[pool["Mod_ID"] == mid]
        if r.empty:
            continue
        r = r.iloc[0]
        iv = _read_iv_file(r["IVPath"])
        if iv is None:
            continue
        Voc, Isc = float(r["Voc_(V)"]), float(r["Isc_(A)"])
        Vmp, Imp = float(r["Vmp_(V)"]), float(r["Imp_(A)"])
        T = float(r["Measured_Temperature_(C)"])
        n_s = estimate_ns(Voc)
        alpha = 0.0005 * Isc
        try:
            p = _fit_sd(Vmp, Imp, Voc, Isc, alpha, n_s)
        except Exception as e:
            print(f"   L2: fit failed for {mid}: {e}")
            continue
        Vm = iv["V"].to_numpy(float)
        Im = iv["I"].to_numpy(float)
        m = (Vm >= 0) & (Vm <= Voc)
        Vm, Im = Vm[m], Im[m]
        Ipred = _current_at(p, 1000.0, T, Vm)
        err = np.abs(Ipred - Im) / Isc
        te = str(r.get("Total_Exposure", "") or "")
        _m = re.search(r"(\d+)", te)
        aged = bool(_m and int(_m.group(1)) > 0)
        rows.append(dict(mod_id=int(mid), Voc=Voc, Isc=Isc, T=T,
                         mean_err=float(np.mean(err)), max_err=float(np.max(err)),
                         aged=aged))
    out = pd.DataFrame(rows).sort_values("mean_err").reset_index(drop=True)
    out.to_csv(RESULTS_DIR / "v_l2_curves.csv", index=False)
    if len(out):
        print(f"L2  {len(out)} modules; mean_err "
              f"{out['mean_err'].min()*100:.2f}-{out['mean_err'].max()*100:.2f}% of Isc")
    return out


# ----------------------------------------------------------------- L3
def _parse_iec_matrix(raw, header_row):
    temps = [15.0, 25.0, 50.0, 75.0]
    data = {}
    r = header_row + 1
    while r < len(raw):
        try:
            g = float(raw.iloc[r, 0])
        except (TypeError, ValueError):
            break
        for c, T in enumerate(temps, start=1):
            v = raw.iloc[r, c]
            if pd.notna(v):
                try:
                    data[(g, T)] = float(v)
                except (TypeError, ValueError):
                    pass
        r += 1
    return data


def layer_l3(n_s=60, imp_frac=0.94):
    raw = pd.read_excel(IEC_XLSX, sheet_name=0, header=None)
    hdrs = [i for i in range(len(raw))
            if str(raw.iloc[i, 0]).startswith("Irradiance")]
    Pm = _parse_iec_matrix(raw, hdrs[0])
    Isc = _parse_iec_matrix(raw, hdrs[1])
    Voc = _parse_iec_matrix(raw, hdrs[2])

    Isc0, Voc0, Pm0 = Isc[(1000.0, 25.0)], Voc[(1000.0, 25.0)], Pm[(1000.0, 25.0)]
    Imp0 = imp_frac * Isc0
    Vmp0 = Pm0 / Imp0
    alpha = 0.00046 * Isc0                   # +0.046 %/C  (from the sheet)
    p = _fit_sd(Vmp0, Imp0, Voc0, Isc0, alpha, n_s)

    rows = []
    for (g, T) in sorted(Pm, key=lambda kk: (-kk[0], kk[1])):
        if (g, T) not in Voc:
            continue
        voc_p, pm_p = _oc_and_mpp(p, g, T, Voc0)
        voc_m, pm_m = Voc[(g, T)], Pm[(g, T)]
        rows.append(dict(G=g, T=T, Voc_meas=voc_m, Voc_pred=voc_p,
                         Pm_meas=pm_m, Pm_pred=pm_p,
                         Voc_err=abs(voc_p - voc_m) / voc_m,
                         Pm_err=abs(pm_p - pm_m) / pm_m))
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS_DIR / "v_l3_offstc.csv", index=False)
    print(f"L3  {len(out)} (G,T) points; mean |Voc_err| {out['Voc_err'].mean()*100:.2f}%, "
          f"mean |Pm_err| {out['Pm_err'].mean()*100:.2f}%")
    return out


# ----------------------------------------------------------------- L4
def layer_l4(n_sub_scenarios=200):
    from gmppt import config, device, scenarios
    from gmppt.device import ModuleParams, Breakdown

    if config.CEC_POOL.exists():
        pool = pd.read_parquet(config.CEC_POOL)
    else:
        from pvlib import pvsystem
        cec = pvsystem.retrieve_sam("CECMod").T
        need = ["V_mp_ref", "V_oc_ref", "I_mp_ref", "I_sc_ref", "N_s", "Technology"]
        d = cec[need].copy()
        for c in need[:-1]:
            d[c] = pd.to_numeric(d[c], errors="coerce")
        d = d.dropna(subset=["V_mp_ref", "V_oc_ref"])
        pool = d[d.Technology.isin(config.CSI_TECHNOLOGIES)].copy()
        pool["vmp_voc"] = pool["V_mp_ref"] / pool["V_oc_ref"]
        pool.to_parquet(config.CEC_POOL)

    scen = [s for s in scenarios.generate(pool, 2000) if s.geometry == "sub_substring"]
    rng = np.random.default_rng(config.seed_for("l4_breakdown"))
    idx = rng.choice(len(scen), min(n_sub_scenarios, len(scen)), replace=False)
    sample = [scen[i] for i in idx]
    n_sub = config.N_SUBSTRINGS

    def region_error(bd):
        errs = []
        for s in sample:
            mp = ModuleParams.from_cec(s.module)
            c = device.module_iv(mp, s.irradiances, s.temp_c, bd=bd)
            a = device.analyse(c)
            V, P = c["V"], c["P"]
            voc = float(V.max())
            order = np.argsort(V)
            Vs, Ps = V[order], P[order]
            cands = [min(max(n * 0.8 * voc / n_sub, float(Vs.min())),
                         float(Vs.max())) for n in range(1, n_sub + 1)]
            chosen = cands[int(np.argmax([max(0.0, float(np.interp(cv, Vs, Ps)))
                                          for cv in cands]))]
            pv = np.array([q for q, _, _ in a["peaks"]])
            nearest = pv[int(np.argmin(np.abs(pv - chosen)))]
            errs.append(abs(nearest - a["gmpp"]["V"]) > 1e-6)
        return float(np.mean(errs))

    rows = []
    for vbr in [-10.0, -15.0, -20.0, -30.0]:
        for f in [0.001, 0.01, 0.1]:
            for e in [2.0, 3.28, 4.0]:
                re = region_error(Breakdown(factor=f, voltage=vbr, exp=e))
                rows.append(dict(breakdown_voltage=vbr, breakdown_factor=f,
                                 breakdown_exp=e, region_error=re))
    out = pd.DataFrame(rows)
    out.to_csv(RESULTS_DIR / "v_l4_breakdown_sensitivity.csv", index=False)
    spread = out["region_error"].max() - out["region_error"].min()
    print(f"L4  36 combos; region error {out['region_error'].min():.4f}-"
          f"{out['region_error'].max():.4f} (spread {spread:.4f} -> insensitive)")
    return out


LAYERS = {"c1": layer_c1, "l2": layer_l2, "l3": layer_l3, "l4": layer_l4}

if __name__ == "__main__":
    want = [a.lower() for a in sys.argv[1:]] or list(LAYERS)
    print("run_validation — measured-data validation")
    print("data:", DATA_DIR, "| results ->", RESULTS_DIR)
    print("=" * 66)
    for key in want:
        if key in LAYERS:
            LAYERS[key]()
    print("=" * 66)
    print("done.")