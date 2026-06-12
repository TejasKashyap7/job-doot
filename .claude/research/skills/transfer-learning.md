---
title: Transfer Learning
type: skill
verdict: strong
---
## Evidence
- [[smart-agri]] — two-phase ImageNet transfer learning in the retrain notebooks: frozen base (Adam 1e-3, EarlyStopping) → full fine-tune (Adam 1e-5), multi-seed (42/1337/2024) with mean±std reporting [verified-in-notebooks].
- [[federated-learning]] — frozen ImageNet EfficientNetB1 backbone with a 2,562-param trainable head as a deliberate constrained-edge design decision (flaws.md F30) [verified-in-code: `model.py`].

## Resume verdict
Yes — resume-worthy as a technique woven into the ML bullets ("two-phase fine-tuning", "frozen-backbone head training for edge clients"). Add to LOCKED_SKILL_SET domains.

## Interview readiness
Can explain freeze-then-fine-tune schedules, learning-rate staging, and the FL-specific rationale (proximal term over a small head space, edge compute budgets). Note: the smart-agri *benchmark* models were trained from scratch for fairness — transfer learning is the retrain/FL work.
