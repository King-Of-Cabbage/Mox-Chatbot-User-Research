# Methodology

The analysis uses one canonical Python pipeline in `src/run_analysis.py`. Canonical mode reads the private questionnaire from `Sheet1`, maps required columns through an explicit field registry, validates 1-5 item coding, parses response duration, applies the duration and attention-check screens, constructs model variables, and writes only aggregate outputs.

The main constructs are `bank_service`, `bank_security_control`, `bank_satisfaction`, `bank_future`, `mox_support`, and `ai_attitude`. `bank_trust_outcome` is retained only as a supplementary descriptive Q11 item and is not included in the prespecified main models.

Composite scoring requires at least four of five valid Q10 service-quality items for `bank_service`, and both Q10 security/control items for `bank_security_control`. OLS coefficient inference uses HC3 robust standard errors and confidence intervals as the public primary specification. Mediation outputs use bootstrap percentile confidence intervals as the primary evidence and should not be interpreted as causal proof.
