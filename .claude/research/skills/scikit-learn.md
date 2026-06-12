---
title: Scikit-learn
type: skill
verdict: moderate
---
## Evidence
- [[smart-agri]] — stratified train/val/test splits (seeded, leakage fix), classification_report, confusion matrices across the 8-model benchmark [verified-in-notebooks].
- [[federated-learning]] — ML utilities/metrics in the evaluation stack (requirements-pinned).

## Resume verdict
Keep in LOCKED_SKILL_SET (already there) as a supporting ML tool. Usage is evaluation/splitting, not model training with sklearn — phrase generically ("scikit-learn for evaluation and data splitting").

## Interview readiness
Can discuss stratified splitting, why seeding matters (the leakage fix is a good story), and standard classification metrics. Don't claim sklearn modeling (pipelines, estimators) depth.
