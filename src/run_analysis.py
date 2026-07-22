
import argparse
import hashlib
import json
import math
import platform
import re
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy
import scipy.stats as stats
import statsmodels.api as sm
from statsmodels.stats.outliers_influence import variance_inflation_factor

RANDOM_SEED = 20260325
EXPECTED = {
    "raw_n": 376,
    "time_clean_n": 360,
    "quality_n": 232,
    "time_threshold_p05_seconds": 126,
    "attention21_pass_n": 264,
    "attention26_pass_n": 268,
    "attention_both_pass_n": 240,
}
CORE = ["bank_service", "bank_trustsec", "bank_satisfaction", "bank_future", "mox_support", "ai_attitude"]
VARIABLE_DEFINITIONS = {
    "bank_service": "Mean of five Q10 service-performance items; higher means stronger perceived service performance.",
    "bank_trustsec": "Mean of Q10 security perception and perceived control; higher means stronger perceived trust/security/control.",
    "bank_satisfaction": "Q11 satisfaction item; higher means greater satisfaction.",
    "bank_future": "Q11 future use intention item; higher means stronger future use intention.",
    "mox_support_raw": "Q16 original coding, where 1 means strongly support and 5 means strongly oppose.",
    "mox_support": "Reverse-coded Q16 as 6 - mox_support_raw; higher means stronger support.",
    "ai_attitude": "Q5 original coding: 1=very anxious/resistant, 2=somewhat uneasy, 3=neutral, 4=somewhat interested, 5=very excited.",
}
KEYWORDS = {
    "duration": "所用时间",
    "attention21": "21ATTENTION",
    "attention26": "26ATTENTION",
    "ai_attitude": "5、面对新的 AI 技术或智能工具",
    "q10_reliability": "10、针对您最常使用的银行聊天机器人",
    "q10_ease": "10、易用性",
    "q10_response": "10、响应性",
    "q10_solve": "10、问题解决能力",
    "q10_natural": "10、交互自然度",
    "q10_security": "10、安全感知",
    "q10_control": "10、掌控感",
    "q11_satisfaction": "11、基于上述体验",
    "q11_trust": "11、信任度",
    "q11_future": "11、未来使用意愿",
    "q16": "16、Mox Bank 准备上线的聊天机器人模块",
}


def p_fmt(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return "NA"
    return "p<0.001" if p < 0.001 else f"p={p:.3f}"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_duration_seconds(value):
    if pd.isna(value):
        return np.nan
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    text = str(value).strip().lower()
    if not text:
        return np.nan
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    if re.fullmatch(r"\d{1,2}:\d{1,2}:\d{1,2}", text):
        h, m, s = [float(x) for x in text.split(":")]
        return h * 3600 + m * 60 + s
    if re.fullmatch(r"\d{1,2}:\d{1,2}", text):
        m, s = [float(x) for x in text.split(":")]
        return m * 60 + s
    total = 0.0
    matched = False
    units = r"小时|小時|时|時|h|hr|hrs|hour|hours|分|分钟|分鐘|m|min|mins|minute|minutes|秒|s|sec|secs|second|seconds"
    for num, unit in re.findall(rf"(\d+(?:\.\d+)?)\s*({units})", text):
        matched = True
        v = float(num)
        if unit in {"小时", "小時", "时", "時", "h", "hr", "hrs", "hour", "hours"}:
            total += v * 3600
        elif unit in {"分", "分钟", "分鐘", "m", "min", "mins", "minute", "minutes"}:
            total += v * 60
        else:
            total += v
    if matched:
        return total
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    return float(nums[0]) if len(nums) == 1 else np.nan


def find_col(cols, keyword):
    for col in cols:
        if keyword in str(col):
            return col
    if keyword == "21ATTENTION":
        for col in cols:
            if "注意力检测" in str(col) and "21、" in str(col):
                return col
    if keyword == "26ATTENTION":
        for col in cols:
            if "注意力检测" in str(col) and "26、" in str(col):
                return col
    raise KeyError(f"Required column not found: {keyword}")


def locate_columns(df):
    cols = list(df.columns)
    return {k: find_col(cols, v) for k, v in KEYWORDS.items()}


def num(s):
    return pd.to_numeric(s, errors="coerce")


def cronbach_alpha(frame):
    data = frame.apply(pd.to_numeric, errors="coerce").dropna()
    k = data.shape[1]
    if k < 2 or data.shape[0] < 3:
        return np.nan
    total_var = data.sum(axis=1).var(ddof=1)
    return float(k / (k - 1) * (1 - data.var(axis=0, ddof=1).sum() / total_var)) if total_var else np.nan


def ols(df, y, xs):
    data = df[[y] + xs].dropna()
    X = sm.add_constant(data[xs], has_constant="add")
    model = sm.OLS(data[y], X).fit()
    robust = model.get_robustcov_results(cov_type="HC3")
    robust_ci = robust.conf_int()
    conventional_ci = model.conf_int()
    names = list(model.params.index)
    params = {}
    for i, name in enumerate(names):
        params[name] = {
            "coef": float(model.params[name]),
            "se_conventional_ols": float(model.bse[name]),
            "p_conventional_ols": float(model.pvalues[name]),
            "p_conventional_ols_formatted": p_fmt(float(model.pvalues[name])),
            "ci95_conventional_ols": [float(conventional_ci.loc[name, 0]), float(conventional_ci.loc[name, 1])],
            "robust_se_hc3": float(robust.bse[i]),
            "robust_p_hc3": float(robust.pvalues[i]),
            "robust_p_hc3_formatted": p_fmt(float(robust.pvalues[i])),
            "robust_ci95_hc3": [float(robust_ci[i][0]), float(robust_ci[i][1])],
        }
    f_hc3 = None
    p_hc3 = None
    if xs:
        constraints = np.zeros((len(xs), len(names)))
        for row, term in enumerate(xs):
            constraints[row, names.index(term)] = 1
        try:
            test = robust.wald_test(constraints, use_f=True, scalar=True)
            f_hc3 = float(test.statistic)
            p_hc3 = float(test.pvalue)
        except Exception:
            test = robust.wald_test(constraints, scalar=True)
            f_hc3 = float(test.statistic)
            p_hc3 = float(test.pvalue)
    return {
        "n": int(model.nobs),
        "df_model": float(model.df_model),
        "df_resid": float(model.df_resid),
        "f_statistic_conventional_ols": float(model.fvalue) if model.fvalue is not None else None,
        "model_p_conventional_ols": float(model.f_pvalue) if model.f_pvalue is not None else None,
        "model_p_conventional_ols_formatted": p_fmt(float(model.f_pvalue)) if model.f_pvalue is not None else "NA",
        "f_statistic_hc3": f_hc3,
        "model_p_hc3": p_hc3,
        "model_p_hc3_formatted": p_fmt(p_hc3),
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
        "params": params,
        "primary_inference": "HC3 robust standard errors, confidence intervals, and overall model test",
    }

def vif(df, xs):
    data = df[xs].dropna()
    X = sm.add_constant(data, has_constant="add")
    return {name: float(variance_inflation_factor(X.values, i)) for i, name in enumerate(X.columns) if name != "const"}


def mediation(df, x, m, y, covariates=None, reps=5000):
    covariates = covariates or []
    cols = [x, m, y] + covariates
    data = df[cols].dropna()
    n = len(data)
    med_xs = [x] + covariates
    out_xs = [x, m] + covariates
    med = sm.OLS(data[m], sm.add_constant(data[med_xs], has_constant="add")).fit()
    out = sm.OLS(data[y], sm.add_constant(data[out_xs], has_constant="add")).fit()
    total = sm.OLS(data[y], sm.add_constant(data[[x] + covariates], has_constant="add")).fit()
    indirect = float(med.params[x] * out.params[m])
    rng = np.random.default_rng(RANDOM_SEED)
    boots = []
    for _ in range(reps):
        sample = data.iloc[rng.integers(0, n, n)]
        try:
            a = sm.OLS(sample[m], sm.add_constant(sample[med_xs], has_constant="add")).fit().params[x]
            b = sm.OLS(sample[y], sm.add_constant(sample[out_xs], has_constant="add")).fit().params[m]
            boots.append(float(a * b))
        except Exception:
            pass
    ci = np.percentile(boots, [2.5, 97.5]).tolist()
    z = indirect / np.std(boots, ddof=1) if np.std(boots, ddof=1) > 0 else np.nan
    approx_p = float(2 * (1 - stats.norm.cdf(abs(z)))) if not np.isnan(z) else np.nan
    return {
        "n": int(n),
        "x": x,
        "mediator": m,
        "y": y,
        "covariates": covariates,
        "a_path": {"coef": float(med.params[x]), "p": float(med.pvalues[x]), "p_formatted": p_fmt(float(med.pvalues[x]))},
        "b_path": {"coef": float(out.params[m]), "p": float(out.pvalues[m]), "p_formatted": p_fmt(float(out.pvalues[m]))},
        "direct_effect": {"coef": float(out.params[x]), "p": float(out.pvalues[x]), "p_formatted": p_fmt(float(out.pvalues[x]))},
        "indirect_effect": {
            "coef": indirect,
            "ci95_bootstrap": [float(ci[0]), float(ci[1])],
            "normal_approximation_p": approx_p,
            "normal_approximation_p_formatted": p_fmt(approx_p),
            "primary_inference": "bootstrap confidence interval",
        },
        "total_effect": {"coef": float(total.params[x]), "p": float(total.pvalues[x]), "p_formatted": p_fmt(float(total.pvalues[x]))},
        "bootstrap_reps": len(boots),
    }


def prepare_canonical(path):
    raw = pd.read_excel(path)
    mapping = locate_columns(raw)
    duration = raw[mapping["duration"]].map(parse_duration_seconds)
    threshold = float(np.percentile(duration.dropna(), 5))
    time_keep = duration >= threshold
    att21 = num(raw[mapping["attention21"]]) == 2
    att26 = num(raw[mapping["attention26"]]) == 2
    keep = time_keep & att21 & att26
    df = pd.DataFrame(index=raw.index)
    for key, col in mapping.items():
        if key not in {"duration", "attention21", "attention26"}:
            df[key] = num(raw[col])
    service = ["q10_reliability", "q10_ease", "q10_response", "q10_solve", "q10_natural"]
    trust = ["q10_security", "q10_control"]
    df["duration_seconds"] = duration
    df["quality_keep"] = keep
    df["bank_service"] = df[service].mean(axis=1)
    df["bank_trustsec"] = df[trust].mean(axis=1)
    df["bank_satisfaction"] = df["q11_satisfaction"]
    df["bank_future"] = df["q11_future"]
    df["mox_support_raw"] = df["q16"]
    df["mox_support"] = 6 - df["mox_support_raw"]
    checks = {
        "raw_n": int(len(raw)),
        "time_threshold_p05_seconds": int(round(threshold)),
        "time_clean_n": int(time_keep.sum()),
        "attention21_pass_n": int(att21.sum()),
        "attention26_pass_n": int(att26.sum()),
        "attention_both_pass_n": int((att21 & att26).sum()),
        "quality_n": int(keep.sum()),
    }
    clean = df.loc[keep].copy()
    clean["centered_bank_trustsec"] = clean["bank_trustsec"] - clean["bank_trustsec"].mean()
    clean["centered_ai_attitude"] = clean["ai_attitude"] - clean["ai_attitude"].mean()
    clean["interaction"] = clean["centered_bank_trustsec"] * clean["centered_ai_attitude"]
    private = {
        "input_file_name": path.name,
        "input_sha256": sha256_file(path),
        "input_size_bytes": path.stat().st_size,
        "column_mapping": {k: str(v) for k, v in mapping.items()},
    }
    return clean, checks, private


def prepare_demo(path):
    df = pd.read_csv(path)
    missing = [c for c in CORE if c not in df.columns]
    if missing:
        raise ValueError("Demo input missing columns: " + ", ".join(missing))
    df["centered_bank_trustsec"] = df["bank_trustsec"] - df["bank_trustsec"].mean()
    df["centered_ai_attitude"] = df["ai_attitude"] - df["ai_attitude"].mean()
    df["interaction"] = df["centered_bank_trustsec"] * df["centered_ai_attitude"]
    return df, {"demo_n": int(len(df)), "quality_n": int(len(df))}, {}


def validate_checks(checks):
    return {k: {"expected": v, "observed": checks.get(k), "match": checks.get(k) == v} for k, v in EXPECTED.items()}


def corr_n_matrix(df, cols):
    out = pd.DataFrame(index=cols, columns=cols, dtype=int)
    for a in cols:
        for b in cols:
            out.loc[a, b] = int(df[[a, b]].dropna().shape[0])
    return out


def run_models(df, mode):
    metrics = {
        "descriptive_statistics": df[CORE].describe().T[["count", "mean", "std", "min", "25%", "50%", "75%", "max"]].to_dict(orient="index"),
        "correlation_matrix": df[CORE].corr().to_dict(),
        "correlation_n_matrix": corr_n_matrix(df, CORE).astype(int).to_dict(),
        "models": {
            "Model A": ols(df, "bank_satisfaction", ["bank_service", "bank_trustsec"]),
            "Model B": ols(df, "bank_future", ["bank_satisfaction", "bank_trustsec", "bank_service"]),
            "Model C": ols(df, "mox_support", ["bank_satisfaction", "bank_trustsec", "bank_service"]),
            "Moderation": ols(df, "bank_future", ["centered_bank_trustsec", "centered_ai_attitude", "interaction"]),
        },
        "vif": {
            "Model A": vif(df, ["bank_service", "bank_trustsec"]),
            "Model B": vif(df, ["bank_satisfaction", "bank_trustsec", "bank_service"]),
            "Model C": vif(df, ["bank_satisfaction", "bank_trustsec", "bank_service"]),
            "Moderation": vif(df, ["centered_bank_trustsec", "centered_ai_attitude", "interaction"]),
        },
    }
    if mode == "canonical":
        metrics["cronbach_alpha"] = {
            "bank_service_q10_5_items": cronbach_alpha(df[["q10_reliability", "q10_ease", "q10_response", "q10_solve", "q10_natural"]]),
            "bank_trustsec_q10_2_items": cronbach_alpha(df[["q10_security", "q10_control"]]),
            "q10_all_7_items": cronbach_alpha(df[["q10_reliability", "q10_ease", "q10_response", "q10_solve", "q10_natural", "q10_security", "q10_control"]]),
        }
        metrics["mediation"] = {
            "Mediation A exploratory bank_service_to_bank_trustsec_to_bank_future": mediation(df, "bank_service", "bank_trustsec", "bank_future"),
            "Mediation B adjusted bank_trustsec_to_bank_satisfaction_to_bank_future_cov_bank_service": mediation(df, "bank_trustsec", "bank_satisfaction", "bank_future", covariates=["bank_service"]),
        }
    return metrics


def save_outputs(metrics, out, mode, checks):
    out.mkdir(parents=True, exist_ok=True)
    tables = out / "tables"
    figs = out / "figures"
    tables.mkdir(exist_ok=True)
    figs.mkdir(exist_ok=True)
    (out / ("canonical_metrics.json" if mode == "canonical" else "demo_metrics.json")).write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    pd.DataFrame(metrics["descriptive_statistics"]).T.to_csv(tables / "descriptive_statistics.csv", encoding="utf-8-sig")
    pd.DataFrame(metrics["correlation_matrix"]).to_csv(tables / "correlation_matrix.csv", encoding="utf-8-sig")
    pd.DataFrame(metrics["correlation_n_matrix"]).to_csv(tables / "correlation_n_matrix.csv", encoding="utf-8-sig")
    rows = []
    for mn, model in metrics["models"].items():
        for term, vals in model["params"].items():
            row = {"model": mn, "term": term, "n": model["n"], "r_squared": model["r_squared"], "adj_r_squared": model["adj_r_squared"], "f_statistic_conventional_ols": model["f_statistic_conventional_ols"], "model_p_conventional_ols": model["model_p_conventional_ols"], "model_p_conventional_ols_formatted": model["model_p_conventional_ols_formatted"], "f_statistic_hc3": model["f_statistic_hc3"], "model_p_hc3": model["model_p_hc3"], "model_p_hc3_formatted": model["model_p_hc3_formatted"]}
            row.update(vals)
            rows.append(row)
    pd.DataFrame(rows).to_csv(tables / "model_coefficients.csv", index=False, encoding="utf-8-sig")
    make_figures(metrics, figs, mode, checks)


def sig_star(p):
    if p < 0.001:
        return "***"
    if p < 0.01:
        return "**"
    if p < 0.05:
        return "*"
    return ""


def make_figures(metrics, figs, mode, checks):
    if mode == "canonical":
        labels = ["Raw responses", "After duration screen", "Final quality sample"]
        values = [checks["raw_n"], checks["time_clean_n"], checks["quality_n"]]
        plt.figure(figsize=(7, 4.2))
        bars = plt.bar(labels, values, color=["#3B6EA8", "#F28E2B", "#59A14F"])
        for b, v in zip(bars, values):
            plt.text(b.get_x() + b.get_width() / 2, v + 5, str(v), ha="center")
        plt.text(1.0, max(values) * 0.78, f"Note: both attention checks passed = {checks['attention_both_pass_n']} of raw responses; this is an independent raw-sample count, not a funnel step.", ha="center", va="center", fontsize=8, wrap=True)
        plt.ylabel("Responses")
        plt.title("Sample Screening")
        plt.tight_layout()
        plt.savefig(figs / "01_sample_screening.png", dpi=170)
        plt.close()
    desc = pd.DataFrame(metrics["descriptive_statistics"]).T
    xs = np.arange(len(desc))
    ci = 1.96 * desc["std"] / np.sqrt(desc["count"])
    plt.figure(figsize=(8, 4.8))
    plt.errorbar(xs, desc["mean"], yerr=ci, fmt="o", capsize=4, color="#2F4B7C")
    for i, (_, row) in enumerate(desc.iterrows()):
        plt.text(i, row["mean"] + ci.iloc[i] + 0.06, f"n={int(row['count'])}", ha="center", fontsize=8)
    plt.xticks(xs, desc.index, rotation=30, ha="right")
    plt.ylim(1, 5)
    plt.ylabel("Mean with 95% CI")
    plt.title("Core Variable Descriptives")
    plt.tight_layout()
    plt.savefig(figs / "02_core_descriptives_ci.png", dpi=170)
    plt.close()
    corr = pd.DataFrame(metrics["correlation_matrix"])
    plt.figure(figsize=(7, 6))
    plt.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
    plt.colorbar(label="Pearson r")
    plt.xticks(range(len(corr)), corr.columns, rotation=45, ha="right")
    plt.yticks(range(len(corr)), corr.index)
    for i in range(len(corr)):
        for j in range(len(corr)):
            plt.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    plt.title("Correlation Matrix (pairwise-complete observations; mox_support pairs have smaller n)")
    plt.tight_layout()
    plt.savefig(figs / "03_correlation_heatmap.png", dpi=170)
    plt.close()
    for idx, mn in enumerate(["Model A", "Model B", "Model C"], start=4):
        model = metrics["models"][mn]
        terms = [t for t in model["params"] if t != "const"]
        coefs = [model["params"][t]["coef"] for t in terms]
        lows = [model["params"][t]["robust_ci95_hc3"][0] for t in terms]
        highs = [model["params"][t]["robust_ci95_hc3"][1] for t in terms]
        y = np.arange(len(terms))
        plt.figure(figsize=(7, 4))
        plt.axvline(0, color="#555", linewidth=1)
        plt.errorbar(coefs, y, xerr=[np.array(coefs) - np.array(lows), np.array(highs) - np.array(coefs)], fmt="o", capsize=4, color="#2F4B7C")
        for c, yy, t in zip(coefs, y, terms):
            p = model["params"][t]["robust_p_hc3"]
            plt.text(c, yy + 0.12, f"{c:.2f}{sig_star(p)}", ha="center", fontsize=8)
        plt.yticks(y, terms)
        plt.xlabel("Coefficient with HC3 robust 95% CI")
        plt.title(f"{mn} HC3 Coefficients (n={model['n']}, R²={model['r_squared']:.3f})")
        plt.tight_layout()
        plt.savefig(figs / f"0{idx}_{mn.lower().replace(' ', '_')}_coef_ci.png", dpi=170)
        plt.close()


def run_analysis(mode, input_path, output_dir, provenance_output=None):
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")
    private = {}
    if mode == "canonical":
        data, checks, private = prepare_canonical(input_path)
        validation = validate_checks(checks)
        if not all(v["match"] for v in validation.values()):
            print(json.dumps({"error": "canonical validation failed", "validation": validation}, ensure_ascii=False), file=sys.stderr)
            return 2
    elif mode == "demo":
        data, checks, private = prepare_demo(input_path)
        validation = {}
    else:
        raise ValueError("mode must be canonical or demo")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        metrics = run_models(data, mode)
    metrics.update({
        "mode": mode,
        "run_metadata": {
            "run_time_utc": datetime.now(timezone.utc).isoformat(),
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "random_seed": RANDOM_SEED,
            "libraries": {"pandas": pd.__version__, "numpy": np.__version__, "scipy": scipy.__version__, "statsmodels": sm.__version__},
            "warnings": sorted({str(w.message) for w in caught}),
        },
        "input_file": {"safe_path": "<private-input>" if mode == "canonical" else input_path.name, "size_bytes": input_path.stat().st_size if mode == "demo" else None},
        "variable_definitions": VARIABLE_DEFINITIONS,
        "cleaning_rules": {"duration": "Keep responses at or above the 5th percentile duration threshold.", "attention": "Both attention checks must equal coding value 2.", "privacy": "Raw responses and sensitive metadata are excluded from public outputs."},
        "sample_checks": checks,
        "expected_validation": validation,
        "validation_passed": all(v["match"] for v in validation.values()) if validation else None,
        "private_provenance": private,
        "efa_status": "Excluded from public main results because KMO/Bartlett/rotation validation was not completed.",
    })
    public_metrics = dict(metrics)
    public_metrics.pop("private_provenance", None)
    save_outputs(public_metrics, output_dir, mode, checks)
    if mode == "canonical" and provenance_output:
        provenance_path = Path(provenance_output)
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        provenance_path.write_text(json.dumps(private, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"mode": mode, "n": checks.get("quality_n"), "validation_passed": public_metrics.get("validation_passed")}, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run IPMN MOX analysis in canonical or demo mode.")
    parser.add_argument("--mode", choices=["canonical", "demo",], required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--provenance-output", default=None)
    args = parser.parse_args()
    try:
        code = run_analysis(args.mode, args.input, args.output, args.provenance_output)
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
