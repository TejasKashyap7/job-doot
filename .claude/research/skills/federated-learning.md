---
title: Federated Learning
type: skill
verdict: strong
---
## Evidence
- [[federated-learning]] — end-to-end FL system: 2 simulated farm clients, deliberate label-skew non-IID splits (150:50 mirrored), FedAvg + hand-written FedProx, server-side held-out evaluation, ONNX export + independent verification. Headline: FedProx μ=1.0 hit 99.0% on skewed data vs 98.8% centralized baseline; documented the FedAvg "bias cancellation" failure mode [verified: logs, results.json, fed_proofs/].

## Resume verdict
Yes — resume and LOCKED_SKILL_SET. Honest phrasing: "99% training-eval / 98% independently verified"; under scrutiny say "matched the centralized baseline" (+0.2pp on a 100-image set is within noise).

## Interview readiness
Deep on FedAvg vs FedProx, non-IID label skew, catastrophic forgetting (F28 analysis), privacy contract reasoning, and the false-plateau/optimizer-reset story. Caveats: binary task, 2 clients, tiny eval sets, simulated (not distributed) — concede these proactively.
