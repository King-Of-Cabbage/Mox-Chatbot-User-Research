# Mox Chatbot User Research

A PolyU × HKMA IPMN Academic Project

[![tests](https://github.com/King-Of-Cabbage/Mox-Chatbot-User-Research/actions/workflows/tests.yml/badge.svg)](https://github.com/King-Of-Cabbage/Mox-Chatbot-User-Research/actions/workflows/tests.yml)

This project was completed through the Hong Kong Monetary Authority's Industry Project Masters Network (HKMA IPMN) Scheme by postgraduate students from the School of Accounting and Finance at The Hong Kong Polytechnic University. The project examines user perceptions and service-design considerations relating to digital banking chatbots, using Mox Bank as the project context.

The analysis and recommendations in this repository are student project work. They do not constitute official statements, policies, approvals, or endorsements by HKMA, PolyU, or Mox Bank. Raw questionnaire exports, respondent-level records, respondent metadata, open-ended answers, original reports, and old presentation files are not included.

## Project Attribution

This project was completed as a two-person academic collaboration by LIN Junyu and SHI.

## Personal Contribution

I drafted and refined approximately half of the questionnaire content, while SHI designed the branching and response logic. I independently cleaned and prepared the survey data, including response-quality screening, variable coding, composite scoring, and the final analysis dataset.

The model framework and specifications were discussed jointly. We shared the report writing, while SHI led the visualisation work. In the final presentation, I covered the research design, data processing, and empirical findings; SHI presented the recommendations and implementation plan.

## Business Question

The project asks how perceived chatbot service quality is associated with satisfaction, future use intention, and support for a proposed digital banking chatbot feature.

## Method

The analysis starts from 376 raw questionnaire responses. It applies a response-time screen and two attention checks, leaving a final quality sample of 232 responses. The main variables are a Q10 service-quality composite, a Q10 security-and-control composite, Q11 satisfaction, Q11 trust, Q11 future use intention, and a Q16 Mox-support item that is reverse-coded so higher values mean stronger support. The main models use OLS regression with HC3 robust inference, and the mediation analyses are exploratory.

## Environment

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
python -m pytest -q
python scripts/validate_release_tree.py .
```

## Run

Demo mode uses only synthetic aggregate variables:

```bash
python src/run_analysis.py --mode demo --input data/synthetic_example.csv --output local_results/demo
```

Canonical mode requires a private local questionnaire file:

```bash
python src/run_analysis.py --mode canonical --input path/to/private_questionnaire.xlsx --output local_results/canonical
```

Optional provenance checks can be written only when an explicit provenance output path is provided. Do not commit private questionnaire files, questionnaire hashes, or local run outputs.

## Directory Guide

- `src`: analysis code for canonical and demo modes.
- `notebooks`: notebook wrapper that runs the synthetic demo by default.
- `data`: data dictionary and synthetic example data.
- `results`: aggregate result tables and public figures from the canonical analysis.
- `docs`: methodology notes, limitations, construct map, and portfolio summary.
- `tests`: checks for the demo run, figures, notebook state, text quality, and public-repo cleanliness.
- `scripts`: release-tree validation before packaging or publishing.

## Privacy And Sample Screening

Canonical analysis requires a private questionnaire file. Public outputs contain only derived variables, aggregate tables, model summaries, figures, and synthetic demo data.

<p align="center">
  <img src="results/figures/01_sample_screening.png" alt="Sample screening" width="850">
</p>

Raw responses: 376. After duration screen: 360. Final quality sample: 232. The attention-check count is reported as an independent raw-sample count, not a funnel step.

## Variables

| Display name | Code name | Definition | Scoring rule | Main-model role |
|---|---|---|---|---|
| Service quality | `bank_service` | Q10 five-item service-quality composite | At least four items must be valid | Predictor |
| Security and control | `bank_security_control` | Q10 security perception and perceived control composite | Both items must be valid | Predictor / exploratory mediator / moderator construct |
| Satisfaction | `bank_satisfaction` | Q11 satisfaction single item | No cross-item imputation | Outcome in Model A; predictor in Models B and C |
| Future use | `bank_future` | Q11 future use intention single item | No cross-item imputation | Outcome in Model B and Moderation |
| Mox support | `mox_support` | Q16 reverse-coded support item | `6 - mox_support_raw` | Outcome in Model C |
| AI attitude | `ai_attitude` | Q5 original coding | 1 very anxious/resistant to 5 very excited | Moderation predictor |

`bank_security_control` and the supplementary Q11 trust item are distinct constructs from different question blocks. They should not both be shortened to "trust."

## Main Results

All primary coefficient p values, confidence intervals, and overall model tests use HC3 robust inference. Conventional OLS statistics remain in the full JSON and CSV outputs for transparency.

<p align="center">
  <img src="results/figures/03_correlation_heatmap.png" alt="Correlation heatmap" width="850">
</p>

The correlation heatmap uses pairwise-complete observations. Pairs involving Mox support have smaller effective sample sizes; see `results/tables/correlation_n_matrix.csv`.

<p align="center">
  <img src="results/figures/05_model_b_coef_ci.png" alt="Model B coefficient plot" width="850">
</p>

| Model | Dependent variable | n | R² | HC3 overall test | Core HC3 result | Interpretation boundary |
|---|---|---:|---:|---|---|---|
| A | Satisfaction (`bank_satisfaction`) | 212 | 0.095 | F=8.712, p<0.001 | Service quality (`bank_service`) coef=0.297, p=0.033; security and control (`bank_security_control`) coef=0.024, p=0.850 | Explanatory power is limited. |
| B | Future use (`bank_future`) | 212 | 0.554 | F=84.103, p<0.001 | Satisfaction (`bank_satisfaction`) coef=0.750, p<0.001 | Association, not causal proof. |
| C | Mox support (`mox_support`) | 164 | 0.046 | F=2.752, p=0.044 | Individual HC3 predictor p values are p=0.189, p=0.302, and p=0.957 | Conventional OLS overall p is p=0.057; interpret cautiously. |

## Mediation

Mediation A is exploratory because service quality and security/control are highly related constructs, and their separation needs further validation. Mediation B is an adjusted exploratory model controlling for service quality in both equations. Adjusted Mediation B indirect effect = 0.018; bootstrap 95% CI = [-0.157, 0.215]. Bootstrap confidence intervals are the main evidence. These models do not prove causality.

## License and Usage

No open-source license has been granted. All rights are reserved by the project contributors unless otherwise stated.
