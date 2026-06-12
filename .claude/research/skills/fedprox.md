---
title: FedProx
type: skill
verdict: strong
---
## Evidence
- [[federated-learning]] — implemented by hand (not a library): custom `@tf.function` training step adding `(μ/2)·||w_local − w_global||²` to client loss against round-start global weights [verified-in-code: `client.py:70-86`]. Found μ non-monotonic on skewed data (μ=0 → 96%, μ=0.1 → 95%, μ=1.0 → 99%); μ=1.0 produced the headline 99% result.

## Resume verdict
Yes inside the FL bullet: "hand-implemented FedProx as a custom TensorFlow training step" is the single most impressive line from this project — it proves the math was understood, not imported.

## Interview readiness
Can write the proximal term from memory, explain it as a drift leash, and discuss why large μ stayed tractable (only a 2,562-param head trains). Caveat: favorable conditions (2 clients, binary, frozen backbone) — concede that μ tuning is harder at scale.
