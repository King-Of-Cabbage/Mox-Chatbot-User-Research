import argparse
import hashlib
import json
import math
import platform
import re
import shutil
import sys
import tempfile
import unicodedata
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
CORE = [
    "bank_service",
    "bank_security_control",
    "bank_satisfaction",
    "bank_future",
    "mox_support",
    "ai_attitude",
]
SUPPLEMENTARY = ["bank_trust_outcome"]
DISPLAY_LABELS = {
    "bank_service": "Service quality",
    "bank_security_control": "Security & control",
    "bank_satisfaction": "Satisfaction",
    "bank_future": "Future use",
    "mox_support": "Mox support",
    "ai_attitude": "AI attitude",
    "bank_trust_outcome": "Trust outcome",
    "centered_bank_security_control": "Security & control",
    "centered_ai_attitude": "AI attitude",
    "interaction": "Interaction",
    "const": "Intercept",
}
VARIABLE_DEFINITIONS = {
    "bank_service": "Mean of five Q10 service-performance items; at least four valid items are required; higher values indicate stronger perceived service quality.",
    "bank_security_control": "Mean of Q10 security perception and perceived control; higher values indicate stronger perceived security and control.",
    "bank_satisfaction": "Q11 satisfaction item; higher values indicate greater satisfaction.",
    "bank_trust_outcome": "Q11 trust item; supplementary single-item outcome only, not included in the main models.",
    "bank_future": "Q11 future use intention item; higher values indicate stronger future use intention.",
    "mox_support_raw": "Q16 original coding, where 1 means strongly support and 5 means strongly oppose.",
    "mox_support": "Reverse-coded Q16 as 6 - mox_support_raw; higher values indicate stronger support.",
    "ai_attitude": "Q5 original coding: 1=very anxious/resistant, 2=somewhat uneasy, 3=neutral, 4=somewhat interested, 5=very excited.",
}
FIELD_REGISTRY = {
    "duration": {
        "exact": ["所用时间"],
        "role": "response duration",
    },
    "attention21": {"exact": ["21ATTENTION"], "role": "attention check; correct coding value is 2"},
    "attention26": {"exact": ["26ATTENTION"], "role": "attention check; correct coding value is 2"},
    "ai_attitude": {
        "exact": ["5、面对新的 AI 技术或智能工具（如聊天机器人、语音助手等），您通常的感受是 🤖"],
        "role": "Q5 AI attitude",
    },
    "q10_reliability": {
        "exact": ["10、针对您最常使用的银行聊天机器人，您在多大程度上同意以下描述？ 📊—可靠性：它能准确理解我的问题"],
        "role": "Q10 reliability",
    },
    "q10_ease": {"exact": ["10、易用性：与它对话的界面和流程很顺畅"], "role": "Q10 ease of use"},
    "q10_response": {"exact": ["10、响应性：它能快速回应我的请求"], "role": "Q10 responsiveness"},
    "q10_solve": {"exact": ["10、问题解决能力：它能独立解决我的大部分问题"], "role": "Q10 problem-solving ability"},
    "q10_natural": {"exact": ["10、交互自然度：与它交流时感觉像在和真人对话"], "role": "Q10 natural interaction"},
    "q10_security": {"exact": ["10、安全感知：我相信它能妥善保护我的个人和账户信息"], "role": "Q10 security perception"},
    "q10_control": {"exact": ["10、掌控感：在整个对话中，我感觉自己控制着局面"], "role": "Q10 perceived control"},
    "q11_satisfaction": {
        "exact": ["11、基于上述体验，请评价您的整体看法： 📊—满意度：我对交互体验感到满意"],
        "role": "Q11 satisfaction",
    },
    "bank_trust_outcome": {
        "exact": ["11、信任度：我信任它能提供准确和安全的服务"],
        "role": "Q11 trust outcome; supplementary only",
    },
    "q11_future": {
        "exact": ["11、未来使用意愿：我未来愿意继续使用它处理简单的银行业务"],
        "role": "Q11 future use intention",
    },
    "q16": {
        "exact": ["16、Mox Bank 准备上线的聊天机器人模块，您在多大程度上认同这一策略？ 🤔"],
        "role": "Q16 Mox support raw coding",
    },
}
MODELS = {
    "Model A": ("bank_satisfaction", ["bank_service", "bank_security_control"]),
    "Model B": ("bank_future", ["bank_satisfaction", "bank_security_control", "bank_service"]),
    "Model C": ("mox_support", ["bank_satisfaction", "bank_security_control", "bank_service"]),
    "Moderation": ("bank_future", ["centered_bank_security_control", "centered_ai_attitude", "interaction"]),
}


class AnalysisValidationError(ValueError):
    pass


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


def normalize_header(value):
    text = unicodedata.normalize("NFKC", str(value)).strip()
    replacements = {"，": ",", "：": ":", "（": "(", "）": ")", "—": "-", "－": "-", "、": "、"}
    for old, new in replacements.items():
        text = text.replace(old, new)
    return re.sub(r"\s+", " ", text)


def _norm_options(options):
    return [normalize_header(x) for x in options]


def locate_columns(headers):
    normalized = [normalize_header(c) for c in headers]
    duplicates = sorted({c for c in normalized if normalized.count(c) > 1})
    if duplicates:
        raise AnalysisValidationError("Duplicate normalized column names found: " + ", ".join(duplicates[:8]))
    mapping = {}
    for safe_name, spec in FIELD_REGISTRY.items():
        candidates = []
        exact = set(_norm_options(spec["exact"]))
        aliases = set(_norm_options(spec.get("aliases", [])))
        allowed = exact | aliases
        for original, normed in zip(headers, normalized):
            if normed in allowed:
                candidates.append(original)
        if len(candidates) == 0:
            raise AnalysisValidationError(f"Missing required field: {safe_name}")
        if len(candidates) > 1:
            safe_candidates = [normalize_header(c) for c in candidates]
            raise AnalysisValidationError(f"Ambiguous field mapping for {safe_name}: {safe_candidates}")
        mapping[safe_name] = candidates[0]
    return mapping


def read_sheet1(path):
    xl = pd.ExcelFile(path)
    if "Sheet1" not in xl.sheet_names:
        raise AnalysisValidationError("Required worksheet Sheet1 not found. Available worksheets: " + ", ".join(xl.sheet_names))
    return pd.read_excel(path, sheet_name="Sheet1")


def parse_duration_seconds(value):
    if pd.isna(value):
        return np.nan
    if isinstance(value, (int, float, np.integer, np.floating)):
        value = float(value)
        if not math.isfinite(value) or value < 0:
            return np.nan
        return value
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    if not text:
        return np.nan
    if text.startswith("-"):
        return np.nan
    if re.fullmatch(r"\d+(\.\d+)?", text):
        return float(text)
    if re.fullmatch(r"\d{1,2}:\d{1,2}(:\d{1,2})?", text):
        parts = [int(x) for x in text.split(":")]
        if len(parts) == 2:
            minutes, seconds = parts
            return np.nan if seconds >= 60 else float(minutes * 60 + seconds)
        hours, minutes, seconds = parts
        return np.nan if minutes >= 60 or seconds >= 60 else float(hours * 3600 + minutes * 60 + seconds)
    duration_unit_pattern = re.compile(
        r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>hours|hour|hrs|hr|h|小时|小時|时|時|minutes|minute|mins|min|m|分钟|分鐘|分|seconds|second|secs|sec|s|秒)"
    )
    pos = 0
    total = 0.0
    matched = False
    for match in duration_unit_pattern.finditer(text):
        if text[pos : match.start()].strip():
            return np.nan
        val = float(match.group("num"))
        unit = match.group("unit")
        if val < 0 or not math.isfinite(val):
            return np.nan
        matched = True
        if unit in {"小时", "小時", "时", "時", "h", "hr", "hrs", "hour", "hours"}:
            total += val * 3600
        elif unit in {"分钟", "分鐘", "分", "m", "min", "mins", "minute", "minutes"}:
            total += val * 60
        else:
            total += val
        pos = match.end()
    if text[pos:].strip():
        return np.nan
    return total if matched and math.isfinite(total) and total >= 0 else np.nan


def validate_duration_series(series):
    parsed = series.map(parse_duration_seconds)
    nonempty = series.notna() & (series.astype(str).str.strip() != "")
    invalid = nonempty & parsed.isna()
    if invalid.any():
        raise AnalysisValidationError(f"Invalid duration values: count={int(invalid.sum())}")
    if parsed.dropna().empty:
        raise AnalysisValidationError("No valid response duration values were parsed.")
    if (parsed.dropna() < 0).any():
        raise AnalysisValidationError("Negative response duration values found.")
    return parsed


def validate_likert_series(series, safe_name, allowed_range=(1, 5), integer_only=False):
    nonempty = series.notna() & (series.astype(str).str.strip() != "")
    numeric = pd.to_numeric(series, errors="coerce")
    invalid_text = nonempty & numeric.isna()
    if invalid_text.any():
        raise AnalysisValidationError(f"Invalid nonnumeric values in {safe_name}: count={int(invalid_text.sum())}")
    finite = numeric.dropna().map(math.isfinite)
    if not finite.all():
        raise AnalysisValidationError(f"Non-finite numeric values in {safe_name}: count={int((~finite).sum())}")
    lo, hi = allowed_range
    out_of_range = numeric.notna() & ~numeric.between(lo, hi)
    if out_of_range.any():
        raise AnalysisValidationError(f"Out-of-range values in {safe_name}: count={int(out_of_range.sum())}")
    if integer_only:
        decimals = numeric.notna() & (numeric % 1 != 0)
        if decimals.any():
            raise AnalysisValidationError(f"Non-integer Likert values in {safe_name}: count={int(decimals.sum())}")
    return numeric


def score_composite(frame, min_valid, allowed_range=(1, 5)):
    numeric = frame.apply(lambda s: validate_likert_series(s, s.name, allowed_range))
    valid_counts = numeric.notna().sum(axis=1)
    scores = numeric.mean(axis=1)
    scores[valid_counts < min_valid] = np.nan
    return scores, valid_counts


def cronbach_alpha(frame):
    data = frame.apply(lambda s: validate_likert_series(s, s.name)).dropna()
    k = data.shape[1]
    if k < 2 or data.shape[0] < 3:
        return {"alpha": np.nan, "n": int(data.shape[0])}
    total_var = data.sum(axis=1).var(ddof=1)
    alpha = float(k / (k - 1) * (1 - data.var(axis=0, ddof=1).sum() / total_var)) if total_var else np.nan
    return {"alpha": alpha, "n": int(data.shape[0])}


def composite_missingness_audit(df, service_counts, security_counts):
    rows = []
    items = ["q10_reliability", "q10_ease", "q10_response", "q10_solve", "q10_natural", "q10_security", "q10_control"]
    for item in items:
        rows.append({"metric": f"{item}_missing_n", "value": int(df[item].isna().sum())})
    for count, n in service_counts.value_counts(dropna=False).sort_index().items():
        rows.append({"metric": f"bank_service_valid_item_count_{int(count)}", "value": int(n)})
    for count, n in security_counts.value_counts(dropna=False).sort_index().items():
        rows.append({"metric": f"bank_security_control_valid_item_count_{int(count)}", "value": int(n)})
    old_service_n = int(df[["q10_reliability", "q10_ease", "q10_response", "q10_solve", "q10_natural"]].mean(axis=1).notna().sum())
    old_security_n = int(df[["q10_security", "q10_control"]].mean(axis=1).notna().sum())
    rows.extend(
        [
            {"metric": "old_rule_bank_service_valid_n", "value": old_service_n},
            {"metric": "new_rule_bank_service_valid_n", "value": int(df["bank_service"].notna().sum())},
            {"metric": "old_rule_bank_security_control_valid_n", "value": old_security_n},
            {"metric": "new_rule_bank_security_control_valid_n", "value": int(df["bank_security_control"].notna().sum())},
        ]
    )
    return pd.DataFrame(rows)


def _validate_model_input(data, y, xs):
    cols = [y] + xs
    clean = data[cols].dropna()
    if len(clean) <= len(xs) + 2:
        raise AnalysisValidationError(f"Insufficient valid observations for model {y}.")
    if not np.isfinite(clean.to_numpy(dtype=float)).all():
        raise AnalysisValidationError(f"Non-finite values found for model {y}.")
    X = sm.add_constant(clean[xs], has_constant="add")
    if np.linalg.matrix_rank(X.to_numpy(dtype=float)) < X.shape[1]:
        raise AnalysisValidationError(f"Design matrix is rank deficient for model {y}.")
    if float(clean[y].var(ddof=1)) == 0:
        raise AnalysisValidationError(f"Outcome has zero variance for model {y}.")
    for x in xs:
        if float(clean[x].var(ddof=1)) == 0:
            raise AnalysisValidationError(f"Predictor has zero variance: {x}.")
    return clean, X


def ols(df, y, xs):
    data, X = _validate_model_input(df, y, xs)
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
    constraints = np.zeros((len(xs), len(names)))
    for row, term in enumerate(xs):
        constraints[row, names.index(term)] = 1
    test = robust.wald_test(constraints, use_f=True, scalar=True)
    return {
        "n": int(model.nobs),
        "df_model": float(model.df_model),
        "df_resid": float(model.df_resid),
        "f_statistic_conventional_ols": float(model.fvalue) if model.fvalue is not None else None,
        "model_p_conventional_ols": float(model.f_pvalue) if model.f_pvalue is not None else None,
        "model_p_conventional_ols_formatted": p_fmt(float(model.f_pvalue)) if model.f_pvalue is not None else "NA",
        "f_statistic_hc3": float(test.statistic),
        "model_p_hc3": float(test.pvalue),
        "model_p_hc3_formatted": p_fmt(float(test.pvalue)),
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
        "params": params,
        "primary_inference": "HC3 robust standard errors, confidence intervals, and overall model test",
    }


def vif(df, xs):
    data = df[xs].dropna()
    X = sm.add_constant(data, has_constant="add")
    results = {}
    warnings_out = []
    for i, name in enumerate(X.columns):
        if name == "const":
            continue
        try:
            value = float(variance_inflation_factor(X.values, i))
            if not math.isfinite(value):
                warnings_out.append(f"Non-finite VIF for {name}")
            results[name] = value
        except Exception as exc:
            results[name] = None
            warnings_out.append(f"VIF failed for {name}: {type(exc).__name__}")
    return {"values": results, "warnings": warnings_out}


def mediation(df, x, m, y, covariates=None, reps=5000):
    covariates = covariates or []
    cols = [x, m, y] + covariates
    data = df[cols].dropna()
    if len(data) < len(cols) + 10:
        raise AnalysisValidationError("Insufficient data for mediation model.")
    med_xs = [x] + covariates
    out_xs = [x, m] + covariates
    med = sm.OLS(data[m], sm.add_constant(data[med_xs], has_constant="add")).fit()
    out = sm.OLS(data[y], sm.add_constant(data[out_xs], has_constant="add")).fit()
    total = sm.OLS(data[y], sm.add_constant(data[[x] + covariates], has_constant="add")).fit()
    indirect = float(med.params[x] * out.params[m])
    rng = np.random.default_rng(RANDOM_SEED)
    boots = []
    failed = 0
    for _ in range(reps):
        sample = data.iloc[rng.integers(0, len(data), len(data))]
        try:
            a = sm.OLS(sample[m], sm.add_constant(sample[med_xs], has_constant="add")).fit().params[x]
            b = sm.OLS(sample[y], sm.add_constant(sample[out_xs], has_constant="add")).fit().params[m]
            value = float(a * b)
            if math.isfinite(value):
                boots.append(value)
            else:
                failed += 1
        except Exception:
            failed += 1
    success_rate = len(boots) / reps
    if success_rate < 0.99:
        raise AnalysisValidationError(f"Mediation bootstrap success rate below 99%: {success_rate:.3f}")
    ci = np.percentile(boots, [2.5, 97.5]).tolist()
    sd = np.std(boots, ddof=1)
    z = indirect / sd if sd > 0 else np.nan
    approx_p = float(2 * (1 - stats.norm.cdf(abs(z)))) if not np.isnan(z) else np.nan
    return {
        "n": int(len(data)),
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
            "primary_inference": "bootstrap percentile confidence interval",
        },
        "total_effect": {"coef": float(total.params[x]), "p": float(total.pvalues[x]), "p_formatted": p_fmt(float(total.pvalues[x]))},
        "bootstrap_requested": reps,
        "bootstrap_succeeded": len(boots),
        "bootstrap_failed": failed,
        "bootstrap_success_rate": success_rate,
    }


def prepare_canonical(path):
    raw = read_sheet1(path)
    mapping = locate_columns(list(raw.columns))
    duration = validate_duration_series(raw[mapping["duration"]])
    threshold = float(np.percentile(duration.dropna(), 5))
    time_keep = duration >= threshold
    att21 = validate_likert_series(raw[mapping["attention21"]], "attention21", integer_only=True) == 2
    att26 = validate_likert_series(raw[mapping["attention26"]], "attention26", integer_only=True) == 2
    keep = time_keep & att21 & att26
    df = pd.DataFrame(index=raw.index)
    for key, col in mapping.items():
        if key not in {"duration", "attention21", "attention26"}:
            df[key] = validate_likert_series(raw[col], key, integer_only=True)
    service_items = ["q10_reliability", "q10_ease", "q10_response", "q10_solve", "q10_natural"]
    security_items = ["q10_security", "q10_control"]
    df["duration_seconds"] = duration
    df["quality_keep"] = keep
    df["bank_service"], service_counts = score_composite(df[service_items], min_valid=4)
    df["bank_security_control"], security_counts = score_composite(df[security_items], min_valid=2)
    df["bank_satisfaction"] = df["q11_satisfaction"]
    df["bank_future"] = df["q11_future"]
    df["mox_support_raw"] = df["q16"]
    df["mox_support"] = 6 - df["mox_support_raw"]
    clean = df.loc[keep].copy()
    clean["centered_bank_security_control"] = clean["bank_security_control"] - clean["bank_security_control"].mean()
    clean["centered_ai_attitude"] = clean["ai_attitude"] - clean["ai_attitude"].mean()
    clean["interaction"] = clean["centered_bank_security_control"] * clean["centered_ai_attitude"]
    checks = {
        "raw_n": int(len(raw)),
        "time_threshold_p05_seconds": int(round(threshold)),
        "time_clean_n": int(time_keep.sum()),
        "attention21_pass_n": int(att21.sum()),
        "attention26_pass_n": int(att26.sum()),
        "attention_both_pass_n": int((att21 & att26).sum()),
        "quality_n": int(keep.sum()),
    }
    private = {
        "input_file_name": path.name,
        "input_sha256": sha256_file(path),
        "input_size_bytes": path.stat().st_size,
        "column_mapping": {k: normalize_header(v) for k, v in mapping.items()},
        "worksheet": "Sheet1",
        "column_count": int(raw.shape[1]),
    }
    audit = composite_missingness_audit(clean, service_counts.loc[keep], security_counts.loc[keep])
    return clean, checks, private, audit


def prepare_demo(path):
    df = pd.read_csv(path)
    required = CORE
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise AnalysisValidationError("Demo input missing columns: " + ", ".join(missing))
    for col in required + [c for c in SUPPLEMENTARY if c in df.columns]:
        df[col] = validate_likert_series(df[col], col)
    df["centered_bank_security_control"] = df["bank_security_control"] - df["bank_security_control"].mean()
    df["centered_ai_attitude"] = df["ai_attitude"] - df["ai_attitude"].mean()
    df["interaction"] = df["centered_bank_security_control"] * df["centered_ai_attitude"]
    return df, {"demo_n": int(len(df)), "quality_n": int(len(df))}, {}, pd.DataFrame()


def validate_checks(checks):
    return {k: {"expected": v, "observed": checks.get(k), "match": checks.get(k) == v} for k, v in EXPECTED.items()}


def corr_n_matrix(df, cols):
    out = pd.DataFrame(index=cols, columns=cols, dtype=int)
    for a in cols:
        for b in cols:
            out.loc[a, b] = int(df[[a, b]].dropna().shape[0])
    return out


def describe_cols(df, cols):
    present = [c for c in cols if c in df.columns]
    return df[present].describe().T[["count", "mean", "std", "min", "25%", "50%", "75%", "max"]].to_dict(orient="index")


def run_models(df, mode):
    metrics = {
        "descriptive_statistics": describe_cols(df, CORE),
        "supplementary_descriptive_statistics": describe_cols(df, SUPPLEMENTARY),
        "correlation_matrix": df[CORE].corr().to_dict(),
        "correlation_n_matrix": corr_n_matrix(df, CORE).astype(int).to_dict(),
        "models": {name: ols(df, y, xs) for name, (y, xs) in MODELS.items()},
        "vif": {name: vif(df, xs) for name, (_y, xs) in MODELS.items()},
    }
    if mode == "canonical":
        metrics["cronbach_alpha"] = {
            "bank_service_q10_5_items": cronbach_alpha(df[["q10_reliability", "q10_ease", "q10_response", "q10_solve", "q10_natural"]]),
            "bank_security_control_q10_2_items": cronbach_alpha(df[["q10_security", "q10_control"]]),
            "q10_all_7_items": cronbach_alpha(df[["q10_reliability", "q10_ease", "q10_response", "q10_solve", "q10_natural", "q10_security", "q10_control"]]),
        }
        metrics["mediation"] = {
            "Mediation A exploratory bank_service_to_bank_security_control_to_bank_future": mediation(
                df, "bank_service", "bank_security_control", "bank_future"
            ),
            "Mediation B adjusted bank_security_control_to_bank_satisfaction_to_bank_future_cov_bank_service": mediation(
                df, "bank_security_control", "bank_satisfaction", "bank_future", covariates=["bank_service"]
            ),
        }
    return metrics


def plot_sample_screening(checks, path):
    fig, ax = plt.subplots(figsize=(7.5, 4.8), constrained_layout=False)
    labels = ["Raw responses", "Duration-screened", "Final quality sample"]
    values = [checks["raw_n"], checks["time_clean_n"], checks["quality_n"]]
    bars = ax.bar(labels, values, color=["#3B6EA8", "#F28E2B", "#59A14F"])
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 6, str(value), ha="center", va="bottom", fontsize=10)
    ax.set_ylabel("Responses")
    ax.set_title("Sample Screening", pad=14)
    ax.set_ylim(0, max(values) * 1.18)
    fig.text(
        0.5,
        0.025,
        "Both attention checks passed: 240 of 376 raw responses. This count is reported separately and is not an intermediate funnel stage.",
        ha="center",
        va="bottom",
        fontsize=8.5,
    )
    fig.subplots_adjust(left=0.11, right=0.98, top=0.86, bottom=0.22)
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def plot_core_descriptives(metrics, path):
    desc = pd.DataFrame(metrics["descriptive_statistics"]).T
    labels = [DISPLAY_LABELS.get(v, v) for v in desc.index]
    y = np.arange(len(desc))
    ci = 1.96 * desc["std"] / np.sqrt(desc["count"])
    fig, ax = plt.subplots(figsize=(9.2, 5.8), constrained_layout=True)
    ax.errorbar(desc["mean"], y, xerr=ci, fmt="o", capsize=4, color="#2F4B7C", ecolor="#7A9CC6")
    for i, (_, row) in enumerate(desc.iterrows()):
        ax.annotate(f"n={int(row['count'])}", (min(5.02, row["mean"] + ci.iloc[i] + 0.08), i), va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlim(1, 5.25)
    ax.set_xlabel("Mean with 95% CI")
    ax.set_title("Core Variable Descriptives", pad=12)
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def plot_correlation_heatmap(metrics, path):
    corr = pd.DataFrame(metrics["correlation_matrix"]).loc[CORE, CORE]
    labels = [DISPLAY_LABELS.get(v, v) for v in corr.index]
    fig, ax = plt.subplots(figsize=(8.2, 7.1), constrained_layout=False)
    image = ax.imshow(corr.values, cmap="coolwarm", vmin=-1, vmax=1)
    cbar = fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Pearson r")
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    ax.set_title("Correlation Matrix", pad=14)
    fig.text(
        0.5,
        0.025,
        "Pairwise-complete observations are used. Pairs involving Mox support have smaller effective sample sizes.",
        ha="center",
        va="bottom",
        fontsize=8.5,
    )
    fig.subplots_adjust(left=0.22, right=0.91, top=0.88, bottom=0.24)
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def plot_model_coefficients(metrics, model_name, title, path):
    model = metrics["models"][model_name]
    terms = [t for t in model["params"] if t != "const"]
    labels = [DISPLAY_LABELS.get(t, t) for t in terms]
    coefs = np.array([model["params"][t]["coef"] for t in terms], dtype=float)
    lows = np.array([model["params"][t]["robust_ci95_hc3"][0] for t in terms], dtype=float)
    highs = np.array([model["params"][t]["robust_ci95_hc3"][1] for t in terms], dtype=float)
    height = max(4.4, 1.0 + len(terms) * 0.85)
    fig, ax = plt.subplots(figsize=(8.5, height), constrained_layout=True)
    y = np.arange(len(terms))
    ax.axvline(0, color="#555555", linewidth=1)
    ax.errorbar(coefs, y, xerr=[coefs - lows, highs - coefs], fmt="o", capsize=4, color="#2F4B7C", ecolor="#7A9CC6")
    xmin, xmax = float(np.nanmin(lows)), float(np.nanmax(highs))
    span = max(0.3, xmax - xmin)
    ax.set_xlim(xmin - 0.22 * span, xmax + 0.34 * span)
    for coef, yy, term in zip(coefs, y, terms):
        p = model["params"][term]["robust_p_hc3"]
        text = f"β={coef:.2f}, {p_fmt(p)}"
        right_x = coef + 0.035 * span
        if right_x > ax.get_xlim()[1] - 0.18 * span:
            ax.annotate(text, (coef, yy), xytext=(-8, 0), textcoords="offset points", ha="right", va="center", fontsize=8.5)
        else:
            ax.annotate(text, (coef, yy), xytext=(8, 0), textcoords="offset points", ha="left", va="center", fontsize=8.5)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Coefficient with HC3 robust 95% CI")
    ax.set_title(title, pad=24)
    ax.text(
        0.5,
        1.02,
        f"HC3 robust 95% CI | n={model['n']} | R²={model['r_squared']:.3f}",
        transform=ax.transAxes,
        ha="center",
        va="bottom",
        fontsize=9,
    )
    ax.margins(y=0.25)
    fig.savefig(path, dpi=220, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)


def make_figures(metrics, figs, mode, checks):
    if mode == "canonical":
        plot_sample_screening(checks, figs / "01_sample_screening.png")
    plot_core_descriptives(metrics, figs / "02_core_descriptives_ci.png")
    plot_correlation_heatmap(metrics, figs / "03_correlation_heatmap.png")
    plot_model_coefficients(metrics, "Model A", "Model A: Satisfaction", figs / "04_model_a_coef_ci.png")
    plot_model_coefficients(metrics, "Model B", "Model B: Future Use", figs / "05_model_b_coef_ci.png")
    plot_model_coefficients(metrics, "Model C", "Model C: Mox Support", figs / "06_model_c_coef_ci.png")


def write_contact_sheet(figs_dir, output_path):
    images = sorted(figs_dir.glob("0*.png"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not images:
        return
    rows = math.ceil(len(images) / 2)
    fig, axes = plt.subplots(rows, 2, figsize=(10, 4.2 * rows), constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()
    for ax, image_path in zip(axes, images):
        ax.imshow(plt.imread(image_path))
        ax.set_title(image_path.name, fontsize=9)
        ax.axis("off")
    for ax in axes[len(images) :]:
        ax.axis("off")
    fig.savefig(output_path, dpi=170, bbox_inches="tight", pad_inches=0.2)
    plt.close(fig)


def save_outputs(metrics, out, mode, checks, audit=None):
    out.mkdir(parents=True, exist_ok=True)
    tables = out / "tables"
    figs = out / "figures"
    tables.mkdir(exist_ok=True)
    figs.mkdir(exist_ok=True)
    metrics_name = "canonical_metrics.json" if mode == "canonical" else "demo_metrics.json"
    (out / metrics_name).write_text(json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    pd.DataFrame(metrics["descriptive_statistics"]).T.to_csv(tables / "descriptive_statistics.csv", encoding="utf-8-sig")
    pd.DataFrame(metrics.get("supplementary_descriptive_statistics", {})).T.to_csv(
        tables / "supplementary_items.csv", encoding="utf-8-sig"
    )
    pd.DataFrame(metrics["correlation_matrix"]).to_csv(tables / "correlation_matrix.csv", encoding="utf-8-sig")
    pd.DataFrame(metrics["correlation_n_matrix"]).to_csv(tables / "correlation_n_matrix.csv", encoding="utf-8-sig")
    rows = []
    for model_name, model in metrics["models"].items():
        for term, vals in model["params"].items():
            row = {
                "model": model_name,
                "term": term,
                "n": model["n"],
                "r_squared": model["r_squared"],
                "adj_r_squared": model["adj_r_squared"],
                "f_statistic_conventional_ols": model["f_statistic_conventional_ols"],
                "model_p_conventional_ols": model["model_p_conventional_ols"],
                "model_p_conventional_ols_formatted": model["model_p_conventional_ols_formatted"],
                "f_statistic_hc3": model["f_statistic_hc3"],
                "model_p_hc3": model["model_p_hc3"],
                "model_p_hc3_formatted": model["model_p_hc3_formatted"],
            }
            row.update(vals)
            rows.append(row)
    pd.DataFrame(rows).to_csv(tables / "model_coefficients.csv", index=False, encoding="utf-8-sig")
    if audit is not None and not audit.empty:
        audit.to_csv(tables / "composite_missingness_audit.csv", index=False, encoding="utf-8-sig")
    make_figures(metrics, figs, mode, checks)


def _atomic_output(output_dir, writer):
    output_dir = Path(output_dir)
    parent = output_dir.parent
    parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=output_dir.name + "_tmp_", dir=parent))
    backup = None
    try:
        writer(tmp)
        if output_dir.exists():
            backup = Path(tempfile.mkdtemp(prefix=output_dir.name + "_old_", dir=parent))
            backup.rmdir()
            output_dir.replace(backup)
        tmp.replace(output_dir)
        if backup and backup.exists():
            shutil.rmtree(backup)
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        if backup and backup.exists():
            if output_dir.exists():
                if output_dir.is_dir():
                    shutil.rmtree(output_dir)
                else:
                    output_dir.unlink()
            backup.replace(output_dir)
        raise


def run_analysis(mode, input_path, output_dir, provenance_output=None, expected_input_sha256=None):
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")
    if expected_input_sha256:
        observed_hash = sha256_file(input_path)
        if observed_hash.lower() != expected_input_sha256.lower():
            raise AnalysisValidationError("Input SHA256 did not match the expected value.")
    if mode == "canonical":
        data, checks, private, audit = prepare_canonical(input_path)
        validation = validate_checks(checks)
        if not all(v["match"] for v in validation.values()):
            message = {"error": "canonical validation failed", "validation": validation}
            raise AnalysisValidationError(json.dumps(message, ensure_ascii=False))
    elif mode == "demo":
        data, checks, private, audit = prepare_demo(input_path)
        validation = {}
    else:
        raise ValueError("mode must be canonical or demo")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        metrics = run_models(data, mode)
    metrics.update(
        {
            "mode": mode,
            "run_metadata": {
                "run_time_utc": datetime.now(timezone.utc).isoformat(),
                "python_version": platform.python_version(),
                "platform": platform.system(),
                "random_seed": RANDOM_SEED,
                "libraries": {
                    "pandas": pd.__version__,
                    "numpy": np.__version__,
                    "scipy": scipy.__version__,
                    "statsmodels": sm.__version__,
                    "matplotlib": matplotlib.__version__,
                },
                "warnings": sorted({str(w.message) for w in caught}),
            },
            "input_file": {"safe_path": "<private-input>" if mode == "canonical" else input_path.name, "size_bytes": input_path.stat().st_size if mode == "demo" else None},
            "variable_definitions": VARIABLE_DEFINITIONS,
            "cleaning_rules": {
                "worksheet": "Canonical mode reads Sheet1 explicitly.",
                "duration": "Keep responses at or above the 5th percentile duration threshold.",
                "attention": "Both attention checks must equal coding value 2.",
                "composites": "bank_service requires at least four of five Q10 service items; bank_security_control requires both Q10 security/control items.",
                "privacy": "Raw responses and sensitive metadata are excluded from public outputs.",
            },
            "sample_checks": checks,
            "expected_validation": validation,
            "validation_passed": all(v["match"] for v in validation.values()) if validation else None,
            "efa_status": "Excluded from public main results because KMO/Bartlett/rotation validation was not completed.",
        }
    )

    def writer(tmp_out):
        save_outputs(metrics, tmp_out, mode, checks, audit)

    _atomic_output(output_dir, writer)
    if mode == "canonical" and provenance_output:
        provenance_path = Path(provenance_output)
        provenance_path.parent.mkdir(parents=True, exist_ok=True)
        provenance_path.write_text(json.dumps(private, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"mode": mode, "n": checks.get("quality_n"), "validation_passed": metrics.get("validation_passed")}, ensure_ascii=False))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run Mox chatbot user research analysis in canonical or demo mode.")
    parser.add_argument("--mode", choices=["canonical", "demo"], required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--provenance-output", default=None)
    parser.add_argument("--expected-input-sha256", default=None)
    args = parser.parse_args()
    try:
        code = run_analysis(args.mode, args.input, args.output, args.provenance_output, args.expected_input_sha256)
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
