# Portfolio Summary

Mox Chatbot User Research is a PolyU x HKMA IPMN academic project examining user perceptions and service-design considerations relating to digital banking chatbots, using Mox Bank as the project context. The public repository contains a privacy-preserving, reproducible analysis package with synthetic demo data and aggregate canonical outputs only.

The analysis focuses on whether perceived service quality and perceived security/control are associated with satisfaction, future use intention, and support for a proposed chatbot service context. `bank_security_control` is the Q10 composite of security perception and perceived control; it is distinct from `bank_trust_outcome`, the Q11 single trust item retained only for supplementary descriptive reporting.

The canonical pipeline applies duration screening and two attention checks before constructing variables. Regression results use HC3 robust inference as the main public specification, while conventional OLS results remain available in the full tables for transparency. Mediation models are exploratory and should not be read as causal proof.

The repository is designed for portfolio review and reproducibility of the analysis workflow without exposing raw survey responses, respondent-level metadata, open-ended answers, or sensitive survey metadata.
