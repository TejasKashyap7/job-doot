---
title: TensorFlow
type: skill
verdict: strong
---
## Evidence
- [[smart-agri]] — full tf.data training pipeline (224×224, batch 64, seeded shuffle, AUTOTUNE, augmentation) for 8 CNN families on 20,638 images; trained on RTX A6000 and Kaggle T4 [verified-in-notebooks].
- [[federated-learning]] — tensorflow-macos 2.16.2 + metal; hand-written `@tf.function` FedProx training step; M1 unified-memory engineering (CPU-pinning clients before flwr import to stop 224 GB swap thrash) [verified-in-code].

## Resume verdict
Yes — already in LOCKED_SKILL_SET; keep it. Backed by both a benchmark study and custom low-level training-step code.

## Interview readiness
Can go below `model.fit`: custom training loops, eager vs graph execution (FL later_concepts.md), tf.data performance, device placement on Apple silicon. Caveat: only claim Apple-silicon *training* for FL — smart-agri training ran on A6000/T4.
