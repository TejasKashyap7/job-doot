---
title: Flower (flwr)
type: skill
verdict: strong
---
## Evidence
- [[federated-learning]] — flwr 1.30.0: custom `FedAvgWithEval` strategy subclass with server-side centralized evaluation and per-round checkpointing; `NumPyClient` clients with per-epoch resume; `--from-checkpoint` warm-start; gRPC transport; 6-experiment matrix run through it [verified-in-code: `phase1/server.py:56-117`, `phase1/client.py`].

## Resume verdict
Yes — LOCKED_SKILL_SET and resume. Phrase as "federated learning with Flower (custom strategy subclass, crash-safe checkpoint/resume, FedAvg/FedProx experiments)".

## Interview readiness
Can discuss strategy customization, round lifecycle, weights-vs-gradients exchange, and the round-numbering-after-resume quirk he handled. Caveat: 2 simulated clients on one Mac over localhost — never imply real distributed deployment (Phase 2 specced, unbuilt).
