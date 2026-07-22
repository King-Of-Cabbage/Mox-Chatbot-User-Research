# Portfolio Summary

This release-ready candidate summarizes an independent academic case study on chatbot service quality in digital banking. It is not affiliated with, commissioned by, or endorsed by Mox Bank. The public package is designed to show reproducible analytical work without exposing raw survey responses or respondent metadata.

The canonical workflow starts from 376 private survey responses. After applying a duration screen and requiring both attention checks, the final quality sample is 232. The duration threshold is 126 seconds. The public repository includes only aggregate model outputs, derived-variable definitions, synthetic demo data, and generated figures.

The main finding is associational. In Model A, `bank_service` is associated with satisfaction, but the model's explanatory power is limited with R²=0.095. In Model B, satisfaction is associated with future use intention and the model has R²=0.554. Model C predicts reverse-coded support for the chatbot strategy; its HC3 overall model test is p=0.044, while the conventional OLS overall p value is p=0.057 and the individual HC3 predictor p values do not provide a simple strong-predictor story.

Mediation A is retained as exploratory because `bank_service` and `bank_trustsec` are highly related and construct distinction still requires validation. Mediation B is an adjusted exploratory model that controls `bank_service` in both the mediator and outcome equations. Its indirect effect is 0.018, with bootstrap 95% CI [-0.157, 0.215]. Bootstrap confidence intervals are used as the primary basis for judging indirect effects, and no causal proof language should be used.

Design implications should remain cautious. Reliable and usable chatbot experiences are associated with better satisfaction-related outcomes in this dataset. Broader topics such as human escalation, complex banking tasks, and emotional support should be treated as design considerations for further validation unless supported by a separate anonymous aggregate analysis.
