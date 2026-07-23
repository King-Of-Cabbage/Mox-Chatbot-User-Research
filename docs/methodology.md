# Methodology

The analysis is implemented in `src/run_analysis.py`. Canonical mode reads the private questionnaire from `Sheet1`, maps required columns through an explicit field registry, validates 1-5 item coding, parses response duration, applies the duration and attention-check screens, constructs model variables, and writes aggregate outputs.

The main constructs are `bank_service`, `bank_security_control`, `bank_satisfaction`, `bank_future`, `mox_support`, and `ai_attitude`. The Q11 trust item is retained as a supplementary descriptive variable and is not included in the main regression models.

Composite scoring requires at least four of five valid Q10 service-quality items for `bank_service`, and both Q10 security/control items for `bank_security_control`. Regression coefficient inference uses HC3 robust standard errors and confidence intervals. Mediation outputs use bootstrap percentile confidence intervals as the main evidence and should not be interpreted as causal proof.
