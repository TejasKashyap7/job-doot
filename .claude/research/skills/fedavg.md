---
title: FedAvg
type: skill
verdict: strong
---
## Evidence
- [[federated-learning]] — sample-count-weighted FedAvg as the aggregation core (custom `FedAvgWithEval` subclass); balanced-data run hit 100% (Exp 7, log-only); documented and theorized its failure under label skew — opposite client bias vectors averaging to zero ("bias cancellation", fl_concepts.md) [verified-in-code + logs].

## Resume verdict
Don't list "FedAvg" as a standalone resume skill — it lives inside the federated-learning bullet ("FedAvg/FedProx under non-IID splits"). Strong for interviews, not for the skills section.

## Interview readiness
Can derive the weighted-averaging update, explain when it works (IID/balanced) and the documented skew failure mode. Caveat: Exp 7's 100% is log-only (no ONNX artifact saved); pre-fix 50% runs were also tainted by the F35 input bug.
